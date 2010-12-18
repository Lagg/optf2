import config, steam, urllib2, web
import cPickle as pickle
from cStringIO import StringIO
from time import time
from copy import deepcopy

database_obj = config.database_obj

def cache_not_stale(row):
    if row and "timestamp" in row:
        return (int(time()) - row["timestamp"]) < config.cache_pack_refresh_interval
    else:
        return False

def refresh_profile_cache(sid):
    user = steam.profile(sid)
    summary = user.get_summary_object()

    try:
        database_obj.insert("profile_cache", id64 = user.get_id64(),
                            timestamp = int(time()),
                            profile = buffer(pickle.dumps(summary)))
    except:
        database_obj.update("profile_cache", id64 = user.get_id64(),
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

    if config.cache_pack:
        try:
            prow = database_obj.select("profile_cache", what = "profile, timestamp",
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
    pack = steam.backpack()
    pack.load_pack(user)
    ts = int(time())

    with database_obj.transaction():
        backpack_items = []
        for item in pack.get_items():
            backpack_items.append(pack.get_item_id(item))
            database_obj.query("INSERT IGNORE INTO items (id64) VALUES ($id64)", vars = {"id64": pack.get_item_id(item)})
            database_obj.update("items", where = "id64 = $id64", vars = {"id64": pack.get_item_id(item)},
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

        lastpack = list(database_obj.select("backpacks", what = "backpack",
                                            where="id64 = $id64",
                                            vars = {"id64": user.get_id64()},
                                            order = "timestamp DESC", limit = 1))
        if db_pack_is_new(lastpack, backpack_items):
            database_obj.insert("backpacks", id64 = user.get_id64(),
                                backpack = buffer(pickle.dumps(backpack_items)),
                                timestamp = ts)
        elif len(lastpack) > 0:
            lastts = database_obj.select("backpacks", what = "MAX(timestamp) AS ts", where = "id64 = $id64",
                                         vars = {"id64": user.get_id64()})[0]["ts"]
            database_obj.update("backpacks", where = "id64 = $id64 AND timestamp = $ts",
                                timestamp = ts, vars = {"id64": user.get_id64(), "ts": lastts})
        return True
    return False

def fetch_pack_for_user(user, date = None):
    """ Returns None if a backpack couldn't be found """
    packrow = database_obj.select("backpacks",
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

def fetch_item_for_id(iid):
    try:
        itemrow = list(database_obj.select("items",
                                           where = "id64 = $id64",
                                           vars = {"id64": iid}))[0]
        return db_to_itemobj(itemrow)
    except IndexError:
        return None

def load_pack_cached(user, stale = False):
    packresult = []
    thepack = fetch_pack_for_user(user)
    if not stale:
        if not cache_not_stale(thepack):
            try:
                refresh_pack_cache(user)
            except urllib2.URLError:
                pass
            thepack = fetch_pack_for_user(user)
    if thepack:
        with database_obj.transaction():
            for item in pickle.loads(str(thepack["backpack"])):
                dbitem = database_obj.select("items", where = "id64 = $id64",
                                       vars =  {"id64": item})[0]
                theitem = db_to_itemobj(dbitem)
                packresult.append(deepcopy(theitem))
        return packresult
