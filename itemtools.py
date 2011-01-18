import web, config, steam, database
from copy import deepcopy

qualitydict = {"unique": "The",
               "normal": ""}

# I don't like this either but Valve didn't expose them
# through the API
particledict = {0: "Invalid Particle",
                1: "Particle 1",
                2: "Flying Bits",
                3: "Nemesis Burst",
                4: "Community Sparkle",
                5: "Holy Glow",
                6: "Green Confetti",
                7: "Purple Confetti",
                8: "Haunted Ghosts",
                9: "Green Energy",
                10: "Purple Energy",
                11: "Circling TF Logo",
                12: "Massed Flies",
                13: "Burning Flames",
                14: "Scorching Flames",
                15: "Searing Plasma",
                16: "Vivid Plasma",
                17: "Sunbeams",
                18: "Circling Peace Sign",
                19: "Circling Heart",
                20: "Map Stamps"}

pack = steam.backpack()

def generate_full_item_name(item, ignore_qdict = False):
    """ Ignores the values in qualitydict if ignore_qdict is True """
    quality_str = pack.get_item_quality(item)["str"]
    pretty_quality_str = pack.get_item_quality(item)["prettystr"]
    custom_name = pack.get_item_custom_name(item)
    item_name = pack.get_item_name(item)

    if ignore_qdict:
        prefix = pretty_quality_str + " "
    else:
        prefix = qualitydict.get(quality_str, pretty_quality_str) + " "

    if item_name.find("The ") != -1 and pack.is_item_prefixed(item):
        item_name = item_name[4:]

    if custom_name or (not pack.is_item_prefixed(item) and quality_str == "unique"):
        prefix = ""
    if custom_name:
        item_name = custom_name

    item_name = web.websafe(item_name)

    if ignore_qdict and (quality_str == "unique" or quality_str == "normal"):
        return item_name
    else:
        return prefix + item_name

def absolute_url(relative_url):
    domain = web.ctx.homedomain
    if domain.endswith('/'): domain = domain[:-1]
    return domain + relative_url

def get_invalid_pos(items):
    poslist = []
    invalid_items = []
    for item in items:
        if not item: continue
        pos = pack.get_item_position(item)
        if pos != -1 and pos not in poslist:
            poslist.append(pack.get_item_position(item))
        else:
            for item in items:
                if item and item not in invalid_items and pos == pack.get_item_position(item):
                    invalid_items.append(deepcopy(item))

    return invalid_items

def sort(items, sortby):
    itemcmp = None
    def defcmp(x, y):
        if x < y:
            return -1
        elif x > y:
            return 1
        elif x == y:
            return 0

    if sortby == "time":
        items.reverse()

    if sortby == "serial":
        def itemcmp(x, y):
            return defcmp(pack.get_item_id(x),
                          pack.get_item_id(y))
    elif sortby == "cell":
        def itemcmp(x, y):
            return defcmp(pack.get_item_position(x),
                          pack.get_item_position(y))
    elif sortby == "level":
        def itemcmp(x, y):
            return defcmp(pack.get_item_level(x),
                          pack.get_item_level(y))
    elif sortby == "name":
        def itemcmp(x, y):
            return defcmp(generate_full_item_name(x),
                          generate_full_item_name(y))
    elif sortby == "slot":
        def itemcmp(x, y):
            return defcmp(pack.get_item_slot(x), pack.get_item_slot(y))
    elif sortby == "class":
        def itemcmp(x, y):
            cx = pack.get_item_equipable_classes(x)
            cy = pack.get_item_equipable_classes(y)
            lenx = len(cx)
            leny = len(cy)

            if lenx == 1 and leny == 1:
                return defcmp(cx[0], cy[0])
            else:
                return defcmp(lenx, leny)

    if itemcmp:
        items.sort(cmp = itemcmp)
    if sortby == "cell":
        cursize = config.backpack_padded_size
        newitems = [None] * (cursize + 1)
        for item in items:
            pos = pack.get_item_position(item)
            try:
                if pos > cursize:
                    while pos > cursize:
                        newitems += ([None] * 100)
                        cursize += 100
                if pos > -1 and newitems[pos] == None:
                    newitems[pos] = deepcopy(item)
            except IndexError: pass
        del newitems[0]
        return newitems
    else:
        if len(items) < config.backpack_padded_size:
            items += ([None] * (config.backpack_padded_size - len(items)))
        else:
            remainder = len(items) % 50
            if remainder != 0: items += ([None] * (50 - remainder))
    return items

def filter_by_class(items, theclass):
    filtered_items = []

    for item in items:
        if not item: continue
        classes = pack.get_item_equipable_classes(item)
        for c in classes:
            if c == theclass:
                filtered_items.append(item)
                break
    return filtered_items

def filter_by_quality(items, thequality):
    filtered_items = []

    for item in items:
        if not item: continue
        if str(pack.get_item_quality(item)["id"]) == thequality:
            filtered_items.append(item)
    return filtered_items

def get_stats(items):
    """ Returns a dict of various backpack stats """
    stats = {"weapons": 0,
             "misc": 0,
             "hats": 0,
             "total": 0}

    for item in items:
        if not item: continue

        slot = pack.get_item_slot(item)
        iclass = pack.get_item_class(item)

        stats["total"] += 1

        if slot == "primary" or slot == "melee" or slot == "secondary":
            if iclass.find("token") == -1:
                stats["weapons"] += 1
        elif slot == "head" and iclass.find("token") == -1:
            stats["hats"] += 1
        elif slot == "misc":
            stats["misc"] += 1
    return stats


def process_attributes(items):
    """ Filters attributes for the item list,
    optf2-specific keys are prefixed with optf2_ """

    for item in items:
        if not item: continue
        attrs = pack.get_item_attributes(item)
        item["optf2_untradeable"] = pack.is_item_untradeable(item)
        item["optf2_attrs"] = []
        item["optf2_description"] = pack.get_item_description(item)
        item["optf2_image_url"] = pack.get_item_image(item, pack.ITEM_IMAGE_SMALL)
        item["optf2_image_url_large"] = pack.get_item_image(item, pack.ITEM_IMAGE_LARGE)
        min_level = pack.get_item_min_level(item)
        max_level = pack.get_item_max_level(item)
        pb_level = pack.get_item_level(item)
        custom_desc = pack.get_item_custom_description(item)

        if custom_desc: item["optf2_description"] = custom_desc

        if min_level == max_level:
            item["optf2_level"] = str(min_level)
        else:
            item["optf2_level"] = str(min_level) + "-" + str(max_level)

        if pb_level != None: item["optf2_level"] = pb_level

        for attr in attrs:
            desc = pack.get_attribute_description(attr)

            if pack.get_attribute_name(attr) == "cannot trade":
                item["optf2_untradeable"] = True
                continue

            # Contained item is a schema id, this is an incredibly
            # ugly hack but I'm too stubborn to make DB changes for this
            if pack.get_attribute_name(attr) == "referenced item def":
                giftcontents = pack.get_attribute_value(attr)

                if not isinstance(giftcontents, dict):
                    giftcontents = pack.get_item_by_schema_id(int(giftcontents))

                giftcontents["optf2_gift_container_id"] = pack.get_item_id(item)
                item["optf2_gift_content"] = generate_full_item_name(giftcontents)
                item["optf2_gift_content_id"] = pack.get_item_schema_id(giftcontents)
                item["optf2_gift_quality"] = pack.get_item_quality(giftcontents)["str"]
                item["optf2_gift_item"] = giftcontents

                attr["description_string"] = 'Contains ' + item["optf2_gift_content"]
                attr["hidden"] = False

            # Workaround until Valve gives sane values
            if (pack.get_attribute_value_type(attr) != "date" and
                attr["value"] > 1000000000 and
                "float_value" in attr):
                attr["value"] = attr["float_value"]

            if pack.get_attribute_name(attr) == "set item tint RGB":
                raw_rgb = int(pack.get_attribute_value(attr))
                # Set to purple for team colored paint
                if pack.get_item_schema_id(item) != 5023 and raw_rgb == 1:
                    item_color = 'url("{0}team_splotch.png")'.format(config.static_prefix)
                else:
                    item_color = "#{0:02X}{1:02X}{2:02X}".format((raw_rgb >> 16) & 0xFF,
                                                                 (raw_rgb >> 8) & 0xFF,
                                                                 (raw_rgb) & 0xFF)

                # Workaround until the icons for colored paint cans are correct
                schema_paintcan = pack.get_item_by_schema_id(pack.get_item_schema_id(item))
                if (schema_paintcan and
                    schema_paintcan.get("name", "").startswith("Paint Can") and
                    raw_rgb != 1 and raw_rgb != 0):
                    paintcan_url = "{0}item_icons/Paint_Can_{1}.png".format(config.static_prefix,
                                                                            item_color[1:])
                    item["optf2_image_url"] = absolute_url(paintcan_url)
                    item["optf2_image_url_large"] = absolute_url(paintcan_url)
                item["optf2_color"] = item_color
                continue

            if pack.get_attribute_name(attr) == "attach particle effect":
                attr["description_string"] = ("Effect: " +
                                              particledict.get(int(attr["value"]), particledict[0]))

            if pack.get_attribute_name(attr) == "gifter account id":
                attr["description_string"] = "Gift"
                item["optf2_gift_from"] = "7656" + str(int(pack.get_attribute_value(attr) +
                                                           1197960265728))
                try:
                    user = database.load_profile_cached(item["optf2_gift_from"], stale = True)
                    item["optf2_gift_from_persona"] = user.get_persona()
                    attr["description_string"] = "Gift from " + item["optf2_gift_from_persona"]
                except:
                    item["optf2_gift_from_persona"] = "this user"

            if "description_string" in attr and not pack.is_attribute_hidden(attr):
                attr["description_string"] = web.websafe(attr["description_string"])
            else:
                continue
            item["optf2_attrs"].append(deepcopy(attr))

        quality_str = pack.get_item_quality(item)["str"]
        full_qdict_name = generate_full_item_name(item)
        full_default_name = generate_full_item_name(item, True)

        item["optf2_cell_name"] = '<div class="{0}_name item_name">{1}</div>'.format(quality_str, full_qdict_name)

        color = item.get("optf2_color")
        paint_job = ""
        if color:
            if color.startswith("url"):
                color = "#FF00FF"
                paint_job = '<span><b style="color: #B8383B;">Pain</b><b style="color: #5885A2;">ted</b></span>'
            else:
                paint_job = '<span style="color: {0}; font-weight: bold;">Painted</span>'.format(color)
        item["optf2_painted_text"] = paint_job
        item["optf2_dedicated_name"] = "{0} {1}".format(paint_job, full_default_name)

        if color:
            paint_job = "Painted"
        item["optf2_title_name"] = "{0} {1}".format(paint_job, full_default_name)

        if color:
            paint_job = "(Painted)"
        else:
            paint_job = ""
        item["optf2_feed_name"] = "{0} {1}".format(full_qdict_name, paint_job)

    return items

def get_equippable_classes(items):
    """ Returns a set of classes that can equip this
    item """

    valid_classes = set()

    for item in items:
        if not item: continue
        classes = pack.get_item_equipable_classes(item)
        if classes[0]: valid_classes |= set(classes)

    return sorted(list(valid_classes))

def _quality_sort(x, y):
    px = x["prettystr"]
    py = y["prettystr"]

    if px < py: return -1
    elif px > py: return 1
    else: return 0

def get_present_qualities(items):
    """ Returns a sorted list of qualities that are in this set
    of items """

    qualities = set()
    qlist = []

    for item in items:
        if not item: continue
        quality = pack.get_item_quality(item)
        if quality["id"] not in qualities:
            qualities.add(quality["id"])
            qlist.append(quality)

    qlist.sort(cmp = _quality_sort)
    return qlist
