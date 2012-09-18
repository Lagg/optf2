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

import steam
from optf2.backend import config
from optf2.backend import log
import items as itemtools
from optf2.frontend.markup import absolute_url

def _(thestring):
    return web.utils.safestr(thestring)

def hilo_to_ugcid64(hi, lo):
    return (int(hi) << 32) | int(lo)

qualitydict = {"unique": "The",
               "normal": ""}

memcached = pylibmc.Client([config.ini.get("cache", "memcached-address")], binary = True,
                           behaviors = {"tcp_nodelay": True,
                                        "ketama": True})
memc = pylibmc.ThreadMappedPool(memcached)

# Keeps track of connection times, until I think of a better way
last_server_checks = {}

class CacheError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return str(self.msg)

class CacheEmptyError(CacheError):
    def __init__(self, msg):
        CacheError.__init__(self, msg)

class cache:
    """ Cache retrieval/setting functions """

    def _get_generic_aco(self, baseclass, keyprefix, cachefilter = None, stale = False, appid = None, getlm = None, usepickle = False):
        """ Initializes and caches Aggresively Cached Objects from steamodd """

        modulename = self._mod_id
        language = self._language
        lm = None
        ctime = int(time())
        memkey = "{0}-{1}-{2}".format(keyprefix, modulename, language)
        timeout = config.ini.getint("steam", "connect-timeout")
        datatimeout = config.ini.getint("steam", "download-timeout")
        cachepath = os.path.join(config.ini.get("resources", "cache-dir"), memkey)
        oldobj = None

        if usepickle:
            try:
                oldobj = pickle.load(open(cachepath))
            except IOError:
                pass
        else:
            oldobj = self.get(memkey)

        if stale: return oldobj
        if oldobj:
            if (ctime - last_server_checks.get(memkey, 0)) < config.ini.getint("cache", keyprefix + "-check-interval"):
                return oldobj

            if getlm: lm = getlm(oldobj)

        aco = oldobj
        try:
            result = None
            if not appid: result = baseclass(lang = language, last_modified = lm, timeout = timeout, data_timeout = datatimeout)
            else: result = baseclass(appid, lang = language, last_modified = lm, timeout = timeout, data_timeout = datatimeout)

            if cachefilter:
                aco = cachefilter(result)
            else:
                aco = result

            if usepickle:
                pickle.dump(aco, open(cachepath, "wb"), pickle.HIGHEST_PROTOCOL)
            else:
                self.set(memkey, aco)
        except steam.base.HttpStale, pylibmc.Error:
            pass
        except Exception as E:
            log.main.error("Cache refresh error: {0}".format(E))
        finally:
            if aco:
                last_server_checks[memkey] = ctime
            else:
                errstr = "Cache record missing: {0}".format(memkey)
                log.main.error(errstr)
                raise CacheEmptyError(errstr)

            return aco

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

    def set(self, key, value, **kwargs):
        key = str(key).encode("ascii")

        try:
            with memc.reserve() as mc:
                mc.set(key, value, min_compress_len = self._compress_len, **kwargs)
        except pylibmc.Error as E:
            log.main.error(str(key) + ": " + str(E))

    def get_schema(self, stale = False):
        modulename = self._mod_id
        language = self._language

        def cb(result):
            pmap = {}
            for item in result:
                if item._schema_item.get("name", "").find("Paint") != -1:
                    for attr in item:
                        if attr.get_name().startswith("set item tint RGB"):
                            pmap[int(attr.get_value())] = item.get_name()
            self.set(str("paints-" + modulename + '-' + language), pmap)

            particles = result.get_particle_systems()
            pmap = dict(zip(particles.keys(),
                            map(operator.itemgetter("name"), particles.values())))
            self.set(str("particles-" + modulename + '-' + language), pmap)

            qualities = result.get_qualities()
            qmap = {}
            if qualities:
                qualities = qualities.values()

                qmap = dict(zip(map(operator.itemgetter("str"), qualities),
                                map(operator.itemgetter("prettystr"), qualities)))
            self.set(self._quality_key, qmap)

            return result

        try:
            modclass = getattr(steam, modulename).item_schema
        except AttributeError:
            raise itemtools.ItemBackendUnimplemented("Backend couldn't give a schema for {0}".format(modulename))

        return self._get_generic_aco(modclass, "schema", cachefilter = cb, stale = stale, getlm = operator.methodcaller("get_last_modified"), usepickle = True)

    def get_assets(self, stale = False):
        modulename = self._mod_id
        language = self._language
        appid = None

        def cb(result):
            amap = dict([(int(asset.get_name()), asset.get_price())
                         for asset in result])
            amap["serverts"] = result.get_last_modified()

            return amap

        try:
            mod = getattr(steam, modulename)
            modclass = mod.assets
        except AttributeError:
            try:
                modclass = steam.items.assets
                appid = mod._APP_ID
            except:
                return None

        return self._get_generic_aco(modclass, "assets", cachefilter = cb, stale = stale, appid = appid, getlm = operator.itemgetter("serverts"))

    def get_vanity(self, sid):
        # Use hash to avoid weird character problems
        vanitykey = "vanity-" + str(crc32(sid))
        vanity = self.get(vanitykey)
        if not vanity:
            vanity = steam.user.vanity_url(sid)
            self.set(vanitykey, vanity.get_id64(), time = config.ini.getint("cache", "vanity-expiry"))
        return vanity

    def _load_profile(self, sid):
        memkey = "profile-" + str(sid)
        profile = self.get(memkey)
        if not profile:
            pobj = steam.user.profile(sid)
            game = pobj.get_current_game()
            profile = {"id64": pobj.get_id64(),
                       "realname": pobj.get_real_name(),
                       "persona": pobj.get_persona(),
                       "avatarurl": pobj.get_avatar_url(pobj.AVATAR_MEDIUM),
                       "status": pobj.get_status()}
            if str(pobj.get_primary_group()) == config.ini.get("steam", "valve-group-id"):
                profile["valve"] = True
            if pobj.get_visibility() != 3: profile["private"] = True
            if game: profile["game"] = (game.get("id"), game.get("extra"), game.get("server"))
            self.set(memkey, profile, time = config.ini.getint("cache", "profile-expiry"))
        return profile

    def get_profile(self, sid):
        sid = str(sid)

        if sid.isdigit():
            try:
                return self._load_profile(sid)
            except steam.user.ProfileError:
                pass

        try:
            return self._load_profile(self.get_vanity(sid))
        except steam.user.VanityError as E:
            raise steam.user.ProfileError(str(E))

    def get_backpack(self, user):
        modulename = self._mod_id
        language = self._language
        id64 = user["id64"]

        memkey = "backpack-{0}-{1}".format(modulename, id64)

        processedpack = {"items": {}}
        pack = self.get(memkey)
        if not pack:
            try:
                schema = self.get_schema()
            except:
                schema = None

            try:
                pack = getattr(steam, modulename).backpack(id64, schema = schema)
            except AttributeError:
                try:
                    pack = self.get_inv_backpack(user)
                except:
                    raise itemtools.ItemBackendUnimplemented("No backend available for " + str(modulename))

            processedpack["cells"] = pack.get_total_cells()
            for item in pack:
                processedpack["items"][item.get_id()] = self._build_processed_item(item)

            pack = processedpack

            self.set(memkey, pack, time = self._bp_lifetime)

        if not processedpack["items"]: return pack

        self.update_recent_pack_list(user)

        return pack

    def get_inv_context(self, user):
        id64 = user["id64"]
        ctxkey = "invctx-{0}".format(id64)
        # TODO: Add cache life config settings for these
        ctx = self.get(ctxkey)
        if not ctx:
            ctx = list(steam.sim.backpack_context(id64))
            self.set(ctxkey, ctx, time = 120)

        return ctx

    def get_inv_backpack(self, user):
        id64 = user["id64"]
        app = self.get_mod_id()

        ctx = self.get_inv_context(user)
        appctx = None
        for c in ctx:
            if str(app) == str(c["appid"]):
                appctx = c
                break

        return steam.sim.backpack(id64, appctx)

    def get_mod_id(self):
        return self._mod_id

    def get_language(self):
        return self._language

    def get_recent_pack_list(self):
        return self.get(self._recent_packs_key)

    def update_recent_pack_list(self, profilerecord):
        lastpackskey = self._recent_packs_key
        lastpacks = self.get(lastpackskey)
        id64 = profilerecord["id64"]

        if not lastpacks:
            lastpacks = []
        else:
            # TODO: Cast is temporary until move away from deque propagates
            lastpacks = list(lastpacks)
            for p in lastpacks:
                if p["id"] == id64:
                    lastpacks.remove(p)
                    break

        lastpacks.insert(0, dict(id = id64, persona = profilerecord["persona"],
                                 avatar = profilerecord["avatarurl"]))
        self.set(lastpackskey, lastpacks[:10])


    def _build_processed_item(self, item):
        if not item: return None

        default_cell_image = self._resource_prefix + "item_icons/Invalid_icon.png";
        newitem = dict(sid = item.get_schema_id())
        appid = None
        mod = self.get_mod_id()
        language = self.get_language()
        try: appid = getattr(steam, mod)._APP_ID
        except AttributeError: pass
        ugc_key = "ugc-{0}"
        ugc_cache_expiry = self._ugc_lifetime
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
        if equipable: newitem["equipable"] = [itemtools.get_class_for_id(c, self._mod_id)[0] for c in equipable]
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
                    paintcan_url = "{0}item_icons/Paint_Can_{1}.png".format(self._resource_prefix,
                                                                            item_color[1:])
                    newitem["image"] = absolute_url(paintcan_url)
                    newitem["imagelarge"] = absolute_url(paintcan_url)

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
                        self.set(memkey, url, time = ugc_cache_expiry)
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

    def __init__(self, mode = None, language = None):
        """ modid and language will be set to their respective values in web.ctx if not given """

        clang = language or web.ctx.language

        try: code, name = steam.get_language(clang)
        except steam.LangErrorUnsupported: code, name = steam.get_language()

        self._language = code
        self._language_name = name
        self._mod_id = str(mode)
        self._recent_packs_key = "lastpacks-" + self._mod_id
        self._resource_prefix = config.ini.get("resources", "static-prefix")
        self._bp_lifetime = config.ini.getint("cache", "backpack-expiry")
        self._ugc_lifetime = config.ini.getint("cache", "ugc-expiry")
        self._compress_len = config.ini.getint("cache", "compress-len")
        self._quality_key = str("qualities" + self._language + self._mod_id)
