"""账户近 60 天数据底座接口。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime

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

_BOOTSTRAP_JOBS: dict[str, dict] = {}
_BOOTSTRAP_TASKS: dict[str, asyncio.Task] = {}


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


def reset_bootstrap_jobs_for_tests() -> None:
    for task in list(_BOOTSTRAP_TASKS.values()):
        if not task.done():
            task.cancel()
    _BOOTSTRAP_TASKS.clear()
    _BOOTSTRAP_JOBS.clear()


def _running_job(account_id: str) -> dict | None:
    for job in _BOOTSTRAP_JOBS.values():
        if job.get("account_id") == account_id and job.get("status") == "running":
            return job
    return None


@router.post("/bootstrap/start", status_code=202)
async def start_account_history_bootstrap(force: bool = False) -> dict:
    account_id = local_config.aavid(settings.aavid)
    if not account_id:
        raise HTTPException(status_code=422, detail="请先在数据源里填写账户 ID")
    existing = _running_job(account_id)
    if existing is not None:
        return existing

    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "account_id": account_id,
        "status": "running",
        "stage": (
            "优先读取开放平台，失败后回退本机浏览器"
            if settings.api_configured and settings.api_advertiser_id
            else "正在读取本机浏览器中的千川账户数据"
        ),
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "result": None,
        "error": "",
    }
    _BOOTSTRAP_JOBS[job_id] = job
    service = make_service()

    async def run_job() -> None:
        try:
            result = await service.bootstrap(
                account_id=account_id,
                room_name=local_config.room_name(settings.live_board_room_name),
                api_available=bool(settings.api_configured and settings.api_advertiser_id),
                force=force,
            )
            job["status"] = "completed"
            job["stage"] = "近60天数据底座已更新"
            job["result"] = result
        except Exception as exc:  # noqa: BLE001
            job["status"] = "failed"
            job["stage"] = "读取失败"
            job["error"] = str(exc)

    task = asyncio.create_task(run_job())
    _BOOTSTRAP_TASKS[job_id] = task
    return job


@router.get("/bootstrap/{job_id}")
def account_history_bootstrap_status(job_id: str) -> dict:
    job = _BOOTSTRAP_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="数据底座读取任务不存在")
    return job