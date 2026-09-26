"""Run ONYX: `python -m station`.

Environment variables (only needed when hosting on a server, see README):
  ONYX_HOST           interface to listen on (default 127.0.0.1 = this computer only)
  ONYX_PORT           port (default 8000)
  ONYX_PASSWORD       require this password to open ONYX (required unless ONYX_HOST is 127.0.0.1)
  ONYX_ALLOWED_HOSTS  comma-separated host names the site is reached by, e.g. onyx.example.com
"""

import os
import sys

from .settings import DATA_DIR

# Started hidden (pythonw on Windows, launchd on Mac) there is no console: log to a file instead.
if sys.stdout is None or sys.stderr is None:
    DATA_DIR.mkdir(exist_ok=True)
    log = open(DATA_DIR / "onyx.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log

import uvicorn  # noqa: E402

host = os.environ.get("ONYX_HOST", "127.0.0.1")
if host not in ("127.0.0.1", "localhost") and not os.environ.get("ONYX_PASSWORD"):
    sys.exit("Refusing to listen on a network address without ONYX_PASSWORD set.")
uvicorn.run("station.app:app", host=host, port=int(os.environ.get("ONYX_PORT", "8000")), proxy_headers=True)
