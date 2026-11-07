import base64
import binascii

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.services.knowledge_base import KnowledgeBaseStore

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])


class KnowledgeFileUpload(BaseModel):
    name: str
    content_base64: str
    content_type: str = ""


class KnowledgeFileUpdate(BaseModel):
    enabled: bool


def _reports(request: Request) -> list[dict]:
    service = getattr(request.app.state, "live_watch_service", None)
    store = getattr(service, "store", None)
    if store is None:
        return []
    return store.list_logs(limit=5000)


@router.get("")
def knowledge_overview(request: Request) -> dict:
    return KnowledgeBaseStore().overview(_reports(request))


@router.post("/files", status_code=201)
def upload_knowledge_file(payload: KnowledgeFileUpload) -> dict:
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="文件内容不是有效的 base64") from exc
    try:
        return KnowledgeBaseStore().save_file(
            payload.name, content, payload.content_type
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.patch("/files/{file_id}")
def update_knowledge_file(file_id: str, payload: KnowledgeFileUpdate) -> dict:
    try:
        return KnowledgeBaseStore().set_file_enabled(file_id, payload.enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Knowledge file not found") from exc


@router.delete("/files/{file_id}", status_code=204)
def delete_knowledge_file(file_id: str) -> Response:
    if not KnowledgeBaseStore().delete_file(file_id):
        raise HTTPException(status_code=404, detail="Knowledge file not found")
    return Response(status_code=204)
