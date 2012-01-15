import config, web, os
import optf2.backend.items as itemtools
from optf2.frontend import markup as markuptools
import optf2.app as app
import logging, traceback

logging.basicConfig(filename = os.path.join(config.cache_file_dir, "op.log"), level = logging.ERROR)

urls = (
    config.virtual_root + "persona/(.+)", app.api.persona,
    config.virtual_root + "comp/(.+)", app.api.search_profile,
    config.virtual_root + "about", app.static.about,
    config.virtual_root, app.index.game_root
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
    urls += (config.virtual_root + "(" + ("|".join(config.game_modes.keys())) + ")/" + url[0], url[1])

application = web.application(urls, globals())

def mode_hook():
    web.ctx.current_game = None

def lang_hook():
    lang = web.input().get("lang")

    if lang not in config.valid_languages: lang = "en"
    web.ctx.language = lang

def internalerror():
    logging.error(web.ctx.fullpath + ": " + traceback.format_exc())
    return web.internalerror(app.template.template.error(config.project_name + " has hit an unhandled error. Moving that traceback up!"))

def notfound():
    return web.notfound(app.template.template.error("You've hit a 404. Witty quotes coming soon!"))

application.add_processor(web.loadhook(mode_hook))
application.add_processor(web.loadhook(lang_hook))

if not web.config.debug: application.internalerror = internalerror
application.notfound = notfound
