import web
import json
import os
from optf2.backend import items as itemtools
from optf2.backend.config import ini as config
from optf2.frontend import markup as markuptools

wikimap = {}
for mode, wiki in config.items("wiki"):
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

import __builtin__
TEMPLATE_BUILTINS = dict([(name, getattr(__builtin__, name)) for name in TEMPLATE_BUILTIN_NAMES if name in __builtin__.__dict__])

# These should stay explicit
globals = {"virtual_root": config.get("resources", "virtual-root"),
           "static_prefix": config.get("resources", "static-prefix"),
           "encode_url": web.urlquote,
           "instance": web.ctx,
           "project_name": config.get("misc", "project-name"),
           "wiki_map": wikimap,
           "qurl": web.http.changequery,
           "markup": markuptools,
           "game_modes": markuptools.odict(config.items("modes")),
           "pagesizes": markuptools.get_page_sizes(),
           "json_dump": json.dumps,
           "json_load": json.loads,
           "f2p_check": config.getlist("misc", "f2p-check-modes")
           }

template = web.template.render(config.get("resources", "template-dir"), base = "base",
                               globals = globals, builtins = TEMPLATE_BUILTINS)
