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
import template
from optf2.backend import items as itemtools
from optf2.backend import database

templates = template.template

class items:
    """ Dumps every item in the schema in a pretty way """

    def GET(self):
        query = web.input()
        items = database.load_schema_cached(web.ctx.language)
        filter_qualities = itemtools.get_present_qualities(items)
        filter_capabilities = itemtools.get_present_capabilities(items)

        try: items = itemtools.filter_by_class(items, query["sortclass"])
        except KeyError: pass
        try: items = itemtools.filter_by_quality(items, query["quality"])
        except KeyError: pass
        # All of these will probably be displaced because of no positioning info
        try:
            displaced = []
            (items, displaced) = itemtools.sort(items, query["sort"], mergedisplaced = True)
            items += displaced
        except KeyError: pass
        try: items = itemtools.filter_by_capability(items, query["capability"])
        except KeyError: pass

        stats = itemtools.get_stats(items)
        filter_classes = itemtools.get_equippable_classes(items)
        items = itemtools.process_attributes(items)
        price_stats = itemtools.get_price_stats(items)

        return templates.schema_dump(items,
                                     filter_classes,
                                     filter_qualities,
                                     filter_capabilities,
                                     stats,
                                     price_stats)

class attributes:
    """ Dumps all schema attributes in a pretty way """

    def GET(self):
        query = web.input()
        schema = database.load_schema_cached(web.ctx.language)
        attribs = schema.get_attributes()

        attachment_check = query.get("att")
        attribute = None

        if attachment_check:
            items = schema
            attached_items = []

            for attr in attribs:
                if attr.get_name() == attachment_check:
                    attribute = attr
                    break
            if not attribute:
                return templates.error(attachment_check + ": No such attribute")

            for item in items:
                attrs = item.get_attributes()
                for attr in attrs:
                    attr_name = attr.get_name()
                    if attachment_check == attr_name:
                        if not attribute: attribute = attr
                        attached_items.append(item)
                        break

            return templates.attribute_attachments(itemtools.process_attributes(attached_items), attribute)
        else:
            return templates.attrib_dump(attribs)

class particles:
    def GET(self):
        schema = database.load_schema_cached(web.ctx.language)
        particles = schema.get_particle_systems()

        return templates.particle_dump(particles)
