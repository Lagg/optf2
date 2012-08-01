import web
from optf2.backend import items as itemtools
from optf2.backend.config import ini as config
from optf2.frontend import markup as markuptools

wikimap = {}
for wiki in config.items("wiki"):
    sep = wiki[1].find(':')
    pair = (wiki[1][:sep], wiki[1][sep + 1:])
    wikimap[wiki[0]] = (pair[0].strip(), pair[1].strip())

cssmap = dict(config.items("css-aliases"))

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
           "iurl": web.input,
           "markup": markuptools,
           "game_modes": markuptools.odict(config.items("modes")),
           "cssaliases": cssmap,
           "pagesizes": markuptools.get_page_sizes()
           }

template = web.template.render(config.get("resources", "template-dir"), base = "base",
                               globals = globals, builtins = TEMPLATE_BUILTINS)
