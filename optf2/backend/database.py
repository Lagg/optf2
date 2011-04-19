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

if config.game_mode == "tf2":
    gamelib = steam.tf2
elif config.game_mode == "p2":
    gamelib = steam.p2

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
                 "profile": buffer(pickle.dumps(summary, pickle.HIGHEST_PROTOCOL))}

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
    cachepath = os.path.join(config.cache_file_dir, "schema-" + lang)
    schema_object = None

    if os.path.exists(cachepath) and not fresh:
        schema_object = pickle.load(open(cachepath, "rb"))
    else:
        schema_object = gamelib.item_schema(lang = lang)
        pickle.dump(schema_object, open(cachepath, "wb"), pickle.HIGHEST_PROTOCOL)

    return schema_object

def refresh_pack_cache(user):
    pack = gamelib.backpack(schema = load_schema_cached(web.ctx.language))
    pack.load(user)
    ts = int(time())

    with database_obj.transaction():
        backpack_items = []
        data = []
        try:
            packitems = list(pack)
        except steam.tf2.ItemError:
            pack.set_schema(load_schema_cached(web.ctx.language, fresh = True))
            packitems = list(pack)
        thequery = web.db.SQLQuery("INSERT INTO items (id64, oid64, " +
                                   "owner, sid, level, untradeable, " +
                                   "token, quality, custom_name, " +
                                   "custom_desc, attributes, quantity) VALUES ")
        for item in packitems:
            backpack_items.append(item.get_id())
            attribs = item.get_attributes()
            pattribs = []

            # Replace gift contents sid with item dict
            contents = item.get_contents()
            for attr in attribs:
                if contents and attr.get_id() == 194:
                    attr._attribute["value"] = contents._item
                pattribs.append(attr._attribute)

            if len(pattribs) > 0 and "attributes" in item._item:
                item._item["attributes"] = pattribs

            row = [item.get_id(), item.get_original_id(), user.get_id64(), item.get_schema_id(),
                   item.get_level(), item.is_untradable(),
                   item.get_inventory_token(), item.get_quality()["id"],
                   item.get_custom_name(), item.get_custom_description(),
                   pickle.dumps(pattribs, pickle.HIGHEST_PROTOCOL), item.get_quantity()]

            data.append('(' + web.db.SQLQuery.join([web.db.SQLParam(ival) for ival in row], ', ') + ')')

        thequery += web.db.SQLQuery.join(data, ', ')
        thequery += (" ON DUPLICATE KEY UPDATE id64=VALUES(id64), oid64=VALUES(oid64), " +
                     "owner=VALUES(owner), sid=VALUES(sid), level=VALUES(level), " +
                     "untradeable=VALUES(untradeable), token=VALUES(token), " +
                     "quality=VALUES(quality), custom_name=VALUES(custom_name), " +
                     "custom_desc=VALUES(custom_desc), attributes=VALUES(attributes), " +
                     "quantity=VALUES(quantity)")

        if len(data) > 0:
            database_obj.query(thequery)

        lastpack = list(database_obj.select("backpacks", what = "backpack",
                                            where="id64 = $id64",
                                            vars = {"id64": user.get_id64()},
                                            order = "timestamp DESC", limit = 1))
        if db_pack_is_new(lastpack, backpack_items):
            database_obj.insert("backpacks", id64 = user.get_id64(),
                                backpack = buffer(pickle.dumps(backpack_items, pickle.HIGHEST_PROTOCOL)),
                                timestamp = ts)
        elif len(lastpack) > 0:
            lastts = database_obj.select("backpacks", what = "MAX(timestamp) AS ts", where = "id64 = $id64",
                                         vars = {"id64": user.get_id64()})[0]["ts"]
            database_obj.update("backpacks", where = "id64 = $id64 AND timestamp = $ts",
                                timestamp = ts, vars = {"id64": user.get_id64(), "ts": lastts})
        return packitems
    return None

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
               "attributes": pickle.loads(str(dbitem["attributes"]))}

    return theitem

def fetch_item_for_id(iid):
    try:
        itemrow = list(database_obj.select("items",
                                           where = "id64 = $id64",
                                           vars = {"id64": iid}))[0]
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
            except urllib2.URLError:
                pass
            except: pass
            thepack = fetch_pack_for_user(user)
    if thepack:
        schema = load_schema_cached(web.ctx.language)
        with database_obj.transaction():
            query = web.db.SQLQuery("SELECT * FROM items WHERE id64=")
            items = pickle.loads(str(thepack["backpack"]))
            dbitems = []

            query += web.db.SQLQuery.join([web.db.SQLParam(id64) for id64 in items], " OR id64=")

            if len(items) > 0:
                dbitems = database_obj.query(query)

            packresult = [steam.tf2.item(schema, db_to_itemobj(item)) for item in dbitems]
        return packresult
