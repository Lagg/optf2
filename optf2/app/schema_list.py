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
error_page = templates.errors

class items:
    """ Dumps every item in the schema in a pretty way """

    def GET(self, app):
        query = web.input()
        cache = database.cache(mode = app)

        markup.init_theme(app)
        markup.set_navlink()

        try:
            sitems = cache.get_processed_schema_items()
            items = sitems["items"].values()
        except database.CacheEmptyError as E:
            raise web.NotFound(error_page.generic(E))

        filters = itemtools.filtering(items)
        try:
            filter_classes = markup.sorted_class_list(itemtools.get_equippable_classes(items, cache), app)
            items = filters.byClass(markup.get_class_for_id(query["cls"], app)[0])
        except KeyError:
            pass

        try:
            filter_qualities = markup.get_quality_strings(itemtools.get_present_qualities(items), cache)
            items = filters.byQuality(query["quality"])
        except KeyError:
            pass

        try:
            filter_capabilities = markup.get_capability_strings(itemtools.get_present_capabilities(items))
            items = filters.byCapability(query["capability"])
        except KeyError:
            pass

        sorter = itemtools.sorting(items)
        try:
            items = sorter.sort(query["sort"])
        except KeyError:
            pass

        stats = itemtools.get_stats(items)
        price_stats = itemtools.get_price_stats(items, cache)

        return templates.schema_items(app, items,
                                      sorter.get_sort_methods(),
                                      filter_classes,
                                      filter_qualities,
                                      filter_capabilities,
                                      stats,
                                      price_stats)

class attributes:
    """ Dumps all schema attributes in a pretty way """

    def GET(self, app, attachment_check = None):
        cache = database.cache(mode = app)

        markup.init_theme(app)
        markup.set_navlink()

        try:
            schema = cache.get_schema()
            attribs = schema.get_attributes()
        except database.CacheEmptyError as E:
            raise web.NotFound(error_page.generic(E))

        attribute = None

        if attachment_check:
            items = cache.get_processed_schema_items()["items"]
            attached_items = []

            for attr in attribs:
                if str(attr.get_id()) == attachment_check:
                    attribute = attr
                    break
            if not attribute:
                raise web.NotFound(error_page.generic(attachment_check + ": No such attribute"))

            for item in cache.get_schema():
                if attr.get_id() in item:
                    attached_items.append(items[item.get_schema_id()])

            return templates.attribute_attachments(app, attached_items, attribute)
        else:
            return templates.schema_attributes(attribs)

class particles:
    def GET(self, app):
        markup.init_theme(app)
        markup.set_navlink()
        try:
            schema = database.cache(mode = app).get_schema()
            particles = schema.get_particle_systems()

            return templates.schema_particles(app, particles)
        except database.CacheEmptyError as E:
            raise web.NotFound(error_page.generic(E))
