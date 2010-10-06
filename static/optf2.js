$(document).ready(function(){
    $(".item_link").removeAttr("href");
});

function item_resize(event, ui) {
    var item = $(event.target);

    item.height(ui.size.height);
    item.width(ui.size.width);
    item.find("#stat_vertrule").height(ui.size.height);
}

function item_open_success(data, status, xhr) {
    var page = $(data);
    var dialog_title = page.filter("#header");
    var dialog_content = page.filter("#content").find("#item_stats");
    var dialog_width = 850;
    var dialog_height = 700;

    if ($(document).height() < dialog_height) {
        dialog_height = $(document).height() - dialog_title.height();
    }
    if ($(document).width() < dialog_width) {
        dialog_width = $(document).width();
    }

    $("#loading_notice").remove();

    $(dialog_content).dialog({
        resize: item_resize,
        title: dialog_title,
        width: dialog_width,
        height: dialog_height,
        modal: true
    });
}

function item_open(item_url, item_id) {
    $("#" + item_id).prepend("<div id=\"loading_notice\"><b>Loading...</b></div>");
    $.get(item_url, item_open_success, {}, "html");
}
