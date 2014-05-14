import __builtin__
import json

import web

from optf2 import markup
from optf2 import config

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
