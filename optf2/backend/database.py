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

import web
import pylibmc
import operator
from time import time
from binascii import crc32
# For temporary schema object store
import cPickle as pickle
import os
import json

import steam
from optf2.backend import config
from optf2.backend import log
import items as itemtools
from urlparse import urljoin

def _(thestring):
    return web.utils.safestr(thestring)

def hilo_to_ugcid64(hi, lo):
    return (int(hi) << 32) | int(lo)

virtual_root = config.ini.get("resources", "virtual-root")
app_aliases = dict(config.ini.items("app-aliases"))

memcached = pylibmc.Client([config.ini.get("cache", "memcached-address")], binary = True,
                           behaviors = {"tcp_nodelay": True,
                                        "ketama": True})
memc = pylibmc.ThreadMappedPool(memcached)

STATIC_PREFIX = config.ini.get("resources", "static-prefix")
CACHE_DIR = config.ini.get("resources", "cache-dir")
STEAM_TIMEOUT = config.ini.getfloat("steam", "connect-timeout")
CACHE_COMPRESS_LEN = config.ini.getint("cache", "compress-len")

class CacheError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return str(self.msg)

class CacheEmptyError(CacheError):
    def __init__(self, msg):
        CacheError.__init__(self, msg)

def verify_lang(code = None):
    try:
        code = steam.loc.language(code).code
    except steam.loc.LangErrorUnsupported:
        code = "en_US"

    return code

def dict_from_item(item, scope = 440, lang = None):
    if not item:
        return None

    default_cell_image = STATIC_PREFIX + "item_icons/Invalid_icon.png";
    newitem = dict(sid = item.schema_id)
    appid = scope
    language = verify_lang(lang)
    ugc_key = "ugc-{0}"
    iid = item.id
    oid = item.original_id
    pos = item.position
    equipped = item.equipped
    equipable = item.equipable_classes
    slot = item.slot_name
    caps = item.capabilities
    rank = (item.rank or {}).get("name")
    itype = item.type
    cdesc = item.custom_description
    desc = item.description
    cname = item.custom_name
    qty = item.quantity
    quality_str = item.quality[1]
    iclass = item.cvar_class or ''
    category = None
    try: category = item.category
    except AttributeError: pass
    imgsmall = item.icon
    imglarge = item.image
    untradable = not item.tradable
    uncraftable = not item.craftable
    styles = item.available_styles
    style = item.style
    origin = item.origin
    gift_giver = None

    if iid != None: newitem["id"] = iid
    if oid != None and (oid != iid): newitem["oid"] = oid
    if pos != None and (pos > 0): newitem["pos"] = pos
    # token class search is a workaround, they tend to be in weird slots
    if (iclass.find("token") == -1) and slot != None:
        newitem["slot"] = str(slot)
    if rank: newitem["rank"] = rank
    if itype and not itype.startswith("TF_"): newitem["type"] = itype
    if equipped: newitem["equipped"] = equipped
    if cdesc or desc: newitem["desc"] = cdesc or desc
    if cname: newitem["cname"] = True
    if cdesc: newitem["cdesc"] = True
    if qty > 1: newitem["qty"] = qty
    if quality_str: newitem["quality"] = quality_str
    # May need string->ID swapper
    if equipable: newitem["equipable"] = [itemtools.get_class_for_id(c, appid)[0] for c in equipable]
    # Certain items will be part of a category system, this is used for advanced paging
    if category: newitem["cat"] = category
    newitem["image"] = imgsmall or default_cell_image
    newitem["imagelarge"] = imglarge or newitem["image"]
    if not untradable: newitem["tradable"] = True
    if not uncraftable: newitem["craftable"] = True
    if style: newitem["style"] = style
    if origin: newitem["origin"] = origin

    # Conditional processing based on whether or not the item is unique or potentially schema only
    if not iid and not origin:
        if styles: newitem["styles"] = styles
        if caps: newitem["caps"] = caps

    custom_texture_lo = None
    custom_texture_hi = None

    attrs = item.attributes
    try:
        namecolor = item.name_color
        if namecolor:
            newitem["namergb"] = namecolor
    except AttributeError: pass
    min_level = item.min_level
    max_level = item.max_level
    pb_level = item.level
    giftcontents = item.contents
    contents_line_rendered = False

    if pb_level != None:
        newitem["level"] = str(pb_level)
    elif min_level != None and max_level != None:
        if min_level == max_level:
            newitem["level"] = str(min_level)
        else:
            newitem["level"] = str(min_level) + "-" + str(max_level)

    # Ordered kill eater attribute lines
    linefmt = u"{0[1]}: {0[2]}"
    eaters = item.kill_eaters
    if eaters: newitem["eaters"] = map(linefmt.format, eaters)

    for theattr in attrs:
        attrname = theattr.name
        attrid = theattr.id
        attrvaluetype = theattr.value_type
        attrdesc = theattr.formatted_description
        attrvalue = theattr.formatted_value
        newattr = {"id": attrid, "val": attrvalue, "type": theattr.type}
        account_info = theattr.account_info
        if account_info:
            if attrname == "gifter account id":
                gift_giver = account_info
                newitem["gifter"] = account_info

            newitem.setdefault("accounts", {})
            newitem["accounts"][attrid] = account_info
        filtered = theattr.hidden

        # referenced item def
        if not contents_line_rendered and (attrid == 194 or attrid == 192 or attrid == 193):
            desc = "Contains: "
            if not giftcontents:
                giftcontents = int(theattr.value)
                desc += "Schema item " + str(giftcontents)
            else:
                desc += '<span class="prefix-{0}">{1}</span>'.format(giftcontents.quality[1],
                                                                     web.websafe(giftcontents.full_name.decode("utf-8")))
            attrdesc = desc
            filtered = False
            contents_line_rendered = True

        elif attrname.startswith("set item tint RGB"):
            raw_rgb = int(theattr.value)
            newitem.setdefault("colors", [])
            nthcolor = attrname[attrname.rfind(' ') + 1:]
            paint_map = cache.get("paints-{0}-{1}".format(appid, language), {})

            try: colori = int(nthcolor)
            except ValueError: colori = 0

            # Workaround for Team Spirit values still being 1
            if raw_rgb == 1:
                raw_rgb = 12073019
                item_color = "#B8383B"
                color_2 = "#256D8D"
                newitem["colors"].append((0, item_color))
                newitem["colors"].append((2, color_2))
            else:
                item_color = "#{0:02X}{1:02X}{2:02X}".format((raw_rgb >> 16) & 0xFF,
                                                             (raw_rgb >> 8) & 0xFF,
                                                             (raw_rgb) & 0xFF)
                newitem["colors"].append((colori, item_color))
                newitem["colors"].sort()

            pname = paint_map.get(raw_rgb, item_color)

            newitem["paint_name"] = pname

            # Workaround until the icons for colored paint cans are correct
            if ((colori == 0) and
                item._schema_item.get("name", "").startswith("Paint Can") and
                raw_rgb != 0):
                paintcan_url = "{0}item_icons/Paint_Can_{1}.png".format(STATIC_PREFIX,
                                                                        item_color[1:])

                full_paintcan_url = urljoin(STATIC_PREFIX, paintcan_url)
                newitem["image"] = full_paintcan_url
                newitem["imagelarge"] = full_paintcan_url

            filtered = True

        elif attrname.startswith("attach particle effect"):
            particle_map = cache.get("particles-{0}-{1}".format(appid, language), {})
            particleid = int(theattr.value)
            default = "unknown particle ({0})".format(particleid)
            pname = particle_map.get(particleid, default)

            newitem["pid"] = particleid
            attrdesc = "Effect: " + pname

        elif attrname == "unique craft index":
            value = int(theattr.value)
            newitem["craftno"] = value
            attrdesc = "Craft number: " + str(value)
            filtered = False

        elif attrname == "tradable after date":
            filtered = False

        elif attrname == "set supply crate series":
            newitem["series"] = int(theattr.value)

        elif attrname == "custom texture lo":
            custom_texture_lo = theattr.value

        elif attrname == "custom texture hi":
            custom_texture_hi = theattr.value

        if attrvaluetype == "account_id" and account_info:
            attrdesc = _(theattr.description.replace("%s1", account_info["persona"]))
            filtered = False

        if not filtered:
            if attrdesc: newattr["desc"] = attrdesc
        else:
            continue

        try:
            attrcolor = theattr.description_color
            if attrcolor: newattr["color"] = attrcolor
        except AttributeError: pass

        newitem.setdefault("attrs", [])
        newitem["attrs"].append(newattr)

    if giftcontents:
        newitem["contents"] = dict_from_item(giftcontents, scope, lang)
        newitem["contents"]["container"] = iid
        # TODO: Redundant maybe since it's already in container dict?
        if gift_giver: newitem["contents"]["gifter"] = gift_giver

    if custom_texture_hi != None and custom_texture_lo != None:
        ugcid = hilo_to_ugcid64(custom_texture_hi, custom_texture_lo)
        try:
            if appid:
                memkey = ugc_key.format(str(ugcid))
                url = cache.get(memkey)
                if not url:
                    url = steam.remote_storage.ugc_file(appid, ugcid).url
                    cache.set(memkey, url)
                newitem["texture"] = url
        except steam.remote_storage.UGCError:
            pass

    normal_item_name = web.websafe(item.full_name)
    basename = item.name

    newitem["mainname"] = _(normal_item_name).decode("utf-8")

    newitem["basename"] = basename

    return newitem

class cache(object):
    @staticmethod
    def get(value, default = None):
        """ Simple cache getter """

        value = str(value).encode("ascii")

        with memc.reserve() as mc:
            try:
                val = mc.get(value)
                if val != None: return val
                else: return default
            except pylibmc.Error as E:
                log.main.error(str(value) + ": " + str(E))
                return default

    @staticmethod
    def set(key, value, **kwargs):
        """ Simple cache setter """

        key = str(key).encode("ascii")

        try:
            with memc.reserve() as mc:
                mc.set(key, value, min_compress_len = CACHE_COMPRESS_LEN, **kwargs)
        except pylibmc.Error as E:
            log.main.error(str(key) + ": " + str(E))

class assets(object):
    def __init__(self, scope = 440, lang = None):
        self._scope = scope
        self._lang = verify_lang(lang)
        self._assets_cache = "assets-{0}-{1}".format(self._scope, self._lang)
        self._assets = None

    def dump(self):
        assetlist = steam.items.assets(self._scope, lang = self._lang)

        try:
            self._assets = dict([(int(asset.name), asset.price)
                                 for asset in assetlist])

            cache.set(self._assets_cache, self._assets)
        except Exception as E:
            log.main.error("Error loading assets: {0}".format(E))

        return self._assets

    def load(self):
        ass = cache.get(self._assets_cache)
        if not ass:
            ass = self.dump()

        self._assets = ass

        return self._assets

    @property
    def price_map(self):
        return self.load()

class schema(object):
    def __init__(self, scope = 440, lang = None):
        self._scope = scope
        self._lang = verify_lang(lang)
        app = self._scope
        lang = self._lang

        self._cdir = CACHE_DIR
        self._items_cache = "schema-items-{0}-{1}".format(app, lang)
        self._schema_cache = "schema-{0}-{1}".format(app, lang)
        self._client_schema_cache = "client-schema-{0}".format(app)
        self._particle_key = "particles-{0}-{1}".format(app, lang)
        self._quality_key = "qualities-{0}-{1}".format(app, lang)
        self._paints_key = "paints-{0}-{1}".format(app, lang)
        self._schema = None

    def _build_client_schema_specials(self):
        schema = self.load()

        cs = schema.client_url
        special = {}

        if not cs:
            return special

        req = steam.api.http_downloader(str(cs), timeout = STEAM_TIMEOUT)

        try:
            clients = steam.vdf.loads(req.download())["items_game"]
        except:
            return special

        prefabs = clients.get("prefabs", {})
        colors = clients.get("colors", {})
        csitems = clients.get("items", {})

        for sitem in schema:
            sid = sitem.schema_id
            item = csitems.get(str(sid))
            clientstuff = {}

            if not item:
                continue

            prefab = item.get("prefab", {})
            if prefab:
                prefab = prefabs.get(prefab, {})

            item = dict(prefab.items() + item.items())

            rarity_name = item.get("item_rarity", '')
            rarity = colors.get("desc_" + rarity_name)
            if rarity:
                tpl = rarity.get("hex_color")
                clientstuff["rarity"] = rarity_name
                if tpl and tpl.startswith('#'): tpl = tpl[1:]
                clientstuff["rarity_color"] = tpl

            slot = item.get("item_slot")
            if slot and not sitem.slot_name:
                clientstuff["slot"] = slot

            usedby = item.get("used_by_heroes", item.get("used_by_classes", {}))
            if usedby and not sitem.equipable_classes:
                clientstuff["used_by"] = usedby.keys()

            if clientstuff:
                special[sid] = clientstuff

        json.dump(special, open(os.path.join(self._cdir, self._client_schema_cache), "w"))
        return special

    @property
    def client_schema_specials(self):
        """ TODO: Temporary, because ugly """
        try:
            specials = json.load(open(os.path.join(self._cdir, self._client_schema_cache), "r"))
        except IOError:
            specials = self._build_client_schema_specials()

        return specials

    def _build_item_store(self):
        if not self._schema:
            schema = self.load()
        else:
            schema = self._schema

        sitems = {}
        for item in (schema or []):
            sitems[item.schema_id] = dict_from_item(item, self._scope, self._lang)

        if sitems:
            json.dump(sitems, open(os.path.join(self._cdir, self._items_cache), "wb"))

        return sitems

    def _build_paint_store(self):
        if not self._schema:
            schema = self.load()
        else:
            schema = self._schema

        pmap = {}
        for item in schema:
            # Look at tool metadata to determine if this is a paint can
            metadata = item.tool_metadata
            if metadata and metadata.get("type") == "paint_can":
                for attr in item:
                    if attr.name.startswith("set item tint RGB"):
                        pmap[int(attr.value)] = item.name
        cache.set(str(self._paints_key), pmap)

        return pmap

    def _build_particle_store(self):
        if not self._schema:
            schema = self.load()
        else:
            schema = self._schema

        particles = schema.particle_systems
        pmap = dict([(k, v["name"]) for k, v in particles.iteritems()])
        cache.set(str(self._particle_key), pmap)

        return pmap

    def _build_quality_store(self):
        if not self._schema:
            schema = self.load()
        else:
            schema = self._schema

        qualities = schema.qualities or {}
        qmap = dict([(strn, locn) for id, strn, locn in qualities.values()])
        cache.set(self._quality_key, qmap)

        return qmap

    def dump(self):
        schema = steam.items.schema(self._scope, lang = self._lang, timeout = STEAM_TIMEOUT)
        self._schema = schema

        try:
            self._build_paint_store()
            self._build_particle_store()
            self._build_quality_store()
            self._build_item_store()
        except steam.api.HTTPError:
            self._schema = None
            schema = None
        except Exception as E:
            log.main.error("Error loading schema: {0}".format(E))
            self._schema = None
            schema = None

        if schema:
            pickle.dump(schema, open(os.path.join(self._cdir, self._schema_cache), "wb"), pickle.HIGHEST_PROTOCOL)

        return schema

    def load(self):
        try:
            schema = pickle.load(open(os.path.join(self._cdir, self._schema_cache)))
        except:
            schema = self.dump()

        self._schema = schema

        if not schema:
            raise itemtools.ItemBackendUnimplemented(self._scope)

        return schema

    @property
    def attributes(self):
        return self.load().attributes

    @property
    def particle_systems(self):
        return self.load().particle_systems

    @property
    def paints(self):
        p = cache.get(self._paints_key)
        if not p:
            return self._build_paint_store()

    @property
    def particles(self):
        p = cache.get(self._particle_key)
        if not p:
            return self._build_particle_store()

    @property
    def processed_items(self):
        try:
            return json.load(open(os.path.join(self._cdir, self._items_cache)))
        except IOError:
            return self._build_item_store()

    @property
    def qualities(self):
        q = cache.get(self._quality_key)
        if not q:
            q = self._build_quality_store()

        return q

class inventory(object):
    def __init__(self, prof, scope = 440, lang = None):
        self._user = prof
        self._lang = verify_lang(lang)
        self._scope = scope
        self._deserialized = None
        self._cache_time = config.ini.getint("cache", "backpack-expiry")
        self._cache_key = "backpack-{0}-{1}".format(self._scope, self.owner)

    def _cache_commit(self, inventory):
        cache.set(self._cache_key, inventory, time = self._cache_time)

    @staticmethod
    def build_processed(inv, scope = 440, lang = None):
        lang = verify_lang(lang)
        pack = {"items": {},
                "cells": inv.cells_total}

        for item in inv:
            pitem = dict_from_item(item, scope, lang)
            pack["items"][item.id] = pitem

        return pack

    def dump(self):
        owner = self.owner
        item_schema = schema(self._scope, self._lang).load()
        bp = steam.items.inventory(self._scope, owner, schema = item_schema, timeout = STEAM_TIMEOUT)

        inventory = self.build_processed(bp, self._scope, self._lang)

        self._cache_commit(inventory)

        return inventory

    def load(self):
        bp = cache.get(self._cache_key)
        if not bp:
            return self.dump()
        else:
            return bp

    @property
    def owner(self):
        """ Returns the user dict associated with this inventory """
        try:
            self._user = self._user.load()
        except AttributeError:
            try:
                self._user = self._user["id64"]
            except:
                pass

        return self._user

class sim_context(object):
    def __init__(self, prof):
        try:
            self._user = prof["id64"]
        except:
            try:
                self._user = prof.id64
            except:
                self._user = str(prof)

        self._cache_key = "invctx-" + str(self._user)
        self._cache_lifetime = config.ini.getint("cache", "inventory-list-expiry")

    def __iter__(self):
        cl = self.load()

        i = 0
        while i < len(cl):
            j = i
            i += 1
            yield cl[j]

    def _populate_navlinks(self):
        try:
            context = cache.get(self._cache_key)
            web.ctx.navlinks = [
                        (c["name"], "{0}{1[appid]}/user/{2}".format(virtual_root, c, self._user))
                        for c in (context or [])
                    ]
        except:
            pass

    def dump(self):
        context = list(steam.sim.inventory_context(self._user, timeout = STEAM_TIMEOUT))
        cache.set(self._cache_key, context, time = self._cache_lifetime)

        return context

    def load(self):
        context = cache.get(self._cache_key)

        if not context:
            context = self.dump()

        self._populate_navlinks()
        return context

class sim_inventory(inventory):
    """ Inventories sourced from the steam inventory manager """
    def __init__(self, user_or_id, scope = 440):
        self._context = None

        if isinstance(user_or_id, sim_context):
            self._context = user_or_id
            user_or_id = self._context._user

        super(sim_inventory, self).__init__(user_or_id, scope)

        if not self._context:
            self._context = sim_context(self.owner)

    def dump(self):
        mid = str(self._scope)
        inv = None

        appctx = None
        for c in self._context:
            if mid == str(c["appid"]):
                appctx = c
                break

        if not appctx:
            raise steam.items.InventoryError("Can't find inventory for SIM:" + str(mid) + " in this backpack.")

        try:
            inv = steam.sim.inventory(appctx, self.owner, timeout = STEAM_TIMEOUT)
        except:
            raise steam.items.InventoryError("SIM inventory not found or unavailable")

        output = self.build_processed(inv, self._scope, self._lang)

        self._cache_commit(output)

        return output

class user(object):
    def __init__(self, sid):
        self._sid = sid
        self._vanity_key = "vanity-" + str(crc32(self._sid))
        self._valve_group_id64 = config.ini.get("steam", "valve-group-id")

    @staticmethod
    def load_from_profile(prof):
        profile = {"id64": prof.id64,
                   "realname": prof.real_name,
                   "persona": prof.persona,
                   "avatarurl": prof.avatar_medium,
                   "status": prof.status,
                   "group": prof.primary_group}

        if prof.visibility != 3:
            profile["private"] = True

        # If app ID is set
        if prof.current_game[0]:
            profile["game"] = prof.current_game

        memkey = "profile-{0[id64]}".format(profile)
        cache.set(memkey, profile, time = config.ini.getint("cache", "profile-expiry"))

        return profile

    @staticmethod
    def resolve_id(id):
        """ Resolves the ID given at instantiation to
        a valid ID64 if one exists """
        resolved = None

        # Hashing due do non-ASCII names
        vanitykey = "vanity-" + str(crc32(id))
        resolved = cache.get(vanitykey)
        if not resolved:
            vanity = steam.user.vanity_url(id)
            resolved = vanity.id64
            cache.set(vanitykey, resolved)

        return resolved

    def load(self):
        sid = self._sid
        memkey = "profile-" + str(sid)

        profile = cache.get(memkey)

        if not profile:
            return self.dump()
        else:
            return profile

    def dump(self):
        sid = str(self._sid)
        prof = None

        if sid.isdigit():
            try:
                prof = steam.user.profile(sid)
            except steam.user.ProfileError:
                pass

        if not prof:
            try:
                prof = steam.user.profile(self.resolve_id(sid))
            except steam.user.VanityError as E:
                raise steam.user.ProfileError(str(E))

        profile = self.load_from_profile(prof)
        self._sid = profile["id64"]

        return profile

class recent_inventories(object):
    def __init__(self, scope = 440):
        self._recent_packs_key = "lastpacks-" + str(scope)
        self._inv_list = []

    def __iter__(self):
        return self.next()

    def next(self):
        if not self._inv_list:
            self._inv_list = cache.get(self._recent_packs_key, [])

        i = 0
        while i < len(self._inv_list):
            j = i
            i += 1
            yield self._inv_list[j]

    def update(self, profile, maxsize = 10):
        try:
            userp = profile.load()
        except AttributeError:
            userp = profile

        lastpackskey = self._recent_packs_key
        lastpacks = cache.get(lastpackskey, [])
        id64 = userp["id64"]

        for p in lastpacks:
            if p["id"] == id64:
                lastpacks.remove(p)
                break

        lastpacks.insert(0, dict(id = id64, persona = userp["persona"],
                                 avatar = userp["avatarurl"]))

        self._inv_list = lastpacks[:maxsize]
        cache.set(lastpackskey, self._inv_list)

def load_inventory(sid, scope):
    profile = user(sid).load()

    try:
        pack = inventory(profile, scope = scope).load()
    except itemtools.ItemBackendUnimplemented:
        pack = sim_inventory(profile, scope = scope).load()

    # TODO: This is just to update the navbar if applicable, could be better
    try:
        sim_context(profile)._populate_navlinks()
    except:
        pass

    recent_inventories(scope).update(profile)

    return profile, pack
