#!/usr/bin/env python2
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

import os, sys

try:
    sys.path += sys.argv[1:]
except IndexError:
    pass

import steam
from optf2.backend import database, config

steam.set_api_key(config.ini.get("steam", "api-key"))

if __name__ == "__main__":
    updatepairs = set()

    for cachefile in os.listdir(database.CACHE_DIR):
        if not cachefile.startswith("schema-"):
            continue

        toks = cachefile.split('-')

        try:
            updatepairs.add((toks[-2], toks[-1]))
        except:
            pass

    # Update loop
    for scope, lang in updatepairs:
        dbcache = database.cache(mode = scope, language = lang)
        schema = database.schema(dbcache)

        print(scope + ' ' + lang)
        schema.dump()
