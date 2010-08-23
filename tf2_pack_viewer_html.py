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

# The url to prefix icon names with
icon_prefix = "/static/"

api_key = None

language = "en"

# End of configuration stuff

urls = (
    virtual_root + "user/(.*)", "pack_fetch",
    virtual_root, "index"
    )

app = web.application(urls, globals())
templates = web.template.render(template_dir, base = "base",
                                globals = {"css_url": css_url,
                                           "virtual_root": virtual_root,
                                           "icon_prefix": icon_prefix,
                                           "encode_url": web.urlquote})

steam.set_api_key(api_key)
steam.set_language(language)

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

class index:
    def GET(self):
        profile_form = form.Form(
            form.Textbox("User"),
            form.Button("View")
            )
        return templates.index(profile_form())
        
if __name__ == "__main__":
    app.run()
