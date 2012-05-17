import web
import json
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_mode_url
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

        items = cache.get_schema(stale = usestale)

        # Last packs
        packs = cache.get_recent_pack_list()

        randitem = None
        itemlist = list(items)
        if itemlist:
            randitem = itemtools.process_attributes([random.choice(itemlist)], cacheobj = cache, stale = usestale)[0]

        return template.template.game_root(randitem, mod.upper(), (packs or []))
