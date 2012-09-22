import web
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_root_url, generate_item_cell, init_theme
import api
import template
import random

class game_root:
    def GET(self, app = None):
        usestale = True

        # Until dedicated main homepage is done
        if not app:
            from optf2.frontend import render
            app = render.valid_modes[0]

        user = web.input().get("user")
        profile = api.profile_search(user)
        if profile:
            dest = web.input().get("formdest", app)
            raise web.seeother(generate_root_url("user/" + profile[0]["id64"], dest))
        else:
            # For people who wish to have their browser go to the right app user search
            # Probably temporary until I write new main home page
            web.ctx._cvars["formDest"] = app

        cache = database.cache(mode = app)

        ckey = str("scrender-" + app + "-" + cache.get_language()).encode("ascii")
        showcase = cache.get(ckey)
        if not showcase:
            try:
                schema = cache.get_schema(stale = usestale)
                items = list(schema)
                if len(items) > 0:
                    item = cache._build_processed_item(random.choice(items))
                    showcase = generate_item_cell(app, item)
                    # May want to add an option for showcase expiration to config later
                    cache.set(ckey, showcase, time = 600)
            except:
                pass

        init_theme(app)

        # Last packs
        packs = cache.get_recent_pack_list()

        return template.template.game_root(app, (packs or []), showcase)
