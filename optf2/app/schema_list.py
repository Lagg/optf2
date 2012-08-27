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
from optf2.frontend import markup

templates = template.template

class items:
    """ Dumps every item in the schema in a pretty way """

    def GET(self):
        query = web.input()
        cache = database.cache()

        try:
            items = [cache._build_processed_item(item) for item in cache.get_schema()]
        except database.CacheEmptyError as E:
            return templates.error(E)

        try:
            filter_classes = markup.sorted_class_list(itemtools.get_equippable_classes(items, cache))
            items = itemtools.filter_by_class(items, query["sortclass"])
        except KeyError:
            pass

        try:
            filter_qualities = markup.get_quality_strings(itemtools.get_present_qualities(items), cache)
            items = itemtools.filter_by_quality(items, query["quality"])
        except KeyError:
            pass

        try:
            filter_capabilities = markup.get_capability_strings(itemtools.get_present_capabilities(items))
            items = itemtools.filter_by_capability(items, query["capability"])
        except KeyError:
            pass

        try:
            items = itemtools.sort(items, query["sort"])
        except KeyError:
            pass

        stats = itemtools.get_stats(items)
        price_stats = itemtools.get_price_stats(items, cache)

        return templates.schema_items(items,
                                      filter_classes,
                                      filter_qualities,
                                      filter_capabilities,
                                      stats,
                                      price_stats)

class attributes:
    """ Dumps all schema attributes in a pretty way """

    def GET(self):
        query = web.input()
        cache = database.cache()

        try:
            schema = cache.get_schema()
            attribs = schema.get_attributes()
        except database.CacheEmptyError as E:
            return templates.error(E)

        attachment_check = query.get("att")
        attribute = None

        if attachment_check:
            items = schema
            attached_items = []

            for attr in attribs:
                if str(attr.get_id()) == str(attachment_check):
                    attribute = attr
                    break
            if not attribute:
                return templates.error(attachment_check + ": No such attribute")

            for item in items:
                attrs = item.get_attributes()
                for attr in attrs:
                    if str(attr.get_id()) == str(attachment_check):
                        if not attribute: attribute = attr
                        attached_items.append(item)
                        break

            return templates.attribute_attachments([cache._build_processed_item(item) for item in attached_items], attribute)
        else:
            return templates.schema_attributes(attribs)

class particles:
    def GET(self):
        try:
            schema = database.cache().get_schema()
            particles = schema.get_particle_systems()

            return templates.schema_particles(particles)
        except database.CacheEmptyError as E:
            return templates.error(E)
