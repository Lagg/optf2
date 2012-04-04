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

    $(".item-link").each(function() {
        var idpart = String($(this).parent().attr("id").slice(1));
        itemurls[idpart] = $(this).attr("href");
    });

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

    /* Still somewhat experimental, aim to replace most
       of toolbar */
    var filterbar = document.createElement("input");
    var default_filter = "Search..."
    filterbar.setAttribute("type", "text");
    filterbar.setAttribute("id", "filterbar");
    filterbar.value = default_filter;
    $(filterbar).appendTo("#option-controls");
    $(filterbar).focus(function() { this.value = ""; });

    function filtermagic(e) {
	var filter = $("#filterbar").val().toLowerCase();
	var cells = $(".item_cell");

	if (filter.length == 0) {
	    cells.show();
	    return;
	}

	cells.each(function() {
	    var cell = $(this);
	    var attribs = cell.find(".tooltip");

	    if (attribs.length == 0) {
		cell.hide();
		return;
	    }

	    if (cell.hasClass("cell-" + filter)) {
		cell.show();
		return;
	    }

	    attribs.each(function() {
		var name = $(this).text().toLowerCase();
		var pos = name.search(filter);

		if(pos == -1) {
		    cell.hide();
		} else {
		    cell.show();
		    return false;
		}
	    });
	});
    }
    $(filterbar).autocomplete({delay: 100, minLength: 0, search: filtermagic, source: []});

    cells.hover(function() {
        var attribs = $(this).find(".tooltip");
        var currentoffset = $(this).offset();
        attribs.show();
        currentoffset["top"] += $(this).height() + 5;
        currentoffset["left"] -= (attribs.width() / 3.4);

        /* Check if attribs go off the document */
        if (currentoffset["left"] < 0) { currentoffset["left"] = 0; }
        if((currentoffset["left"] + attribs.width()) > document.documentElement.clientWidth) {
            currentoffset["left"] = document.documentElement.clientWidth - attribs.width();
        }

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
        $(this).find(".tooltip").hide();
    });
    $(".tooltip").hover(function() { $(this).hide(); });

    $(document).scroll(function() {
        $(".tooltip").hide();
    });

    $(".item-link").click(function(event) {
        event.preventDefault();
        item_open($(this).parent().attr("id").slice(1));
    });

    $(".item-image").one("error", function() {
        this.src = invalid_icon_url;
        $(this).addClass("invalid");
    });
    $(".icon-particle").one("error", function() {
        $(this).remove();
    });

    $(".button").mousedown(function() { return false; });

    $(".box").each(function() {
        var box = $(this);

        if(!box.hasClass("autosize")) {
            return;
        }

        var innerlength = 0;
        box.children().not(".titlebar").each(function() {
            innerlength += $(this).outerWidth(true);
        });
        box.width(innerlength);
    });

    var search = $("#search-field");
    var default_search = "Enter name, URL, or ID";

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

function preserved_ar_resize(elem, ew, eh, w, h) {
    var ratio = Math.min(w / ew, h / eh);

    elem.width(ratio * ew);
    elem.height(ratio * eh);
}

function item_resize_event(event, ui) {
    var item = $(event.target);
    var image = item.find(".item-image");
    var container = item.find(".item-zoom");


    if (ui.size == undefined) {
        ui.size = {"height":  item.height(),
                   "width": item.width()};
    } else {
        last_dialog_size = ui.size;
    }

    preserved_ar_resize(image, image.width(), image.height(),
                        Math.min(ui.size.width - 200, 512),
                        Math.min(ui.size.height - 100, 512));

    var particle = item.find(".icon-particle");
    preserved_ar_resize(particle, particle.width(), particle.height(),
                        Math.min(container.width()/2.5, 200),
                        Math.min(container.height()/2.5, 200));

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
