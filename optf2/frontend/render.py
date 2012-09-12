import traceback
import web
import os
import random
import sys

from optf2.backend import log
from optf2.backend import config
from optf2 import app

virtual_root = config.ini.get("resources", "virtual-root")
static_prefix = config.ini.get("resources", "static-prefix")
valid_modes = [op[0] for op in config.ini.items("modes")]
default_cvars = {"vRoot": virtual_root,
                 "staticPrefix": static_prefix,
                 "cellsPerRow": 10}

urls = (
    virtual_root + "persona/(.+)", app.api.persona,
    virtual_root + "about", app.static.about,
    virtual_root + "(.+)/items", app.schema_list.items,
    virtual_root + "(.+)/attributes", app.schema_list.attributes,
    virtual_root + "(.+)/particles", app.schema_list.particles,
    virtual_root + "(.+)/item/(-?[0-9]+)", app.backpack.item,
    virtual_root + "(.+)/item/(.+)/(-?[0-9]+)", app.backpack.live_item,
    virtual_root + "(.+)/loadout/(.+)", app.backpack.loadout,
    virtual_root + "(.+)/feed/(.+)", app.backpack.feed,
    virtual_root + "(.+)/user/(.*)", app.backpack.fetch,
    virtual_root + "(.+)/(.+)", app.backpack.fetch,
    virtual_root + "(.*)", app.index.game_root
    )

application = web.application(urls, globals())

def lang_hook():
    lang = web.input().get("lang")

    web.ctx.language = lang

def motd_hook():
    motdfile = config.ini.get("motd", "filename")
    if not motdfile or not os.path.exists(motdfile): return

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
    return web.internalerror(app.template.template.error("A problem related to a '" + etype.__name__ + "' error has been logged. Nudge Lagg to fix it."))

def notfound():
    return web.notfound(app.template.template.error("I couldn't find the page you were looking for but it sure was fun trying! (404)"))

application.add_processor(web.loadhook(lang_hook))
application.add_processor(web.loadhook(motd_hook))
application.add_processor(web.loadhook(conf_hook))

if not config.ini.getboolean("cgi", "web-debug-mode"): application.internalerror = internalerror
application.notfound = notfound
