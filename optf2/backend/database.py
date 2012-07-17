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
from collections import deque
from time import time
from hashlib import md5

import steam
from optf2.backend import config
from optf2.backend import log

memcached = pylibmc.Client([config.ini.get("cache", "memcached-address")], binary = True,
                           behaviors = {"tcp_nodelay": True,
                                        "ketama": True})
memc = pylibmc.ThreadMappedPool(memcached)

# Keeps track of connection times, until I think of a better way
last_server_checks = {}

class cache:
    """ Cache retrieval/setting functions """

    def _get_generic_aco(self, baseclass, keyprefix, freshcallback = None, stale = False, appid = None):
        """ Initializes and caches Aggresively Cached Objects from steamodd """

        modulename = self._mod_id
        language = self._language
        lm = None
        ctime = int(time())
        memkey = "{0}-{1}-{2}".format(keyprefix, modulename, language)

        oldobj = self.get(memkey)
        if stale: return oldobj
        if oldobj:
            if (ctime - last_server_checks.get(memkey, 0)) < config.ini.getint("cache", keyprefix + "-check-interval"):
                return oldobj
            lm = oldobj.get_last_modified()

        result = None
        try:
            timeout = config.ini.getint("steam", "connect-timeout")
            datatimeout = config.ini.getint("steam", "download-timeout")
            if not appid: result = baseclass(lang = language, last_modified = lm, timeout = timeout, data_timeout = datatimeout)
            else: result = baseclass(appid, lang = language, last_modified = lm, timeout = timeout, data_timeout = datatimeout)
            if freshcallback: freshcallback(result)
            result._get()
            self.set(memkey, result)
        except steam.base.HttpStale:
            result = oldobj
        except pylibmc.Error:
            return result
        except Exception as E:
            log.main.error("Cached loading error: {0}".format(E))
            result = oldobj

        last_server_checks[memkey] = ctime

        return result or oldobj

    def get(self, value, default = None):
        with memc.reserve() as mc:
            try:
                return mc.get(value) or default
            except pylibmc.Error as E:
                log.main.error(str(value) + ": " + str(E))
                return default

    def set(self, key, value, **kwargs):
        try:
            with memc.reserve() as mc:
                mc.set(key, value, min_compress_len = 1000000, **kwargs)
        except pylibmc.Error as E:
            log.main.error(str(key) + ": " + str(E))

    def get_schema(self, stale = False):
        modulename = self._mod_id
        language = self._language

        def freshfunc(result):
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

        try:
            modclass = getattr(steam, modulename).item_schema
            # there's no real schema yet, TODO
            if modulename == "sim": return modclass()
        except AttributeError:
            raise steam.items.SchemaError("steamodd hasn't implemented a schema for {0}".format(modulename))

        return self._get_generic_aco(modclass, "schema", freshcallback = freshfunc, stale = stale)

    def get_assets(self, stale = False):
        modulename = self._mod_id
        language = self._language
        appid = None

        try:
            mod = getattr(steam, modulename)
            modclass = mod.assets
        except AttributeError:
            try:
                modclass = steam.items.assets
                appid = mod._APP_ID
            except:
                return None

        return self._get_generic_aco(modclass, "assets", stale = stale, appid = appid)

    def get_vanity(self, sid):
        vanitykey = "vanity-" + md5(sid).hexdigest()
        vanity = self.get(vanitykey)
        if not vanity:
            vanity = str(steam.user.vanity_url(sid))
            # May want a real option for this later
            self.set(vanitykey, vanity, time = (config.ini.getint("cache", "profile-expiry") * 4))
        return vanity

    def _load_profile(self, sid):
        memkey = "profile-" + sid
        profile = self.get(memkey)
        if not profile:
            profile = steam.user.profile(sid)
            profile._get()
            self.set(memkey, profile, time = config.ini.getint("cache", "profile-expiry"))
        return profile

    def get_profile(self, sid):
        # Use memcache's hashing function to avoid weird character problems
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

        memkey = "backpack-{0}-{1}".format(modulename, user.get_id64())

        pack = self.get(memkey)
        if not pack:
            pack = getattr(steam, modulename).backpack(user, schema = self.get_schema())
            pack._get()
            self.set(memkey, pack, time = config.ini.getint("cache", "backpack-expiry"))

        if len(pack) <= 0: return pack

        lastpackskey = self._recent_packs_key
        lastpacks = self.get(lastpackskey)
        if not lastpacks:
            lastpacks = deque(maxlen = 10)
        else:
            for p in lastpacks:
                if p["id"] == user.get_id64():
                    lastpacks.remove(p)
                    break

        lastpacks.appendleft({"id": user.get_id64(),
                              "persona": user.get_persona(),
                              "avatar": user.get_avatar_url(user.AVATAR_SMALL)})
        self.set(lastpackskey, lastpacks)

        return pack

    def get_mod_id(self):
        return self._mod_id

    def get_language(self):
        return self._language

    def get_recent_pack_list(self):
        return self.get(self._recent_packs_key)

    def __init__(self, modid = None, language = None):
        """ modid and language will be set to their respective values in web.ctx if not given """

        clang = language or web.ctx.language
        langpair = None

        try: langpair = steam.get_language(clang)
        except steam.LangErrorUnsupported: langpair = steam.get_language()

        self._language = langpair[0]
        self._language_name = langpair[1]
        self._mod_id = str(modid or web.ctx.current_game)
        self._recent_packs_key = "lastpacks-" + self._mod_id
