from __future__ import annotations

import io
import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_KNOWLEDGE_ROOT = (
    Path(__file__).resolve().parents[3] / ".local" / "knowledge_base"
)
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml"}
DOCUMENT_SUFFIXES = {".pdf", ".docx"}
MAX_FILE_BYTES = 10 * 1024 * 1024
METRIC_FIELDS = {
    "roi": ("ROI", "", 2),
    "gpm": ("GPM", "元", 2),
    "cpm": ("CPM", "元", 2),
    "exposure_view_rate": ("曝光观看率", "%", 2),
    "view_conversion_rate": ("观看成交转化率", "%", 2),
    "online_viewers": ("在线人数均值", "人", 0),
    "assist_share": ("追投/调控占比", "%", 1),
}


def _numeric(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return str(value)
    return parsed.isoformat()


def _assist_share(report: dict) -> float | None:
    split = report.get("spend_split") or {}
    basic = _numeric(split.get("basic_spend"))
    assist = _numeric(split.get("assist_spend"))
    if basic is None or assist is None or basic + assist <= 0:
        return None
    return assist / (basic + assist) * 100


def build_historical_reference(reports: list[dict]) -> dict:
    valid: list[dict] = []
    for report in reports:
        if str(report.get("source") or "") == "cdp-error":
            continue
        if report.get("verify_passed") is False:
            continue
        quality = report.get("data_quality") or {}
        if quality and quality.get("status") != "good":
            continue
        valid.append(report)

    buckets: dict[str, list[float]] = {key: [] for key in METRIC_FIELDS}
    timestamps: list[str] = []
    for report in valid:
        observed = _iso(report.get("captured_at") or report.get("created_at"))
        if observed:
            timestamps.append(observed)
        for key in ("roi", "gpm", "cpm", "exposure_view_rate", "view_conversion_rate"):
            value = _numeric(report.get(key))
            if value is not None:
                buckets[key].append(value)
        online = _numeric(report.get("average_online_viewers"))
        if online is None:
            online = _numeric(report.get("online_viewers"))
        if online is not None:
            buckets["online_viewers"].append(online)
        assist_share = _assist_share(report)
        if assist_share is not None:
            buckets["assist_share"].append(assist_share)

    metrics: list[dict] = []
    for key, (label, unit, digits) in METRIC_FIELDS.items():
        values = buckets[key]
        if not values:
            continue
        metrics.append(
            {
                "key": key,
                "label": label,
                "average": round(sum(values) / len(values), digits),
                "unit": unit,
                "samples": len(values),
            }
        )

    return {
        "sample_count": len(valid),
        "window_start": min(timestamps) if timestamps else None,
        "window_end": max(timestamps) if timestamps else None,
        "metrics": metrics,
        "note": (
            "未上传知识文件时，使用本账户历史有效采样平均值；"
            "仅作历史参考，不是规则，也不代表未来一定如此。"
        ),
    }


class KnowledgeBaseStore:
    def __init__(self, root: Path = DEFAULT_KNOWLEDGE_ROOT) -> None:
        self.root = Path(root)
        self.files_dir = self.root / "files"
        self.index_path = self.root / "index.json"
        self._lock = threading.Lock()

    def list_files(self) -> list[dict]:
        items = [self._normalized(item) for item in self._read_index()]
        return sorted(items, key=lambda item: item.get("uploaded_at") or "", reverse=True)

    def save_file(self, name: str, content: bytes, content_type: str = "") -> dict:
        safe_name = Path(str(name or "")).name.strip()
        if not safe_name:
            raise ValueError("文件名不能为空")
        if len(content) > MAX_FILE_BYTES:
            raise ValueError("文件超过 10MB 限制")

        item_id = str(uuid.uuid4())
        suffix = Path(safe_name).suffix.lower()
        stored_name = f"{item_id}{suffix}"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        (self.files_dir / stored_name).write_bytes(content)

        preview = ""
        parse_status = "stored_only"
        text_stored_name = None
        extracted_text = self._extract_text(suffix, content)
        if extracted_text.strip():
            text_stored_name = f"{item_id}.extracted.txt"
            (self.files_dir / text_stored_name).write_text(
                extracted_text, encoding="utf-8"
            )
            preview = extracted_text.strip()[:2000]
            parse_status = "parsed"
        item = {
            "id": item_id,
            "name": safe_name,
            "size": len(content),
            "content_type": content_type or "",
            "uploaded_at": datetime.now(UTC).isoformat(),
            "parse_status": parse_status,
            "preview": preview,
            "stored_name": stored_name,
            "text_stored_name": text_stored_name,
            "enabled": True,
        }
        with self._lock:
            items = self._read_index()
            items.append(item)
            self._write_index(items)
        return self._public(item)

    def set_file_enabled(self, item_id: str, enabled: bool) -> dict:
        with self._lock:
            items = self._read_index()
            target = next(
                (item for item in items if str(item.get("id")) == str(item_id)),
                None,
            )
            if target is None:
                raise KeyError("Knowledge file not found")
            target["enabled"] = bool(enabled)
            self._write_index(items)
            return self._public(self._normalized(target))

    def delete_file(self, item_id: str) -> bool:
        with self._lock:
            items = self._read_index()
            target = next(
                (item for item in items if str(item.get("id")) == str(item_id)),
                None,
            )
            if target is None:
                return False
            for key in ("stored_name", "text_stored_name"):
                stored_name = str(target.get(key) or "")
                if not stored_name:
                    continue
                try:
                    (self.files_dir / stored_name).unlink()
                except FileNotFoundError:
                    pass
            self._write_index(
                [item for item in items if str(item.get("id")) != str(item_id)]
            )
            return True

    def knowledge_excerpt(self, limit: int = 6000) -> str:
        chunks: list[str] = []
        used = 0
        for item in self.list_files():
            if not item.get("enabled", True) or item.get("parse_status") != "parsed":
                continue
            text_name = str(
                item.get("text_stored_name") or item.get("stored_name") or ""
            )
            path = self.files_dir / text_name
            try:
                if item.get("text_stored_name"):
                    text = path.read_text(encoding="utf-8").strip()
                else:
                    text = self._decode_text(path.read_bytes()).strip()
            except OSError:
                continue
            if not text:
                continue
            heading = f"### 投手知识文件：{item.get('name')}"
            chunk = f"{heading}\n{text}"
            remaining = limit - used
            if remaining <= 0:
                break
            chunks.append(chunk[:remaining])
            used += len(chunks[-1])
        return "\n\n".join(chunks)

    def overview(self, reports: list[dict]) -> dict:
        files = [self._public(item) for item in self.list_files()]
        active_count = sum(1 for item in files if item.get("enabled", True))
        historical = None if active_count else build_historical_reference(reports)
        if active_count:
            mode = "uploaded"
        elif historical and historical.get("metrics"):
            mode = "historical_average"
        else:
            mode = "empty"
        return {
            "mode": mode,
            "files": files,
            "active_count": active_count,
            "historical_reference": historical,
        }

    @staticmethod
    def _extract_text(suffix: str, content: bytes) -> str:
        if suffix in TEXT_SUFFIXES:
            return KnowledgeBaseStore._decode_text(content)
        try:
            if suffix == ".pdf":
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(content))
                return "\n".join((page.extract_text() or "") for page in reader.pages)
            if suffix == ".docx":
                from docx import Document

                document = Document(io.BytesIO(content))
                lines = [paragraph.text for paragraph in document.paragraphs]
                for table in document.tables:
                    for row in table.rows:
                        lines.append(" | ".join(cell.text for cell in row.cells))
                return "\n".join(line for line in lines if line.strip())
        except Exception:  # noqa: BLE001
            return ""
        return ""

    @staticmethod
    def _decode_text(content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    def _read_index(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []

    def _write_index(self, items: list[dict]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _normalized(item: dict) -> dict:
        normalized = dict(item)
        normalized["enabled"] = bool(normalized.get("enabled", True))
        return normalized

    @staticmethod
    def _public(item: dict) -> dict:
        return {
            key: value
            for key, value in item.items()
            if key not in {"stored_name", "text_stored_name"}
        }
