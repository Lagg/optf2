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

inv_graylist = map(operator.itemgetter(0), config.ini.items("inv-graylist"))
virtual_root = config.ini.get("resources", "virtual-root")

qualitydict = {"unique": "The",
               "normal": ""}

memcached = pylibmc.Client([config.ini.get("cache", "memcached-address")], binary = True,
                           behaviors = {"tcp_nodelay": True,
                                        "ketama": True})
memc = pylibmc.ThreadMappedPool(memcached)

STATIC_PREFIX = config.ini.get("resources", "static-prefix")
CACHE_DIR = config.ini.get("resources", "cache-dir")
STEAM_TIMEOUT = config.ini.getfloat("steam", "connect-timeout")

class CacheError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return str(self.msg)

class CacheEmptyError(CacheError):
    def __init__(self, msg):
        CacheError.__init__(self, msg)

class cache(object):
    """ Cache retrieval/setting functions """

    def get(self, value, default = None):
        value = str(value).encode("ascii")

        with memc.reserve() as mc:
            try:
                val = mc.get(value)
                if val != None: return val
                else: return default
            except pylibmc.Error as E:
                log.main.error(str(value) + ": " + str(E))
                return default

    @property
    def scope(self):
        return self._mod_id

    @property
    def lang(self):
        return self._language

    def set(self, key, value, **kwargs):
        key = str(key).encode("ascii")

        try:
            with memc.reserve() as mc:
                mc.set(key, value, min_compress_len = self._compress_len, **kwargs)
        except pylibmc.Error as E:
            log.main.error(str(key) + ": " + str(E))

    def _build_processed_item(self, item):
        if not item: return None

        default_cell_image = STATIC_PREFIX + "item_icons/Invalid_icon.png";
        newitem = dict(sid = item.get_schema_id())
        appid = None
        mod = self.scope
        language = self.lang
        try: appid = getattr(steam, mod)._APP_ID
        except AttributeError: pass
        ugc_key = "ugc-{0}"
        iid = item.get_id()
        oid = item.get_original_id()
        pos = item.get_position()
        equipped = item.get_equipped_slots()
        equipable = item.get_equipable_classes()
        slot = item.get_slot()
        caps = item.get_capabilities()
        rank = (item.get_rank() or {}).get("name")
        itype = item.get_type()
        cdesc = item.get_custom_description()
        desc = item.get_description()
        cname = item.get_custom_name()
        qty = item.get_quantity()
        quality_str = item.get_quality()["str"]
        iclass = item.get_class() or ''
        category = None
        try: category = item.get_category_name()
        except AttributeError: pass
        imgsmall = item.get_image(item.ITEM_IMAGE_SMALL)
        imglarge = item.get_image(item.ITEM_IMAGE_LARGE)
        untradable = item.is_untradable()
        uncraftable = item.is_uncraftable()
        styles = item.get_styles()
        style = item.get_current_style_name()
        origin = item.get_origin_name()
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
        if equipable: newitem["equipable"] = [itemtools.get_class_for_id(c, mod)[0] for c in equipable]
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

        attrs = item.get_attributes()
        try:
            namecolor = item.get_name_color()
            if namecolor:
                newitem["namergb"] = namecolor
        except AttributeError: pass
        min_level = item.get_min_level()
        max_level = item.get_max_level()
        pb_level = item.get_level()
        giftcontents = item.get_contents()

        if pb_level != None:
            newitem["level"] = str(pb_level)
        elif min_level != None and max_level != None:
            if min_level == max_level:
                newitem["level"] = str(min_level)
            else:
                newitem["level"] = str(min_level) + "-" + str(max_level)

        # Ordered kill eater attribute lines
        linefmt = "{0[1]}: {0[2]}"
        eaters = item.get_kill_eaters()
        if eaters: newitem["eaters"] = map(linefmt.format, eaters)

        for theattr in attrs:
            attrname = theattr.get_name()
            attrid = theattr.get_id()
            attrvaluetype = theattr.get_value_type()
            attrdesc = theattr.get_description_formatted()
            attrvalue = theattr.get_value_formatted()
            newattr = dict(id = attrid, val = attrvalue,
                           type = theattr.get_type())
            account_info = theattr.get_account_info()
            if account_info:
                if attrname == "gifter account id":
                    gift_giver = account_info
                    newitem["gifter"] = account_info

                newitem.setdefault("accounts", {})
                newitem["accounts"][attrid] = account_info
            filtered = theattr.is_hidden()

            if attrname == "referenced item def":
                desc = "Contains: "
                if not giftcontents:
                    giftcontents = int(theattr.get_value())
                    desc += "Schema item " + str(giftcontents)
                else:
                    desc += '<span class="prefix-{0}">{1}</span>'.format(giftcontents.get_quality()["str"],
                                                                         web.websafe(giftcontents.get_full_item_name(prefixes = qualitydict)))
                attrdesc = desc
                filtered = False

            elif attrname.startswith("set item tint RGB"):
                raw_rgb = int(theattr.get_value())
                newitem.setdefault("colors", [])
                nthcolor = attrname[attrname.rfind(' ') + 1:]
                paint_map = self.get(str("paints-" + mod + '-' + language), {})

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
                particle_map = self.get(str("particles-" + mod + '-' + language), {})
                particleid = int(theattr.get_value())
                default = "unknown particle ({0})".format(particleid)
                pname = particle_map.get(particleid, default)

                newitem["pid"] = particleid
                attrdesc = "Effect: " + pname

            elif attrname == "unique craft index":
                value = int(theattr.get_value())
                newitem["craftno"] = value
                attrdesc = "Craft number: " + str(value)
                filtered = False

            elif attrname == "tradable after date":
                filtered = False

            elif attrname == "set supply crate series":
                newitem["series"] = int(theattr.get_value())

            elif attrname == "custom texture lo":
                custom_texture_lo = theattr.get_value()

            elif attrname == "custom texture hi":
                custom_texture_hi = theattr.get_value()

            if attrvaluetype == "account_id" and account_info:
                attrdesc = _(theattr.get_description().replace("%s1", account_info["persona"]))
                filtered = False

            if not filtered:
                if attrdesc: newattr["desc"] = attrdesc
            else:
                continue

            try:
                attrcolor = theattr.get_description_color()
                if attrcolor: newattr["color"] = attrcolor
            except AttributeError: pass

            newitem.setdefault("attrs", [])
            newitem["attrs"].append(newattr)

        if giftcontents:
            newitem["contents"] = self._build_processed_item(giftcontents)
            newitem["contents"]["container"] = iid
            # TODO: Redundant maybe since it's already in container dict?
            if gift_giver: newitem["contents"]["gifter"] = gift_giver

        if custom_texture_hi != None and custom_texture_lo != None:
            ugcid = hilo_to_ugcid64(custom_texture_hi, custom_texture_lo)
            try:
                if appid:
                    memkey = ugc_key.format(str(ugcid))
                    url = self.get(memkey)
                    if not url:
                        url = steam.remote_storage.user_ugc(appid, ugcid).get_url()
                        self.set(memkey, url)
                    newitem["texture"] = url
            except steam.remote_storage.UGCError:
                pass

        normal_item_name = web.websafe(item.get_full_item_name(prefixes = qualitydict))
        possessive_item_name = web.websafe(item.get_full_item_name({"normal": None, "unique": None}))
        basename = item.get_name()

        newitem["ownedname"] = _(possessive_item_name)

        newitem["mainname"] = _(normal_item_name)

        newitem["basename"] = basename

        return newitem

    def __init__(self, mode = "tf2", language = None):
        """ modid and language will be set to their respective values in web.ctx if not given """

        clang = language or web.ctx.get("language", "en_US")

        try: code, name = steam.get_language(clang)
        except steam.LangErrorUnsupported: code, name = steam.get_language()

        self._language = code
        self._mod_id = str(mode)
        self._compress_len = config.ini.getint("cache", "compress-len")

class assets(object):
    def __init__(self, cache):
        self._cache = cache
        self._app = cache.scope
        self._lang = cache.lang
        self._assets_cache = "assets-{0}-{1}".format(self._app, self._lang)
        self._assets = None

    def dump(self):
        try:
            mod = getattr(steam, self._app)
            assetlist = mod.assets(lang = self._lang)
        except AttributeError:
            try:
                appid = mod._APP_ID
                assetlist = steam.items.assets(appid, lang = self._lang)
            except:
                return None

        try:
            self._assets = dict([(int(asset.get_name()), asset.get_price())
                                 for asset in assetlist])

            self._cache.set(self._assets_cache, self._assets)
        except Exception as E:
            log.main.error("Error loading assets: {0}".format(E))

        return self._assets

    def load(self):
        ass = self._cache.get(self._assets_cache)
        if not ass:
            ass = self.dump()

        self._assets = ass

        return self._assets

    @property
    def price_map(self):
        return self.load()

class schema(object):
    def __init__(self, cache):
        self._cache = cache
        self._app = cache.scope
        self._lang = cache.lang
        app = self._app
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
        if not self._schema:
            schema = self.load()
        else:
            schema = self._schema

        cs = schema.get_client_schema_url()
        special = {}

        if not cs:
            return special

        # TODO: Make VDF specific handler in steamodd, and generic handler
        req = steam.json_request(str(cs), timeout = 3, data_timeout = 5)

        try:
            clients = steam.vdf.loads(req._download())["items_game"]
        except:
            return special

        prefabs = clients.get("prefabs", {})
        colors = clients.get("colors", {})
        csitems = clients.get("items", {})

        for sitem in schema:
            sid = sitem.get_schema_id()
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
            if slot and not sitem.get_slot():
                clientstuff["slot"] = slot

            usedby = item.get("used_by_heroes", item.get("used_by_classes", {}))
            if usedby and not sitem.get_equipable_classes():
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
            sitems[item.get_schema_id()] = self._cache._build_processed_item(item)

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
            if item._schema_item.get("name", "").find("Paint") != -1:
                for attr in item:
                    if attr.get_name().startswith("set item tint RGB"):
                        pmap[int(attr.get_value())] = item.get_name()
        self._cache.set(str(self._paints_key), pmap)

        return pmap

    def _build_particle_store(self):
        if not self._schema:
            schema = self.load()
        else:
            schema = self._schema

        particles = schema.get_particle_systems()
        pmap = dict([(k, v["name"]) for k, v in particles.iteritems()])
        self._cache.set(str(self._particle_key), pmap)

        return pmap

    def _build_quality_store(self):
        if not self._schema:
            schema = self.load()
        else:
            schema = self._schema

        qualities = schema.get_qualities() or {}
        qmap = dict([(q["str"], q["prettystr"]) for q in qualities.values()])
        self._cache.set(self._quality_key, qmap)

        return qmap

    def dump(self):
        try:
            schema = getattr(steam, str(self._app)).item_schema(lang = self._lang, timeout = STEAM_TIMEOUT)
        except AttributeError:
            schema = steam.items.schema(self._app, lang = self._lang, timeout = STEAM_TIMEOUT)

        self._schema = schema

        try:
            self._build_paint_store()
            self._build_particle_store()
            self._build_quality_store()
            self._build_item_store()
        except steam.HttpError:
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
        return schema

    @property
    def attributes(self):
        return self.load().get_attributes()

    @property
    def particle_systems(self):
        return self.load().get_particle_systems()

    @property
    def paints(self):
        p = self._cache.get(self._paints_key)
        if not p:
            return self._build_paint_store()

    @property
    def particles(self):
        p = self._cache.get(self._particle_key)
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
        q = self._cache.get(self._quality_key)
        if not q:
            return self._build_quality_store()

class inventory(object):
    @property
    def _cached_backpack(self):
        if not self._deserialized:
            self._deserialized = self._cache.get(self._cache_key)

        return self._deserialized

    @property
    def _cache_key(self):
        return "backpack-{0}-{1[id64]}".format(self._cache.scope, self.owner)

    def _commit_to_cache(self, inventory):
        self._cache.set(self._cache_key, inventory, time = self._cache_time)

        if inventory.get("items"):
            recent_packs = recent_inventories(self._cache)
            recent_packs.update(self.owner)

    #@staticmethod
    def build_processed(self, inv):
        pack = {"items": {},
                "cells": inv.get_total_cells()}

        for item in inv:
            pitem = self._cache._build_processed_item(item)
            pack["items"][item.get_id()] = pitem

        return pack

    def dump(self):
        scope = self._cache.scope
        owner = self.owner
        bp = None

        try:
            pack_class = getattr(steam, scope).backpack
            item_schema = schema(self._cache).load()
            bp = pack_class(owner["id64"], schema = item_schema, timeout = STEAM_TIMEOUT)
        except AttributeError:
            raise itemtools.ItemBackendUnimplemented(scope)

        inventory = self.build_processed(bp)

        self._commit_to_cache(inventory)

        return inventory

    def load(self):
        return self._cached_backpack or self.dump()

    @property
    def owner(self):
        """ Returns the user dict associated with this inventory """
        try:
            return self._user.load()
        except AttributeError:
            return self._user

    def _store(self, bp):
        modulename = self._cache.scope

        return pack

    def __init__(self, cache, prof):
        self._user = prof
        self._cache = cache
        self._deserialized = None
        self._cache_time = config.ini.getint("cache", "backpack-expiry")

class sim_context(object):
    def __init__(self, cache, prof):
        try:
            self._user = prof["id64"]
        except:
            try:
                self._user = prof.id64
            except:
                self._user = str(prof)

        self._cache_key = "invctx-" + str(self._user)
        self._cache_lifetime = config.ini.getint("cache", "inventory-list-expiry")
        self._deserialized = None
        self._cache = cache

    def __iter__(self):
        cl = self.load()

        i = 0
        while i < len(cl):
            j = i
            i += 1
            yield cl[j]

    def _populate_navlinks(self, context):
        try:
            web.ctx.navlinks = [
                        (c["name"], "{0}{1[appid]}/user/{2}".format(virtual_root, c, self._user))
                        for c in (context or [])
                        if str(c["appid"]) not in inv_graylist
                    ]
        except:
            pass

    def dump(self):
        context = list(steam.sim.backpack_context(self._user, timeout = STEAM_TIMEOUT))
        self._cache.set(self._cache_key, context, time = self._cache_lifetime)

        self._deserialized = context

        return context

    def load(self):
        if self._deserialized:
            self._populate_navlinks(self._deserialized)
            return self._deserialized

        context = self._cache.get(self._cache_key)

        if not context:
            context = self.dump()

        self._populate_navlinks(context)
        return context

    @property
    def user_id(self):
        return self._user

class sim_inventory(inventory):
    """ Inventories sourced from the steam inventory manager """
    def __init__(self, cache, user_or_id):
        super(sim_inventory, self).__init__(cache, user_or_id)

        if not isinstance(user_or_id, sim_context):
            self._context = sim_context(cache, self._user)
        else:
            self._context = user_or_id

    def dump(self):
        mid = str(self._cache.scope)
        inv = None

        appctx = None
        for c in self._context:
            if mid == str(c["appid"]):
                appctx = c
                break

        if not appctx:
            raise steam.items.BackpackError("Can't find inventory for SIM:" + str(mid) + " in this backpack.")

        try:
            inv = steam.sim.backpack(self._context.user_id, appctx, timeout = STEAM_TIMEOUT)
        except:
            raise steam.items.BackpackError("SIM inventory not found or unavailable")

        self._deserialized = self.build_processed(inv)

        self._commit_to_cache(self._deserialized)

        return self._deserialized

class user(object):
    def __init__(self, cache, sid):
        self._cache = cache
        self._sid = sid
        self._true_id = None
        self._vanity_key = "vanity-" + str(crc32(self._sid))
        self._deserialized = None
        self._valve_group_id64 = config.ini.get("steam", "valve-group-id")

    @property
    def __profile(self):
        if self._deserialized:
            return self._deserialized
        else:
            return self.load()

    @property
    def avatar(self):
        return self.__profile.get("avatarurl")

    @property
    def group_id64(self):
        return self.__profile.get("group")

    @property
    def id64(self):
        return self.__profile.get("id64")

    @property
    def name(self):
        return self.__profile.get("realname")

    @property
    def persona(self):
        return self.__profile.get("persona")

    @property
    def status(self):
        return self.__profile.get("status")

    @property
    def valve_employee(self):
        return str(self.group_id64) == self._valve_group_id64

    @staticmethod
    def load_from_profile(prof, cacheobj = None):
        game = prof.get_current_game()
        profile = {"id64": prof.get_id64(),
                   "realname": prof.get_real_name(),
                   "persona": prof.get_persona(),
                   "avatarurl": prof.get_avatar_url(prof.AVATAR_MEDIUM),
                   "status": prof.get_status(),
                   "group": prof.get_primary_group()}
        if prof.get_visibility() != 3: profile["private"] = True
        if game: profile["game"] = (game.get("id"), game.get("extra"), game.get("server"))

        memkey = "profile-{0[id64]}".format(profile)
        (cacheobj or cache()).set(memkey, profile, time = config.ini.getint("cache", "profile-expiry"))

        return profile

    def resolve_id(self):
        """ Resolves the ID given at instantiation to
        a valid ID64 if one exists """
        if self._true_id: return self._true_id

        # Hashing due do non-ASCII names
        vanitykey = "vanity-" + str(crc32(self._sid))
        self._true_id = self._cache.get(vanitykey)
        if not self._true_id:
            vanity = steam.user.vanity_url(self._sid)
            self._true_id = vanity.get_id64()
            self._cache.set(vanitykey, self._true_id)

        return self._true_id

    def load(self):
        sid = self._sid
        memkey = "profile-" + str(sid)

        profile = self._deserialized
        if not profile:
            return self.dump()
        else:
            self._true_id = profile["id64"]
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
                prof = steam.user.profile(self.resolve_id())
            except steam.user.VanityError as E:
                raise steam.user.ProfileError(str(E))

        profile = self.load_from_profile(prof)

        self._deserialized = profile
        self._true_id = profile["id64"]

        return profile

class recent_inventories(object):
    def __init__(self, cache):
        self._cache = cache
        self._recent_packs_key = "lastpacks-" + self._cache.scope
        self._inv_list = []

    def __iter__(self):
        return self.next()

    def next(self):
        if not self._inv_list:
            self._inv_list = self._cache.get(self._recent_packs_key, [])

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
        lastpacks = self._cache.get(lastpackskey, [])
        id64 = userp["id64"]

        for p in lastpacks:
            if p["id"] == id64:
                lastpacks.remove(p)
                break

        lastpacks.insert(0, dict(id = id64, persona = userp["persona"],
                                 avatar = userp["avatarurl"]))

        self._inv_list = lastpacks[:maxsize]
        self._cache.set(lastpackskey, self._inv_list)
