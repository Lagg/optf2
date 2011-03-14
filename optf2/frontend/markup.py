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

from config import static_prefix, virtual_root

def generate_cell(item, invalid = False, show_equipped = True):
    if not item: return '<div class="item_cell"></div>'

    item_id = item.get_id()
    schema_item = False
    equipped = (len(item.get_equipped_classes()) > 0)

    if not show_equipped: equipped = False
    if not item_id:
        schema_item = True
        item_id = item.get_schema_id()

    item_link = "{0}item/{1}".format(virtual_root, item_id)
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

    markup = ('<div class="{0} cell-{1}" id="s{2}">' +
              '<a class="item_link" href="{3}">' +
              '<img class="item-image small" src="{4}" alt="{5}"/>' +
              '</a>').format(cell_class, quality, item_id, item_link, item.optf2["image_url"], item_id)

    if item.get_custom_name():
        markup += '<img src="' + static_prefix + 'name_tag.png" class="icon-name" alt="Named"/>'
    if item.get_custom_description():
        markup += '<img src="' + static_prefix + 'desc_tag.png" class="icon-desc"  alt="Described"/>'
    if "gift_from" in item.optf2:
        markup += '<img src="' + static_prefix + 'gift_icon.png" class="icon-gift"  alt="Gift"/>'
    if "color" in item.optf2:
        markup += '<span class="paint_splotch" style="background: ' + item.optf2['color'] + ';">&nbsp;</span>'
    if equippedstr:
        markup += '<span class="equipped">' + equippedstr + '</span>'

    markup += '<div class="item_attribs">' + item.optf2["cell_name"]

    painty = item.optf2.get("painted_text", "")

    markup += '<div class="item-level">Level {0} {1}</div>'.format(item.optf2["level"],
                                                                       item.optf2["type"].encode("utf-8"))

    if item.optf2["description"]: markup += '<div class="item-description">' + item.optf2["description"].replace("\n", "<br/>").encode("utf-8") + '</div>'

    for attr in item.optf2["attrs"]:
        markup += '<div class="attr-' + attr.get_type().encode("utf-8") + '">'
        if "gift_content" in item.optf2 and attr.get_name() == "referenced item def":
            markup += 'Contains <span class="prefix-' + item.optf2['gift_quality'].encode("utf-8") + '">' + item.optf2["gift_content"].encode("utf-8") + '</span>'
        else:
            markup += attr.get_description_formatted().replace("\n", "<br/>")
        markup += '</div>'

    if "paintcan" in item.optf2:
        paintcan = item.optf2["paint_name"]
        markup += '<div class="attr-positive">{1} with {2}</div>'.format(item.optf2["painted_text"], item.get_name())

    if item.is_untradable():
        markup += '<div class="attr-neutral">Untradable</div>'

    markup += '</div></div>\n'

    return markup
