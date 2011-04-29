import template, web, config, os

class main:
    def GET(self):
        user = web.input().get("user")

        if user:
            if user.endswith('/'): user = user[:-1]
            raise web.seeother(config.virtual_root + "user/" + os.path.basename(user))

        countlist = config.database_obj.select("unique_views", order = "count DESC", limit = config.top_backpack_rows)
        return template.template.index(countlist)
