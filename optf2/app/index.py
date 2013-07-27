import web
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_root_url, generate_item_cell, init_theme
import api
import template
import random

cache = database.cache

class game_root:
    def GET(self, app = None):
        usestale = True

        # Until dedicated main homepage is done
        if not app:
            from optf2.frontend import render
            app = render.valid_modes[0]

        app = database.app_aliases.get(app, app)
        user = web.input().get("user")
        profile = api.profile_search(user)
        if profile:
            dest = web.input().get("formdest", app)
            raise web.seeother(generate_root_url("user/" + profile[0]["id64"], dest))
        else:
            # For people who wish to have their browser go to the right app user search
            # Probably temporary until I write new main home page
            web.ctx._cvars["formDest"] = app

        ckey = str("scrender-" + app + "-" + database.verify_lang()).encode("ascii")
        showcase = cache.get(ckey)
        if not showcase:
            try:
                sitems = database.schema(scope = app).processed_items.values()
                if len(sitems) > 0:
                    item = random.choice(sitems)
                    showcase = generate_item_cell(app, item)
                    # May want to add an option for showcase expiration to config later
                    cache.set(ckey, showcase, time = 600)
            except:
                pass

        init_theme(app)
        web.ctx.notopsearch = True

        # Last packs
        packs = database.recent_inventories(scope = app)

        return template.template.game_root(app, (packs or []), showcase)
