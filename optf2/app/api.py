import web
import urllib2
import json
import os
import steam
from optf2.backend import database
from optf2.backend import config

class search_profile:
    """ Searches for an account matching the username given in the query
    and returns a JSON object
    Yes it's dirty, yes it'll probably die if Valve changes the layout.
    Yes it's Valve's fault for not providing an equivalent API call.
    Yes I can't use minidom because I would have to replace unicode chars
    because of Valve's lazy encoding.
    Yes I'm designing it to be reusable by other people and myself. """

    _community_url = "http://steamcommunity.com/"
    def GET(self, user):
        search_url = self._community_url + "actions/Search?T=Account&K={0}".format(web.urlquote(user))

        try:
            res = urllib2.urlopen(search_url, timeout = config.ini.getint("steam", "fetch-timeout")).read().split('<a class="linkTitle" href="')
            userlist = []

            for user in res:
                if user.startswith(self._community_url):
                    userobj = {
                        "persona": user[user.find(">") + 1:user.find("<")],
                        "id": os.path.basename(user[:user.find('"')])
                        }
                    if user.startswith(self._community_url + "profiles"):
                        userobj["id_type"] = "id64"
                    else:
                        userobj["id_type"] = "id"
                    userlist.append(userobj)
            return json.dumps(userlist)
        except:
            return "{}"

class persona:
    def GET(self, id):
        theobject = {"persona": "", "realname": ""}
        callback = web.input().get("jsonp")

        try:
            user = steam.user.profile(id)
            persona = user.get_persona()
            realname = user.get_real_name()
            theobject["persona"] = persona
            theobject["realname"] = realname
            theobject["id64"] = str(user.get_id64())
            theobject["avatarurl"] = user.get_avatar_url(user.AVATAR_SMALL)
        except: pass

        web.header("Content-Type", "text/javascript")
        if not callback:
            return json.dumps(theobject)
        else:
            return callback + '(' + json.dumps(theobject) + ');'


class wiki_attributes:
    def GET(self):
        attrs = {}
        sattrs = None

        for lang in [str(l).strip() for l in config.ini.get("misc", "languages").split(',')]:
            cache = database.cache(language = lang)
            schema = cache.get_schema()
            sattrs = schema.get_attributes()
            for attr in sattrs:
                aid = attr.get_id()
                if aid not in attrs:
                    attrs[aid] = {}
                desc = attr.get_description()
                if desc:
                    attrs[aid][lang] = desc.replace('\n', "<br/>").replace("%s1", "n")

        web.header("Content-Type", "text/plain; charset=UTF-8")
        output = "{{List of item attributes/Header}}\n"

        for attr in sattrs:
            descstring = ""
            notestring = ""
            attrdict = attrs[attr.get_id()]

            if attrdict: descstring = "{{{{lang|{0}}}}}"
            if not attrdict or attrdict.get("en", "").find("Attrib_") != -1: notestring = "Hidden or unused"

            midstring = []
            for k, v in attrdict.iteritems():
                midstring.append(k + "=" + v.encode("utf-8"))

            descstring = descstring.format("|".join(midstring))

            output += "|-\n{{{{Item Attribute|id={0}|name={1}|description={2}|value-type={3}|class={4}|effect-type={5}|notes={6}}}}}\n".format(
                attr.get_id(), attr.get_name(), descstring, attr.get_value_type() or "", attr.get_class(), attr.get_type(), notestring)

        output += "|}"
        return output
