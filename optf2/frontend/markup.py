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

def generate_item_price_string(item, stats):
    assets = None

    if not stats: return None

    if isinstance(stats, dict): assets = stats["assets"]
    else: assets = stats

    try: return "Store price: ${0}".format(assets[item].get_price()["USD"])
    except: return None

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

    markup += item.optf2["level_string"]

    if item.optf2["description"]: markup += '<div class="item-description">' + item.optf2["description"].replace("\n", "<br/>").encode("utf-8") + '</div>'

    for attr in item.optf2["attrs"]:
        markup += '<div class="attr-' + attr.get_type().encode("utf-8") + '"'
        if "color" in attr.optf2: markup += ' style="color: #{0};"'.format(attr.optf2["color"])
        markup += '>'
        if attr.get_name() == "referenced item def":
            markup += item.optf2["content_string"]
        else:
            markup += attr.get_description_formatted().replace("\n", "<br/>").encode("utf-8")
        markup += '</div>'

    style = item.get_current_style_name()
    if style: markup += '<div class="attr-neutral">Style: {0}</div>'.format(style)

    if "paintcan" in item.optf2:
        paintcan = item.optf2["paint_name"]
        markup += '<div class="attr-positive">{1} with {2}</div>'.format(item.optf2["painted_text"], item.get_name())

    for line in item.optf2["eaters"]:
        markup += '<div class="attr-positive">' + line + '</div>'

    if untradable:
        markup += '<div class="attr-neutral">Untradable</div>'
    if uncraftable:
        markup += '<div class="attr-neutral">Uncraftable</div>'

    pricestr = generate_item_price_string(item, pricestats)
    if pricestr: markup += '<div class="attr-neutral">{0}</div>'.format(pricestr)

    markup += '</div></div>\n'

    return markup
