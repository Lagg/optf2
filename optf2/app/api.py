import web
import json
import os
import steam
from HTMLParser import HTMLParser
from optf2.backend import database
from optf2.backend import config

class search_page_parser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        link = None
        aclass = None
        src = None
        self._lasttag = tag

        for attr in attrs:
            if attr[0] == "href": link = attr[1]
            if attr[0] == "class": aclass = attr[1]
            if attr[0] == "src": src = attr[1]

        if aclass == "linkTitle" and link and link.startswith(self._community_url):
            self._obj["id"] = os.path.basename(link)

            if link.startswith(self._community_url + "profiles"): self._obj["id_type"] = "id64"
            else: self._obj["id_type"] = "id"

        if tag == "img":
            self._lastimg = src

    def handle_data(self, data):
        if self._lasttag == "a" and "id" in self._obj:
            self._obj["persona"] = data.strip()

    def handle_endtag(self, tag):
        if self._obj:
            self._obj["avatar"] = self._lastimg.replace("_medium", "")
            self._results.append(self._obj)
            self._obj = {}

    def get_results(self):
        return self._results

    def __init__(self, user):
        self._obj = {}
        self._lasttag = None
        self._lastimg = None
        self._community_url = "http://steamcommunity.com/"
        self._results = []
        search_url = self._community_url + "actions/Search?T=Account&K={0}".format(web.urlquote(user))

        HTMLParser.__init__(self)

        req = steam.json_request(search_url, timeout = config.ini.getint("steam", "connect-timeout"),
                                 data_timeout = config.ini.getint("steam", "download-timeout"))

        self.feed(req._download())

class search_profile:
    """ Searches for an account matching the username given in the query
    and returns a JSON object
    Yes it's dirty, yes it'll probably die if Valve changes the layout.
    Yes it's Valve's fault for not providing an equivalent API call.
    Yes I can't use minidom because I would have to replace unicode chars
    because of Valve's lazy encoding.
    Yes I'm designing it to be reusable by other people and myself. """

    def GET(self, user):
        try:
            parser = search_page_parser(user)
            userlist = parser.get_results()
            ulen = len(userlist)
            umax = ulen - 1
            ul = user.lower()

            for i in range(umax):
                elem = userlist[i]
                pl = elem["persona"].lower()
                uid = elem["id"].lower()

                if pl == ul:
                    userlist.insert(0, userlist.pop(i))
                elif uid == ul:
                    userlist.insert(min(1, umax), userlist.pop(i))
                elif ul.startswith(pl):
                    userlist.insert(min(2, umax), userlist.pop(i))
                elif ul.startswith(uid):
                    userlist.insert(min(3, umax), userlist.pop(i))

            return json.dumps(userlist)
        except:
            return "[]"

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
        lang = "en" # TODO: Rewrite all of this

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
