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

import steam.user, steam.tf2

try:
    import web
    from web import form
except:
    raise SystemExit("I want web.py.")

template_dir = "html_templates/"
stylesheet = template_dir + "style.css"

urls = (
    "/user/(.+)", "pack_fetch",
    "/style.css", "style",
    "/(.*)", "index"
    )
app = web.application(urls, globals())
templates = web.template.render(template_dir)

class style:
    def GET(self):
        web.header("Content-type", "text/css")
        return file(stylesheet).read()
    
class pack_fetch:
    def GET(self, sid):
        sortby = "default"
        if not sid:
            return "Need an ID"
        try:
            user = steam.user.profile(sid)
            pack = steam.tf2.backpack(user)
            inputs = web.input()
            if inputs.has_key("sort"):
                sortby = inputs["sort"]
        except Exception as E:
            return templates.error(E)
        return templates.inventory(user, pack, sortby)

class index:
    def GET(self, arg):
        return templates.index(arg, self.profile_form())

    def POST(self, arg):
        try:
            inputdata = web.input()
            raise web.seeother("/user/" + inputdata["User"])
        except Exception as E:
            return templates.error(E)

    def __init__(self):
        self.profile_form = form.Form(
            form.Textbox("User"),
            form.Button("View")
            )
        
if __name__ == "__main__":
    app.run()
