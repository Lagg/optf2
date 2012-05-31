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
import re
import time
import operator
import steam
from optf2.frontend.markup import absolute_url
from optf2.backend import config
from optf2.backend import log

qualitydict = {"unique": "The",
               "normal": ""}

# Capability string mapping, this will probably need localizing too
capabilitydict = {"can_gift_wrap": "Gift wrappable",
                  "can_craft_count": "Can be a numbered craft",
                  "decodable": "Opened via key",
                  "usable": "Action item",
                  "usable_gc": "Usable outside Action slot",
                  "usable_out_of_game": "Usable out of game",
                  "can_craft_mark": "Holds crafter name",
                  "nameable": "Nameable",
                  "paintable": "Paintable"}

# Russia, for the sake of OPTF2. Give real symbol.
currencysymbols = {"USD": "$",
                   "RUB": "",
                   "GBP": unichr(0x00A3),
                   "EUR": unichr(0x20AC)}

def _(thestring):
    return web.utils.safestr(thestring)

def hilo_to_ugcid64(hi, lo):
    return (int(hi) << 32) | int(lo)

def condensed_to_id64(value):
    return "7656" + str(int(value) + 1197960265728)

def build_page_object_unpositioned(items, pagesize = 50):
    """ Returns the same thing build_page_object does, but
    ignores positioning info and places cells in the order
    items are listed """

    fitems = filter(None, items)
    ilen = len(fitems)
    (pages, rem) = divmod(ilen, pagesize)
    imap = {}

    if rem > 0: pages += 1

    sections = range(1, pages + 1)

    for i in sections:
        imap[i] = fitems[(i - 1) * pagesize:i * pagesize]

    if rem:
        imap[sections[-1]] += [None] * (pagesize - rem)

    return imap

def build_page_object(items, pagesize = 50, ignore_position = False):
    """ Returns a dict of items mapped to their sections and positions, or a default integer
    map if not implemented. Pagesize is the default minimum number of cells to a page
    if ignoreposition is true ignore any positioning info and build pages as items are given
    in the list """

    imap = {}
    displaced = []

    if ignore_position:
        return build_page_object_unpositioned(items, pagesize), displaced

    for item in items:
        if not item: continue

        itempos = item.get_position()

        if itempos < 0:
            displaced.append(item)
            continue

        try:
            section = item.get_category_name()
        except AttributeError:
            section = 1
            if itempos > pagesize:
                (section, diff) = divmod(itempos, pagesize)
                if diff > 0: section += 1

        if section not in imap:
            imap[section] = [None] * (pagesize + 1)

        expandedsize = 0
        if itempos > len(imap[section]) - 1:
            try:
                itempos -= (pagesize * (section - 1))
            except TypeError:
                expandedsize = itempos
                rem = expandedsize % pagesize
                if rem > 0: expandedsize += (pagesize - rem)

        imap[section] += [None] * expandedsize
        imap[section][itempos] = item

    def ded(x): del imap[x][0]
    map(ded, imap.keys())

    return imap, displaced

def sort(items, sortby):
    if not items:
        return []

    itemcmp = None

    if sortby == "id" or sortby == "time":
        itemcmp = operator.methodcaller("get_id")
    elif sortby == "level":
        def levelcmp(obj):
            level = obj.get_level()

            if level == None:
                level = obj.get_min_level()
                levelmax = obj.get_max_level()
                if level != levelmax: level = levelmax - level

            return level
        itemcmp = lambda obj: levelcmp(obj)
    elif sortby == "name":
        itemcmp = lambda obj: obj.get_full_item_name(prefixes = None)
    elif sortby == "slot":
        itemcmp = operator.methodcaller("get_slot")
    elif sortby == "class":
        def classcmp(obj):
            eq = obj.get_equipable_classes()
            eqlen = len(eq)

            if eqlen == 1:
                return eq[0]
            else:
                return eqlen
        itemcmp = lambda obj: classcmp(obj)
    elif sortby == "schemaid":
        itemcmp = operator.methodcaller("get_schema_id")

    solid_items = items

    if itemcmp:
        solid_items = list(items)
        solid_items.sort(key = itemcmp)

        if sortby == "time":
            solid_items.reverse()

    return solid_items

def filter_by_class(items, theclass):
    filtered_items = []

    for item in items:
        if not item: continue
        classes = item.get_equipable_classes()
        for c in classes:
            if c == theclass:
                filtered_items.append(item)
                break
    return filtered_items

def filter_by_quality(items, thequality):
    filtered_items = []

    for item in items:
        if not item: continue
        if str(item.get_quality()["id"]) == thequality:
            filtered_items.append(item)
    return filtered_items

def get_stats(items):
    """ Returns a dict of various backpack stats """
    stats = {"total": 0}
    merged = {
        "weapons": ["primary", "secondary", "melee", "weapon"],
        "hats": ["hat", "head"],
        "misc": ["misc"],
        "pda": ["pda", "pda2"],
        "other": ["none"]
        }

    for item in items:
        if not item: continue

        slot = str(item.get_slot())
        iclass = item.get_class()

        stats["total"] += 1

        ismerged = False

        if iclass and iclass.find("token") != -1:
            slot = "none"

        for k, v in merged.iteritems():
            if slot.lower() in v:
                if k not in stats: stats[k] = 0
                stats[k] += 1
                ismerged = True

        if not ismerged:
            if slot not in stats: stats[slot] = 0
            stats[slot] += 1

    return stats

def process_attributes(items, gift = False):
    """ Filters attributes for the item list,
    optf2-specific data is stored in item.optf2 """

    default_item_image = config.ini.get("resources", "static-prefix") + "item_icons/Invalid_icon.png";
    newitems = []

    for item in items:
        if not item: continue

        schema = item._schema
        custom_texture_lo = None
        custom_texture_hi = None

        if not getattr(item, "optf2", None):
            item.optf2 = {"description": None, "attrs": []}
        attrs = item.get_attributes()
        item.optf2["image_url"] = item.get_image(item.ITEM_IMAGE_SMALL) or default_item_image
        item.optf2["image_url_large"] = item.get_image(item.ITEM_IMAGE_LARGE) or default_item_image
        try:
            namecolor = item.get_name_color()
            if namecolor:
                item.optf2["namecolor"] = namecolor
        except AttributeError: pass
        min_level = item.get_min_level()
        max_level = item.get_max_level()
        pb_level = item.get_level()
        giftcontents = item.get_contents()

        if min_level == max_level:
            item.optf2["level"] = str(min_level)
        else:
            item.optf2["level"] = str(min_level) + "-" + str(max_level)

        if pb_level != None: item.optf2["level"] = pb_level

        # Ordered kill eater attribute lines
        rank = item.get_rank()
        item.optf2["eaters"] = []
        if rank:
            for line in item.get_kill_eaters():
                item.optf2["eaters"].append("{0}: {1}".format(line[1], line[2]))

        for theattr in attrs:
            newattr = {}
            attrname = theattr.get_name()
            attrvaluetype = theattr.get_value_type()
            account_info = theattr.get_account_info()
            item.optf2[str(theattr.get_id()) + "_account"] = account_info

            if attrname == "referenced item def":
                if not giftcontents:
                    giftcontents = schema[int(theattr.get_value())]
                newattr["description_string"] = 'Contains ' + web.websafe(giftcontents.get_full_item_name(prefixes = qualitydict))
                newattr["hidden"] = False

            if (attrname == "set item tint RGB" or
                attrname == "set item tint RGB 2"):
                raw_rgb = int(theattr.get_value())
                secondary_color = attrname.endswith("2")

                # Workaround for Team Spirit values still being 1
                if raw_rgb == 1:
                    raw_rgb = 12073019
                    item.optf2["color_2"] = "#256D8D"

                item_color = "#{0:02X}{1:02X}{2:02X}".format((raw_rgb >> 16) & 0xFF,
                                                             (raw_rgb >> 8) & 0xFF,
                                                             (raw_rgb) & 0xFF)

                try: paint_can = schema[schema.optf2_paints.get(raw_rgb)]
                except KeyError: paint_can = None
                if paint_can: item.optf2["paint_name"] = paint_can.get_name()
                elif "paint_name" not in item.optf2: item.optf2["paint_name"] = "unknown paint"

                # Workaround until the icons for colored paint cans are correct
                if (not secondary_color and
                    item._schema_item.get("name", "").startswith("Paint Can") and
                    raw_rgb != 0):
                    paintcan_url = "{0}item_icons/Paint_Can_{1}.png".format(config.ini.get("resources", "static-prefix"),
                                                                            item_color[1:])
                    item.optf2["image_url"] = absolute_url(paintcan_url)
                    item.optf2["image_url_large"] = absolute_url(paintcan_url)

                if secondary_color:
                    item.optf2["color_2"] = item_color
                else:
                    item.optf2["color"] = item_color
                continue

            if attrname.startswith("attach particle effect"):
                particles = schema.get_particle_systems()
                particleid = int(theattr.get_value())
                particlename = particles.get(particleid)
                if particlename: particlename = particlename["name"]
                else: particlename = str(particleid)
                newattr["description_string"] = ("Effect: " + particlename)
                item.optf2["particle-id"] = particleid

            if attrvaluetype == "account_id" and account_info:
                newattr["hidden"] = False
                newattr["description_string"] = _(theattr.get_description().replace("%s1", account_info["persona"]))

            if attrname == "gifter account id":
                item.optf2["gift"] = account_info

            if attrname == "unique craft index":
                newattr["description_string"] = "Craft number: " + str(int(theattr.get_value()))
                newattr["hidden"] = False

            if attrname == "tradable after date":
                # WORKAROUND: For some reason this has the wrong type and is hidden,
                # not sure if this should be in steamodd or not
                d = time.gmtime(theattr.get_value())
                newattr["description_string"] = "Tradable after: " + time.strftime("%F %H:%M:%S", d)
                newattr["hidden"] = False

            if attrname == "set supply crate series":
                item.optf2["series"] = int(theattr.get_value())

            if attrname == "unlimited quantity":
                item._item["quantity"] = 1

            if attrname == "custom texture lo":
                custom_texture_lo = theattr.get_value()
            elif attrname == "custom texture hi":
                custom_texture_hi = theattr.get_value()

            if not newattr.get("hidden", theattr.is_hidden()):
                newattr["description_string"] = web.websafe(newattr.get("description_string",
                                                                        theattr.get_description()))
            else:
                continue

            finalattr = type(theattr)(dict(theattr._attribute.items() + newattr.items()))
            finalattr.optf2 = {}
            try:
                color = finalattr.get_description_color()
                if color:
                    finalattr.optf2["color"] = color
            except AttributeError: pass
            item.optf2["attrs"].append(finalattr)

        caps = item.get_capabilities()
        if caps:
            item.optf2["capabilities"] = [capabilitydict.get(cap, cap) for cap in caps]

        if giftcontents:
            item.optf2["contents"] = giftcontents
            item.optf2["content_string"] = ('Contains <span class="prefix-{0}">{1}</span>').format(giftcontents.get_quality()["str"],
                                                                                                   web.websafe(giftcontents.get_full_item_name(prefixes = qualitydict)))

        if custom_texture_hi != None and custom_texture_lo != None:
            ugcid = hilo_to_ugcid64(custom_texture_hi, custom_texture_lo)
            try:
                test = steam.remote_storage.user_ugc(item._schema._app_id, ugcid)
                item.optf2["custom texture"] = test.get_url()
            except steam.remote_storage.UGCError:
                pass

        quality_str = item.get_quality()["str"]
        full_qdict_name = web.websafe(item.get_full_item_name(prefixes = qualitydict))
        full_unquoted_default_name = item.get_full_item_name({"normal": None, "unique": None})
        full_default_name = web.websafe(full_unquoted_default_name)
        color = item.optf2.get("color")
        color_2 = item.optf2.get("color_2")
        paint_job = ""
        prefix = ""

        if color and color_2:
            paint_job = '<span><b style="color: {0};">Pain</b><b style="color: {1};">ted</b></span>'.format(color,
                                                                                                            color_2)
        elif color:
            paint_job = '<span style="color: {0}; font-weight: bold;">Painted</span>'.format(color)

        if gift:
            prefix = '<span class="prefix-giftwrapped">Giftwrapped</span>'

        item.optf2["painted_text"] = paint_job
        item.optf2["dedicated_name"] = "{0} {1}".format(_(prefix), _(full_default_name))

        style = ""
        if "namecolor" in item.optf2:
            style = ' style="color: #' + item.optf2["namecolor"] + ';"'
        item.optf2["cell_name"] = '<div class="prefix-{0} item-name"{2}>{1}</div>'.format(_(quality_str),
                                                                                           _(full_qdict_name),
                                                                                           style)

        if color:
            paint_job = "Painted"
        if gift:
            prefix = "Giftwrapped"
        item.optf2["title_name"] = "{0} {1} {2}".format(_(prefix), _(paint_job), _(full_unquoted_default_name))

        if color:
            paint_job = "(Painted)"
        else:
            paint_job = ""
        item.optf2["feed_name"] = "{0} {1}".format(_(full_qdict_name), _(paint_job))

        newitems.append(item)

    return newitems

def get_equippable_classes(items, cache):
    """ Returns a set of classes that can equip the listed items """

    valid_classes = set()
    schema = cache.get_schema()

    if not items: return []

    for item in items:
        if not item: continue
        classes = item.get_equipable_classes()
        valid_classes |= set(classes)

    ordered_classes = list(schema.get_classes().values())
    for c in ordered_classes:
        if c not in valid_classes:
            del c

    return ordered_classes

def get_present_qualities(items):
    """ Returns a sorted list of qualities that are in this set
    of items """

    qualities = set()
    qlist = []

    for item in items:
        if not item: continue
        quality = item.get_quality()
        if quality["id"] not in qualities:
            qualities.add(quality["id"])
            qlist.append(quality)

    qlist.sort(key = lambda q: q["prettystr"])
    return qlist

def get_present_capabilities(items):
    """ Returns a sorted list of capabilities in this set of items,
    uses the capabilitydict """

    caps = set()

    for item in items:
        if not item: continue
        caps |= set(item.get_capabilities())

    caplist = [{"name": capabilitydict.get(cap, cap), "flag": cap} for cap in caps]
    caplist.sort(key = operator.itemgetter("name"))
    return caplist

def filter_by_capability(items, capability):

    if not items: return []

    filtered = []
    for item in items:
        if not item: continue
        if capability in item.get_capabilities():
            filtered.append(item)

    return filtered

def get_price_stats(items, cache):
    assets = cache.get_assets()
    stats = {"assets": assets, "sym": currencysymbols, "worth": {}, "most-expensive": [], "avg": {}}

    if not assets:
        return stats

    worth = stats["worth"]
    costs = {}
    count = 0

    for item in items:
        if not item: continue
        if item.get_id() and item.get_origin_id() != 2:
            continue # Not explicit purchase
        try:
            asset = assets[item].get_price()
            count += 1
        except KeyError: continue
        costs[item] = asset
        for k, v in asset.iteritems():
            if k not in worth:
                worth[k] = v
            else:
                worth[k] += v

    stats["most-expensive"] = [item for item in sorted(costs.iteritems(), reverse = True, key = operator.itemgetter(1))[:10]]

    if count != 0:
        for k, v in worth.iteritems():
            stats["avg"][k] = round((v / count), 2)

    return stats
