import config, web, os
import optf2.backend.items as itemtools
from optf2.frontend import markup as markuptools
import optf2.app as app
import logging, traceback

logging.basicConfig(filename = os.path.join(config.cache_file_dir, config.game_mode + ".log"), level = logging.DEBUG)

urls = (
    config.virtual_root + "user/(.*)", app.backpack.fetch,
    config.virtual_root + "feed/(.+)", app.backpack.feed,
    config.virtual_root + "item/(.+)", app.backpack.item,
    config.virtual_root + "loadout/(.+)", app.backpack.loadout,
    config.virtual_root + "persona/(.+)", app.api.persona,
    config.virtual_root + "comp/(.+)", app.api.search_profile,
    config.virtual_root + "attrib_dump", app.schema_list.attributes,
    config.virtual_root + "schema_dump", app.schema_list.items,
    config.virtual_root + "about", app.static.about,
    config.virtual_root + "openid", app.account.openid_consume,
    config.virtual_root + "(.+)", app.backpack.fetch,
    config.virtual_root, app.index.main
    )

application = web.application(urls, globals())

def lang_hook():
    lang = web.input().get("lang")

    if lang not in config.valid_languages: lang = "en"
    web.ctx.language = lang

def internalerror():
    logging.error(traceback.format_exc())
    return web.internalerror(app.template.template.error("Unknown error, " + config.project_name + " may be down for maintenance"))

application.add_processor(web.loadhook(lang_hook))

session = web.session.Session(application, web.session.DBStore(config.database_obj, "sessions"))

if not web.config.debug: application.internalerror = internalerror
