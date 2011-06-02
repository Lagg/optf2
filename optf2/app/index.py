import template, web, config, os
from optf2.backend import database

class main:
    def GET(self):
        user = web.input().get("user")

        if user:
            if user.endswith('/'): user = user[:-1]
            raise web.seeother(config.virtual_root + "user/" + os.path.basename(user))

        return template.template.index(database.get_top_pack_views(limit = config.top_backpack_rows))
