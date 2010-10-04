$(document).ready(function(){
    $(".item_link").removeAttr("href");
});

function item_overlay_success(elem) {
    $("#navbar").remove();
    $("#item_stats").hide().fadeIn('slow');
}

function item_open(item_url) {
    if (($(window).height() - 100) <= 600 ||
        ($(window).width() - 100) <= 800) {
        window.location = item_url;
    } else {
        $().jOverlay({url: item_url, onSuccess: item_overlay_success});
    }
}
