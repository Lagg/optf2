#!/usr/bin/env python

"""
Copyright (c) 2008-2011, Anthony Garcia <lagg@lavabit.com>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""
import os
import web
import steam
from optf2.backend import config

# Cache file stuff
cache_dir = config.ini.get("resources", "cache-dir")
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

from optf2.frontend import render

# Configuration specific initialization

steam.set_api_key(config.ini.get("steam", "api-key"))

web.config.debug = config.ini.getboolean("cgi", "web-debug-mode")

# Redirect workarounds if enabled
if config.ini.getboolean("cgi", "redirect-workaround"):
    os.environ["SCRIPT_NAME"] = ''
    os.environ["REAL_SCRIPT_NAME"] = ''

# HTTP specific
web.config.session_parameters["timeout"] = config.ini.getint("http", "session-timeout")
web.config.session_parameters["cookie_name"] = config.ini.get("http", "session-cookie-name")

# wsgi (Only used if being hosted by wsgi implementation)
application = render.application.wsgifunc()

if config.ini.getboolean("cgi", "fastcgi"):
    web.wsgi.runwsgi = lambda func, addr=None: web.wsgi.runfcgi(func, addr)

if __name__ == "__main__":
    render.application.run()
