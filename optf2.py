#!/usr/bin/env python

"""
Copyright (c) 2010, Anthony Garcia <lagg@lavabit.com>

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

try:
    import steam.user, steam.tf2, steam
    import web
    from web import form
except ImportError as E:
    print(str(E))
    raise SystemExit

# Configuration stuff

# You probably want this to be
# an absolute path if you're not running the built-in server
template_dir = "static/"

# Most links to other viewer pages will
# be prefixed with this.
virtual_root = "/"

css_url = "/static/style.css"

# The url to prefix URLs
# pointing to static data with
# e.g. class icons
static_prefix = "/static/"

api_key = None

language = "en"

# It would be nice of you not to change this
product_name = "OPTF2"

# Where to get the source code.
source_url = "http://gitorious.org/steamodd/optf2"

# End of configuration stuff

urls = (
    virtual_root + "user/(.*)", "pack_fetch",
    virtual_root + "feed/(.+)", "pack_feed",
    virtual_root + "item/(.+)", "pack_item",
    virtual_root + "about", "about",
    virtual_root, "index"
    )

# These should stay explicit
render_globals = {"css_url": css_url,
                  "virtual_root": virtual_root,
                  "static_prefix": static_prefix,
                  "encode_url": web.urlquote,
                  "len": len,
                  "qualitydict": {"unique": "The ", "community": "Community ",
                                  "developer": "Legendary ", "normal": "",
                                  "selfmade": "My "},
                  "instance": web.ctx,
                  "product_name": product_name,
                  "source_url": source_url
                  }

app = web.application(urls, globals())
templates = web.template.render(template_dir, base = "base",
                                globals = render_globals)

steam.set_api_key(api_key)
steam.set_language(language)

class pack_item:
    def GET(self, iid):
        try:
            idl = iid.split('/')
            user = steam.user.profile(idl[0])
            pack = steam.tf2.backpack(user)
            try: idl[1] = int(idl[1])
            except: raise Exception("Item ID must be an integer")
            item = pack.get_item_by_id(int(idl[1]))
            if not item:
                raise Exception("Item not found")
        except Exception as E:
            return templates.error(str(E))
        return templates.item(user, item, pack)

class about:
    def GET(self):
        return templates.about()

class pack_fetch:
    def _get_page_for_sid(self, sid):
        try:
            if not sid:
                return templates.error("Need an ID")
            user = steam.user.profile(sid)
            pack = steam.tf2.backpack(user)
            sortby = web.input().get("sort", "default")
        except Exception as E:
            return templates.error(str(E))
        return templates.inventory(user, pack, sortby)

    def GET(self, sid):
        return self._get_page_for_sid(sid)

    def POST(self, s):
        return self._get_page_for_sid(web.input().get("User"))

class pack_feed:
    # Eventually I'll add code that uses the wiki API and make dedicated
    # pages for each item for the feed to link to, for now it just goes to the
    # main viewer page
    def GET(self, sid):
        try:
            user = steam.user.profile(sid)
            pack = steam.tf2.backpack(user)
        except Exception as E:
            return templates.error(str(E))
        web.header("Content-Type", "application/rss+xml")
        return web.template.render(template_dir,
                                   globals = render_globals).inventory_feed(user,
                                                                            pack)

class index:
    def GET(self):
        profile_form = form.Form(
            form.Textbox("User"),
            form.Button("View")
            )
        return templates.index(profile_form())
        
if __name__ == "__main__":
    app.run()
