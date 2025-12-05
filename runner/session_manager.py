# runner/session_manager.py
import asyncio
import time
import uuid
import shutil
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from .logger import log
from .errors import BrowserHealthError
from .paths import make_session_dir, session_screenshot_path, session_video_path
from .config import DEFAULT_VIEWPORT

@dataclass
class SessionMeta:
    session_id: str
    created_at: float
    status: str  # 'active' | 'closed' | 'error'
    session_dir: str
    video_enabled: bool
    context: Any = field(default=None)  # Playwright BrowserContext
    page: Any = field(default=None)     # Playwright Page
    last_update: float = field(default_factory=lambda: time.time())
    metadata: Dict[str, Any] = field(default_factory=dict)

class SessionManager:
    """
    Manages per-task isolated browser contexts/sessions.
    Async version.
    """

    def __init__(self, browser_manager, artifacts_root: Optional[str] = None):
        self._bm = browser_manager
        self._sessions: Dict[str, SessionMeta] = {}
        self._lock = asyncio.Lock()
        self._artifacts_root = artifacts_root or os.getenv("BM_ARTIFACTS_ROOT", "/tmp/browser_runner_artifacts")
        os.makedirs(self._artifacts_root, exist_ok=True)

    # ---------------------
    # Session lifecycle
    # ---------------------
    async def create_session(self, video: bool = False, context_kwargs: Optional[Dict] = None, keep_artifacts: bool = False) -> str:
        """
        Create a new isolated browser context and page.
        :param video: enable Playwright video recording for this session
        :param context_kwargs: additional kwargs to pass to browser.new_context(...)
        :param keep_artifacts: when closing, whether to keep the session dir (default False)
        :return: session_id
        """
        context_kwargs = context_kwargs or {}
        session_id = uuid.uuid4().hex
        session_dir = make_session_dir(session_id)

        # configure record_video arg if requested
        if video:
            # Playwright expects record_video_dir
            context_kwargs["record_video_dir"] = session_dir
        # set default viewport if not provided
        if "viewport" not in context_kwargs:
            context_kwargs["viewport"] = DEFAULT_VIEWPORT

        async with self._lock:
            log("INFO", "session_create_start", f"Creating session {session_id}", session_id=session_id, video=video, session_dir=session_dir)
            try:
                # ensure BM has browser available
                self._bm.ensure_browser()

                ctx = await self._bm.new_context(**context_kwargs)
                page = await ctx.new_page()
                meta = SessionMeta(
                    session_id=session_id,
                    created_at=time.time(),
                    status="active",
                    session_dir=session_dir,
                    video_enabled=video,
                    context=ctx,
                    page=page,
                )
                meta.metadata["keep_artifacts_on_close"] = bool(keep_artifacts)
                self._sessions[session_id] = meta
                log("INFO", "session_create_done", "Session created", session_id=session_id)
                return session_id
            except BrowserHealthError as bhe:
                log("ERROR", "session_create_bm_unavailable", "BrowserManager unavailable", error=str(bhe))
                raise
            except Exception as e:
                # cleanup partial dir if something went wrong
                try:
                    shutil.rmtree(session_dir)
                except Exception:
                    pass
                log("ERROR", "session_create_failed", "Failed to create session", session_id=session_id, error=str(e))
                raise

    def get_session(self, session_id: str) -> Optional[SessionMeta]:
        # Lock not strictly needed for read if we accept slight race, but good for consistency
        # However, making this async might complicate synchronous callers if any.
        # But we are fully async now.
        return self._sessions.get(session_id)

    def get_page(self, session_id: str):
        meta = self._sessions.get(session_id)
        if not meta:
            raise KeyError(f"Session {session_id} not found")
        return meta.page

    # ---------------------
    # Snapshot / artifacts
    # ---------------------
    async def snapshot(self, session_id: str, filename: str = "screenshot.png") -> str:
        """
        Take a screenshot and store it in the session artifacts directory.
        Returns the saved path.
        """
        async with self._lock:
            meta = self._sessions.get(session_id)
            if not meta or meta.status != "active":
                raise KeyError(f"Active session {session_id} not found")
            path = session_screenshot_path(meta.session_dir, filename)
            try:
                await meta.page.screenshot(path=path)
                meta.last_update = time.time()
                log("INFO", "session_snapshot", "Saved screenshot", session_id=session_id, path=path)
                return path
            except Exception as e:
                log("ERROR", "session_snapshot_failed", "Screenshot failed", session_id=session_id, error=str(e))
                raise

    def get_video_path(self, session_id: str) -> Optional[str]:
        meta = self._sessions.get(session_id)
        if not meta:
            return None
        if not meta.video_enabled:
            return None
        # Playwright writes video files inside session_dir; there may be one or many per page.
        # We return the first .webm file (if present).
        for f in os.listdir(meta.session_dir):
            if f.lower().endswith(".webm") or f.lower().endswith(".mp4"):
                return os.path.join(meta.session_dir, f)
        return None

    # ---------------------
    # Close / cleanup
    # ---------------------
    async def close_session(self, session_id: str, keep_artifacts: Optional[bool] = None) -> bool:
        """
        Close page/context and cleanup temp dir unless keep_artifacts==True.
        Returns True if closed successfully.
        """
        async with self._lock:
            meta = self._sessions.get(session_id)
            if not meta:
                log("WARN", "session_close_missing", "Session not found (maybe already closed)", session_id=session_id)
                return False

            # honor explicit arg; otherwise honor the session's metadata flag
            if keep_artifacts is None:
                keep = bool(meta.metadata.get("keep_artifacts_on_close", False))
            else:
                keep = bool(keep_artifacts)

            log("INFO", "session_closing", "Closing session", session_id=session_id, keep_artifacts=keep)
            try:
                # close page then context
                try:
                    if meta.page:
                        try:
                            await meta.page.close()
                        except Exception as e:
                            log("WARN", "session_page_close_err", "Error closing page", session_id=session_id, error=str(e))
                except Exception:
                    pass

                try:
                    if meta.context:
                        await meta.context.close()
                except Exception as e:
                    log("WARN", "session_context_close_err", "Error closing context", session_id=session_id, error=str(e))

                meta.status = "closed"
                meta.last_update = time.time()

                # if not keep -> delete directory
                if not keep:
                    try:
                        shutil.rmtree(meta.session_dir)
                        log("INFO", "session_dir_removed", "Removed session artifacts", session_id=session_id)
                    except Exception as e:
                        log("WARN", "session_dir_remove_err", "Error removing session dir", session_id=session_id, error=str(e))
                else:
                    log("INFO", "session_dir_kept", "Keeping session artifacts", session_id=session_id, dir=meta.session_dir)

                # remove from in-memory map
                del self._sessions[session_id]
                return True
            except Exception as e:
                meta.status = "error"
                log("ERROR", "session_close_error", "Failed to close session cleanly", session_id=session_id, error=str(e))
                raise

    # ---------------------
    # Utilities
    # ---------------------
    def list_sessions(self) -> Dict[str, SessionMeta]:
        return dict(self._sessions)

    async def cleanup_expired(self, ttl_seconds: int = 3600) -> int:
        """
        Remove sessions that were created earlier than TTL and are closed or stale.
        Returns the number of removed session dirs.
        """
        now = time.time()
        removed = 0
        to_remove = []
        async with self._lock:
            for sid, meta in list(self._sessions.items()):
                age = now - meta.created_at
                # if closed but still present (should not normally happen)
                if meta.status != "active" and age > ttl_seconds:
                    to_remove.append(sid)
                # if active but too old -> attempt close then remove
                elif meta.status == "active" and age > ttl_seconds * 2:
                    log("WARN", "session_expired_active", "Active session too old, closing", session_id=sid, age=age)
                    try:
                        await self.close_session(sid)
                        to_remove.append(sid)
                    except Exception as e:
                        log("ERROR", "session_expired_close_err", "Failed to close expired session", session_id=sid, error=str(e))

        # physically remove any lingering dirs that might remain (only for closed ones)
        for sid in to_remove:
            try:
                path = os.path.join(self._artifacts_root, sid)
                if os.path.exists(path):
                    shutil.rmtree(path)
                removed += 1
            except Exception as e:
                log("WARN", "session_cleanup_err", "Failed to remove old session dir", session_id=sid, error=str(e))
        log("INFO", "cleanup_expired_done", f"Removed {removed} expired sessions", removed=removed)
        return removed

    async def _cleanup_all_on_exit(self):
        log("INFO", "session_cleanup_exit", "Cleaning up all sessions on process exit")
        async with self._lock:
            sids = list(self._sessions.keys())
        for sid in sids:
            try:
                await self.close_session(sid, keep_artifacts=False)
            except Exception:
                pass
