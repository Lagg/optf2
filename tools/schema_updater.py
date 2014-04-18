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
import threading

try:
    sys.path += sys.argv[1:]
except IndexError:
    pass

import steam
from optf2.backend import database, config

steam.api.key.set(config.ini.get("steam", "api-key"))

class DumpThread(threading.Thread):
    def __init__(self, scope, language):
        threading.Thread.__init__(self)
        self.scope = scope
        self.language = language

    def run(self):
        schema = database.schema(scope = self.scope, lang = self.language)

        schema.dump()

        # For the moment there is no differences between client schemas as they only have loc tokens
        if self.language.lower() == "en_us":
            schema.dump_client()

        print("{0}-{1}: Finished".format(self.scope, self.language))

if __name__ == "__main__":
    updatepairs = set()

    # Iterate cache dir and gather names to dump (not a perfect method, I know)
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
        t = DumpThread(scope, lang)

        print("{0}-{1}: Starting".format(scope, lang))
        t.start()
