#!/usr/bin/env python

"""
Copyright (c) 2010, Anthony Garcia <lagg@lavabit.com>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""

try:
    import steam.user, steam.tf2, steam, os, json, urllib2
    from time import time
    import cPickle as pickle
    from cStringIO import StringIO
    import web
    from web import form
    from copy import deepcopy
except ImportError as E:
    print(str(E))
    raise SystemExit

# Configuration stuff

# You probably want this to be
# an absolute path if you're not running the built-in server
template_dir = "templates/"

# Most links to other viewer pages will
# be prefixed with this.
virtual_root = "/"

css_url = "/static/style.css"

# The url to prefix URLs
# pointing to static data with
# e.g. class icons
static_prefix = "/static/"

api_key = None

language = "en"

# It would be nice of you not to change this
product_name = "OPTF2"

# Where to get the source code.
source_url = "http://gitorious.org/steamodd/optf2"

# Cache a player's backpack. Reduces the number of API
# requests and makes it a lot faster but might make the
# database big
cache_pack = True

# Refresh cache every x seconds.
cache_pack_refresh_interval = 30

# How many rows to show for the top viewed backpacks table
top_backpack_rows = 10

# End of configuration stuff

urls = (
    virtual_root + "comp/(.+)", "user_completion",
    virtual_root + "user/(.*)", "pack_fetch",
    virtual_root + "feed/(.+)", "pack_feed",
    virtual_root + "item/(.+)", "pack_item",
    virtual_root + "schema_dump", "schema_dump",
    virtual_root + "about", "about",
    virtual_root, "index"
    )

# The 64 bit ID of the Valve group (this is how I check
# if the user is a Valve employee)
valve_group_id = 103582791429521412

qualitydict = {"unique": "The ", "community": "Community ",
               "developer": "Legendary ", "normal": "",
               "selfmade": "My ", "vintage": "Vintage ",
               "rarity4": "Unusual "}

# These should stay explicit
render_globals = {"css_url": css_url,
                  "virtual_root": virtual_root,
                  "static_prefix": static_prefix,
                  "encode_url": web.urlquote,
                  "len": len,
                  "qualitydict": qualitydict,
                  "instance": web.ctx,
                  "product_name": product_name,
                  "source_url": source_url,
                  "wiki_url": "http://wiki.teamfortress.com/wiki/"
                  }

app = web.application(urls, globals())
templates = web.template.render(template_dir, base = "base",
                                globals = render_globals)

steam.set_api_key(api_key)
steam.set_language(language)

db_schema = ["CREATE TABLE IF NOT EXISTS search_count (id64 INTEGER, persona TEXT, count INTEGER, valve BOOLEAN)",
             "CREATE TABLE IF NOT EXISTS backpack_cache (id64 INTEGER, backpack BLOB, last_refresh DATE)"]
db_obj = web.database(dbn = "sqlite", db = os.path.join(steam.get_cache_dir(), "optf2.db"))
for s in db_schema:
    db_obj.query(s)

def make_packfile_path(id64):
    return os.path.join(steam.get_cache_dir(), "{0}.pack".format(id64))

def refresh_pack_cache(user, pack):
    pack.load_pack(user)
    try:
        id64 = db_obj.select("backpack_cache", what = "id64", where = "id64 = $uid64",
                             vars = {"uid64": user.get_id64()})[0]["id64"]
        db_obj.update("backpack_cache", where = "id64 = $uid64", vars = {"uid64": id64},
                      backpack = pickle.dumps(pack.get_pack_object()), last_refresh = int(time()))
    except IndexError:
        db_obj.insert("backpack_cache", id64 = user.get_id64(), last_refresh = int(time()),
                      backpack = pickle.dumps(pack.get_pack_object()))

def load_pack_cached(user, pack, stale = False):
    if cache_pack:
        packfile = make_packfile_path(user.get_id64())
        try:
            packrow = db_obj.select("backpack_cache", what = "backpack, last_refresh", where = "id64 = $uid64",
                                    vars = {"uid64": user.get_id64()})[0]
            if stale or (int(time()) - packrow["last_refresh"]) < cache_pack_refresh_interval:
                pack.load_pack_file(StringIO(str(packrow["backpack"])))
            else:
                refresh_pack_cache(user, pack)
        except IndexError:
            refresh_pack_cache(user, pack)
    else:
        pack.load_pack(user)

def sort_items(items, pack, sortby):
    itemcmp = None
    def defcmp(x, y):
        if x < y:
            return -1
        elif x > y:
            return 1
        elif x == y:
            return 0

    if sortby == "serial":
        def itemcmp(x, y):
            return defcmp(pack.get_item_id(x),
                          pack.get_item_id(y))
    elif sortby == "cell":
        def itemcmp(x, y):
            return defcmp(pack.get_item_position(x),
                          pack.get_item_position(y))
    elif sortby == "level":
        def itemcmp(x, y):
            return defcmp(pack.get_item_level(x),
                          pack.get_item_level(y))
    elif sortby == "name":
        def itemcmp(x, y):
            return defcmp(pack.get_item_quality(x)["str"] + " " + pack.get_item_name(x),
                          pack.get_item_quality(y)["str"] + " " + pack.get_item_name(y))
    elif sortby == "slot":
        def itemcmp(x, y):
            return defcmp(pack.get_item_slot(x), pack.get_item_slot(y))
    elif sortby == "class":
        def itemcmp(x, y):
            cx = pack.get_item_equipable_classes(x)
            cy = pack.get_item_equipable_classes(y)
            lenx = len(cx)
            leny = len(cy)

            if lenx == 1 and leny == 1:
                return defcmp(cx[0], cy[0])
            else:
                return defcmp(lenx, leny)

    if itemcmp:
        items.sort(cmp = itemcmp)

def process_attributes(items, pack):
    """ Filters attributes for the item list,
    optf2-specific keys are prefixed with optf2_ """

    for item in items:
        attrs = pack.get_item_attributes(item)

        for attr in attrs:
            desc = pack.get_attribute_description(attr)
            if desc.find("Attrib_") != -1:
                attrs.remove(attr)
                continue
            if pack.get_attribute_name(attr) == "set item tint RGB":
                raw_rgb = int(pack.get_attribute_value(attr))
                item_color = "rgb({0:d},{1:d},{2:d})".format((raw_rgb >> 16) & 0xFF,
                                                             (raw_rgb >> 8) & 0xFF,
                                                             (raw_rgb) & 0xFF)
                item["optf2_color"] = item_color
                attrs.remove(attr)
                continue
            if pack.get_attribute_name(attr) == "gifter account id":
                attr["description_string"] = "Gift"
                item["optf2_gift_from"] = "7656" + str(int(pack.get_attribute_value(attr) +
                                                           1197960265728))
            attr["description_string"] = attr["description_string"].replace("\n", "<br/>")
        item["optf2_attrs"] = deepcopy(attrs)

        quality_str = pack.get_item_quality(item)["str"]
        pretty_quality_str = pack.get_item_quality(item)["prettystr"]
        prefix = qualitydict.get(quality_str, "")
        custom_name = pack.get_item_custom_name(item)
        item_name = pack.get_item_name(item)

        if custom_name or (not pack.is_item_prefixed(item) and quality_str == "unique"):
            prefix = ""
        if custom_name:
            item_name = custom_name

        item["optf2_cell_name"] = '<div class="{0}_name">{1} {2}</div>'.format(
            quality_str, prefix, item_name)

        if custom_name or (not pack.is_item_prefixed(item) and quality_str == "unique"):
            prefix = ""
        else:
            prefix = pretty_quality_str
        color = item.get("optf2_color")
        paint_job = ""
        if color:
            paint_job = '<span style="color: {0}; font-weight: bold;">Painted</span>'.format(color)
        item["optf2_dedicated_name"] = "{0} {1} {2}".format(paint_job, prefix, item_name)

        if color:
            paint_job = "(Painted)"
        else:
            paint_job = ""
        if prefix:
            prefix = qualitydict.get(quality_str, pretty_quality_str)

        item["optf2_feed_name"] = "{0} {1} {2}".format(prefix, item_name, paint_job)

    return items

class schema_dump:
    """ Dumps everything in the schema in a pretty way """

    def GET(self):
        try:
            pack = steam.tf2.backpack()
            return templates.schema_dump(pack, process_attributes(pack.get_items(from_schema = True), pack))
        except Exception as E:
            return templates.error(E)

class user_completion:
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
            res = urllib2.urlopen(search_url).read().split('<a class="linkTitle" href="')
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

class pack_item:
    def GET(self, iid):
        def item_get(idl):
            if idl[0] == "from_schema":
                item = pack.get_item_by_schema_id(int(idl[1]))
            else:
                item = pack.get_item_by_id(int(idl[1]))
                if not item:
                    refresh_pack_cache(user, pack)
                item = pack.get_item_by_id(int(idl[1]))

            if not item:
                raise Exception("Item not found")
            return item

        try:
            idl = iid.split('/')
            pack = steam.tf2.backpack()
            if idl[0] != "from_schema":
                user = steam.user.profile(idl[0])
                load_pack_cached(user, pack, stale = True)
            else:
                user = None

            try: idl[1] = int(idl[1])
            except: raise Exception("Item ID must be an integer")

            item = process_attributes([item_get(idl)], pack)[0]
        except Exception as E:
            return templates.error(str(E))
        return templates.item(user, item, pack)

class about:
    def GET(self):
        return templates.about()

class pack_fetch:
    def _get_page_for_sid(self, sid):
        try:
            if not sid:
                return templates.error("Need an ID")
            try:
                user = steam.user.profile(os.path.basename(sid))
            except steam.user.ProfileError:
                search = json.loads(user_completion().GET(sid))
                nuser = None
                for result in search:
                    if result["persona"] == sid:
                        nuser = result["id"]
                        break
                for result in search:
                    if result["persona"].lower() == sid.lower():
                        nuser = result["id"]
                        break
                for result in search:
                    if result["persona"].lower().find(sid.lower()) != -1:
                        nuser = result["id"]
                        break
                if nuser:
                    user = steam.user.profile(nuser)
                else:
                    raise steam.user.ProfileError("Bad profile name")

            pack = steam.tf2.backpack()

            isvalve = (user.get_primary_group() == valve_group_id)

            load_pack_cached(user, pack)

            items = pack.get_items()
            sort_items(items, pack, web.input().get("sort", "default"))
            process_attributes(items, pack)

            count = db_obj.select("search_count", what="count", where = "id64 = $uid64", vars = {"uid64": user.get_id64()})
            try:
                newcount = count[0]["count"] + 1
                db_obj.update("search_count", where = "id64 = $uid64", vars = {"uid64": user.get_id64()}, count = newcount,
                              persona = user.get_persona(), valve = isvalve)
            except IndexError:
                db_obj.insert("search_count", valve = isvalve,
                              count = 1, id64 = user.get_id64(), persona = user.get_persona())
        except Exception as E:
            return templates.error(str(E))
        return templates.inventory(user, pack, isvalve, items)

    def GET(self, sid):
        return self._get_page_for_sid(sid)

    def POST(self, s):
        return self._get_page_for_sid(web.input().get("User"))

class pack_feed:
    def GET(self, sid):
        try:
            user = steam.user.profile(sid)
            pack = steam.tf2.backpack()
            load_pack_cached(user, pack)
            items = pack.get_items()
            process_attributes(items, pack)
        except Exception as E:
            return templates.error(str(E))
        web.header("Content-Type", "application/rss+xml")
        return web.template.render(template_dir,
                                   globals = render_globals).inventory_feed(user,
                                                                            pack,
                                                                            items)

class index:
    def GET(self):
        profile_form = form.Form(
            form.Textbox("User"),
            form.Button("View")
            )
        countlist = db_obj.select("search_count", order = "count DESC", limit = top_backpack_rows)
        return templates.index(profile_form(), countlist)
        
if __name__ == "__main__":
    app.run()