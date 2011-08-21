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

import web
from optf2.backend import items as itemtools
from optf2.backend import database
import config
import template
templates = template.template

class items:
    """ Dumps every item in the schema in a pretty way """

    def GET(self):
        try:
            query = web.input()
            items = database.load_schema_cached(web.ctx.language)
            filter_qualities = itemtools.get_present_qualities(items)
            filter_capabilities = itemtools.get_present_capabilities(items)

            try: items = itemtools.filter_by_class(items, query["sortclass"])
            except KeyError: pass
            try: items = itemtools.filter_by_quality(items, query["quality"])
            except KeyError: pass
            try: items = itemtools.sort(items, query["sort"])
            except KeyError: pass
            try: items = itemtools.filter_by_capability(items, query["capability"])
            except KeyError: pass

            stats = itemtools.get_stats(items)
            filter_classes = itemtools.get_equippable_classes(items)

            return templates.schema_dump(itemtools.process_attributes(items),
                                         filter_classes,
                                         filter_qualities = filter_qualities,
                                         filter_capabilities = filter_capabilities,
                                         stats = stats)
        except:
            return templates.error("Couldn't load schema")

class attributes:
    """ Dumps all schema attributes in a pretty way """

    def GET(self):
        try:
            query = web.input()
            schema = database.load_schema_cached(web.ctx.language)
            attribs = schema.get_attributes()

            attachment_check = query.get("att")
            if attachment_check:
                items = schema
                attached_items = []

                for item in items:
                    attrs = item.get_attributes()
                    for attr in attrs:
                        attr_name = attr.get_name()
                        if attachment_check == attr_name:
                            attached_items.append(item)
                            break

                return templates.schema_dump(itemtools.process_attributes(attached_items), [], attrdump = attachment_check)

            return templates.attrib_dump(attribs)
        except:
            return templates.error("Couldn't load attributes")

class particles:
    def GET(self):
        try:
            schema = database.load_schema_cached(web.ctx.language)
            particles = schema.get_particle_systems()

            return templates.particle_dump(particles)
        except KeyboardInterrupt:
            return templates.error("Couldn't load particle systems")
