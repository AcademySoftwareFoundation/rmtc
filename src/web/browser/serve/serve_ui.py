# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os
from werkzeug.middleware.shared_data import SharedDataMiddleware

DIST = os.path.join(os.environ.get("RMTC_WEB_ROOT"), "dist")

with open(os.path.join(DIST, "index.html"), "rb") as f:
    INDEX = f.read()

def single_page_fallback(environ, start_response):
    """
    Provide index.html for any path that isn't a real file.
    This allows the client-side router to handle routing.
    """
    start_response("200 OK", [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Cache-Control", "no-cache"),
    ])
    return [INDEX]

app = SharedDataMiddleware(
    single_page_fallback,
    {"/": DIST},            # serve files from dist/ at the root url
    cache_timeout=60 * 60   # browsers may cache files from dist/ for 1 hour
)
