import template, web, config, json
from optf2.backend import database
from optf2.frontend.markup import generate_mode_url
import api

def handle_searchbar_input():
    user = web.input().get("user")
    if not user: return
    baseurl = user.strip('/').split('/')
    if len(baseurl) > 0: baseurl = baseurl[-1]

    try: prof = database.load_profile_cached(baseurl)
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
    def GET(self, game = None):
        web.ctx.current_game = game
        handle_searchbar_input()
        return template.template.game_root()
