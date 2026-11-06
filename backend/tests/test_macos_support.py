from pathlib import Path

from app.services import cdp_connection as conn


def _use_macos_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(conn.sys, "platform", "darwin")
    monkeypatch.setattr(conn.Path, "home", classmethod(lambda cls: tmp_path))


def test_macos_chrome_executable_uses_user_applications(monkeypatch, tmp_path):
    _use_macos_home(monkeypatch, tmp_path)
    chrome = (
        tmp_path
        / "Applications"
        / "Google Chrome.app"
        / "Contents"
        / "MacOS"
        / "Google Chrome"
    )
    chrome.parent.mkdir(parents=True)
    chrome.touch()

    assert conn._chrome_executable() == str(chrome)


def test_macos_default_profile_dir(monkeypatch, tmp_path):
    _use_macos_home(monkeypatch, tmp_path)

    assert conn.default_profile_dir() == (
        tmp_path / "Library" / "Application Support" / "Google" / "Chrome"
    )


def test_macos_assistant_profile_dir(monkeypatch, tmp_path):
    _use_macos_home(monkeypatch, tmp_path)

    assert conn.assistant_profile_dir() == (
        tmp_path / "Library" / "Application Support" / "QianchuanAssistantChrome"
    )


def test_macos_chrome_running_uses_pgrep(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return conn.subprocess.CompletedProcess(args, 0, "12345\n", "")

    monkeypatch.setattr(conn.sys, "platform", "darwin")
    monkeypatch.setattr(conn.subprocess, "run", fake_run)

    assert conn._chrome_running() is True
    assert calls[0][0] == ["pgrep", "-f", "Google Chrome.app/Contents/MacOS/Google Chrome"]
