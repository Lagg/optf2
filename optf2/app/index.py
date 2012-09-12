import web
import json
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_root_url, generate_item_cell, init_theme
import api
import template
import random

def handle_searchbar_input(root):
    user = web.input().get("user")
    if not user: return
    baseurl = user.strip('/').split('/')
    if len(baseurl) > 0: baseurl = baseurl[-1]

    try: prof = database.cache().get_profile(baseurl)
    except: prof = None

    if prof:
        raise web.seeother(generate_root_url("user/" + str(prof["id64"], root)))

    search = json.loads(api.search_profile().GET(user))
    nuser = user
    for result in search:
        if result["persona"] == user:
            nuser = result["id"]
            break
    for result in search:
        if result["persona"].lower() == user.lower():
            nuser = result["id"]
            break
    for result in search:
        if result["persona"].lower().find(user.lower()) != -1:
            nuser = result["id"]
            break

    raise web.seeother(generate_root_url("user/" + nuser, root))

class game_root:
    def GET(self, app = None):
        usestale = True

        # Random mainpages (until dedicated main homepage is done)
        if not app:
            from optf2.frontend import render
            app = random.choice(render.valid_modes)

        handle_searchbar_input(app)

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
