from optf2.backend import items as itemtools
from optf2.frontend import markup as markuptools
from optf2.backend import openid
import web, config

# These should stay explicit
globals = {"virtual_root": config.virtual_root,
           "static_prefix": config.static_prefix,
           "encode_url": web.urlquote,
           "len": len,
           "instance": web.ctx,
           "project_name": config.project_name,
           "wiki_map": config.wiki_mapping[config.game_mode],
           "news_url": config.news_url,
           "qurl": web.http.changequery,
           "iurl": web.input,
           "markup": markuptools,
           "get_openid": openid.get_id,
           "game_mode": config.game_mode,
           "opnet_map": config.opnet_mapping
           }

template = web.template.render(config.template_dir, base = "base",
                               globals = globals)
