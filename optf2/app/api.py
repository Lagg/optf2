import web
import json
import os
import steam
from HTMLParser import HTMLParser
from optf2.backend import database
from optf2.backend import config

class search_page_parser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        link = attr.get("href")
        aclass = attr.get("class")

        self._tagstack.append((tag, aclass))

        if aclass == "linkTitle" and link and link.startswith(self._community_url):
            # id64 is a misnomer, but is there for compatibility reasons
            self._obj["id64"] = os.path.basename(link)

            if link.startswith(self._community_url + "profiles"): self._obj["id_type"] = "id64"
            else: self._obj["id_type"] = "id"

        img = attr.get("src")
        if tag == "img" and img and img.find("avatars") != -1:
            self._obj["avatarurl"] = img.replace("_medium", "")

    def handle_data(self, data):
        try:
            lasttag, aclass = self._tagstack[-1]
            if aclass and aclass == "linkTitle":
                self._obj["persona"] = data.strip()
        except IndexError:
            pass

    def handle_endtag(self, tag):
        stag, aclass = self._tagstack.pop()
        if aclass and aclass.find("resultItem") != -1:
            self._results.append(self._obj)
            self._obj = {}

    def get_results(self):
        return self._results

    def __init__(self, user):
        self._obj = {}
        self._tagstack = []
        self._community_url = "http://steamcommunity.com/"
        self._results = []
        search_url = self._community_url + "actions/Search?T=Account&K={0}".format(web.urlquote(user))

        HTMLParser.__init__(self)

        req = steam.json_request(search_url, timeout = config.ini.getint("steam", "connect-timeout"),
                                 data_timeout = config.ini.getint("steam", "download-timeout"))

        self.feed(req._download())

def profile_search(user, greedy = False):
    """ If greedy it'll search even if the
    given string is exactly matched against
    an ID or vanity. Exact matches marked with
    'exact' property """
    # TODO: Previous weighted search is ugly and inaccurate, make something better
    resultlist = []
    if not user: return
    baseurl = user.strip('/').split('/')
    if len(baseurl) > 0:
        user = baseurl[-1]

    try:
        prof = database.cache().get_profile(user)
        prof["exact"] = True
        resultlist.append(prof)
        if not greedy:
            return resultlist
    except:
        pass

    try:
        parser = search_page_parser(user)
        resultlist += parser.get_results()
    except:
        pass

    return resultlist

class search_profile:
    """ API interface to built in profile searcher """
    def GET(self, user):
        web.header("Content-Type", "text/javascript")
        return json.dumps(profile_search(user, greedy = True))

class persona:
    """ Used for wiki cap related things """
    def GET(self, uid):
        user = {}
        callback = web.input().get("jsonp")
        cache = database.cache()

        try:
            user = cache.get_profile(uid)
            # JS is bad at numbers
            user["id64"] = str(user["id64"])
        except: pass

        web.header("Content-Type", "text/javascript")
        jsonobj = json.dumps(user)
        if not callback:
            return jsonobj
        else:
            return callback + '(' + jsonobj + ');'
