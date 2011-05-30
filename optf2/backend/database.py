"""
Copyright (c) 2008-2011, Anthony Garcia <lagg@lavabit.com>

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

import config, steam, urllib2, web, os
import cPickle as pickle
from cStringIO import StringIO
from time import time

gamelib = getattr(steam, config.game_mode)

database_obj = config.database_obj

def cache_not_stale(row):
    if row and "timestamp" in row:
        return (int(time()) - row["timestamp"]) < config.cache_pack_refresh_interval
    else:
        return False

def refresh_profile_cache(sid, vanity = None):
    user = steam.user.profile(sid)
    summary = user._summary_object
    queryvars = {"id64": user.get_id64(),
                 "timestamp": int(time()),
                 "profile": pickle.dumps(summary, pickle.HIGHEST_PROTOCOL)}

    if vanity: queryvars["vanity"] = vanity
    if not sid.isdigit(): queryvars["vanity"] = sid

    itervars = list(queryvars.iteritems())

    database_obj.query("INSERT INTO profile_cache (" + web.db.SQLQuery.join([k for k,v in itervars], ", ") + ") VALUES " +
                       "(" + web.db.SQLQuery.join([web.db.SQLParam(v) for k,v in itervars], ", ") + ")" +
                       " ON DUPLICATE KEY UPDATE " + web.db.SQLQuery.join(["{0}=VALUES({0})".format(k) for k,v in itervars], ", "))

    return user

def load_profile_cached(sid, stale = False):
    user = steam.user.profile()
    try:
        if sid.isdigit():
            prow = database_obj.select("profile_cache", what = "profile, timestamp",
                                       where = "id64 = $id64", vars = {"id64": int(sid)})[0]
        else:
            prow = database_obj.select("profile_cache", what = "profile, timestamp",
                                       where = "vanity = $v", vars = {"v": sid})[0]

        pfile = pickle.loads(prow["profile"])

        if stale or cache_not_stale(prow):
            return steam.user.profile(pfile)
        else:
            try:
                return refresh_profile_cache(sid)
            except:
                return steam.user.profile(pfile)
    except:
        return refresh_profile_cache(sid)

def db_pack_is_new(lastpack, newpack):
    return (len(lastpack) <= 0 or
            sorted(pickle.loads(str(lastpack[0]["backpack"]))) != sorted(newpack))

def load_schema_cached(lang, fresh = False):
    cachepath = os.path.join(config.cache_file_dir, "schema-" + config.game_mode + "-" + lang)
    schema_object = None

    if os.path.exists(cachepath) and not fresh:
        schema_object = pickle.load(open(cachepath, "rb"))
    else:
        schema_object = gamelib.item_schema(lang = lang)
        schema_object.optf2_paints = {}
        for sitem in schema_object:
            if sitem._schema_item.get("name", "").startswith("Paint Can"):
                for attr in sitem:
                    if attr.get_name() == "set item tint RGB":
                        schema_object.optf2_paints[int(attr.get_value())] = sitem
        pickle.dump(schema_object, open(cachepath, "wb"), pickle.HIGHEST_PROTOCOL)

    return schema_object

def refresh_pack_cache(user):
    pack = gamelib.backpack(schema = load_schema_cached(web.ctx.language))
    pack.load(user)
    ts = int(time())

    with database_obj.transaction():
        backpack_items = set()
        data = []
        attrdata = []

        try:
            packitems = list(pack)
        except steam.items.ItemError:
            pack.set_schema(load_schema_cached(web.ctx.language, fresh = True))
            packitems = list(pack)

        thequery = web.db.SQLQuery("INSERT INTO items (id64, oid64, " +
                                   "owner, sid, level, untradeable, " +
                                   "token, quality, custom_name, " +
                                   "custom_desc, style, quantity) VALUES ")
        theattrquery = web.db.SQLQuery("INSERT INTO attributes(id64, attrs) VALUES ")

        for item in packitems:
            backpack_items.add(item.get_id())
            rawattrs = item._item.get("attributes")
            if rawattrs:
                rawattrs = pickle.dumps(rawattrs, pickle.HIGHEST_PROTOCOL)
                attrdata.append('(' + web.db.SQLParam(item.get_id()) + ', ' + web.db.SQLParam(rawattrs) + ')')

            row = [item.get_id(), item.get_original_id(), user.get_id64(), item.get_schema_id(),
                   item.get_level(), item.is_untradable(),
                   item.get_inventory_token(), item.get_quality()["id"],
                   item.get_custom_name(), item.get_custom_description(),
                   item.get_current_style_id(),
                   item.get_quantity()]

            data.append('(' + web.db.SQLQuery.join([web.db.SQLParam(ival) for ival in row], ', ') + ')')

        thequery += web.db.SQLQuery.join(data, ', ')
        thequery += (" ON DUPLICATE KEY UPDATE id64=VALUES(id64), oid64=VALUES(oid64), " +
                     "owner=VALUES(owner), sid=VALUES(sid), level=VALUES(level), " +
                     "untradeable=VALUES(untradeable), token=VALUES(token), " +
                     "quality=VALUES(quality), custom_name=VALUES(custom_name), " +
                     "custom_desc=VALUES(custom_desc), style=VALUES(style), " +
                     "quantity=VALUES(quantity)")

        theattrquery += web.db.SQLQuery.join(attrdata, ', ')
        theattrquery += " ON DUPLICATE KEY UPDATE id64=VALUES(id64), attrs=VALUES(attrs)"
        if len(attrdata) > 0:
            database_obj.query(theattrquery)

        if len(data) > 0:
            database_obj.query(thequery)

        lastpack = list(database_obj.select("backpacks", what = "backpack",
                                            where="id64 = $id64",
                                            vars = {"id64": user.get_id64()},
                                            order = "timestamp DESC", limit = 1))
        if db_pack_is_new(lastpack, backpack_items):
            database_obj.insert("backpacks", id64 = user.get_id64(),
                                backpack = pickle.dumps(list(backpack_items), pickle.HIGHEST_PROTOCOL),
                                timestamp = ts)
        elif len(lastpack) > 0:
            lastts = database_obj.select("backpacks", what = "MAX(timestamp) AS ts", where = "id64 = $id64",
                                         vars = {"id64": user.get_id64()})[0]["ts"]
            database_obj.update("backpacks", where = "id64 = $id64 AND timestamp = $ts",
                                timestamp = ts, vars = {"id64": user.get_id64(), "ts": lastts})
        return packitems
    return []

def fetch_pack_for_user(user, date = None, tl_size = None):
    """ Returns None if a backpack couldn't be found, returns
    tl_size rows from the timeline
    """
    packrow = list(database_obj.select("backpacks",
                                       where = "id64 = $id64",
                                       order = "timestamp DESC",
                                       limit = tl_size,
                                       vars = {"id64": user.get_id64()}))

    if tl_size: return packrow

    for pack in packrow:
        if not date:
            return pack
        if str(pack["timestamp"]) == str(date):
            return pack
    if len(packrow) > 0: return packrow[0]

def db_to_itemobj(dbitem):
    theitem = {"id": dbitem["id64"],
               "original_id": dbitem["oid64"],
               "owner": dbitem["owner"],
               "defindex": dbitem["sid"],
               "level": dbitem["level"],
               "quantity": dbitem["quantity"],
               "flag_cannot_trade": dbitem["untradeable"],
               "inventory": dbitem["token"],
               "quality": dbitem["quality"],
               "custom_name": dbitem["custom_name"],
               "custom_desc": dbitem["custom_desc"],
               "style": dbitem["style"]}

    rawattrs = dbitem["attributes"]
    if rawattrs: theitem["attributes"] = pickle.loads(rawattrs)

    return theitem

item_select_query = web.db.SQLQuery("SELECT items.*, attributes.attrs as attributes FROM items " +
                                    "LEFT JOIN attributes ON items.id64=attributes.id64 " +
                                    "WHERE items.id64")

def fetch_item_for_id(iid):
    try:
        itemrow = database_obj.query(item_select_query + " = " + web.db.SQLParam(int(iid)))[0]
        return db_to_itemobj(itemrow)
    except IndexError:
        return None

def load_pack_cached(user, stale = False, date = None):
    packresult = []
    thepack = fetch_pack_for_user(user, date = date)
    if not stale and not date:
        if not cache_not_stale(thepack):
            try:
                return refresh_pack_cache(user)
            except: pass
    if thepack:
        schema = load_schema_cached(web.ctx.language)
        with database_obj.transaction():
            items = pickle.loads(str(thepack["backpack"]))
            query = web.db.SQLQuery(item_select_query + ' IN (' +
                                    web.db.SQLQuery.join([web.db.SQLParam(id64) for id64 in items], ", ") + ')')
            dbitems = []

            if len(items) > 0:
                dbitems = database_obj.query(query)

            packresult = [schema.create_item(db_to_itemobj(item)) for item in dbitems]
        return packresult
    return []
