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

import config, steam, urllib2, web, os, zlib
import cPickle as pickle
from time import time

gamelib = getattr(steam, config.game_mode)

database_obj = config.database_obj

def cache_not_stale(row):
    if row and "timestamp" in row:
        return (int(time()) - row["timestamp"]) < config.cache_pack_refresh_interval
    else:
        return False

def db_to_profileobj(db):
    profile = {"steamid": db["id64"],
               "communityvisibilitystate": db["profile_status"],
               "personaname": db["persona"],
               "avatar": db["avatar_url"],
               "avatarmedium": db["avatar_url"],
               "avatarfull": db["avatar_url"],
               "personastate": db["online_status"],
               "realname": db["real_name"],
               "primaryclanid": db["primary_group"],
               "gameserverip": db["last_server_ip"],
               "gameextrainfo": db["last_game_info"],
               "gameid": db["last_app_id"],
               "profileurl": db["profile_url"]
               }
    for k in profile.keys():
        if profile[k] == None: del profile[k]

    return profile

def refresh_profile_cache(sid, vanity = None):
    user = steam.user.profile(sid)
    summary = user._summary_object
    vanitystr = vanity
    gameinfo = user.get_current_game()

    if not sid.isdigit(): vanitystr = sid

    querystr = ("INSERT INTO profiles (id64, persona, vanity, real_name, last_server_ip " +
                ", last_app_id, last_game_info, profile_url, avatar_url, primary_group, " +
                "profile_status, online_status, timestamp) VALUES " +
                "($id, $persona, $vanity, $realname, $lastip, $lastapp, $lastinfo, $purl, $aurl, " +
                "$group, $pstatus, $ostatus, $ts)" +
                " ON DUPLICATE KEY UPDATE " +
                "timestamp = VALUES(timestamp), vanity = VALUES(vanity)" +
                ", persona = VALUES(persona), real_name = VALUES(real_name), last_server_ip = VALUES(last_server_ip)" +
                ", last_app_id = VALUES(last_app_id), last_game_info = VALUES(last_game_info)" +
                ", profile_url = VALUES(profile_url), avatar_url = VALUES(avatar_url), primary_group = VALUES(primary_group)" +
                ", profile_status = VALUES(profile_status), online_status = VALUES(online_status)")
    database_obj.query(querystr, vars = {"id": user.get_id64(),
                                         "ts": int(time()),
                                         "vanity": vanitystr,
                                         "persona": user.get_persona(),
                                         "realname": user.get_real_name(),
                                         "lastip": gameinfo.get("server"),
                                         "lastapp": gameinfo.get("id"),
                                         "lastinfo": gameinfo.get("extra"),
                                         "purl": user.get_profile_url(),
                                         "aurl": user.get_avatar_url(user.AVATAR_SMALL),
                                         "group": user.get_primary_group(),
                                         "pstatus": user.get_visibility(),
                                         "ostatus": user.get_status()})

    return user

def load_profile_cached(sid, stale = False):
    try:
        if sid.isdigit():
            prow = database_obj.select("profiles", where = "id64 = $id64", vars = {"id64": int(sid)})[0]
        else:
            prow = database_obj.select("profiles", where = "vanity = $v", vars = {"v": sid})[0]
    except IndexError:
        return refresh_profile_cache(sid)

    if stale or cache_not_stale(prow):
        return steam.user.profile(db_to_profileobj(prow))
    else:
        return refresh_profile_cache(sid)

def db_pack_is_new(lastpack, newpack):
    olditems = []
    newitems = []
    for i in lastpack:
        try: olditems.append(int(i))
        except TypeError:
            try: olditems.append(i[0])
            except KeyError: olditems.append(i["id"])
    for i in newpack:
        try: newitems.append(int(i))
        except TypeError:
            try: newitems.append(i[0])
            except KeyError: newitems.append(i["id"])

    return (sorted(olditems) != sorted(newitems))

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

    try:
        packitems = list(pack)
    except steam.items.ItemError:
        pack.set_schema(load_schema_cached(web.ctx.language, fresh = True))
        packitems = list(pack)

    last_packid = None
    backpack_items = [item._item for item in packitems]
    with database_obj.transaction():
        lastpack = get_pack_snapshot_for_user(user)
        if not lastpack or db_pack_is_new(pickle.loads(str(lastpack["backpack"])), backpack_items):
            database_obj.query("INSERT INTO backpacks (id64, backpack, timestamp) VALUES ($id64, $bp, $ts)",
                               vars = {"id64": user.get_id64(),
                                       "bp": zlib.compress(pickle.dumps(backpack_items, pickle.HIGHEST_PROTOCOL)),
                                       "ts": ts})
            last_packid = database_obj.query("SELECT LAST_INSERT_ID() AS lastid")[0]["lastid"]
        elif lastpack:
            database_obj.query("UPDATE backpacks SET timestamp = $ts, backpack = $bp WHERE id = $id",
                               vars = {"id": lastpack["id"],
                                       "bp": zlib.compress(pickle.dumps(backpack_items, pickle.HIGHEST_PROTOCOL)),
                                       "ts": ts})
            last_packid = lastpack["id"]

    web.ctx.current_pid = last_packid
    return packitems

def get_pack_timeline_for_user(user, tl_size = None):
    """ Returns None if a backpack couldn't be found, returns
    tl_size rows from the timeline
    """
    packrow = database_obj.select("backpacks",
                                  where = "id64 = $id64",
                                  order = "timestamp DESC",
                                  limit = tl_size,
                                  what = "id, timestamp",
                                  vars = {"id64": user.get_id64()})

    if len(packrow) > 0:
        return packrow
    else:
        return []

def get_pack_snapshot_for_user(user, pid = None):
    """ Returns the backpack snapshot or None if it couldn't be found,
    if id is not given the latest snapshot will be returned."""

    tsstr = ""
    if pid: tsstr = " AND id = $id"

    rows = database_obj.select("backpacks",
                               where = "id64 = $id64" + tsstr,
                               what = "id, backpack, timestamp",
                               limit = 1,
                               order = "timestamp DESC",
                               vars = {"id64": user.get_id64(), "id": pid})

    if len(rows) > 0:
        pack = rows[0]
        pack["backpack"] = zlib.decompress(pack["backpack"])
        return pack
    else:
        return None


def db_to_itemobj(dbitem):
    if "id" in dbitem:
        return dbitem
    if "id64" not in dbitem:
        return {"id": dbitem[0], "defindex": dbitem[1], "inventory": dbitem[2]}

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
    if rawattrs: theitem["attributes"] = pickle.loads(zlib.decompress(rawattrs))
    rawcontents = dbitem["contents"]
    if rawcontents: theitem["contained_item"] = pickle.loads(zlib.decompress(rawcontents))

    return theitem

item_select_query = web.db.SQLQuery("SELECT items.*, attributes.attrs as attributes, attributes.contents FROM items " +
                                    "LEFT JOIN attributes ON items.id64=attributes.id64 " +
                                    "WHERE items.id64")

def fetch_item_for_id(id64):
    pid = web.input().get("pid")

    if not pid:
        itemrow = database_obj.query(item_select_query + " = " + web.db.SQLParam(int(id64)))[0]
        return db_to_itemobj(itemrow)

    pack = database_obj.select("backpacks", where = "id = $pid",
                               vars = {"pid": pid})[0]
    items = pickle.loads(zlib.decompress(pack["backpack"]))
    for item in items:
        try:
            packitem = db_to_itemobj(item)
        except:
            continue
        if int(packitem["id"]) == int(id64):
            packitem["owner"] = pack["id64"]
            return packitem

def get_items_for_backpack(backpack):
    idlist = []
    inlinelist = []

    for item in backpack:
        try: idlist.append(int(item))
        except TypeError:
            itemized = db_to_itemobj(item)
            itemized["inlinemapped"] = True
            inlinelist.append(itemized)

    query = web.db.SQLQuery(item_select_query + ' IN (' +
                            web.db.SQLQuery.join(idlist, ", ") + ')')
    dbitems = []

    if idlist and len(backpack) > 0:
        dbitems = database_obj.query(query)

    return [db_to_itemobj(item) for item in dbitems] + inlinelist

def load_pack_cached(user, stale = False, pid = None):
    thepack = get_pack_snapshot_for_user(user, pid = pid)
    web.ctx.current_uid64 = user.get_id64()
    if not stale and not pid:
        if not cache_not_stale(thepack):
            try:
                return refresh_pack_cache(user)
            except: pass
    if thepack:
        web.ctx.current_pid = thepack["id"]
        schema = load_schema_cached(web.ctx.language)
        dbitems = get_items_for_backpack(pickle.loads(thepack["backpack"]))
        return [schema.create_item(item) for item in dbitems]
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

    result = database_obj.select("profiles", what = "bp_views, persona, primary_group, id64",
                                 where = "bp_views > 0",  order = "bp_views DESC", limit = limit)
    profiles = []
    for row in result:
        profiles.append((row["bp_views"], row["primary_group"] == config.valve_group_id, row["persona"], row["id64"]))

    return profiles

def is_item_unique(item):
    """ Checks if the item is different enough
    from it's schema counterpart to be stored in the item table. """

    schema = load_schema_cached(web.ctx.language)
    sitem = schema[item.get_schema_id()]

    if sitem.get_min_level() == sitem.get_max_level():
        if item.get_level() != sitem.get_min_level():
            return True
    else: return True

    if (item.get_quantity() != sitem.get_quantity() or
        item.get_custom_name() or
        item.get_custom_description() or
        item.get_current_style_id() or
        item._item.get("attributes") or
        item.is_untradable() != sitem.is_untradable() or
        item.get_quality()["id"] != sitem.get_quality()["id"] or
        item.get_contents()):
        return True
    else:
        return False
