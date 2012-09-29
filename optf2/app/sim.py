import web
import steam
import template
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_root_url
import api

templates = template.template

class selector:
    def GET(self, user):
        cache = database.cache(mode = "inv")
        baseurl = user.strip('/').split('/')
        if len(baseurl) > 0:
            user = baseurl[-1]

        if not user: raise steam.items.BackpackError("Need an ID")

        try:
            uid = cache.get_profile(user)
            ctx = cache.get_inv_context(uid)

            return templates.sim_selector(uid, ctx)
        except steam.items.Error as E:
            return templates.error("Failed to load backpack ({0})".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Failed to load profile ({0})".format(E))
        except steam.base.HttpError as E:
            return templates.error("Couldn't connect to Steam (HTTP {0})".format(E))
        except database.CacheEmptyError as E:
            return templates.error(E)
