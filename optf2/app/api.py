import web
import json
import os
import steam
import re
from HTMLParser import HTMLParser
from optf2.backend import database
from optf2.backend import config
cache = database.cache

# Subapplication and URLs defined after classes
# TODO: Well defined error objects for when this is
# more fleshed out

jsonMimeType = "application/json"

class jsonHTTPError(web.HTTPError):
    """" Replacement for web.* stuff,
    they set content-types to text/html by default.
    Not sure if two headers of those are allowed in the spec. """
    def __init__(self, status, message = None):
        headers = {"Content-Type": jsonMimeType}
        web.HTTPError.__init__(self, status, headers, message or "{}")

class jsonBadRequest(jsonHTTPError):
    """ Replacement for web.BadRequest """
    def __init__(self, message = None):
        status = "400 Bad Request"
        jsonHTTPError.__init__(self, status, message)

class jsonNotFound(jsonHTTPError):
    """ Replacement for web.NotFound """
    def __init__(self, message = None):
        status = "404 Not Found"
        jsonHTTPError.__init__(self, status, message)

class jsonInternalError(jsonHTTPError):
    """ Replacement for web._InternalError
    no stack calls needed here really """
    def __init__(self, message = None):
        status = "500 Internal Server Error"
        jsonHTTPError.__init__(self, status, message)

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
            if self._str != self._obj["id64"].lower() and self._str != str(self._prof.get("id64")):
                self._results.append(self._obj)
            self._obj = {}

    def get_results(self):
        return self._results

    def __init__(self, user, prof = None):
        self._obj = {}
        self._tagstack = []
        self._community_url = "http://steamcommunity.com/"
        self._results = []
        self._prof = prof or {}
        self._str = user.lower()
        search_url = self._community_url + "actions/Search?T=Account&K={0}".format(web.urlquote(user))

        HTMLParser.__init__(self)

        req = steam.api.http_downloader(search_url, timeout = config.ini.getint("steam", "connect-timeout"))

        self.feed(req.download())

class group_member_page_parser(HTMLParser):
    _member_count_exp = re.compile("[\d,]+ - [\d,]+ of ([\d,]+) Members")

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        aclass = attr.get("class", '').strip().split(' ')

        self._tagstack.append((tag, aclass))

        if tag == "img":
            for tag, tclass in reversed(self._tagstack):
                src = attr.get("src", '')
                if "playerAvatar" in tclass:
                    self._obj["avatar"] = src
                    # May not be reliable, but there's no
                    # other source besides friendSmallText,
                    # which seems even less reliable
                    if len(tclass) > 1:
                        self._obj["status"] = tclass[1]
                    break
                elif not self._logo and "grouppage_logo" in tclass:
                    self._logo = src
                    break
        elif tag == "a" and "linkFriend" in aclass:
            self._obj["profile"] = attr.get("href")

    def handle_data(self, data):
        mcount = self._member_count_exp.search(data)

        try:
            if mcount: self._member_count = int(mcount.group(1).replace(',', ''))
        except TypeError:
            pass

        try:
            stag, sclass = self._tagstack[-1]
        except IndexError:
            return

        data = data.strip()
        if stag == "a" and "linkFriend" in sclass:
            self._obj["persona"] = data
        elif "grouppage_header_name" in sclass and not self._name:
            self._name = data
        elif "grouppage_header_abbrev" in sclass and not self._abbrev:
            self._abbrev = data

    def handle_endtag(self, tag):
        stag, sclass = self._tagstack.pop()

        # For some reason the HTMLParser thinks member blocks aren't being closed
        if "avatar" in self._obj and "profile" in self._obj and "persona" in self._obj:
            self._members_short.append(self._obj)
            self._obj = {}

    def get_member_list_short(self):
        return self._members_short

    def get_member_count(self):
        return self._member_count

    def get_logo(self, size = ''):
        if size: size = '_' + size

        return self._logo.replace("_full", size)

    def get_name(self):
        return self._name

    def get_abbreviation(self):
        return self._abbrev

    def __init__(self, group):
        self._community_url = "http://steamcommunity.com/"
        self._tagstack = []
        self._member_count = 0
        self._members_short = []
        self._logo = ''
        self._name = ''
        self._abbrev = ''
        self._obj = {}

        url = "{0}groups/{1}/members".format(self._community_url, group)

        HTMLParser.__init__(self)

        req = steam.api.http_downloader(url, timeout = config.ini.getint("steam", "connect-timeout"))

        data = req.download()
        self.feed(data)

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

    prof = None
    try:
        prof = database.user(user).load()
        prof["exact"] = True
        prof["id64"] = str(prof["id64"])
        resultlist.append(prof)
        if not greedy:
            return resultlist
    except:
        pass

    try:
        parser = search_page_parser(user, prof)
        resultlist += parser.get_results()
    except:
        pass

    return resultlist

class search_profile:
    """ API interface to built in profile searcher """
    def GET(self):
        user = web.input().get("user")

        if user:
            web.header("Content-Type", jsonMimeType)
            return json.dumps(profile_search(user, greedy = True))
        else:
            raise jsonBadRequest()

class persona:
    """ Used for wiki cap related things """
    def GET(self, uid):
        user = {}
        callback = web.input().get("jsonp")

        try:
            user = database.user(uid).load()
            # JS is bad at numbers
            user["id64"] = str(user["id64"])
        except: pass

        web.header("Content-Type", jsonMimeType)

        jsonobj = json.dumps(user)
        if not callback:
            return jsonobj
        else:
            return callback + '(' + jsonobj + ');'

class groupStats:
    def GET(self, group):
        obj = {}
        try:
            memkey = "groupstats-" + str(group)
            obj = cache.get(memkey)

            if not obj:
                parser = group_member_page_parser(group)
                obj = {}
                obj["memberCount"] = parser.get_member_count()
                obj["memberListShort"] = parser.get_member_list_short()
                obj["logo"] = parser.get_logo()
                obj["name"] = parser.get_name()
                obj["abbreviation"] = parser.get_abbreviation()

                cache.set(memkey, obj, time = config.ini.getint("cache", "group-stats-expiry"))
        except:
            pass

        web.header("Content-Type", jsonMimeType)
        return json.dumps(obj)

urls = (
    "/profileSearch", search_profile,
    "/persona/(.+)", persona,
    "/groupStats/(\w+)", groupStats
    )

subapplication = web.application(urls)
subapplication.internalerror = jsonInternalError
subapplication.notfound = jsonNotFound
