import __builtin__
import json
import operator
import random

import web

from optf2 import markup
from optf2 import config
from optf2 import models
from optf2.app import api

valid_modes = map(operator.itemgetter(0), config.ini.items("modes"))

def template_setup(directory, base=None):
    wikimap = {}
    for mode, wiki in config.ini.items("wiki"):
        wikimap[mode] = map(str.strip, wiki.split(':', 1))

    # Using this from web.template, don't want to import entire __builtin__
    # module (i.e. eval) so this will do
    TEMPLATE_BUILTIN_NAMES = [
        "dict", "enumerate", "float", "int", "bool", "list", "long", "reversed",
        "set", "slice", "tuple", "xrange",
        "abs", "all", "any", "callable", "chr", "cmp", "divmod", "filter", "hex",
        "id", "isinstance", "iter", "len", "max", "min", "oct", "ord", "pow", "range",
        "True", "False",
        "None",
        "len", "map", "str",
        "__import__", # some c-libraries like datetime requires __import__ to present in the namespace
    ]

    TEMPLATE_BUILTINS = dict([(name, getattr(__builtin__, name)) for name in TEMPLATE_BUILTIN_NAMES if name in __builtin__.__dict__])

    # These should stay explicit
    globals = {"virtual_root": config.ini.get("resources", "virtual-root"),
               "static_prefix": config.ini.get("resources", "static-prefix"),
               "encode_url": web.urlquote,
               "instance": web.ctx,
               "project_name": config.ini.get("misc", "project-name"),
               "wiki_map": wikimap,
               "qurl": web.http.changequery,
               "markup": markup,
               "game_modes": markup.odict(config.ini.items("modes")),
               "pagesizes": markup.get_page_sizes(),
               "json_dump": json.dumps,
               "json_load": json.loads,
               "f2p_check": config.ini.getlist("misc", "f2p-check-modes")
               }

    return web.template.render(directory, base=base, globals=globals, builtins=TEMPLATE_BUILTINS)

template = template_setup(config.ini.get("resources", "template-dir"), "base")

class index:
    def GET(self, app = None):
        usestale = True

        # Until dedicated main homepage is done
        if not app:
            app = random.choice(valid_modes)

        app = models.app_aliases.get(app, app)
        query = web.input()
        user = query.get("user")

        # TODO: Won't be much use in the big restructuring, for now try to extract app from path
        appfrom = query.get("from", '')[len(markup.virtual_root):].strip('/').split('/')[0]
        if appfrom not in valid_modes:
            appfrom = valid_modes[0]

        profile = api.profile_search(user)
        if profile:
            raise web.seeother(markup.generate_root_url("user/" + str(profile[0]["id64"]), appfrom))

        ckey = "scrender"
        showcase = models.cache.get(ckey)
        showcase_cell = None
        try:
            if not showcase:
                sitems = models.schema(scope = app).processed_items.values()
                if len(sitems) > 0:
                    showcase = random.choice(sitems)
                    showcase["app"] = app
                    # May want to add an option for showcase expiration to config later
                    models.cache.set(ckey, showcase, time=60)

            app = showcase.get("app", app)
            showcase_cell = markup.generate_item_cell(app, showcase, user=showcase.get("user"))
        except Exception as E:
            pass

        markup.init_theme(app)
        web.ctx.notopsearch = True

        # Last packs
        packs = models.recent_inventories(scope = app)

        return template.index(app, (packs or []), showcase_cell)

class about:
    def GET(self):
        return template.about()
