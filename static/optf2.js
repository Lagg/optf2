var current_page = 0;
var page_switcher = document.createElement("div");
var ispaginated = false;
var last_dialog_size = null;
var invalid_icon_url = static_prefix + "item_icons/Invalid_icon.png";
var itemurls = {}

$(document).ready(function(){
    var cells = $(".item_cell");
    var pages = $(".backpack-page").not("#page-0");
    var hashpart = document.location.hash;
    var thepage = hashpart.substring(6) - 1;
    var attrib_dict = {};
    var bpinfo = $("#backpack").attr("class").split("-");
    /* TODO: This whole thing is ugly. Also this context number needs to be easier to grab. */
    steam_inventory_prefix = "http://steamcommunity.com/profiles/" + bpinfo[2] + "/inventory#" + bpinfo[1] + "_2_";

    var domattribs = $(".item_attribs");

    $(".item-link").each(function() {
        var idpart = String($(this).parent().attr("id").slice(1));
        itemurls[idpart] = $(this).attr("href");
        this.href = steam_inventory_prefix + idpart;
    });

    domattribs.each(function() { this.id = "a" + $(this).parent().attr("id"); attrib_dict[String(this.id)] = this; });
    domattribs.remove();

    if (pages.length > 0) {
        page_switcher.id = "page-switcher";
        page_switcher.innerHTML = '<div class="button" id="prev-button">&lt; Previous</div><span id="page-counter">' +
            '</span><div class="button" id="next-button">Next &gt;</div>';
        $(page_switcher).appendTo("#backpack");
        $("#next-button, #prev-button").click(backpack_page_switch);
        $(page_switcher).hide();
    }

    if (thepage >= 0 || (get_cookie("pagination") == 1 && pages.length > 0)) {
        var backpack = $("#backpack");

        if (thepage < 0) {
            thepage = 0;
        }

        if (pages[thepage] != undefined) {
            current_page = thepage;
            backpack_mode_paginated(pages);
        }
    }
    var pagination_toggler = document.createElement("div");
    if (ispaginated) {
        pagination_toggler.innerHTML = "Show All";
    } else {
        pagination_toggler.innerHTML = "Show Pages";
    }
    $(pagination_toggler).addClass("button");
    $(pagination_toggler).appendTo("#option-controls");
    $(pagination_toggler).click(function(){
        if (ispaginated) {
            set_cookie("pagination", 0);
            backpack_mode_full(pages);
            pagination_toggler.innerHTML = "Show Pages";
        } else {
            set_cookie("pagination", 1);
            backpack_mode_paginated(pages);
            pagination_toggler.innerHTML = "Show All";
        }
    });

    var untradable_toggler = document.createElement("div");
    untradable_toggler.innerHTML = "Toggle Untradable";
    $(untradable_toggler).addClass("button");
    $(untradable_toggler).appendTo("#option-controls");
    $(untradable_toggler).click(function() {
        fade_untradable();
    });

    cells.hover(function() {
        var attribs = $(attrib_dict["a" + this.id])
        var currentoffset = $(this).offset();
        attribs.appendTo(document.body);
        attribs.show();
        currentoffset["top"] += $(this).height() + 5;
        currentoffset["left"] -= (attribs.width() / 3.4);
        attribs.offset(currentoffset);
        if (attribs.length > 0) {
            var scrollh = $(document).scrollTop();
            /* When a browser supports something simple yet non-standard like
               window.innerHeight, IE has to be ULTRA non-standard.
            */
            var windowh = document.documentElement.clientHeight;
            var offsety = attribs.offset().top;
            var threshold = (scrollh + windowh);
            var posbottom = (offsety + attribs.height());

            if (posbottom > threshold) {
                attribs.offset({top: ($(this).offset()["top"] - attribs.height() - 5)});
            }
        }
    }, function() {
        $("#a" + this.id).remove();
    });

    $(document).scroll(function() {
        $(".item_attribs").remove();
    });

    $(".item-link").click(function(event) {
        event.preventDefault();
        item_open($(this).parent().attr("id").slice(1));
    });

    $(".item-image").one("error", function() {
        this.src = invalid_icon_url;
        $(this).addClass("invalid");
    });

    $(".button").mousedown(function() { return false; });

    var search = $("#search-field");
    var default_search = "Search...";

    search.autocomplete({
        minLength: 2,
        source: autocomplete_magic,
        open: function() { $(".ui-autocomplete").css("z-index", "100"); },
        select: function(e, ui) { this.value = ui.item.value; $("#search-form").submit(); }
    });

    search.val(default_search);
    search.focus(function() { this.value = ""; });
    search.focusout(function() { if(this.value.length == 0) { this.value = default_search; } });
});

function item_image_resize(img, iw, ih, w, h) {
    var ratio = Math.min(w / iw, h / ih);

    img.width(ratio * iw);
    img.height(ratio * ih);
}

function item_resize_event(event, ui) {
    var item = $(event.target);
    var image = item.find(".item-image");

    if (ui.size == undefined) {
        ui.size = {"height":  item.height(),
                   "width": item.width()};
    } else {
        last_dialog_size = ui.size;
    }

    item_image_resize(image, image.width(), image.height(),
                      Math.min(ui.size.width - 200, 512),
                      Math.min(ui.size.height - 100, 512));

    item.height(ui.size.height);
    item.width(image.width() + item.find(".item-attrs").width() + 50);
}

function item_open_success(data, status, xhr) {
    var page = $(data);
    var dialog_title = page.filter("#header").find("h1");
    var dialog_content = page.filter("#content").find("#item_stats");
    var dialog_width = 850;
    var dialog_height = 670;
    var item_id = dialog_content.find("#item_id").html();

    if (last_dialog_size != null) {
        dialog_width = last_dialog_size["width"];
        dialog_height = last_dialog_size["height"];
    }

    var dialog_buttons = dialog_content.find(".item-attrs .button-list");
    dialog_buttons.append("<li><a class=\"button\" href=\"" + itemurls[item_id] + "\">Link to this item</a></li>");
    dialog_buttons.append("<li><a class=\"button\" href=\"" + steam_inventory_prefix + item_id + "\">Steam inventory</a></li>");
    dialog_title.css({"font-size": "1.6em", "margin": "0", "padding": "0"});

    if ($(window).height() < dialog_height) {
        dialog_height = $(window).height();
    }
    if ($(window).width() < dialog_width) {
        dialog_width = $(window).width();
    }

    $("#loading_" + item_id).remove();

    $(dialog_content).dialog({
        resize: item_resize_event,
        open: function(event, ui) {
            var cellimg = $("#s" + item_id + " .item-image");
            if (cellimg.hasClass("invalid")) {
                $(event.target).find(".item-image").attr("src", invalid_icon_url);
            }
            item_resize_event(event, ui);
        },
        title: dialog_title,
        width: dialog_width,
        height: dialog_height,
        minWidth: 250,
        minHeight: 200
    });
}

function item_open(item_id) {
    var item_url = itemurls[item_id];
    var loading_id = "loading_" + item_id;
    var cell_id = $("#s" + item_id);
    if ($("#" + loading_id).length > 0) {
        return;
    }
    cell_id.prepend("<img id=\"" + loading_id + "\" style=\"z-index: 5; position: absolute; top: 37.5px; left: 37.5px;\" src=\"" +
                    static_prefix + "loading.gif\" alt=\"Loading...\"/>");
    var oldcontent = $("body").find(".dedicated_item");
    var reallyoldcontent = null;
    for (var i = 0; i < oldcontent.length; i++) {
        var id = $(oldcontent[i]).find("#item_id").html();
        if (id == item_id) {
            reallyoldcontent = oldcontent[i];
            break;
        }
    }

    if (reallyoldcontent) {
        $("#" + loading_id).remove();
        $(reallyoldcontent).dialog({open: function(e, u) { item_resize_event(e, u); }});
    } else {
        $.get(item_url, item_open_success, {}, "html");
    }
}

function autocomplete_magic(req, resp) {
  var finalcomp = new Array ();
  $.getJSON (virtual_root + "comp/" + req.term, function (data, status) {
      for (var i = 0; i < data.length; i++) {
          itemdata = data[i]
          itemlabel = itemdata["persona"];
          if (itemdata["id_type"] == "id") {
              itemlabel += " (" + itemdata["id"] + ')';
          }
          finalcomp.push({label: itemlabel, value: itemdata["id"]});
      }

      resp (finalcomp.slice (0, 20));
  });
}

function backpack_page_switch() {
    var bp = $("#backpack");
    var packs = $(".backpack-page").not("#page-0");
    var newpage;

    if (this.id == "prev-button") {
        newpage = current_page - 1;
    } else {
        newpage = current_page + 1;
    }

    if (newpage < 0 || (newpage + 1) > packs.length) {
        return;
    }

    if (newpage <= 0) {
        $("#prev-button").addClass("inactive");
    } else {
        $("#prev-button").removeClass("inactive");
    }

    if ((newpage + 2) > packs.length) {
        $("#next-button").addClass("inactive");
    } else {
        $("#next-button").removeClass("inactive");
    }

    $(packs).hide();
    current_page = newpage;
    $(packs[current_page]).show();

    document.location.hash = '#page-' + (current_page + 1);
    $("#page-counter")[0].innerHTML = (current_page + 1) + '/' + packs.length;
}

function backpack_mode_paginated(pages) {
    $("#page-counter")[0].innerHTML = (current_page + 1) + '/' + pages.length;
    pages.hide();
    $(pages[current_page]).show();
    $(page_switcher).show();
    ispaginated = true;
    if(current_page <= 0) {
        $("#prev-button").addClass("inactive");
    } else if ((current_page + 2) > pages.length) {
        $("#next-button").addClass("inactive");
    }
}

function backpack_mode_full(pages) {
    pages.show();
    $(page_switcher).hide();
    ispaginated = false;
}

function delete_cookie(cookie) {
    document.cookie = cookie + "=0; expires=Thu Feb 17 2011 08:33:55 GMT-0700 (MST); path=/";
}

function get_cookie(cookie) {
    cookies = document.cookie.split(';');
    for (i = 0; i < cookies.length; i++) {
        thecookie = cookies[i];
        cookiename = $.trim(thecookie.substr(0, thecookie.indexOf('=')));
        cookievalue = $.trim(thecookie.substr(thecookie.indexOf('=') + 1));

        if (cookiename == cookie) {
            return cookievalue;
        }
    }
}

function set_cookie(cookie, val) {
    document.cookie = cookie + "=" + val+"; path=/";
}

function fade_untradable() {
    $(".item_cell[class~=untradable]").toggleClass("faded");
}
