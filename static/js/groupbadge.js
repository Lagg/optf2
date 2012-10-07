$(document).ready(function() {
    var flattery = ["Beautiful People", "Heroes", "Grizzled Veterans", "Meepros", "Kings of Men", "Mighty Warriors"];
    var groupID = "officialoptf2";
    var groupLink = "http://steamcommunity.com/groups/" + groupID;
    $.getJSON(jsConf.vRoot + "api/groupStats/" + groupID, function(data) {
	var badge = $('<div id="group-badge" class="box"></div>'),
            flatter = flattery[Math.round(Math.random() * 100) % flattery.length];

	badge.insertAfter("#rp-form");

	badge.append('<div class="group-name"><b><a href="' + groupLink + '">' + data.name + '</a></b></div>' +
		     '<div class="member-count"><b>' + data.memberCount + ' ' + flatter + '</b>' +
		     ' - <a class="group-link" href="' +
		     groupLink + '">Be #' + String(data.memberCount + 1) + '</a></div>');

	var statusOrder = { "in-game": -1, "online": 0, "offline": 1 };
	var memberList = data.memberListShort.sort(function (a, b) { return statusOrder[a.status]; });
	var avatarList = $('<div class="member-list"></div>');
	$(memberList.slice(0, 7)).each(function() {
	    avatarList.append('<a href="' + this.profile + '"><img class="member-avatar" src="' + this.avatar + '"/></a>');
	});
	avatarList.appendTo(badge);

	badge.append('<a href="' + groupLink + '"><img class="logo" src="' + data.logo + '"/></a>');
    });
});
