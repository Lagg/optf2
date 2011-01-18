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
        data = []
        packitems = pack.get_items()
        thequery = web.db.SQLQuery("INSERT INTO items (id64, " +
                                   "owner, sid, level, untradeable, " +
                                   "token, quality, custom_name, " +
                                   "custom_desc, attributes, quantity) VALUES ")
        for item in packitems:
            backpack_items.append(pack.get_item_id(item))
            attribs = pack.get_item_attributes(item)

            # Replace gift contents sid with item dict
            contents = pack.get_item_contents(item)
            if contents:
                for attr in attribs:
                    # referenced item def
                    if pack.get_attribute_id(attr) == 194:
                        attr["value"] = deepcopy(contents)
                        break
            if "attributes" in item:
                item["attributes"]["attribute"] = deepcopy(attribs)

            row = [pack.get_item_id(item), user.get_id64(), pack.get_item_schema_id(item),
                   pack.get_item_level(item), pack.is_item_untradeable(item),
                   pack.get_item_inventory_token(item), pack.get_item_quality(item)["id"],
                   pack.get_item_custom_name(item), pack.get_item_custom_description(item),
                   pickle.dumps(attribs), pack.get_item_quantity(item)]

            data.append('(' + web.db.SQLQuery.join([web.db.SQLParam(ival) for ival in row], ', ') + ')')

        thequery += web.db.SQLQuery.join(data, ', ')
        thequery += (" ON DUPLICATE KEY UPDATE id64=VALUES(id64), " +
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
                                backpack = buffer(pickle.dumps(backpack_items)),
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
        with database_obj.transaction():
            query = web.db.SQLQuery("SELECT * FROM items WHERE id64=")
            items = pickle.loads(str(thepack["backpack"]))
            dbitems = []

            query += web.db.SQLQuery.join([web.db.SQLParam(id64) for id64 in items], " OR id64=")

            if len(items) > 0:
                dbitems = database_obj.query(query)

            for item in dbitems:
                theitem = db_to_itemobj(item)
                packresult.append(deepcopy(theitem))
        return packresult
