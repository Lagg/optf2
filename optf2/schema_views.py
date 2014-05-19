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
import operator

import optf2
from optf2 import items as itemtools
from optf2 import models
from optf2 import markup
from optf2.views import template

class items:
    """ Dumps every item in the schema in a pretty way """

    def GET(self, app):
        query = web.input()
        schema = models.schema(scope = app)

        markup.init_theme(app)
        markup.set_navlink()

        try:
            sitems = schema.processed_items
            items = sitems.values()
        except (models.CacheEmptyError, models.ItemBackendUnimplemented) as E:
            raise web.NotFound(template.errors.generic(E))

        dropdowns = itemtools.build_dropdowns(items)
        filter_classes = markup.sorted_class_list(dropdowns["equipable_classes"], app)
        filter_qualities = markup.get_quality_strings(dropdowns["qualities"], schema)
        filter_capabilities = markup.get_capability_strings(dropdowns["capabilities"])

        filters = itemtools.filtering(items)
        try:
            items = filters.byClass(markup.get_class_for_id(query["cls"], app)[0])
        except KeyError:
            pass

        try:
            items = filters.byQuality(query["quality"])
        except KeyError:
            pass

        try:
            items = filters.byCapability(query["capability"])
        except KeyError:
            pass

        sorter = itemtools.sorting(items)
        try:
            items = sorter.sort(query.get("sort", "SchemaID"))
        except KeyError:
            pass

        item_page = itemtools.item_page(items)
        stats = item_page.summary
        price_stats = item_page.build_price_summary(models.assets(scope = app))

        return template.schema_items(app, items,
                                      sorter.get_sort_methods(),
                                      filter_classes,
                                      filter_qualities,
                                      filter_capabilities,
                                      stats,
                                      price_stats)

class attributes:
    """ Dumps all schema attributes in a pretty way """

    def GET(self, app, attachment_check = None):
        markup.init_theme(app)
        markup.set_navlink()

        try:
            schema = models.schema(scope = app)
            attribs = schema.attributes
        except (models.CacheEmptyError, models.ItemBackendUnimplemented) as E:
            raise web.NotFound(template.errors.generic(E))

        attribute = None

        if attachment_check:
            attached_items = []

            for attr in attribs:
                if str(attr.id) == attachment_check:
                    attribute = attr
                    break
            if not attribute:
                raise web.NotFound(template.errors.generic(attachment_check + ": No such attribute"))

            for item in schema.processed_items.values():
                if attr.id in map(operator.itemgetter("id"), item.get("attrs", [])):
                    attached_items.append(item)

            return template.attribute_attachments(app, attached_items, attribute)
        else:
            return template.schema_attributes(attribs)

class particles:
    def GET(self, app):
        markup.init_theme(app)
        markup.set_navlink()
        try:
            schema = models.schema(scope = app)
            particles = schema.particle_systems

            return template.schema_particles(app, particles)
        except (models.CacheEmptyError, models.ItemBackendUnimplemented) as E:
            raise web.NotFound(template.errors.generic(E))
