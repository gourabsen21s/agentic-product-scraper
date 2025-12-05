# browser_manager/config.py
import os

# Playwright / browser config
HEADLESS = os.getenv("BM_HEADLESS", "false").lower() == "true"
BROWSER_EXEC_PATH = os.getenv("BM_BROWSER_EXEC_PATH", None)  # optional
DEFAULT_VIEWPORT = {"width": int(os.getenv("BM_VIEWPORT_W", "1440")),
                    "height": int(os.getenv("BM_VIEWPORT_H", "900"))}

# Health & monitor
HEALTH_PROBE_INTERVAL_SEC = int(os.getenv("BM_HEALTH_PROBE_INTERVAL", "10"))  # probe every N seconds
HEALTH_PROBE_TIMEOUT_SEC = int(os.getenv("BM_HEALTH_PROBE_TIMEOUT", "10"))    # timeout for each probe
HEALTH_PROBE_RETRY = int(os.getenv("BM_HEALTH_PROBE_RETRY", "1"))            # retries during probe

# Restart behaviour
RESTART_BACKOFF_BASE_SEC = int(os.getenv("BM_RESTART_BACKOFF_BASE", "2"))
RESTART_BACKOFF_MAX_SEC = int(os.getenv("BM_RESTART_BACKOFF_MAX", "60"))

# Prometheus metrics server (optional)
PROMETHEUS_METRICS_PORT = int(os.getenv("BM_PROM_PORT", "8001"))

# Logging
LOG_LEVEL = os.getenv("BM_LOG_LEVEL", "INFO")

# Perception
# YOLO_MODEL_PATH = os.getenv("BM_YOLO_MODEL_PATH", "OpenDILabCommunity/webpage_element_detection")
YOLO_MODEL_PATH = os.getenv("BM_YOLO_MODEL_PATH", "models/web_detect_best_m.pt") # Use standard model for easy start
