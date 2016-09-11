import random
import traceback
import os
import sys

import web
import steam

from optf2 import log
from optf2 import config
from optf2.views import template
from optf2 import api_views

virtual_root = config.ini.get("resources", "virtual-root")
static_prefix = config.ini.get("resources", "static-prefix")
default_cvars = {"vRoot": virtual_root,
                 "staticPrefix": static_prefix,
                 "cellsPerRow": 10}

def lang_hook():
    lang = web.input().get("lang")

    web.ctx.language = lang

def motd_hook():
    motdfile = config.ini.get("motd", "filename")
    if not motdfile or not os.path.exists(motdfile):
        return

    with open(motdfile, "r") as motd:
        motdlines = motd.readlines()
        web.ctx["motd"] = random.choice(motdlines)

def conf_hook():
    web.ctx._cvars = dict(default_cvars)

def internalerror():
    # Compact traceback line
    etype, evalue, etb = sys.exc_info()
    fmt = "{0[0]}:{0[1]} ({0[2]}) -> {0[3]}"
    logstr = " | ".join(map(fmt.format, traceback.extract_tb(etb))) + " - " + etype.__name__ + ': "' + str(evalue) + '"'
    log.main.error(logstr)
    return web.internalerror(template.errors.generic("Something didn't load here and I logged it. Sorry for the inconvenience."))

def notfound():
    return web.notfound(template.errors.generic("The page you were looking for couldn't be found."))

def main():
    """ Main setup function """

    def urlr(exp):
        return virtual_root + exp + "/*"

    # Redirect workarounds if enabled
    if config.ini.getboolean("cgi", "redirect-workaround"):
        os.environ["SCRIPT_NAME"] = ''
        os.environ["REAL_SCRIPT_NAME"] = ''

    web.config.debug = config.ini.getboolean("cgi", "web-debug-mode")
    web.config.session_parameters["timeout"] = config.ini.getint("http", "session-timeout")
    web.config.session_parameters["cookie_name"] = config.ini.get("http", "session-cookie-name")

    if config.ini.getboolean("cgi", "fastcgi"):
        web.wsgi.runwsgi = lambda func, addr=None: web.wsgi.runfcgi(func, addr)

    steam.api.key.set(config.ini.get("steam", "api-key"))

    # Cache file stuff
    cache_dir = config.ini.get("resources", "cache-dir")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    urls = (
        virtual_root + "api", api_views.subapplication,
        urlr("inv/(?:user/)?(.+)"), "optf2.inventory_views.sim_selector",
        urlr(""), "optf2.views.index",
        urlr("about"), "optf2.views.about",
        urlr("(\w+)/items"), "optf2.schema_views.items",
        urlr("(\w+)/attributes/?(\d*)"), "optf2.schema_views.attributes",
        urlr("(\w+)/particles"), "optf2.schema_views.particles",
        urlr("(\w+)/item/(-?\d+)"), "optf2.inventory_views.item",
        urlr("(\w+)/item/(\w+)/(-?\d+)"), "optf2.inventory_views.live_item",
        urlr("(\w+)/loadout/(\w+)/?(\d*)"), "optf2.inventory_views.loadout",
        urlr("(\w+)/feed/(.+)"), "optf2.inventory_views.feed",
        urlr("(\w+)/(?:user/)?(.+)"), "optf2.inventory_views.fetch"
        )

    application = web.application(urls, globals())

    application.notfound = notfound
    if not config.ini.getboolean("cgi", "web-debug-mode"):
        application.internalerror = internalerror

    application.add_processor(web.loadhook(lang_hook))
    application.add_processor(web.loadhook(motd_hook))
    application.add_processor(web.loadhook(conf_hook))

    return application
