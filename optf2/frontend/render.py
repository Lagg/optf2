import traceback
import web
import os
import random
import sys

from optf2.backend import log
from optf2.backend import config
from optf2 import app

virtual_root = config.ini.get("resources", "virtual-root")
valid_modes = [op[0] for op in config.ini.items("modes")]

urls = (
    virtual_root + "persona/(.+)", app.api.persona,
    virtual_root + "about", app.static.about,
    virtual_root, app.index.game_root
    )

generic_urls = [
    ("items", app.schema_list.items),
    ("attributes", app.schema_list.attributes),
    ("particles", app.schema_list.particles),
    ("item/(-?[0-9]+)", app.backpack.item),
    ("item/(.+)/(-?[0-9]+)", app.backpack.live_item),
    ("api/attributes", app.api.wiki_attributes),
    ("user/(.*)", app.backpack.fetch),
    ("loadout/(.+)", app.backpack.loadout),
    ("feed/(.+)", app.backpack.feed),
    ("(.+)", app.backpack.fetch),
    ("*", app.index.game_root)
    ]

for url in generic_urls:
    urls += (virtual_root + "(?:" + "|".join(valid_modes) + ")/" + url[0], url[1])

application = web.application(urls, globals())

def mode_hook():
    """ If there's a better way to do this I'm all ears """
    path = filter(None, web.ctx.path.split('/'))

    try:
        gamecandidate = path[0]
        if gamecandidate in valid_modes:
            web.ctx.current_game = gamecandidate
            return
    except IndexError: pass

    web.ctx.current_game = None

def lang_hook():
    lang = web.input().get("lang")

    web.ctx.language = lang

def motd_hook():
    motdfile = config.ini.get("motd", "filename")
    if not motdfile or not os.path.exists(motdfile): return

    with open(motdfile, "r") as motd:
        motdlines = motd.readlines()
        web.ctx["motd"] = random.choice(motdlines)

def internalerror():
    # Compact traceback line
    etype, evalue, etb = sys.exc_info()
    fmt = "{0[0]}:{0[1]} ({0[2]}) -> {0[3]}"
    logstr = " | ".join(map(fmt.format, traceback.extract_tb(etb))) + " - " + etype.__name__ + ': "' + str(evalue) + '"'
    log.main.error(logstr)
    return web.internalerror(app.template.template.error("A problem related to a '" + etype.__name__ + "' error has been logged. Nudge Lagg to fix it."))

def notfound():
    return web.notfound(app.template.template.error("I couldn't find the page you were looking for but it sure was fun trying! (404)"))

application.add_processor(web.loadhook(mode_hook))
application.add_processor(web.loadhook(lang_hook))
application.add_processor(web.loadhook(motd_hook))

if not config.ini.getboolean("cgi", "web-debug-mode"): application.internalerror = internalerror
application.notfound = notfound
