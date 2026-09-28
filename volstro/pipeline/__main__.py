"""Run the Volstro pipeline: `python -m pipeline`.

Environment variables (only needed when hosting on a server, see README):
  VOLSTRO_HOST           interface to listen on (default 127.0.0.1 = this computer only)
  VOLSTRO_PORT           port (default 8100)
  VOLSTRO_PASSWORD       require this password to open the app (required unless VOLSTRO_HOST is 127.0.0.1)
  VOLSTRO_ALLOWED_HOSTS  comma-separated host names the site is reached by, e.g. pipeline.volstro.com
"""

import os
import sys

import uvicorn

host = os.environ.get("VOLSTRO_HOST", "127.0.0.1")
if host not in ("127.0.0.1", "localhost") and not os.environ.get("VOLSTRO_PASSWORD"):
    sys.exit("Refusing to listen on a network address without VOLSTRO_PASSWORD set.")
uvicorn.run("pipeline.app:app", host=host, port=int(os.environ.get("VOLSTRO_PORT", "8100")), proxy_headers=True)
