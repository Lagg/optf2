import template, web, config, json
from optf2.backend import database
from optf2.frontend.markup import generate_mode_url
import api

class main:
    def GET(self):
        user = web.input().get("user")

        if not user:
            return template.template.index(database.get_top_pack_views(limit = config.top_backpack_rows))

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

        raise web.seeother(config.virtual_root + "user/" + nuser)

class game_root:
    def GET(self, game):
        web.ctx.current_game = game
        return template.template.game_root()
