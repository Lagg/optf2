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

def urlr(exp):
    return virtual_root + exp + "/*"

urls = (
    urlr("persona/(.+)"), app.api.persona,
    urlr("api/profileSearch/(.+)"), app.api.search_profile,
    urlr("inv/(?:user/)?(.+)"), app.sim.selector,
    urlr("inv"), app.sim.main,
    urlr("about"), app.static.about,
    urlr("(\w+)/items"), app.schema_list.items,
    urlr("(\w+)/attributes"), app.schema_list.attributes,
    urlr("(\w+)/particles"), app.schema_list.particles,
    urlr("(\w+)/item/(-?\d+)"), app.backpack.item,
    urlr("(\w+)/item/(\w+)/(-?\d+)"), app.backpack.live_item,
    urlr("(\w+)/loadout/(.+)"), app.backpack.loadout,
    urlr("(\w+)/feed/(.+)"), app.backpack.feed,
    urlr("(\w+)/(?:user/)?(.+)"), app.backpack.fetch,
    urlr("(\w*)"), app.index.game_root
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
