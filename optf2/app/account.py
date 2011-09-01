from openid.consumer import consumer
from openid.store import filestore
import optf2.backend.openid as ooid
import template
import web, os, config

templates = template.template

class openid_consume:
    def GET(self):
        openid_store = filestore.FileOpenIDStore(os.path.join(config.cache_file_dir, "OpenIDStore"))

        dance = consumer.Consumer(ooid.gsession, openid_store)
        openid_realm = web.ctx.homedomain
        openid_return_url = openid_realm + config.virtual_root + "openid"
        try:
            auth = dance.begin("http://steamcommunity.com/openid/")
            openid_auth_url = auth.redirectURL(openid_realm, return_to = openid_return_url)
        except: return templates.error("Can't connect to Steam")

        if web.input().get("openid.return_to"):
            openid_return_url = openid_realm + config.virtual_root + "openid"
            response = dance.complete(web.input(), openid_return_url)
            if response.status != consumer.SUCCESS or not response.identity_url:
                return templates.error("Login Error")
            ooid.gsession["identity_hash"] = ooid.make_hash(response.identity_url) + "," + response.identity_url

            raise web.seeother(config.virtual_root + "user/" + os.path.basename(response.identity_url))
        else:
            raise web.seeother(openid_auth_url)
