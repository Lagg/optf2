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

import config, steam, urllib2, web, os, json, logging, threading
import cPickle as pickle
from email.utils import formatdate, parsedate
from time import time, mktime

class CacheStale(steam.items.Error):
    def __init__(self, msg):
        steam.items.Error.__init__(self, msg)
        self.msg = msg

class cached_asset_catalog(steam.items.assets):
    def _download(self):
        return self._http.download()

    def __new__(cls, *args, **kwargs):
        try:
            game_class = getattr(steam, web.ctx.current_game).assets
        except AttributeError:
            raise steam.items.AssetError("steamodd hasn't implemented an asset catalog for " + web.ctx.current_game)
        cls.__bases__ = (game_class, )
        instance = super(cached_asset_catalog, cls).__new__(cls, *args, **kwargs)

        return instance

    def __init__(self, lang = None, currency = None):
        self._http = http_helpers(self)

        super(cached_asset_catalog, self).__init__(lang, currency)

class cached_item_schema(steam.items.schema):
    def _download(self):
        return self._http.download()

    def __new__(cls, *args, **kwargs):
        try:
            game_class = getattr(steam, web.ctx.current_game).item_schema
        except AttributeError:
            raise steam.items.SchemaError("steamodd hasn't implemented a schema for " + web.ctx.current_game)
        cls.__bases__ = (game_class, )
        instance = super(cached_item_schema, cls).__new__(cls, *args, **kwargs)

        return instance

    def __init__(self, lang = None, fresh = False):
        self.optf2_paints = {}
        self._http = http_helpers(self)

        super(cached_item_schema, self).__init__(lang)

        for item in self:
            if item._schema_item.get("name", "").startswith("Paint Can"):
                for attr in item:
                    if attr.get_name().startswith("set item tint RGB"):
                        self.optf2_paints[int(attr.get_value())] = item.get_schema_id()

def generate_cache_path(obj):
    try:
        name = obj.__name__
    except AttributeError:
        name = obj.__class__.__name__

    return os.path.join(config.cache_file_dir, name +
                        "-" + web.ctx.current_game + "-" + web.ctx.language)

class http_helpers:
    """ Probably going to be made into proper request objects
    later """

    def download(self):
        cachepath = self.get_cache_path()
        basename = os.path.basename(cachepath)
        cachepath_am = time()
        cachepath_lm = None
        headers = {}
        dumped = None

        try:
            cachestat = os.stat(cachepath)
            cachepath_lm = cachestat.st_mtime
            # Used for grace time checking. There is some kind of 
            # desync on Valve's servers if they're sent a if-modified-since
            # value that is less than two minutes or so older than the current time
            cachepath_am = cachestat.st_atime
            headers["If-Modified-Since"] = formatdate(cachepath_lm, usegmt = True)
        except OSError:
            pass

        req = urllib2.Request(self._obj._get_download_url(), headers = headers)

        try:
            if not os.path.exists(cachepath) or (time() - cachepath_am) > config.cache_schema_grace_time:
                response = urllib2.urlopen(req)
                dumped = response.read()
                server_lm = parsedate(response.headers.get("last-modified"))
                if server_lm: cachepath_lm = mktime(server_lm)
        except urllib2.HTTPError as err:
            code = err.getcode()
            if code != 304:
                logging.error(basename + ": Server returned " + str(code))
            else:
                logging.debug(basename + ": No change")
        except urllib2.URLError as err:
            logging.error("Schema server connection error: " + str(err))

        self._obj.cache_am = cachepath_am
        self._obj.cache_lm = cachepath_lm

        if not dumped: raise CacheStale("No change")

        return dumped

    def get_cache_path(self):
        return self.__cachepath

    def __init__(self, obj):
        """ Accepts an object implementing the base
        steamodd downloadable API """

        self._obj = obj
        self.__cachepath = generate_cache_path(obj)

# This will be a placehold for memcached for now
cached = {}

def load_schema_cached(lang = None):
    return steamodd_api_request(cached_item_schema, lang)

def load_assets_cached(lang = None):
    return steamodd_api_request(cached_asset_catalog, lang)

def steamodd_api_request(apiobj, *args, **kwargs):
    def touch_pickle_cache(obj):
        try:
            os.utime(generate_cache_path(obj), (int(time()), obj.cache_lm))
        except Exception as E:
            logging.error("Failed to touch cache: " + str(E))

    cachepath = generate_cache_path(apiobj)
    lock = threading.Lock()
    obj = None

    try:
        obj = apiobj(*args, **kwargs)
    except steam.items.AssetError as E:
        print("No " + cachepath + ": " + str(E))
    except:
        pass

    with lock:
        if not obj and os.path.exists(cachepath):
            cf = open(cachepath, "rb")
            obj = cached.get(cachepath, pickle.load(cf))
            cf.close()
            if cachepath in cached: cached[cachepath] = obj
        else:
            cf = open(cachepath, "wb")
            pickle.dump(obj, cf, pickle.HIGHEST_PROTOCOL)
            cf.close()
            touch_pickle_cache(obj)

    return obj

def load_profile_cached(sid, stale = False):
    return steam.user.profile(sid)

def refresh_pack_cache(user):
    pack = getattr(steam, web.ctx.current_game).backpack(schema = load_schema_cached(web.ctx.language))
    pack.load(user)

    try:
        packitems = list(pack)
    except steam.items.ItemError:
        pack.set_schema(load_schema_cached(web.ctx.language))
        packitems = list(pack)

    return pack

def get_pack_timeline_for_user(user, tl_size = None):
    """ Returns None if a backpack couldn't be found, returns
    tl_size rows from the timeline
    """
    return []

def fetch_item_for_id(id64):
    return None

def load_pack_cached(user, stale = False, pid = None):
    return refresh_pack_cache(user)

def get_user_pack_views(user):
    """ Returns the viewcount of a user's backpack """

    return 0

def get_top_pack_views(limit = 10):
    """ Will return the top viewed backpacks sorted in descending order
    no more than limit rows will be returned """

    return []
