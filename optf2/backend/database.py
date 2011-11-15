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

import config, steam, urllib2, web, os, marshal, json, logging
from email.utils import formatdate, parsedate
from time import time, mktime

class cached_item_schema(steam.items.schema):
    def _download(self):
        cachepath = os.path.join(config.cache_file_dir, "schema-" + self._app_id + "-" + self.get_language())
        cachepath_lm = -1
        cachepath_am = time()
        headers = {}

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

        req = urllib2.Request(self._game_class._get_download_url(self), headers = headers)

        try:
            self.load_fresh = False

            if cachepath_lm < 0 or (time() - cachepath_am) > config.cache_schema_grace_time:
                response = urllib2.urlopen(req)
                dumped = marshal.dumps(json.load(response))
                open(cachepath, "wb").write(dumped)
                self.load_fresh = True

                server_lm = parsedate(response.headers.get("last-modified"))
                if server_lm: cachepath_lm = mktime(server_lm)
            else:
                dumped = open(cachepath, "rb").read()
        except urllib2.HTTPError as err:
            code = err.getcode()
            if code != 304:
                logging.error("Server returned {0} when trying to do cache dance for schema-{1}".format(code, self._app_id))
            else:
                logging.debug("schema-{0} hasn't changed".format(self._app_id))
                cachepath_am = time()
            dumped = open(cachepath, "rb").read()
        except urllib2.URLError as err:
            logging.error("Schema server connection error: " + str(err))
            dumped = open(cachepath, "rb").read()

        # So we don't bother wasting Valve's bandwidth with our massive 1KB or so request
        os.utime(cachepath, (cachepath_am, cachepath_lm))

        return dumped

    def _deserialize(self, schema):
        return marshal.loads(schema)

    def __init__(self, lang = None, fresh = False):
        self._game_class = getattr(steam, web.ctx.current_game).item_schema
        cached_item_schema.__bases__ = (self._game_class,)

        self.optf2_paints = {}
        paintcache = os.path.join(config.cache_file_dir, "paints-" + self._app_id)

        self._game_class.__init__(self, lang)

        if os.path.exists(paintcache) and not self.load_fresh:
            self.optf2_paints = marshal.load(open(paintcache, "rb"))
        else:
            for item in self:
                if item._schema_item.get("name", "").startswith("Paint Can"):
                    for attr in item:
                        if attr.get_name().startswith("set item tint RGB"):
                            self.optf2_paints[int(attr.get_value())] = item.get_schema_id()
            marshal.dump(self.optf2_paints, open(paintcache, "wb"))

def load_profile_cached(sid, stale = False):
    return steam.user.profile(sid)

def load_schema_cached(lang, fresh = False):
    return cached_item_schema(lang, fresh)

def refresh_pack_cache(user):
    pack = getattr(steam, web.ctx.current_game).backpack(schema = load_schema_cached(web.ctx.language))
    pack.load(user)

    try:
        packitems = list(pack)
    except steam.items.ItemError:
        pack.set_schema(load_schema_cached(web.ctx.language, fresh = True))
        packitems = list(pack)

    return packitems

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
