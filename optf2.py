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
    import logging, traceback
    from openid.consumer import consumer
    from openid.store import sqlstore
    import sqlite3
    import hmac, hashlib
    import steam, os, json, urllib2
    import socket
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

# It would be nice of you not to change these
project_name = "OPTF2"
project_homepage = "http://projects.optf2.com/projects/optf2"

# Cache a player's backpack. Reduces the number of API
# requests and makes it a lot faster but might make the
# database big
cache_pack = True

# Refresh cache every x seconds.
cache_pack_refresh_interval = 30

# How many rows to show for the top viewed backpacks table
top_backpack_rows = 10

# Turn on debugging (prints a backtrace and other info
# instead of returning an internal server error)
web.config.debug = False

# Enables fastcgi support with flup, be sure to have it
# installed.
enable_fastcgi = False

# These stop the script name from showing up
# in URLs after a redirect. Remove them
# if they cause problems.
os.environ["SCRIPT_NAME"] = ''
os.environ["REAL_SCRIPT_NAME"] = ''

# The link to the news page/changelog
# set this to None if you don't want
# this shown. (Not recommended)
news_url = "http://agg.optf2.com/log/?cat=5"

# The max size of the backpack. Used
# for the padded cell sort
backpack_padded_size = 200

# The cache directory, this will
# have sensitive data in it that
# shouldn't be publicly accessible

cache_file_dir = "/tmp/steamodd"

# End of configuration stuff

socket.setdefaulttimeout(5)

urls = (
    virtual_root + "comp/(.+)", "user_completion",
    virtual_root + "user/(.*)", "pack_fetch",
    virtual_root + "feed/(.+)", "pack_feed",
    virtual_root + "item/(.+)", "pack_item",
    virtual_root + "persona/(.+)", "persona",
    virtual_root + "attrib_dump", "attrib_dump",
    virtual_root + "schema_dump", "schema_dump",
    virtual_root + "about", "about",
    virtual_root + "openid", "openid_consume",
    virtual_root + "(.+)", "pack_fetch",
    virtual_root, "index"
    )

# The 64 bit ID of the Valve group (this is how I check
# if the user is a Valve employee)
valve_group_id = 103582791429521412

qualitydict = {"unique": "The",
               "normal": ""}

# I don't like this either but Valve didn't expose them
# through the API
particledict = {0: "Invalid Particle",
                1: "Particle 1",
                2: "Flying Bits",
                3: "Nemesis Burst",
                4: "Community Sparkle",
                5: "Holy Glow",
                6: "Green Confetti",
                7: "Purple Confetti",
                8: "Haunted Ghosts",
                9: "Green Energy",
                10: "Purple Energy",
                11: "Circling TF Logo",
                12: "Massed Flies",
                13: "Burning Flames",
                14: "Scorching Flames",
                15: "Searing Plasma",
                16: "Vivid Plasma",
                17: "Sunbeams",
                18: "Circling Peace Sign",
                19: "Circling Heart"}

# These should stay explicit
render_globals = {"css_url": css_url,
                  "virtual_root": virtual_root,
                  "static_prefix": static_prefix,
                  "encode_url": web.urlquote,
                  "len": len,
                  "particledict": particledict,
                  "instance": web.ctx,
                  "project_name": project_name,
                  "project_homepage": project_homepage,
                  "wiki_url": "http://wiki.teamfortress.com/wiki/",
                  "news_url": news_url,
                  "qurl": web.http.changequery
                  }

web.config.session_parameters["timeout"] = 86400
web.config.session_parameters["cookie_name"] = "optf2_session_id"

app = web.application(urls, globals())
templates = web.template.render(template_dir, base = "base",
                                globals = render_globals)

steam.set_api_key(api_key)
steam.set_language(language)
steam.set_cache_dir(cache_file_dir)

logging.basicConfig(filename = os.path.join(steam.get_cache_dir(), "optf2.log"), level = logging.DEBUG)

db_path = os.path.join(steam.get_cache_dir(), "optf2.db")
db_obj = None

if not os.path.exists(db_path):
    db_schema = ["CREATE TABLE IF NOT EXISTS search_count (id64 INTEGER, ip TEXT, count INTEGER DEFAULT 1)",
                 "CREATE TABLE IF NOT EXISTS profile_cache (id64 INTEGER PRIMARY KEY, profile BLOB, timestamp DATE)",
                 "CREATE TABLE IF NOT EXISTS unique_views (id64 INTEGER PRIMARY KEY, count INTEGER DEFAULT 1, persona TEXT, valve BOOLEAN)",
                 "CREATE TABLE IF NOT EXISTS items (id64 INTEGER PRIMARY KEY, owner INTEGER, sid INTEGER, level INTEGER, untradeable BOOLEAN, token INTEGER, quality INTEGER, custom_name TEXT, custom_desc TEXT, attributes BLOB, quantity INTEGER DEFAULT 1)",
                 "CREATE TABLE IF NOT EXISTS backpacks (id64 INTEGER, backpack BLOB, timestamp INTEGER)",
                 "CREATE TABLE IF NOT EXISTS sessions (session_id CHAR(128) UNIQUE NOT NULL, atime timestamp NOT NULL default current_timestamp, data TEXT)"]
    db_obj = web.database(dbn = "sqlite", db = db_path)
    for s in db_schema:
        db_obj.query(s)
    sqlstore.SQLiteStore(sqlite3.connect(db_path)).createTables()
else:
    db_obj = web.database(dbn = "sqlite", db = db_path)

session = web.session.Session(app, web.session.DBStore(db_obj, "sessions"))

openid_secret = os.path.join(steam.get_cache_dir(), "oid_super_secret")
if not os.path.exists(openid_secret):
    secretfile = file(openid_secret, "wb+")
    secretfile.write(os.urandom(32))
    secretfile.close()
openid_secret = file(openid_secret, "rb").read()

def make_openid_hash(url):
    return hmac.new(openid_secret, url, hashlib.sha1).hexdigest()

def check_openid_hash(thehash):
    strs = thehash.split(',')
    if len(strs) == 2 and strs[0] == make_openid_hash(strs[1]):
        return True
    session.kill()
    return False

def openid_get_id():
    thehash = session.get("identity_hash")
    if thehash and check_openid_hash(thehash):
        hashurl = thehash.split(',')[1]
        if hashurl.endswith('/'): hashurl = hashurl[:-1]
        return load_profile_cached(os.path.basename(hashurl))
    return None
render_globals["get_openid"] = openid_get_id

pack = steam.backpack()

def cache_not_stale(row):
    if row and "timestamp" in row:
        return (int(time()) - row["timestamp"]) < cache_pack_refresh_interval
    else:
        return False

def refresh_profile_cache(sid):
    user = steam.profile(sid)
    summary = user.get_summary_object()

    try:
        db_obj.insert("profile_cache", id64 = user.get_id64(),
                      timestamp = int(time()),
                      profile = buffer(pickle.dumps(summary)))
    except:
        db_obj.update("profile_cache", id64 = user.get_id64(),
                      timestamp = int(time()),
                      profile = buffer(pickle.dumps(summary)),
                      where = "id64 = $id64", vars = {"id64": user.get_id64()})

    return user

def load_profile_cached(sid, stale = False):
    user = steam.profile()
    if not sid.isdigit():
        sid = user.get_id64_from_sid(sid.encode("ascii", "replace"))
        if not sid:
            return refresh_profile_cache(sid)

    if cache_pack:
        try:
            prow = db_obj.select("profile_cache", what = "profile, timestamp",
                                 where = "id64 = $id64", vars = {"id64": int(sid)})[0]
            pfile = StringIO(str(prow["profile"]))

            if stale or cache_not_stale(prow):
                user.load_summary_file(pfile)
            else:
                try:
                    return refresh_profile_cache(sid)
                except:
                    user.load_summary_file(pfile)
                    return user
            return user
        except IndexError:
            return refresh_profile_cache(sid)
    else:
        return refresh_profile_cache(sid)

def db_pack_is_new(lastpack, newpack):
    return (len(lastpack) <= 0 or
            sorted(pickle.loads(str(lastpack[0]["backpack"]))) != sorted(newpack))

def refresh_pack_cache(user):
    pack.load_pack(user)
    ts = int(time())

    with db_obj.transaction():
        backpack_items = []
        for item in pack.get_items():
            backpack_items.append(pack.get_item_id(item))
            db_obj.query("INSERT OR IGNORE INTO items (id64) VALUES ($id64)", vars = {"id64": pack.get_item_id(item)})
            db_obj.update("items", where = "id64 = $id64", vars = {"id64": pack.get_item_id(item)},
                          owner = user.get_id64(),
                          sid = pack.get_item_schema_id(item),
                          level = pack.get_item_level(item),
                          untradeable = pack.is_item_untradeable(item),
                          token = pack.get_item_inventory_token(item),
                          quality = pack.get_item_quality(item)["id"],
                          custom_name = pack.get_item_custom_name(item),
                          custom_desc = pack.get_item_custom_description(item),
                          attributes = buffer(pickle.dumps(pack.get_item_attributes(item))),
                          quantity = pack.get_item_quantity(item))

        lastpack = list(db_obj.select("backpacks", what = "backpack",
                                      where="id64 = $id64",
                                      vars = {"id64": user.get_id64()},
                                      order = "timestamp DESC", limit = 1))
        if db_pack_is_new(lastpack, backpack_items):
            db_obj.insert("backpacks", id64 = user.get_id64(),
                          backpack = buffer(pickle.dumps(backpack_items)),
                          timestamp = ts)
        elif len(lastpack) > 0:
            db_obj.update("backpacks", where = "id64 = $id64 AND timestamp = (SELECT MAX(timestamp) FROM backpacks where id64 = $id64)",
                          timestamp = ts, vars = {"id64": user.get_id64()})
        return True
    return False

def db_fetch_pack_for_user(user, date = None):
    """ Returns None if a backpack couldn't be found """
    packrow = db_obj.select("backpacks",
                            where = "id64 = $id64",
                            order = "timestamp DESC",
                            vars = {"id64": user.get_id64()})
    for pack in packrow:
        if not date:
            return pack
        if packrow["timestamp"] == date:
            return pack

def db_to_itemobj(dbitem):
    theitem = {"id": dbitem["id64"],
               "owner": dbitem["owner"],
               "defindex": dbitem["sid"],
               "level": dbitem["level"],
               "quantity": dbitem["quantity"],
               "flag_cannot_trade": dbitem["untradeable"],
               "inventory": dbitem["token"],
               "quality": dbitem["quality"],
               "custom_name": dbitem["custom_name"],
               "custom_desc": dbitem["custom_desc"],
               "attributes": {"attribute": pickle.loads(str(dbitem["attributes"]))}}
    return theitem

def db_fetch_item_for_id(iid):
    try:
        itemrow = list(db_obj.select("items",
                                     where = "id64 = $id64",
                                     vars = {"id64": iid}))[0]
        return db_to_itemobj(itemrow)
    except IndexError:
        return None

def load_pack_cached(user, stale = False):
    packresult = []
    thepack = db_fetch_pack_for_user(user)
    if not stale:
        if not cache_not_stale(thepack):
            try:
                refresh_pack_cache(user)
            except urllib2.URLError:
                pass
            thepack = db_fetch_pack_for_user(user)
    if thepack:
        with db_obj.transaction():
            for item in pickle.loads(str(thepack["backpack"])):
                dbitem = db_obj.select("items", where = "id64 = $id64",
                                       vars =  {"id64": item})[0]
                theitem = db_to_itemobj(dbitem)
                packresult.append(deepcopy(theitem))
        return packresult

def get_invalid_pos_items(items):
    poslist = []
    invalid_items = []
    for item in items:
        if not item: continue
        pos = pack.get_item_position(item)
        if pos != -1 and pos not in poslist:
            poslist.append(pack.get_item_position(item))
        else:
            for item in items:
                if item and item not in invalid_items and pos == pack.get_item_position(item):
                    invalid_items.append(deepcopy(item))

    return invalid_items

def sort_items(items, sortby):
    itemcmp = None
    def defcmp(x, y):
        if x < y:
            return -1
        elif x > y:
            return 1
        elif x == y:
            return 0

    if sortby == "time":
        items.reverse()

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
    if sortby == "cell":
        newitems = [None] * backpack_padded_size
        for item in items:
            pos = pack.get_item_position(item) - 1
            try:
                if pos > -1 and newitems[pos] == None:
                    newitems[pos] = deepcopy(item)
            except IndexError: pass
        return newitems
    else:
        if len(items) < backpack_padded_size:
            items += ([None] * (backpack_padded_size - len(items)))
    return items

def filter_items_by_class(items, theclass):
    filtered_items = []

    for item in items:
        if not item: continue
        classes = pack.get_item_equipable_classes(item)
        for c in classes:
            if c == theclass:
                filtered_items.append(item)
                break
    return filtered_items

def get_item_stats(items):
    """ Returns a dict of various backpack stats """
    stats = {"weapons": 0,
             "misc": 0,
             "hats": 0,
             "total": 0}

    for item in items:
        if not item: continue

        slot = pack.get_item_slot(item)
        iclass = pack.get_item_class(item)

        stats["total"] += 1

        if slot == "primary" or slot == "melee" or slot == "secondary":
            if iclass.find("token") == -1:
                stats["weapons"] += 1
        elif slot == "head" and iclass.find("token") == -1:
            stats["hats"] += 1
        elif slot == "misc":
            stats["misc"] += 1
    return stats

def absolute_url(relative_url):
    domain = web.ctx.homedomain
    if domain.endswith('/'): domain = domain[:-1]
    return domain + relative_url

def process_attributes(items):
    """ Filters attributes for the item list,
    optf2-specific keys are prefixed with optf2_ """

    for item in items:
        if not item: continue
        attrs = pack.get_item_attributes(item)
        item["optf2_untradeable"] = pack.is_item_untradeable(item)
        item["optf2_attrs"] = []
        item["optf2_description"] = pack.get_item_description(item)
        item["optf2_image_url"] = pack.get_item_image(item, pack.ITEM_IMAGE_SMALL)
        item["optf2_image_url_large"] = pack.get_item_image(item, pack.ITEM_IMAGE_LARGE)
        min_level = pack.get_item_min_level(item)
        max_level = pack.get_item_max_level(item)
        custom_desc = pack.get_item_custom_description(item)

        if custom_desc: item["optf2_description"] = custom_desc

        if min_level == max_level:
            item["optf2_level"] = str(min_level)
        else:
            item["optf2_level"] = str(min_level) + "-" + str(max_level)

        for attr in attrs:
            desc = pack.get_attribute_description(attr)

            if pack.get_attribute_name(attr) == "cannot trade":
                item["optf2_untradeable"] = True
                continue

            # Workaround until Valve gives sane values
            if (pack.get_attribute_value_type(attr) != "date" and
                attr["value"] > 1000000000 and
                "float_value" in attr):
                attr["value"] = attr["float_value"]

            # Contained item is a schema id
            if pack.get_attribute_name(attr) == "referenced item def":
                sival = int(pack.get_attribute_value(attr))
                sitem = pack.get_item_by_schema_id(sival)
                item["optf2_gift_content"] = "an invalid item"

                if item:
                    item["optf2_gift_content"] = pack.get_item_name(sitem)
                    item["optf2_gift_content_id"] = sival
                attr["description_string"] = 'Contains ' + item["optf2_gift_content"]
                attr["hidden"] = False

            if pack.get_attribute_name(attr) == "set item tint RGB":
                raw_rgb = int(pack.get_attribute_value(attr))
                # Set to purple for team colored paint
                if pack.get_item_schema_id(item) != 5023 and raw_rgb == 1:
                    item_color = 'url("{0}team_splotch.png")'.format(static_prefix)
                else:
                    item_color = "#{0:02X}{1:02X}{2:02X}".format((raw_rgb >> 16) & 0xFF,
                                                                 (raw_rgb >> 8) & 0xFF,
                                                                 (raw_rgb) & 0xFF)

                # Workaround until the icons for colored paint cans are correct
                schema_paintcan = pack.get_item_by_schema_id(pack.get_item_schema_id(item))
                if (schema_paintcan and
                    schema_paintcan.get("name", "").startswith("Paint Can") and
                    raw_rgb != 1 and raw_rgb != 0):
                    paintcan_url = "{0}item_icons/Paint_Can_{1}.png".format(static_prefix,
                                                                            item_color[1:])
                    item["optf2_image_url"] = absolute_url(paintcan_url)
                    item["optf2_image_url_large"] = absolute_url(paintcan_url)
                item["optf2_color"] = item_color
                continue

            if pack.get_attribute_name(attr) == "attach particle effect":
                attr["description_string"] = ("Effect: " +
                                              particledict.get(int(attr["value"]), particledict[0]))

            if pack.get_attribute_name(attr) == "gifter account id":
                attr["description_string"] = "Gift"
                item["optf2_gift_from"] = "7656" + str(int(pack.get_attribute_value(attr) +
                                                           1197960265728))
                try:
                    user = load_profile_cached(item["optf2_gift_from"], stale = True)
                    item["optf2_gift_from_persona"] = user.get_persona()
                    attr["description_string"] = "Gift from " + item["optf2_gift_from_persona"]
                except:
                    item["optf2_gift_from_persona"] = "this user"

            if "description_string" in attr and not pack.is_attribute_hidden(attr):
                attr["description_string"] = web.websafe(attr["description_string"])
            else:
                continue
            item["optf2_attrs"].append(deepcopy(attr))

        quality_str = pack.get_item_quality(item)["str"]
        pretty_quality_str = pack.get_item_quality(item)["prettystr"]
        prefix = qualitydict.get(quality_str, pretty_quality_str)
        custom_name = pack.get_item_custom_name(item)
        item_name = pack.get_item_name(item)

        if item_name.find("The ") != -1 and pack.is_item_prefixed(item):
            item_name = item_name[4:]

        if custom_name or (not pack.is_item_prefixed(item) and quality_str == "unique"):
            prefix = ""
        if custom_name:
            item_name = custom_name

        item["optf2_cell_name"] = '<div class="{0}_name item_name">{1} {2}</div>'.format(
            quality_str, prefix, item_name)

        if custom_name or (not pack.is_item_prefixed(item) and quality_str == "unique"):
            prefix = ""
        else:
            prefix = pretty_quality_str
        color = item.get("optf2_color")
        paint_job = ""
        if color:
            if color.startswith("url"):
                color = "#FF00FF"
            paint_job = '<span style="color: {0}; font-weight: bold;">Painted</span>'.format(color)
        item["optf2_dedicated_name"] = "{0} {1} {2}".format(paint_job, prefix, item_name)

        if color:
            paint_job = "Painted"
        item["optf2_title_name"] = "{0} {1} {2}".format(paint_job, prefix, item_name)

        if color:
            paint_job = "(Painted)"
        else:
            paint_job = ""
        if prefix:
            prefix = qualitydict.get(quality_str, pretty_quality_str)

        item["optf2_feed_name"] = "{0} {1} {2}".format(prefix, item_name, paint_job)

    return items

def get_equippable_classes(items):
    """ Returns a set of classes that can equip this
    item """

    valid_classes = set()

    for item in items:
        if not item: continue
        classes = pack.get_item_equipable_classes(item)
        if classes[0]: valid_classes |= set(classes)

    return valid_classes

def internalerror():
    logging.error(traceback.format_exc())
    return web.internalerror(templates.error("Unknown error, " + project_name + " may be down for maintenance"))
if not web.config.debug: app.internalerror = internalerror

class schema_dump:
    """ Dumps everything in the schema in a pretty way """

    def GET(self):
        try:
            query = web.input()
            items = pack.get_items(from_schema = True)

            if "sortclass" in query:
                items = filter_items_by_class(items, query["sortclass"])

            filter_classes = get_equippable_classes(items)

            return templates.schema_dump(pack, process_attributes(items), filter_classes)
        except:
            return templates.error("Couldn't load schema")

class attrib_dump:
    """ Dumps all schema attributes in a pretty way """

    def GET(self):
        try:
            query = web.input()
            if not pack.get_item_schema_attributes():
                raise Exception

            attachment_check = query.get("att")
            if attachment_check:
                items = pack.get_items(from_schema = True)
                attached_items = []

                for item in items:
                    attrs = pack.get_item_attributes(item)
                    for attr in attrs:
                        attr_name = pack.get_attribute_name(attr)
                        if attachment_check == attr_name:
                            attached_items.append(item)
                            break

                return templates.schema_dump(pack, process_attributes(attached_items), [], attachment_check)

            if query.get("wikitext"):
                web.header("Content-Type", "text/plain; charset=UTF-8")
                return web.template.render(template_dir,
                                           globals = render_globals).attrib_wiki_dump(pack)

            return templates.attrib_dump(pack)
        except:
            return templates.error("Couldn't load attributes")

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
        def item_get(id64):
            item = db_fetch_item_for_id(id64)
            if not item:
                item = pack.get_item_by_schema_id(int(id64))
            return item

        try:
            user = None
            item_outdated = False
            idl = iid.split('/')
            if len(idl) == 1:
                idl.append(idl[0])
            theitem = item_get(idl[1])
            if "owner" in theitem:
                user = load_profile_cached(str(theitem["owner"]), stale = True)
                if user:
                    backpack = db_fetch_pack_for_user(user)
                    if backpack and pack.get_item_id(theitem) not in pickle.loads(str(backpack["backpack"])):
                        item_outdated = True

            item = process_attributes([theitem])[0]
        except Exception:
            return templates.item_error_notfound(idl[1])
        return templates.item(user, item, pack, item_outdated)

class persona:
    def GET(self, id):
        theobject = {"persona": "", "realname": ""}
        callback = web.input().get("jsonp")

        try:
            user = steam.profile(id)
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

class about:
    def GET(self):
        return templates.about()

class pack_fetch:
    def _get_page_for_sid(self, sid):
        if not sid:
            return templates.error("Need an ID")
        try:
            user = load_profile_cached(sid)
        except steam.ProfileError:
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
                try:
                    user = load_profile_cached(nuser)
                except:
                    return templates.error("Failed to load user profile")
            else:
                return templates.error("Bad profile name")

        query = web.input()
        sortby = query.get("sort", "cell")
        sortclass = query.get("sortclass")

        try:
            items = load_pack_cached(user)

            filter_classes = get_equippable_classes(items)
            if sortclass:
                items = filter_items_by_class(items, sortclass)

            process_attributes(items)
            stats = get_item_stats(items)

            baditems = get_invalid_pos_items(items)

            items = sort_items(items, sortby)

            for bitem in baditems:
                if bitem in items:
                    bpos = pack.get_item_position(bitem)
                    if bpos > 0 and sortby == "cell":
                        items[items.index(bitem)] = None
                    else:
                        items.remove(bitem)
                        items.append(None)

        except steam.TF2Error as E:
            return templates.error("Failed to load backpack ({0})".format(E))
        except steam.ProfileError as E:
            return templates.error("Failed to load profile ({0})".format(E))
        except:
            return templates.error("Failed to load backpack")

        isvalve = (user.get_primary_group() == valve_group_id)
        views = 1
        with db_obj.transaction():
            uid64 = user.get_id64()
            ipaddr = web.ctx.ip

            count = list(db_obj.select("search_count", where = "id64 = $id64 AND ip = $ip",
                                       vars = {"ip": ipaddr, "id64": uid64}))
            if len(count) <= 0:
                db_obj.query("INSERT INTO search_count (id64, ip) VALUES ($id64, $ip)",
                             vars = {"id64": uid64, "ip": ipaddr})
            else:
                db_obj.query("UPDATE search_count SET count = count + 1 WHERE id64 = $id64 AND ip = $ip",
                             vars = {"id64": uid64, "ip": ipaddr})

            views = db_obj.query("SELECT COUNT(*) AS views FROM search_count WHERE id64 = $id64",
                                 vars = {"id64": uid64})[0]["views"]
            db_obj.query("INSERT OR IGNORE INTO unique_views (id64) VALUES ($id64)",
                         vars = {"id64": uid64})
            db_obj.update("unique_views", where = "id64 = $id64",
                          vars = {"id64": uid64},
                          persona = user.get_persona(), valve = isvalve,
                          count = views)

        web.ctx.env["optf2_rss_url"] = "{0}feed/{1}".format(virtual_root, uid64)
        web.ctx.env["optf2_rss_title"] = "{0}'s Backpack".format(user.get_persona())
        return templates.inventory(user, pack, isvalve, items, views, filter_classes, sortby, baditems, stats)

    def GET(self, sid):
        return self._get_page_for_sid(sid)

class pack_feed:
    def GET(self, sid):
        try:
            user = load_profile_cached(sid, stale = True)
            items = load_pack_cached(user)
            process_attributes(items)
        except Exception as E:
            return templates.error(str(E))
        web.header("Content-Type", "application/rss+xml")
        return web.template.render(template_dir,
                                   globals = render_globals).inventory_feed(user,
                                                                            pack,
                                                                            items)

class index:
    def GET(self):
        countlist = db_obj.select("unique_views", order = "count DESC", limit = top_backpack_rows)
        return templates.index(countlist)
    def POST(self):
        user = web.input().get("user")
        if user:
            if user.endswith('/'): user = user[:-1]
            raise web.seeother(virtual_root + "user/" + os.path.basename(user))
        else: return web.seeother(virtual_root)

class openid_consume:
    def GET(self):
        openid_store = sqlstore.SQLiteStore(sqlite3.connect(db_path))

        openid = consumer.Consumer(session, openid_store)
        openid_realm = web.ctx.homedomain
        openid_return_url = openid_realm + virtual_root + "openid"
        auth = openid.begin("http://steamcommunity.com/openid/")
        openid_auth_url = auth.redirectURL(openid_realm, return_to = openid_return_url)

        if web.input().get("openid.return_to"):
            openid_return_url = openid_realm + virtual_root + "openid"
            response = openid.complete(web.input(), openid_return_url)
            if response.status != consumer.SUCCESS or not response.identity_url:
                return templates.error("Login Error")
            session["identity_hash"] = make_openid_hash(response.identity_url) + "," + response.identity_url

            raise web.seeother(virtual_root + "user/" + os.path.basename(response.identity_url))
        else:
            raise web.seeother(openid_auth_url)

if enable_fastcgi:
    web.wsgi.runwsgi = lambda func, addr=None: web.wsgi.runfcgi(func, addr)

if __name__ == "__main__":
    app.run()
