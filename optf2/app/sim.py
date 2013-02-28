import web
import steam
import template
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_root_url
import api

templates = template.template
error_page = templates.errors

class selector:
    def GET(self, user):
        cache = database.cache(mode = "inv")
        baseurl = user.strip('/').split('/')
        if len(baseurl) > 0:
            user = baseurl[-1]

        if not user: raise steam.items.BackpackError("Need an ID")

        try:
            prof = database.user(cache, user).load()
            ctx = database.sim_context(cache, prof).load()

            return templates.sim_selector(prof, ctx)
        except steam.items.Error as E:
            raise web.NotFound(error_page.generic("Failed to load backpack ({0})".format(E)))
        except steam.user.ProfileError as E:
            raise web.NotFound(error_page.generic("Failed to load profile ({0})".format(E)))
        except steam.base.HttpError as E:
            raise web.NotFound(error_page.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except database.CacheEmptyError as E:
            raise web.NotFound(error_page.generic(E))
