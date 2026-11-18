import pytest

from app.execution.cdp.browser import CdpBrowserGateway


class FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakePlaywright:
    def __init__(self) -> None:
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


@pytest.mark.asyncio
async def test_cdp_gateway_close_disconnects_without_closing_browser():
    gateway = CdpBrowserGateway("http://127.0.0.1:9222")
    browser = FakeBrowser()
    playwright = FakePlaywright()
    gateway.browser = browser
    gateway._playwright = playwright

    await gateway.close()

    assert browser.closed is False
    assert playwright.stopped is True
    assert gateway.browser is None


@pytest.mark.asyncio
async def test_connect_login_tab_does_not_false_alarm(monkeypatch):
    """浏览器里留着一个 /login 标签，但千川页正常 → 不能误报「需要登录千川」。"""
    from app.services import cdp_connection as conn

    async def fake_probe(endpoint, timeout=4.0):
        return {
            "endpoint": endpoint,
            "connected": True,
            "browser": "Chrome/155",
            "pages": 3,
            "qianchuan_pages": 3,
            "login_pages": 1,
            "error": None,
        }

    async def fake_ensure(endpoint, urls=None):
        return []

    monkeypatch.setattr(conn, "probe", fake_probe)
    monkeypatch.setattr(conn, "ensure_pages", fake_ensure)

    status = await conn.connect("http://127.0.0.1:9222")
    assert status["needs_login"] is False


@pytest.mark.asyncio
async def test_connect_reports_login_when_no_qianchuan_pages(monkeypatch):
    """真没登录：只有登录页、一个千川页都没有 → 要提示登录。"""
    from app.services import cdp_connection as conn

    async def fake_probe(endpoint, timeout=4.0):
        return {
            "endpoint": endpoint,
            "connected": True,
            "browser": "Chrome/155",
            "pages": 1,
            "qianchuan_pages": 0,
            "login_pages": 1,
            "error": None,
        }

    async def fake_ensure(endpoint, urls=None):
        return []

    monkeypatch.setattr(conn, "probe", fake_probe)
    monkeypatch.setattr(conn, "ensure_pages", fake_ensure)

    status = await conn.connect("http://127.0.0.1:9222")
    assert status["needs_login"] is True
@pytest.mark.asyncio
async def test_connect_does_not_open_extra_tabs_when_browser_is_already_connected(monkeypatch):
    """已连接时只返回状态，不再自动补开记住的页面；否则每次点击都会多开 tab。"""
    from app.services import cdp_connection as conn

    async def fake_probe(endpoint, timeout=4.0):
        return {
            "endpoint": endpoint,
            "connected": True,
            "browser": "Chrome/155",
            "pages": 2,
            "qianchuan_pages": 1,
            "login_pages": 0,
            "error": None,
        }

    async def fail_ensure(endpoint, urls=None):
        raise AssertionError("connected path must not auto-open remembered pages")

    monkeypatch.setattr(conn, "probe", fake_probe)
    monkeypatch.setattr(conn, "ensure_pages", fail_ensure)

    status = await conn.connect("http://127.0.0.1:9222")

    assert status["connected"] is True
    assert status["opened_pages"] == []


@pytest.mark.asyncio
async def test_connect_launches_one_qianchuan_page_without_extra_tabs(monkeypatch, tmp_path):
    """首次拉起浏览器时只打开千川首页，不再额外补开记住的页面。"""
    from app.services import cdp_connection as conn

    state = {"connected": False}
    launched: list[list[str]] = []

    async def fake_probe(endpoint, timeout=4.0):
        return {
            "endpoint": endpoint,
            "connected": state["connected"],
            "browser": "Chrome/155" if state["connected"] else None,
            "pages": 1 if state["connected"] else 0,
            "qianchuan_pages": 1 if state["connected"] else 0,
            "login_pages": 0,
            "error": None,
        }

    async def fake_sleep(_seconds):
        return None

    async def fail_ensure(endpoint, urls=None):
        raise AssertionError("launch path must not auto-open remembered pages")

    def fake_popen(args, **kwargs):
        launched.append(list(args))
        state["connected"] = True
        return object()

    profile = tmp_path / "chrome-profile"
    profile.mkdir()
    monkeypatch.setattr(conn, "probe", fake_probe)
    monkeypatch.setattr(conn.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(conn, "ensure_pages", fail_ensure)
    monkeypatch.setattr(conn, "_chrome_executable", lambda: "chrome.exe")
    monkeypatch.setattr(conn, "_chrome_running", lambda: False)
    monkeypatch.setattr(conn, "default_profile_dir", lambda: profile)
    monkeypatch.setattr(conn.subprocess, "Popen", fake_popen)

    status = await conn.connect("http://127.0.0.1:9222")

    assert status["connected"] is True
    assert status["opened_pages"] == []
    assert len(launched) == 1
    assert launched[0][-1] == conn.QIANCHUAN_URL
