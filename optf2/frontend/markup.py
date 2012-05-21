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
from urlparse import urljoin
from optf2.backend import config

virtual_root = config.ini.get("resources", "virtual-root")
static_prefix = config.ini.get("resources", "static-prefix")

def absolute_url(relative_url):
    return urljoin(web.ctx.homedomain, relative_url)

def generate_mode_url(path = "", mode = None):
    """ Generates a URL appropriate for the current mode
    with path appended to it. """

    cg = mode
    default = "tf2"
    try:
        if not mode:
            cg = web.ctx.current_game or default
    except AttributeError:
        print("Couldn't get current game mode, falling back to tf2")
        cg = default

    return virtual_root + cg + "/" + path

def generate_item_description(item):
    desc = item.get_custom_description() or item.get_description()
    if desc: return '<div class="item-description">' + web.websafe(desc).replace('\n', '<br/>') + '</div>'

    return ''

def generate_item_type_line(item, classic = True):
    """ If classic is true the full Level X Y
    formatting will be used, if not only the type and other relevant information
    will be """

    origin_name = ""
    levelprefix = ""
    rank = item.get_rank()
    itemorigin = item.get_origin_name()

    if classic and "level" in item.optf2:
        levelprefix = "Level " + str(item.optf2["level"]) + " "

    if itemorigin:
        origin_name = " - " + itemorigin

    itype = item.get_type()
    if itype.startswith("TF_"): itype = ""

    rankname = ""
    if rank: rankname = rank["name"]
    if rankname: levelprefix = ""

    return '<div class="item-level">{0}{1} {2}{3}</div>'.format(levelprefix,
                                                                web.websafe(rankname),
                                                                web.websafe(itype),
                                                                web.websafe(origin_name))


def generate_item_url(item, user = None, mode = None):
    """ Intelligently generates a URL linking to
    the given item """

    itemid = item.get_id()
    pathuser = ""

    if not mode: mode = web.ctx.current_game

    if itemid and user:
        try: pathuser = str(user.get_id64())
        except AttributeError: pathuser = str(user)

    if pathuser: pathuser += "/"

    return generate_mode_url("item/" + pathuser + str(itemid or item.get_schema_id()), mode = mode)

def generate_item_paint_line(item):
    """ Returns a "Painted with X" line if available """

    if "paint_name" in item.optf2:
        paintcan = item.optf2["paint_name"]
        return '<div class="attr-positive">{0} with {1}</div>'.format(item.optf2["painted_text"], web.websafe(paintcan))
    else:
        return ''

def generate_item_price_string(item, stats):
    assets = None

    if not stats: return None

    if isinstance(stats, dict): assets = stats["assets"]
    else: assets = stats

    try: return "Store price: ${0}".format(assets[item].get_price()["USD"])
    except: return None

def generate_attribute_list(item, showlinks = False):
    markup = ''
    list_open = '<ul class="attribute-list">'
    list_close = '</ul>'
    extra = item.optf2

    morestr = ""
    if showlinks: morestr = ' <a href="{0}">(more)</a>'

    for attr in extra["attrs"]:
        desc = attr.get_description_formatted()
        style = ""
        acct = extra.get("{0}_account".format(attr.get_id()))
        contents = extra.get("contents")

        if "color" in attr.optf2: style = ' style="color: #{0};"'.format(attr.optf2["color"])
        markup += '<li class="attr-{0}"{1}>'.format(attr.get_type(), style)

        if contents and attr.get_name() == "referenced item def":
            markup += extra["content_string"]
            markup += morestr.format(web.http.changequery(contents = 1))
        else:
            markup += web.websafe(desc)

        if acct: markup += morestr.format(generate_mode_url("user/"  + str(acct["id64"])))

        markup += '</li>'

    for eater in extra["eaters"]: markup += '<li class="attr-positive">{0}</li>'.format(eater)

    style = item.get_current_style_name()
    if style: markup += '<li class="attr-neutral">Style: {0}</li>'.format(style)

    quantity = item.get_quantity()
    if quantity > 1: markup += '<li class="attr-neutral">Quantity: {0}</li>'.format(quantity)

    if item.is_untradable(): markup += '<li class="attr-negative">Untradable</li>'
    if item.is_uncraftable(): markup += '<li class="attr-negative">Uncraftable</li>'

    if not markup:
        # XHTML compliance
        markup = '<li></li>'

    return (list_open + markup + list_close)


def generate_cell(item, invalid = False, show_equipped = True, user = None, pricestats = None, mode = None):
    if not item: return '<div class="item_cell"></div>'

    item_id = item.get_id()
    schema_item = False
    equipped = (len(item.get_equipped_classes()) > 0)
    untradable = item.is_untradable()
    uncraftable = item.is_uncraftable()

    if not show_equipped: equipped = False
    if not item_id:
        schema_item = True
        item_id = item.get_schema_id()

    item_link = generate_item_url(item, user, mode = mode)
    quality = item.get_quality()["str"]
    equippedstr = ""
    quantity = item.get_quantity()

    if equipped:
        equippedstr = "Equipped "
    if quantity > 1:
        if not equipped:
            equippedstr += "{0}".format(quantity)
        else:
            equippedstr += "({0})".format(quantity)

    cell_class = "item_cell"
    if not schema_item and item.get_position() <= -1: cell_class += " undropped"
    if untradable: cell_class += " untradable"
    if uncraftable: cell_class += " uncraftable"

    style = ""
    if "namecolor" in item.optf2:
        style = ' style="border-color: #{0};"'.format(item.optf2["namecolor"])

    markup = ('<div class="{0} cell-{1}"{6} id="s{2}">' +
              '<a class="item-link" href="{3}">' +
              '</a>' +
              '<img class="item-image small" src="{4}" alt="{5}"/>'
              ).format(cell_class, quality, item_id, item_link, item.optf2["image_url"], item_id, style)

    contents = item.optf2.get("contents")
    if contents:
        markup += '<img src="' + contents.get_image(item.ITEM_IMAGE_SMALL) + '" alt="0" class="item-image gift-preview"/>'
    if item.get_custom_name():
        markup += '<img src="' + static_prefix + 'name_tag.png" class="icon-name" alt="Named"/>'
    if item.get_custom_description():
        markup += '<img src="' + static_prefix + 'desc_tag.png" class="icon-desc"  alt="Described"/>'
    if item.optf2.get("gift"):
        markup += '<img src="' + static_prefix + 'gift_icon.png" class="icon-gift"  alt="Gift"/>'
    if "color" in item.optf2:
        markup += '<span class="paint_splotch" style="background: ' + item.optf2['color'] + ';">&nbsp;</span>'
    if "color_2" in item.optf2:
        markup += '<span class="paint_splotch secondary" style="background: ' + item.optf2['color_2'] + ';">&nbsp;</span>'
    if "series" in item.optf2:
        markup += '<span class="crate-series-icon">' + str(item.optf2["series"]) + '</span>'
    if "particle-id" in item.optf2:
        markup += '<img class="icon-particle" alt="Picon" src="' + static_prefix + 'particle_icons/' + str(item.optf2["particle-id"]) + '.png"/>'
    if "custom texture" in item.optf2:
        markup += '<img class="icon-custom-texture"  src="' + item.optf2["custom texture"] + '" alt="texture"/>'
    if equippedstr:
        markup += '<span class="equipped">' + equippedstr + '</span>'

    markup += '<div class="tooltip">' + item.optf2["cell_name"]

    painty = item.optf2.get("painted_text", "")

    markup += generate_item_type_line(item)

    markup += generate_item_description(item)

    markup += generate_attribute_list(item, showlinks = False)

    markup += generate_item_paint_line(item)

    pricestr = generate_item_price_string(item, pricestats)
    if pricestr: markup += '<div class="attr-neutral">{0}</div>'.format(pricestr)

    markup += '</div></div>\n'

    return markup

def generate_class_sprite_img(c, styleextra = "", mode = None):
    if not mode: mode = web.ctx.current_game or "tf2"

    idmap = {
        "tf2": ["medic", "demoman", "engineer", "heavy", "pyro", "scout", "sniper", "soldier", "spy"],
        "tf2b": "tf2",
        "p2": ["atlas", "p-body"]
        }

    try:
        rec = idmap[mode]
        if isinstance(rec, str):
            mode = rec
            rec = idmap[rec]
        spriteindex = rec.index(c.lower())
        style = "background: url('{0}') -{1}px 0px;".format(static_prefix + mode + "_class_icons.png", spriteindex * 16)
    except (ValueError, KeyError):
        style = ""

    return '<img class="class-icon" src="{0}" style="{1}{2}" alt="{3}"/>'.format(static_prefix + "pixel.png", style, styleextra, c)
