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

# These should stay explicit
globals = {"virtual_root": config.get("resources", "virtual-root"),
           "static_prefix": config.get("resources", "static-prefix"),
           "encode_url": web.urlquote,
           "len": len,
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
                               globals = globals)
