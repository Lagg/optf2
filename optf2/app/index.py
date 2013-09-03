import web
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_root_url, generate_item_cell, init_theme, virtual_root
import api
import template
import random

cache = database.cache

class index:
    def GET(self, app = None):
        usestale = True

        # Until dedicated main homepage is done
        from optf2.frontend.render import valid_modes
        if not app:
            app = random.choice(valid_modes)

        app = database.app_aliases.get(app, app)
        query = web.input()
        user = query.get("user")

        # TODO: Won't be much use in the big restructuring, for now try to extract app from path
        appfrom = query.get("from", '')[len(virtual_root):].strip('/').split('/')[0]
        if appfrom not in valid_modes:
            appfrom = valid_modes[0]

        profile = api.profile_search(user)
        if profile:
            raise web.seeother(generate_root_url("user/" + str(profile[0]["id64"]), appfrom))

        ckey = "scrender"
        showcase = cache.get(ckey)
        showcase_cell = None
        try:
            if not showcase:
                sitems = database.schema(scope = app).processed_items.values()
                if len(sitems) > 0:
                    showcase = random.choice(sitems)
                    showcase["app"] = app
                    # May want to add an option for showcase expiration to config later
                    cache.set(ckey, showcase, time=60)

            app = showcase.get("app", app)
            showcase_cell = generate_item_cell(app, showcase, user=showcase.get("user"))
        except Exception as E:
            pass

        init_theme(app)
        web.ctx.notopsearch = True

        # Last packs
        packs = database.recent_inventories(scope = app)

        return template.template.index(app, (packs or []), showcase_cell)
