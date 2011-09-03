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

import config, steam, urllib2, web, os, marshal
import couchdbkit as couchdb
from time import time

gamelib = getattr(steam, config.game_mode)

couch_obj = config.database_server

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

def get_mode_db(name):
    return couch_obj[config.game_mode + "_" + name]

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
        vres = profiledb.view("views/vanity", include_docs = True)[sid]
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
    ts = time()
    itemdb = get_mode_db("items")
    packdb = get_mode_db("backpacks")

    try:
        packitems = list(pack)
    except steam.items.ItemError:
        pack.set_schema(load_schema_cached(web.ctx.language, fresh = True))
        packitems = list(pack)

    last_packid = None
    backpack_items = {}

    for item in packitems:
        iid = str(item.get_id()).decode("utf-8")
        item._item["_id"] = iid
        item._item["owner"] = user.get_id64()
        backpack_items[iid] = item._item

    sorteddbkeys = sorted(backpack_items.keys())

    lastpack = get_pack_snapshot_for_user(user)
    packmap = {"_id": str(user.get_id64()) + "-" + str(ts), "timestamp": ts,
               "map": sorteddbkeys}

    if lastpack:
        if packmap["map"] == lastpack["map"]:
            packdb.delete_doc(lastpack["_id"])

    packdb.save_doc(packmap)

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

    itemdb.save_docs(sorted(backpack_items.values(), key = lambda item: item["_id"]))

    return packitems

def get_pack_timeline_for_user(user, tl_size = None):
    """ Returns None if a backpack couldn't be found, returns
    tl_size rows from the timeline
    """

    packdb = get_mode_db("backpacks")

    try:
        uid = str(user.get_id64())
        results = packdb.view("views/timeline", limit = tl_size, descending = True)[[uid, {}]:[uid]]
        return [res["key"][1] for res in results]
    except couchdb.ResourceNotFound:
        return []

def get_pack_snapshot_for_user(user, pid = None):
    """ Returns the backpack snapshot or None if it couldn't be found,
    if id is not given the latest snapshot will be returned."""

    packdb = get_mode_db("backpacks")

    try:
        tspart = pid
        if not tspart: tspart = str(get_pack_timeline_for_user(user, tl_size = 1)[0])

        return packdb[str(user.get_id64()) + '-' + tspart]
    except couchdb.ResourceNotFound:
        return None
    except IndexError:
        return None

def fetch_item_for_id(id64):
    itemdb = get_mode_db("items")

    try:
        item = itemdb[str(id64)]
    except couchdb.ResourceNotFound:
        return None

    return item

def get_items_for_backpack(backpack):
    itemdb = get_mode_db("items")

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

    viewdb = get_mode_db("viewcounts")
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

    countdb = get_mode_db("viewcounts")
    result = countdb.view("views/counts", descending = True, limit = limit)
    counts = {}
    for count in result: counts[count["id"]] = count["key"]

    profiles = []
    for row in couch_obj["profiles"].view("_all_docs", include_docs = True)[[doc["id"] for doc in result]]:
        prof = steam.user.profile(row["doc"])
        profiles.append((counts[row["id"]], prof.get_primary_group() == config.valve_group_id, prof.get_persona(), prof.get_id64()))

    return profiles
