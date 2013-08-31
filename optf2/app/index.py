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

        return template.template.index(app, (packs or []), showcase)
