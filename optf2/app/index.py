import template, web, config, os, json
from optf2.backend import database
import api

class main:
    def GET(self):
        user = web.input().get("user")

        if not user:
            return template.template.index(database.get_top_pack_views(limit = config.top_backpack_rows))

        basei = user.find('/')
        baseurl = user

        if basei > -1: baseurl = os.path.basename(user[:basei])

        try: prof = database.load_profile_cached(baseurl)
        except: prof = None

        if prof:
            raise web.seeother(config.virtual_root + "user/" + str(prof.get_id64()))

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
