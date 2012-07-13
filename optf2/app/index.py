import web
import json
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_mode_url, generate_cell
import api
import template
import random

def handle_searchbar_input():
    user = web.input().get("user")
    if not user: return
    baseurl = user.strip('/').split('/')
    if len(baseurl) > 0: baseurl = baseurl[-1]

    try: prof = database.cache().get_profile(baseurl)
    except: prof = None

    if prof:
        raise web.seeother(generate_mode_url("user/" + str(prof.get_id64())))

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

    raise web.seeother(generate_mode_url("user/" + nuser))

class game_root:
    def GET(self):
        mod = web.ctx.current_game
        usestale = True

        handle_searchbar_input()

        # Random items
        if not mod:
            from optf2.frontend import render
            mod = random.choice(render.valid_modes)

        cache = database.cache(modid = mod)

        ckey = str("scrender-" + mod + "-" + cache.get_language()).encode("ascii")
        showcase = cache.get(ckey)
        if not showcase:
            items = cache.get_schema(stale = usestale)
            if items:
                items = list(items)
                if len(items) > 0:
                    item = itemtools.process_attributes([random.choice(items)])[0]
                    showcase = generate_cell(item, mode = mod)
                    # May want to add an option for showcase expiration to config later
                    cache.set(ckey, showcase, time = 300)

        # Last packs
        packs = cache.get_recent_pack_list()

        return template.template.game_root(mod.upper(), (packs or []), showcase)
