"""盯盘日志存储（SQLite）。

原来用 JSON：每 5 分钟把整个文件读进来、改完再整个写回去。跑到 5MB 之后
每次都读+写 5MB，基线还要再解析 400 条，越来越慢。

换成 SQLite：追加是插入一条，读取按时间倒序取 N 条。老 JSON 会在首次使用时
自动导入一次（原文件保留，当备份）。
"""

import hashlib
import json
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[3] / ".local" / "live_watch_logs.sqlite3"
)
LEGACY_JSON_PATH = Path(__file__).resolve().parents[3] / ".local" / "live_watch_logs.json"
# 保留多少条盯盘记录。
# 之前是 1500（约 5 天）—— 那会让"数据资产"变成一个 5 天滚动窗口，永远长不大。
# 提到 20000（约 70 天 @ 每5分钟一条）：本地 SQLite 约 200MB 量级，可接受。
KEEP_ROWS = 20000


class SqliteWatchLogStore:
    """和原来的 LiveWatchLogStore 保持一样的对外接口。"""

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        legacy_json_path: Path = LEGACY_JSON_PATH,
        keep: int = KEEP_ROWS,
    ) -> None:
        self.path = Path(db_path)
        self.legacy_json_path = Path(legacy_json_path)
        self.keep = keep
        self._init_db()
        self._import_legacy_once()

    # --- 对外接口 ---------------------------------------------------------
    def list_logs(self, limit: int = 50) -> list[dict]:
        """按时间倒序（最新的在前）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM watch_reports ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [self._decode(row[0]) for row in rows]

    def list_analysis_logs(self, limit: int = 20000) -> list[dict]:
        """读取轻量分析投影；不解析素材数组、Markdown 等大字段。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT a.id, a.created_at, a.source, a.spend, a.gmv, a.operations, "
                "a.online_viewers, a.cpm, a.exposure_view_rate, a.roi, a.assist_share "
                "FROM watch_analysis a JOIN watch_reports w ON w.id = a.id "
                "ORDER BY a.created_at DESC, a.rowid DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        items = []
        for row in rows:
            try:
                operations = json.loads(row[5])
            except (TypeError, json.JSONDecodeError):
                operations = []
            items.append(
                {
                    "id": row[0],
                    "created_at": row[1],
                    "source": row[2],
                    "spend": row[3],
                    "gmv": row[4],
                    "online_viewers": row[6],
                    "cpm": row[7],
                    "exposure_view_rate": row[8],
                    "roi": row[9],
                    "assist_share": row[10],
                    "_operations": operations if isinstance(operations, list) else [],
                }
            )
        return items

    def latest(self) -> dict | None:
        items = self.list_logs(limit=1)
        return items[0] if items else None

    def append(self, report: dict) -> dict:
        payload = json.dumps(report, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO watch_reports "
                "(id, created_at, room_name, live_room_id, live_started_at, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(report.get("id") or ""),
                    str(report.get("created_at") or ""),
                    str(report.get("room_name") or ""),
                    str(report.get("live_room_id") or ""),
                    str(report.get("live_started_at") or ""),
                    payload,
                ),
            )
            self._upsert_analysis(conn, report, payload)
            conn.execute(
                "DELETE FROM watch_reports WHERE id NOT IN "
                "(SELECT id FROM watch_reports ORDER BY created_at DESC, rowid DESC LIMIT ?)",
                (self.keep,),
            )
            conn.execute(
                "DELETE FROM watch_analysis WHERE id NOT IN (SELECT id FROM watch_reports)"
            )
            conn.commit()
        return report

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM watch_reports").fetchone()[0])

    # --- 内部 -------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS watch_reports (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    room_name TEXT,
                    live_room_id TEXT,
                    live_started_at TEXT,
                    payload TEXT NOT NULL
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_watch_reports_created "
                "ON watch_reports(created_at DESC)"
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS watch_analysis (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    source TEXT,
                    spend REAL,
                    gmv REAL,
                    operations TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    online_viewers REAL,
                    cpm REAL,
                    exposure_view_rate REAL,
                    roi REAL,
                    assist_share REAL
                )"""
            )
            self._ensure_analysis_columns(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_watch_analysis_created "
                "ON watch_analysis(created_at DESC)"
            )
            self._backfill_analysis(conn)
            conn.commit()

    def _import_legacy_once(self) -> None:
        """首次运行：把老的 JSON 导进来（文件保留，不删）。"""
        if self.count() > 0:
            return
        if not self.legacy_json_path.exists():
            return
        try:
            items = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(items, list) or not items:
            return
        for report in items[-self.keep :]:
            if isinstance(report, dict):
                try:
                    self.append(report)
                except sqlite3.Error:
                    continue

    @staticmethod
    def _decode(payload: str) -> dict:
        try:
            value = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _numeric(value):
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _serialized_operations(report: dict) -> str:
        from app.services.ops_outcome import _ops_from_report

        try:
            operations = _ops_from_report(report)
        except Exception:  # noqa: BLE001
            operations = []
        payload = [
            {"at": at.isoformat(), "operation": name, "meta": meta}
            for at, name, meta in operations
        ]
        return json.dumps(payload, ensure_ascii=False)

    def _ensure_analysis_columns(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(watch_analysis)").fetchall()}
        wanted = {
            "online_viewers": "REAL",
            "cpm": "REAL",
            "exposure_view_rate": "REAL",
            "roi": "REAL",
            "assist_share": "REAL",
        }
        added = False
        for name, kind in wanted.items():
            if name in columns:
                continue
            conn.execute(f"ALTER TABLE watch_analysis ADD COLUMN {name} {kind}")
            added = True
        if added:
            # 旧投影缺少状态字段时强制重算，避免返回半截数据。
            conn.execute("DELETE FROM watch_analysis")

    @staticmethod
    def _assist_share(report: dict) -> float | None:
        split = report.get("spend_split") or {}
        try:
            basic = float(split.get("basic_spend") or 0)
            assist = float(split.get("assist_spend") or 0)
        except (TypeError, ValueError):
            return None
        return round(assist / (basic + assist), 3) if basic + assist > 0 else None

    def _upsert_analysis(self, conn: sqlite3.Connection, report: dict, payload: str) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO watch_analysis "
            "(id, created_at, source, spend, gmv, operations, payload_hash, "
            "online_viewers, cpm, exposure_view_rate, roi, assist_share) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(report.get("id") or ""),
                str(report.get("created_at") or ""),
                str(report.get("source") or ""),
                self._numeric(report.get("spend")),
                self._numeric(report.get("gmv")),
                self._serialized_operations(report),
                hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                self._numeric(report.get("online_viewers")),
                self._numeric(report.get("cpm")),
                self._numeric(report.get("exposure_view_rate")),
                self._numeric(report.get("roi")),
                self._assist_share(report),
            ),
        )

    def _backfill_analysis(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT w.id, w.payload, a.payload_hash FROM watch_reports w "
            "LEFT JOIN watch_analysis a ON a.id = w.id"
        ).fetchall()
        for report_id, payload, old_hash in rows:
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if digest == old_hash:
                continue
            report = self._decode(payload)
            if not report or not report.get("created_at"):
                conn.execute("DELETE FROM watch_analysis WHERE id = ?", (report_id,))
                continue
            self._upsert_analysis(conn, report, payload)
        conn.execute(
            "DELETE FROM watch_analysis WHERE id NOT IN (SELECT id FROM watch_reports)"
        )
