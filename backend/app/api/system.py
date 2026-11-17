"""客户部署自检接口。"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services import doctor, local_config
from app.services.cdp_connection import probe as probe_cdp
from app.services.knowledge_base import KnowledgeBaseStore

router = APIRouter(prefix="/api/system", tags=["system"])

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = ROOT / "frontend" / "dist"
LOCAL_DIR = ROOT / ".local"


@router.get("/doctor")
async def system_doctor(request: Request, db: Annotated[Session, Depends(get_db)]) -> dict:
    cdp_status = await probe_cdp(settings.cdp_endpoint)
    service = getattr(request.app.state, "live_watch_service", None)
    store = getattr(service, "store", None)
    reports = store.list_logs(limit=500) if store is not None else []
    report_count = store.count() if store is not None else len(reports)
    monitor_status = service.status() if service is not None else {}
    knowledge = KnowledgeBaseStore().overview(reports)
    return doctor.assess_deployment(
        db=db,
        frontend_dist=FRONTEND_DIST,
        local_dir=LOCAL_DIR,
        room_name=local_config.room_name(settings.live_board_room_name),
        aavid=local_config.aavid(settings.aavid),
        cdp_status=cdp_status,
        api_configured=bool(settings.api_configured and settings.api_advertiser_id),
        knowledge=knowledge,
        report_count=report_count,
        monitor_status=monitor_status,
        llm_configured=bool(settings.llm_api_key),
    )
