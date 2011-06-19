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
    profile = pickle.dumps(summary, pickle.HIGHEST_PROTOCOL)
    vanitystr = vanity

    if not sid.isdigit(): vanitystr = sid

    p = web.db.SQLParam
    querystr = ("INSERT INTO profiles (id64, timestamp, profile, vanity) VALUES " +
                "($id, $ts, $profile, $v)" +
                " ON DUPLICATE KEY UPDATE " +
                "timestamp = VALUES(timestamp), profile = VALUES(profile), vanity = VALUES(vanity)")
    database_obj.query(querystr, vars = {"id": user.get_id64(),
                                         "ts": int(time()),
                                         "profile": profile,
                                         "v": vanitystr})

    return user

def load_profile_cached(sid, stale = False):
    user = steam.user.profile()
    try:
        if sid.isdigit():
            prow = database_obj.select("profiles", what = "profile, timestamp",
                                       where = "id64 = $id64", vars = {"id64": int(sid)})[0]
        else:
            prow = database_obj.select("profiles", what = "profile, timestamp",
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
    return (sorted(lastpack) != sorted(newpack))

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
    backpack_items = set()
    data = []
    attrdata = []
    deltapack = []
    olditems = {}

    try:
        packitems = list(pack)
    except steam.items.ItemError:
        pack.set_schema(load_schema_cached(web.ctx.language, fresh = True))
        packitems = list(pack)


    with database_obj.transaction():
        lastpack = get_pack_snapshot_for_user(user)
        if lastpack:
            deltapack = pickle.loads(lastpack["backpack"])
            for item in get_items_for_backpack(deltapack):
                compitem = db_to_itemobj(item)
                olditems[compitem["id"]] = compitem

    for item in packitems:
        backpack_items.add(item.get_id())

        if item.get_id() in olditems:
            compitem = item._item
            olditem = olditems[compitem["id"]]
            if dict(olditem.items() + compitem.items()) == olditem:
                continue

        rawattrs = item._item.get("attributes")
        if rawattrs:
            rawattrs = pickle.dumps(rawattrs, pickle.HIGHEST_PROTOCOL)
            rawcontent = item.get_contents()
            if rawcontent: rawcontent = pickle.dumps(rawcontent._item, pickle.HIGHEST_PROTOCOL)
            attrdata.append('(' + web.db.SQLParam(item.get_id()) + ', ' + web.db.SQLParam(rawattrs) + ', ' +
                            web.db.SQLParam(rawcontent) + ')')

        row = [item.get_id(), item.get_original_id(), user.get_id64(), item.get_schema_id(),
               item.get_level(), item.is_untradable(),
               item.get_inventory_token(), item.get_quality()["id"],
               item.get_custom_name(), item.get_custom_description(),
               item.get_current_style_id(),
               item.get_quantity()]

        data.append('(' + web.db.SQLQuery.join([web.db.SQLParam(ival) for ival in row], ', ') + ')')

    with database_obj.transaction():
        if len(attrdata) > 0:
            theattrquery = web.db.SQLQuery("INSERT INTO attributes(id64, attrs, contents) VALUES " +
                                           web.db.SQLQuery.join(attrdata, ', ') +
                                           " ON DUPLICATE KEY UPDATE attrs=VALUES(attrs), contents=VALUES(contents)")
            database_obj.query(theattrquery)

        if len(data) > 0:
            thequery = web.db.SQLQuery("INSERT INTO items (id64, oid64, " +
                                       "owner, sid, level, untradeable, " +
                                       "token, quality, custom_name, " +
                                       "custom_desc, style, quantity) VALUES " +
                                       web.db.SQLQuery.join(data, ', ') +
                                       " ON DUPLICATE KEY UPDATE oid64=VALUES(oid64), " +
                                       "owner=VALUES(owner), sid=VALUES(sid), level=VALUES(level), " +
                                       "untradeable=VALUES(untradeable), token=VALUES(token), " +
                                       "quality=VALUES(quality), custom_name=VALUES(custom_name), " +
                                       "custom_desc=VALUES(custom_desc), style=VALUES(style), " +
                                       "quantity=VALUES(quantity)")
            database_obj.query(thequery)

        if not lastpack or db_pack_is_new(pickle.loads(str(lastpack["backpack"])), backpack_items):
            database_obj.insert("backpacks", id64 = user.get_id64(),
                                backpack = pickle.dumps(list(backpack_items), pickle.HIGHEST_PROTOCOL),
                                timestamp = ts)
        elif lastpack:
            database_obj.update("backpacks", where = "id64 = $id64 AND timestamp = $ts",
                                timestamp = ts, vars = {"id64": user.get_id64(), "ts": lastpack["timestamp"]})
    return packitems

def get_pack_timeline_for_user(user, tl_size = None):
    """ Returns None if a backpack couldn't be found, returns
    tl_size rows from the timeline
    """
    packrow = database_obj.select("backpacks",
                                  where = "id64 = $id64",
                                  order = "timestamp DESC",
                                  limit = tl_size,
                                  vars = {"id64": user.get_id64()})

    if len(packrow) > 0:
        return packrow
    else:
        return []

def get_pack_snapshot_for_user(user, date = None):
    """ Returns the backpack snapshot or None if it couldn't be found,
    if date is not give the latest snapshot will be returned."""

    tsstr = ""
    if date: tsstr = " AND timestamp = $ts"

    rows = database_obj.select("backpacks",
                               where = "id64 = $id64" + tsstr,
                               what = "backpack, timestamp",
                               limit = 1,
                               order = "timestamp DESC",
                               vars = {"id64": user.get_id64(), "ts": date})

    if len(rows) > 0:
        return rows[0]
    else:
        return None


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
    rawcontents = dbitem["contents"]
    if rawcontents: theitem["contained_item"] = pickle.loads(rawcontents)

    return theitem

item_select_query = web.db.SQLQuery("SELECT items.*, attributes.attrs as attributes, attributes.contents FROM items " +
                                    "LEFT JOIN attributes ON items.id64=attributes.id64 " +
                                    "WHERE items.id64")

def fetch_item_for_id(iid):
    try:
        itemrow = database_obj.query(item_select_query + " = " + web.db.SQLParam(int(iid)))[0]
        return db_to_itemobj(itemrow)
    except IndexError:
        return None

def get_items_for_backpack(backpack):
    query = web.db.SQLQuery(item_select_query + ' IN (' +
                            web.db.SQLQuery.join([web.db.SQLParam(id64) for id64 in backpack], ", ") + ')')
    dbitems = []

    if len(backpack) > 0:
        dbitems = database_obj.query(query)

    return dbitems

def load_pack_cached(user, stale = False, date = None):
    packresult = []
    thepack = get_pack_snapshot_for_user(user, date = date)
    if not stale and not date:
        if not cache_not_stale(thepack):
            try:
                return refresh_pack_cache(user)
            except: pass
    if thepack:
        schema = load_schema_cached(web.ctx.language)
        dbitems = get_items_for_backpack(pickle.loads(thepack["backpack"]))
        return [schema.create_item(db_to_itemobj(item)) for item in dbitems]
    return []

def get_user_pack_views(user):
    """ Returns the viewcount of a user's backpack """

    views = 0
    uid64 = user.get_id64()
    ipaddr = web.ctx.ip

    with database_obj.transaction():
        count = database_obj.select("search_count", where = "id64 = $id64 AND ip = $ip",
                                    vars = {"ip": ipaddr, "id64": uid64})
        if len(count) <= 0:
            database_obj.insert("search_count", ip = ipaddr, id64 = uid64)
            database_obj.query("UPDATE profiles SET bp_views = bp_views + 1 WHERE id64 = $id64",
                               vars = {"id64": user.get_id64(), "c": views})

        views = database_obj.select("profiles", what = "bp_views", where = "id64 = $id64",
                                    vars = {"id64": uid64})[0]["bp_views"]

    return views

def get_top_pack_views(limit = 10):
    """ Will return the top viewed backpacks sorted in descending order
    no more than limit rows will be returned """

    result = database_obj.select("profiles", what = "bp_views, profile",
                                 where = "bp_views > 0",  order = "bp_views DESC", limit = limit)
    profiles = []
    for row in result:
        profile = steam.user.profile(pickle.loads(row["profile"]))
        profiles.append((row["bp_views"], profile.get_primary_group() == config.valve_group_id, profile))

    return profiles
