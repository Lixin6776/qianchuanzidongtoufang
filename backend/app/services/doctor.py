"""客户版部署自检。

这个模块只回答一个问题：**这台电脑现在能不能正常交付给客户使用**。
它不做数据判断，也不读取任何凭据明文；只返回环境、存储、配置和连接状态。
"""

from __future__ import annotations

import platform as platform_module
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

APP_VERSION = "0.1.0"


def _check(
    key: str,
    label: str,
    status: str,
    message: str,
    *,
    action_label: str = "",
    action_target: str = "",
    optional: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "message": message,
        "action_label": action_label,
        "action_target": action_target,
        "optional": optional,
    }


def _runtime_check(python_version: tuple[int, ...], platform_name: str) -> dict[str, Any]:
    version_text = ".".join(str(part) for part in python_version[:3])
    if tuple(python_version[:2]) >= (3, 11):
        return _check("runtime", "运行环境", "ok", f"Python {version_text} · {platform_name}")
    return _check(
        "runtime",
        "运行环境",
        "blocked",
        f"Python {version_text} 过低，需要 Python 3.11 或更高版本",
    )


def _frontend_check(dist_dir: Path) -> dict[str, Any]:
    if (Path(dist_dir) / "index.html").is_file():
        return _check("frontend", "客户界面", "ok", "前端页面文件完整")
    return _check("frontend", "客户界面", "blocked", "未找到前端构建产物，请重新运行安装脚本")


def _storage_check(local_dir: Path) -> dict[str, Any]:
    root = Path(local_dir)
    probe: Path | None = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=root, prefix=".doctor-", delete=False
        ) as handle:
            handle.write(b"ok")
            probe = Path(handle.name)
        return _check("storage", "本机数据目录", "ok", "可正常读写本地数据")
    except OSError:
        return _check(
            "storage",
            "本机数据目录",
            "blocked",
            "本机数据目录不可写，请检查文件夹权限或磁盘空间",
        )
    finally:
        if probe is not None:
            try:
                probe.unlink()
            except OSError:
                pass


def _database_check(db: Any) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        return _check("database", "本地数据库", "ok", "数据库可正常读取")
    except Exception:  # noqa: BLE001
        return _check(
            "database",
            "本地数据库",
            "blocked",
            "数据库不可读，请检查 backend/qianchuan.db 和文件权限",
        )


def _configuration_check(room_name: str, aavid: str) -> dict[str, Any]:
    room = str(room_name or "").strip()
    account = str(aavid or "").strip()
    if not room:
        return _check(
            "configuration",
            "直播间配置",
            "blocked",
            "尚未填写要盯的直播间",
            action_label="打开数据源",
            action_target="data_source",
        )
    if not account:
        return _check(
            "configuration",
            "直播间配置",
            "warning",
            f"已配置直播间「{room}」，但账户 ID 尚未填写",
            action_label="补账户 ID",
            action_target="data_source",
        )
    return _check(
        "configuration",
        "直播间配置",
        "ok",
        f"直播间「{room}」和账户 ID 已配置",
    )


def _data_source_check(cdp_status: dict[str, Any], api_configured: bool) -> dict[str, Any]:
    if api_configured:
        return _check(
            "data_source",
            "数据连接",
            "warning",
            "开放平台凭据已配置；请运行一次连接测试确认可用",
        )

    connected = bool(cdp_status.get("connected"))
    qianchuan_pages = int(cdp_status.get("qianchuan_pages") or 0)
    login_pages = int(cdp_status.get("login_pages") or 0)
    if connected and qianchuan_pages > 0:
        return _check(
            "data_source",
            "数据连接",
            "ok",
            f"本机浏览器已连接，检测到 {qianchuan_pages} 个千川页面",
        )
    if connected and login_pages > 0:
        return _check(
            "data_source",
            "数据连接",
            "blocked",
            "浏览器已连上，但还没登录千川；请在弹出的浏览器里登录一次",
            action_label="重新连接",
            action_target="data_source",
        )
    if connected:
        return _check(
            "data_source",
            "数据连接",
            "blocked",
            "浏览器已连上，但没有检测到千川页面",
            action_label="打开数据源",
            action_target="data_source",
        )
    return _check(
        "data_source",
        "数据连接",
        "blocked",
        "本机浏览器尚未连接数据源",
        action_label="连接数据源",
        action_target="data_source",
    )


def _knowledge_check(knowledge: dict[str, Any]) -> dict[str, Any]:
    active_count = int(knowledge.get("active_count") or 0)
    if active_count > 0:
        return _check("knowledge", "投手知识库", "ok", f"已启用 {active_count} 份投手知识文件")
    if str(knowledge.get("mode") or "") == "historical_average":
        return _check(
            "knowledge",
            "投手知识库",
            "warning",
            "未上传知识文件，当前使用本账户历史平均值作为参考",
            action_label="打开知识库",
            action_target="decisions",
            optional=True,
        )
    return _check(
        "knowledge",
        "投手知识库",
        "warning",
        "暂无知识文件和足够历史样本，建议先上传投手 SOP",
        action_label="打开知识库",
        action_target="decisions",
        optional=True,
    )


def _monitor_check(monitor_status: dict[str, Any]) -> dict[str, Any]:
    if bool(monitor_status.get("running")):
        return _check("monitor", "直播盯盘", "ok", "盯盘正在运行")
    if bool(monitor_status.get("interrupted")) or bool(monitor_status.get("desired_running")):
        return _check(
            "monitor",
            "直播盯盘",
            "blocked",
            "盯盘已中断，请打开直播盯盘恢复",
            action_label="恢复盯盘",
            action_target="live_watch",
        )
    return _check(
        "monitor",
        "直播盯盘",
        "warning",
        "盯盘尚未启动；需要时在直播盯盘里手动开启",
        action_label="打开直播盯盘",
        action_target="live_watch",
        optional=True,
    )


def _report_check(report_count: int) -> dict[str, Any]:
    count = int(report_count or 0)
    if count > 0:
        return _check("first_report", "首份报表", "ok", f"已有 {count} 份盯盘记录")
    return _check(
        "first_report",
        "首份报表",
        "warning",
        "还没有第一份盯盘报表；连接成功后立即读取一次",
        action_label="去读取",
        action_target="live_watch",
    )


def _llm_check(configured: bool) -> dict[str, Any]:
    if configured:
        return _check("llm", "运营助手对话", "ok", "大模型已配置", optional=True)
    return _check(
        "llm",
        "运营助手对话",
        "warning",
        "大模型未配置；盯盘、复盘和素材分析仍可使用",
        action_label="打开大模型",
        action_target="llm",
        optional=True,
    )


def assess_deployment(
    *,
    db: Any,
    frontend_dist: Path,
    local_dir: Path,
    room_name: str,
    aavid: str,
    cdp_status: dict[str, Any],
    api_configured: bool,
    knowledge: dict[str, Any],
    report_count: int,
    monitor_status: dict[str, Any],
    llm_configured: bool,
    python_version: tuple[int, ...] = sys.version_info[:3],
    platform_name: str = platform_module.platform(terse=True),
    app_version: str = APP_VERSION,
) -> dict[str, Any]:
    """汇总客户部署状态；不包含任何 Token、Secret、Cookie 或完整凭据。"""
    checks = [
        _runtime_check(tuple(python_version), platform_name),
        _frontend_check(frontend_dist),
        _storage_check(local_dir),
        _database_check(db),
        _configuration_check(room_name, aavid),
        _data_source_check(cdp_status, api_configured),
        _knowledge_check(knowledge),
        _monitor_check(monitor_status),
        _report_check(report_count),
        _llm_check(llm_configured),
    ]
    summary = {
        "total": len(checks),
        "ok": sum(item["status"] == "ok" for item in checks),
        "warning": sum(item["status"] == "warning" for item in checks),
        "blocked": sum(item["status"] == "blocked" for item in checks),
    }
    if summary["blocked"]:
        status = "blocked"
    elif summary["warning"]:
        status = "attention"
    else:
        status = "ready"
    return {
        "status": status,
        "ready": summary["blocked"] == 0,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "environment": {
            "app_version": app_version,
            "python": ".".join(str(part) for part in python_version[:3]),
            "platform": platform_name,
            "deployment": "single_account_local",
        },
        "summary": summary,
        "checks": checks,
    }
