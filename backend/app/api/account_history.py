"""账户近 60 天数据底座接口。"""

from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.execution.api_read_provider import ApiReadProvider
from app.execution.cdp.account_history_reader import CdpAccountHistoryReader
from app.services import local_config
from app.services.account_history import (
    AccountHistoryError,
    AccountHistoryService,
    AccountHistoryStore,
    parse_api_history,
)
from app.services.api_client import OceanEngineApiClient

router = APIRouter(prefix="/api/account-history", tags=["account-history"])


def make_service() -> AccountHistoryService:
    async def api_collector(account_id: str, start_date: str, end_date: str) -> dict:
        advertiser_id = settings.api_advertiser_id or int(account_id)
        client = OceanEngineApiClient(config=settings)
        provider = ApiReadProvider(client, advertiser_id)
        payload = await asyncio.to_thread(
            provider.get_account_history, start_date, end_date
        )
        return parse_api_history(payload)

    async def cdp_collector(account_id: str, start_date: str, end_date: str) -> dict:
        return await CdpAccountHistoryReader(settings.cdp_endpoint).read(
            account_id,
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
        )

    return AccountHistoryService(
        store=AccountHistoryStore(),
        api_collector=api_collector,
        cdp_collector=cdp_collector,
    )


@router.get("")
def account_history_status(account_id: str | None = None) -> dict:
    account = str(account_id or local_config.aavid(settings.aavid) or "").strip()
    if not account:
        return {"account_id": "", "configured": False, "history": None}
    history = AccountHistoryStore().get(account)
    return {"account_id": account, "configured": history is not None, "history": history}


@router.post("/bootstrap")
async def bootstrap_account_history(force: bool = False) -> dict:
    account_id = local_config.aavid(settings.aavid)
    if not account_id:
        raise HTTPException(status_code=422, detail="请先在数据源里填写账户 ID")
    service = make_service()
    try:
        return await service.bootstrap(
            account_id=account_id,
            room_name=local_config.room_name(settings.live_board_room_name),
            api_available=bool(settings.api_configured and settings.api_advertiser_id),
            force=force,
        )
    except AccountHistoryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
