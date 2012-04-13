import logging
import traceback
import web
import os

from optf2.backend import config
from optf2 import app

virtual_root = config.ini.get("resources", "virtual-root")
valid_languages = [str(code).strip() for code in config.ini.get("misc", "languages").split(',')]

logging.basicConfig(filename = os.path.join(config.ini.get("resources", "cache-dir"), "op.log"), level = logging.ERROR)

urls = (
    virtual_root + "persona/(.+)", app.api.persona,
    virtual_root + "comp/(.+)", app.api.search_profile,
    virtual_root + "about", app.static.about,
    virtual_root, app.index.game_root
    )

generic_urls = [
    ("items", app.schema_list.items),
    ("attributes", app.schema_list.attributes),
    ("particles", app.schema_list.particles),
    ("item/([0-9]+)", app.backpack.item),
    ("item/(.+)/([0-9]+)", app.backpack.live_item),
    ("api/attributes", app.api.wiki_attributes),
    ("user/(.*)", app.backpack.fetch),
    ("loadout/(.+)", app.backpack.loadout),
    ("feed/(.+)", app.backpack.feed),
    ("*", app.index.game_root),
    ("(.+)", app.backpack.fetch)
    ]

for url in generic_urls:
    urls += (virtual_root + "(" + "|".join([op[0] for op in config.ini.items("modes")]) + ")/" + url[0], url[1])

application = web.application(urls, globals())

def mode_hook():
    web.ctx.current_game = None

def lang_hook():
    lang = web.input().get("lang")

    if lang not in valid_languages: lang = "en"
    web.ctx.language = lang

def motd_hook():
    motdfile = config.ini.get("motd", "filename")
    if not motdfile or not os.path.exists(motdfile): return

    with open(motdfile, "r") as motd:
        web.ctx["motd"] = motd.read()

def internalerror():
    logging.error(web.ctx.fullpath + ": " + traceback.format_exc())
    return web.internalerror(app.template.template.error(config.ini.get("misc", "project-name") + " has hit an unhandled error. Moving that traceback up!"))

def notfound():
    return web.notfound(app.template.template.error("You've hit a 404. Witty quotes coming soon!"))

application.add_processor(web.loadhook(mode_hook))
application.add_processor(web.loadhook(lang_hook))
application.add_processor(web.loadhook(motd_hook))

if not config.ini.getboolean("cgi", "web-debug-mode"): application.internalerror = internalerror
application.notfound = notfound
