from __future__ import annotations

import html
import json
import logging
import threading
import uuid
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from wf_authoring import node

_LOGGER = logging.getLogger(__name__)
_MAX_SESSION_EVENTS = 10


class Snapshot(BaseModel):
    title: str
    url: str
    button_text: str
    status_text: str
    clicked: bool
    events: list[str] = Field(default_factory=list, max_length=10)


class OpenPageInput(BaseModel):
    button_label: str = "Click to continue"
    open_browser: bool = Field(
        default=False,
        description="Open the page in the default browser for manual runs.",
    )


class OpenPageOutput(BaseModel):
    session_id: str
    url: str
    before: Snapshot


class WaitForClickInput(BaseModel):
    session_id: str
    simulate: bool = Field(
        default=True,
        description="When true, perform a deterministic HTTP click instead of waiting.",
    )
    timeout_seconds: float = Field(default=10.0, gt=0)


class WaitForClickOutput(BaseModel):
    clicked: bool
    after: Snapshot


class CollectSnapshotsInput(BaseModel):
    session_id: str
    before: Snapshot
    after: Snapshot


class CollectSnapshotsOutput(BaseModel):
    before: Snapshot
    after: Snapshot
    closed: bool


@dataclass(slots=True)
class _ClickSession:
    session_id: str
    button_label: str
    server: ThreadingHTTPServer
    thread: threading.Thread
    clicked: threading.Event
    events: list[str]

    @property
    def url(self) -> str:
        host = self.server.server_address[0]
        port = self.server.server_address[1]
        return f"http://{host}:{port}/"

    def snapshot(self) -> Snapshot:
        clicked = self.clicked.is_set()
        return Snapshot(
            title="Workflow Click Fixture",
            url=self.url,
            button_text=self.button_label,
            status_text="Button clicked" if clicked else "Waiting for click",
            clicked=clicked,
            events=list(self.events[-10:]),
        )

    def add_event(self, event: str) -> None:
        """Record bounded click-session events for compact snapshots."""
        self.events.append(event)
        if len(self.events) > _MAX_SESSION_EVENTS:
            del self.events[: len(self.events) - _MAX_SESSION_EVENTS]

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            _LOGGER.warning(
                "click session %s server thread did not stop within timeout",
                self.session_id,
            )


_SESSIONS: dict[str, _ClickSession] = {}
_SESSIONS_LOCK = threading.Lock()


class _ClickHandler(BaseHTTPRequestHandler):
    server: _ClickServer

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep example runs quiet; workflow trace carries the useful output."""

    def do_GET(self) -> None:
        if self.path == "/":
            self._send_html()
            return
        if self.path == "/snapshot":
            self._send_json(self.server.session.snapshot().model_dump(mode="json"))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/click":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        session = self.server.session
        session.clicked.set()
        session.add_event("click")
        self._send_json(session.snapshot().model_dump(mode="json"))

    def _send_html(self) -> None:
        session = self.server.session
        status = "Button clicked" if session.clicked.is_set() else "Waiting for click"
        html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Workflow Click Fixture</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 3rem; background: #f8f3e8; color: #1f2933; }}
    main {{ max-width: 720px; padding: 2rem; border: 3px solid #1f2933; background: #fffaf0; }}
    button {{ font-size: 1.25rem; padding: 0.9rem 1.3rem; border: 2px solid #1f2933; background: #f2b84b; cursor: pointer; }}
    #status {{ margin-top: 1rem; font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <h1>Workflow Click Fixture</h1>
    <button id="continue" type="button">{html.escape(session.button_label)}</button>
    <p id="status">{html.escape(status)}</p>
  </main>
  <script>
    document.getElementById("continue").addEventListener("click", async () => {{
      await fetch("/click", {{ method: "POST" }});
      document.getElementById("status").textContent = "Button clicked";
    }});
  </script>
</body>
</html>"""
        encoded = html_doc.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class _ClickServer(ThreadingHTTPServer):
    session: _ClickSession
    allow_reuse_address: ClassVar[bool] = True


@node(name="open_click_page")
def open_click_page(payload: OpenPageInput) -> OpenPageOutput:
    return _open_click_page(payload)


@node(name="wait_for_click")
def wait_for_click(payload: WaitForClickInput) -> WaitForClickOutput:
    return _wait_for_click(payload)


@node(name="collect_snapshots")
def collect_snapshots(payload: CollectSnapshotsInput) -> CollectSnapshotsOutput:
    return _collect_snapshots(payload)


def _open_click_page(payload: OpenPageInput) -> OpenPageOutput:
    session_id = f"click_{uuid.uuid4().hex}"
    server = _ClickServer(("127.0.0.1", 0), _ClickHandler)
    session = _ClickSession(
        session_id=session_id,
        button_label=payload.button_label,
        server=server,
        thread=threading.Thread(target=server.serve_forever, daemon=True),
        clicked=threading.Event(),
        events=["opened"],
    )
    server.session = session
    with _SESSIONS_LOCK:
        _SESSIONS[session_id] = session
    session.thread.start()
    if payload.open_browser:
        try:
            opened = webbrowser.open(session.url)
        except Exception:
            _LOGGER.exception("failed to open browser for click session %s", session_id)
        else:
            if not opened:
                _LOGGER.warning("browser did not report opening %s", session.url)
    return OpenPageOutput(
        session_id=session_id,
        url=session.url,
        before=session.snapshot(),
    )


def _wait_for_click(payload: WaitForClickInput) -> WaitForClickOutput:
    session = _get_session(payload.session_id)
    if payload.simulate:
        request = Request(f"{session.url}click", method="POST")
        try:
            with urlopen(request, timeout=payload.timeout_seconds) as response:
                response.read()
        except (HTTPError, URLError) as exc:
            raise RuntimeError(
                f"simulated click failed for session {payload.session_id!r}"
            ) from exc
    elif not session.clicked.wait(timeout=payload.timeout_seconds):
        raise TimeoutError("timed out waiting for click")
    return WaitForClickOutput(
        clicked=session.clicked.is_set(), after=session.snapshot()
    )


def _collect_snapshots(payload: CollectSnapshotsInput) -> CollectSnapshotsOutput:
    session = _get_session(payload.session_id)
    session.close()
    with _SESSIONS_LOCK:
        _SESSIONS.pop(payload.session_id, None)
    return CollectSnapshotsOutput(
        before=payload.before, after=payload.after, closed=True
    )


def _get_session(session_id: str) -> _ClickSession:
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"unknown click session {session_id!r}")
    return session


def _active_session_count() -> int:
    with _SESSIONS_LOCK:
        return len(_SESSIONS)


registry = [open_click_page, wait_for_click, collect_snapshots]
