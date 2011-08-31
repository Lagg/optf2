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

import config, steam, urllib2, web, os, zlib, marshal
import couchdbkit as couchdb
import cPickle as pickle
from time import time

gamelib = getattr(steam, config.game_mode)

database_obj = config.database_obj
couch_obj = couchdb.Server()

schema_obj = {}

class cached_item_schema(gamelib.item_schema):
    def _download(self, lang):
        self._language = lang
        cachepath = os.path.join(config.cache_file_dir, "schema-" + config.game_mode + "-" + lang)

        if os.path.exists(cachepath) and not self.load_fresh:
            return open(cachepath, "rb").read()
        else:
            dumped = marshal.dumps(gamelib.item_schema._deserialize(self, gamelib.item_schema._download(self, lang)))
            open(cachepath, "wb").write(dumped)
            return dumped

    def _deserialize(self, schema):
        return marshal.loads(schema)

    def __init__(self, lang = None, fresh = False):
        self.load_fresh = fresh
        self.optf2_paints = {}
        paintcache = os.path.join(config.cache_file_dir, "paints-" + config.game_mode)

        gamelib.item_schema.__init__(self, lang)

        if os.path.exists(paintcache) and not self.load_fresh:
            self.optf2_paints = marshal.load(open(paintcache, "rb"))
        else:
            for item in self:
                if item._schema_item.get("name", "").startswith("Paint Can"):
                    for attr in item:
                        if attr.get_name().startswith("set item tint RGB"):
                            self.optf2_paints[int(attr.get_value())] = item.get_schema_id()
            marshal.dump(self.optf2_paints, open(paintcache, "wb"))

def cache_not_stale(row):
    if row and "timestamp" in row:
        return (time() - row["timestamp"]) < config.cache_pack_refresh_interval
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
    profiledb = couch_obj["profiles"]
    uid = str(user.get_id64())

    if not sid.isdigit(): vanitystr = sid

    summary["vanity"] = vanitystr
    summary["_id"] = uid
    summary["timestamp"] = time()

    profiledb.save_doc(summary, force_update = True)

    return user

def load_profile_cached(sid, stale = False):
    profiledb = couch_obj["profiles"]
    sid = str(sid)

    try:
        prow = profiledb[sid]
    except couchdb.ResourceNotFound:
        vres = profiledb.view("views/vanity", include_docs = True, key = sid)
        if len(vres) > 0:
            prow = vres.one()["doc"]
        else:
            return refresh_profile_cache(sid)

    user = steam.user.profile(prow)

    if stale or cache_not_stale(prow):
        return user
    else:
        try:
            return refresh_profile_cache(sid)
        except:
            return user

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
    if lang in schema_obj and not fresh:
        return schema_obj[lang]
    else:
        schema = cached_item_schema(lang = lang, fresh = fresh)
        schema_obj[lang] = schema
        return schema

def refresh_pack_cache(user):
    pack = gamelib.backpack(schema = load_schema_cached(web.ctx.language))
    pack.load(user)
    ts = int(time())
    itemdb = couch_obj["items"]
    packdb = couch_obj["backpacks"]

    try:
        packitems = list(pack)
    except steam.items.ItemError:
        pack.set_schema(load_schema_cached(web.ctx.language, fresh = True))
        packitems = list(pack)

    last_packid = None
    backpack_items = {}

    for item in packitems:
        iid = str(item.get_id())
        item._item["_id"] = iid
        item._item["owner"] = user.get_id64()
        backpack_items[iid] = item._item

    sorteddbkeys = sorted(backpack_items.keys(), key = int)

    packmap = {"_id": str(user.get_id64()), "timestamp": ts,
               "map": sorteddbkeys}
    packdb.save_doc(packmap, force_update = True)

    olditems = itemdb.view("_all_docs", include_docs = True)[sorteddbkeys]
    for item in olditems:
        olditem = item.get("doc")
        if not olditem: continue

        oldid = olditem["_id"]
        newitem = backpack_items.get(oldid)

        if newitem:
            newitem["_rev"] = olditem["_rev"]
            if newitem != olditem:
                backpack_items[oldid]["_rev"] = olditem["_rev"]
            else:
                del backpack_items[oldid]

    itemdb.save_docs(sorted(backpack_items.values(), cmp = lambda x, y: cmp(x["id"], y["id"])))

    return packitems

def get_pack_timeline_for_user(user, tl_size = None):
    """ Returns None if a backpack couldn't be found, returns
    tl_size rows from the timeline
    """

    packdb = couch_obj["backpacks"]

    try:
        return [packdb[str(user.get_id64())]]
    except couchdb.ResourceNotFound:
        return []

def get_pack_snapshot_for_user(user, pid = None):
    """ Returns the backpack snapshot or None if it couldn't be found,
    if id is not given the latest snapshot will be returned."""

    packdb = couch_obj["backpacks"]

    try:
        return packdb[str(user.get_id64())]
    except couchdb.ResourceNotFound:
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
    itemdb = couch_obj["items"]

    try:
        item = itemdb[str(id64)]
    except couchdb.ResourceNotFound:
        return None

    return item

def get_items_for_backpack(backpack):
    itemdb = couch_obj["items"]

    dbitems = itemdb.view("_all_docs", include_docs = True)[backpack]
    realitems = []
    for item in dbitems:
        if "doc" in item:
            realitems.append(item["doc"])

    return realitems

def load_pack_cached(user, stale = False, pid = None):
    thepack = get_pack_snapshot_for_user(user, pid = pid)
    if not stale and not pid:
        if not cache_not_stale(thepack):
            try:
                return refresh_pack_cache(user)
            except: pass
    if thepack:
        schema = load_schema_cached(web.ctx.language)
        dbitems = get_items_for_backpack(thepack["map"])
        return [schema.create_item(item) for item in dbitems]
    return []

def get_user_pack_views(user):
    """ Returns the viewcount of a user's backpack """

    viewdb = couch_obj[config.game_mode + "_viewcounts"]
    uid = str(user.get_id64())
    ip = web.ctx.ip
    ipkey = (uid + "-" + ip)

    try: countdoc = viewdb.get(uid)
    except couchdb.ResourceNotFound: countdoc = {"_id": uid, "c": 0}

    if ipkey not in viewdb:
        viewdb.save_doc({"_id": ipkey})
        countdoc["c"] += 1
        viewdb.save_doc(countdoc)

    return countdoc["c"]

def get_top_pack_views(limit = 10):
    """ Will return the top viewed backpacks sorted in descending order
    no more than limit rows will be returned """

    countdb = couch_obj[config.game_mode + "_viewcounts"]
    result = countdb.view("views/counts", descending = True, limit = limit)

    profiles = []
    for row in result:
        prof = load_profile_cached(row["id"], stale = True)
        profiles.append((row["key"], prof.get_primary_group() == config.valve_group_id, prof.get_persona(), prof.get_id64()))

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
