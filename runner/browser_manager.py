# browser_manager/browser_manager.py
import asyncio
import traceback
from typing import Optional
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext
from . import config, logger, errors, metrics

class BrowserManager:
    """
    Manages a Playwright browser instance with health monitoring and auto-restart.
    Async version.
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._restart_count = 0
        self._last_restart_ts = 0
        # Start prometheus metrics server if requested
        try:
            metrics.start_metrics_server(config.PROMETHEUS_METRICS_PORT)
        except Exception:
            logger.log("WARN", "metrics_start_failed", "Could not start Prometheus metrics server; continuing without metrics")

    # -------------------------
    # Lifecycle: start / stop
    # -------------------------
    async def start(self):
        logger.log("INFO", "bm_starting", "Starting BrowserManager")
        await self._start_browser()
        self._start_monitor()

    async def stop(self):
        logger.log("INFO", "bm_stopping", "Stopping BrowserManager")
        self._stop_event.set()
        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=5)
            except asyncio.TimeoutError:
                pass
        await self._close_browser()
        logger.log("INFO", "bm_stopped", "BrowserManager stopped")

    # -------------------------
    # Internal helpers
    # -------------------------
    async def _start_browser(self):
        try:
            logger.log("INFO", "bm_launch", "Launching Playwright + Chromium",
                       headless=config.HEADLESS, exec_path=config.BROWSER_EXEC_PATH)
            self._playwright = await async_playwright().start()
            launch_args = [] # Firefox doesn't need the same sandbox args usually, but we can keep empty or minimal
            if config.BROWSER_EXEC_PATH:
                self._browser = await self._playwright.chromium.launch(
                    headless=config.HEADLESS,
                    executable_path=config.BROWSER_EXEC_PATH,
                    args=launch_args
                )
            else:
                self._browser = await self._playwright.chromium.launch(
                    headless=config.HEADLESS,
                    args=launch_args
                )
            self._restart_count = 0 if self._restart_count == 0 else self._restart_count
            metrics.BROWSER_UP.set(1)
            logger.log("INFO", "bm_launched", "Chromium launched")
        except Exception as e:
            logger.log("ERROR", "bm_launch_error", "Failed to launch browser", error=str(e), tb=traceback.format_exc())
            metrics.BROWSER_UP.set(0)
            raise errors.BrowserStartError(str(e))

    async def _close_browser(self):
        try:
            if self._browser:
                logger.log("INFO", "bm_browser_close", "Closing browser process")
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.log("WARN", "bm_browser_close_err", "Error while closing browser", error=str(e))
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.log("WARN", "bm_playwright_stop_err", "Error while stopping playwright", error=str(e))
                self._playwright = None
            metrics.BROWSER_UP.set(0)
        except Exception as e:
            logger.log("ERROR", "bm_close_error", "Unexpected error during browser close", error=str(e), tb=traceback.format_exc())

    # -------------------------
    # Context factory for sessions
    # -------------------------
    async def new_context(self, **kwargs) -> BrowserContext:
        """
        Create and return an isolated browser context.
        Raises BrowserHealthError if browser is not available.
        """
        if not self._browser:
            raise errors.BrowserHealthError("Browser not started")
        # merge default viewport etc
        context_kwargs = {
            "viewport": config.DEFAULT_VIEWPORT,
            "ignore_https_errors": True,
            **kwargs
        }
        try:
            ctx = await self._browser.new_context(**context_kwargs)
            logger.log("DEBUG", "bm_new_context", "Created new browser context")
            return ctx
        except Exception as e:
            logger.log("ERROR", "bm_new_context_error", "Failed to create context", error=str(e), tb=traceback.format_exc())
            raise errors.BrowserHealthError(str(e))

    # -------------------------
    # Health-check probe & restart
    # -------------------------
    def _start_monitor(self):
        if self._monitor_task and not self._monitor_task.done():
            return
        self._stop_event.clear()
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.log("INFO", "bm_monitor_start", "Health monitor task started")

    async def _monitor_loop(self):
        backoff = config.RESTART_BACKOFF_BASE_SEC
        while not self._stop_event.is_set():
            try:
                healthy = await self._probe_once()
                if healthy:
                    backoff = config.RESTART_BACKOFF_BASE_SEC
                # sleep the interval (but wake earlier if stopping)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=max(1, config.HEALTH_PROBE_INTERVAL_SEC))
                except asyncio.TimeoutError:
                    pass
            except Exception as e:
                logger.log("ERROR", "bm_monitor_exception", "Monitor loop exception", error=str(e), tb=traceback.format_exc())
                # exponential backoff on unexpected monitor exceptions
                await asyncio.sleep(min(backoff, config.RESTART_BACKOFF_MAX_SEC))
                backoff = min(backoff * 2, config.RESTART_BACKOFF_MAX_SEC)

    async def _probe_once(self) -> bool:
        """
        Lightweight probe: try creating a temporary context and open about:blank or a small data URL.
        If context creation or navigation fails, attempt a restart of the browser.
        """
        if not self._browser:
            logger.log("WARN", "bm_probe", "No browser object found — attempting restart")
            await self._restart_browser()
            return False

        try:
            # create a tiny context and page and do a no-op navigation
            logger.log("DEBUG", "bm_probe_start", "Starting probe")
            ctx = await self._browser.new_context() # minimal context
            page = await ctx.new_page()
            logger.log("DEBUG", "bm_probe_nav", "Navigating to data URL")
            await page.goto("data:text/plain,ok", timeout=config.HEALTH_PROBE_TIMEOUT_SEC * 1000)
            logger.log("DEBUG", "bm_probe_nav_done", "Navigation done")
            try:
                await page.close()
                await ctx.close()
            except Exception:
                pass # ignore cleanup errors if navigation succeeded
            logger.log("DEBUG", "bm_probe_ok", "Browser probe successful")
            metrics.BROWSER_UP.set(1)
            return True
        except Exception as e:
            logger.log("ERROR", "bm_probe_failed", "Browser probe failed — will attempt restart", error=str(e), tb=traceback.format_exc())
            metrics.BROWSER_UP.set(0)
            # attempt restart with backoff
            await self._restart_browser()
            return False

    async def _restart_browser(self):
        """
        Close and restart browser. Maintain restart metrics and backoff.
        """
        try:
            logger.log("WARN", "bm_restart", "Restarting browser due to failed probe")
            await self._close_browser()
        except Exception as e:
            logger.log("ERROR", "bm_restart_close_err", "Error during browser close", error=str(e))
        # exponential backoff handled by monitor loop
        # attempt to start again — if start fails, bubble up after logging
        try:
            await self._start_browser()
            self._restart_count += 1
            self._last_restart_ts = int(asyncio.get_running_loop().time()) # use loop time or time.time()
            metrics.RESTART_COUNTER.inc()
            metrics.LAST_RESTART_TS.set(self._last_restart_ts)
            logger.log("INFO", "bm_restart_done", "Browser restart completed", restart_count=self._restart_count)
        except Exception as e:
            logger.log("ERROR", "bm_restart_failed", "Failed to restart browser", error=str(e), tb=traceback.format_exc())

    # -------------------------
    # Health API
    # -------------------------
    def get_health(self) -> dict:
        ok = self._browser is not None
        return {
            "browser_up": ok,
            "restart_count": self._restart_count,
            "last_restart_ts": self._last_restart_ts
        }

    # -------------------------
    # Utility for other modules
    # -------------------------
    def ensure_browser(self):
        """
        Ensure browser is available, raise BrowserHealthError otherwise.
        """
        if not self._browser:
            logger.log("WARN", "bm_ensure", "Browser not available")
            raise errors.BrowserHealthError("Browser not available")
        return True
