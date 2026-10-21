/* Programming contest management system
 * Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 */

var Config = new function () {
    var self = this;

    self.get_contest_list_url = function () {
        return "contests/";
    };

    self.get_task_list_url = function () {
        return "tasks/";
    };

    self.get_team_list_url = function () {
        return "teams/";
    };

    self.get_user_list_url = function () {
        return "users/";
    };

    self.get_flag_url = function (t_key) {
        return "flags/" + t_key;
    };

    self.get_face_url = function (u_key) {
        return "faces/" + u_key;
    };

    self.get_submissions_url = function (u_key) {
        return "sublist/" + u_key;
    };

    self.get_score_url = function () {
        return "scores";
    };

    self.get_history_url = function () {
        return "history";
    }

    self.get_asset_config_url = function() {
        return "asset_config"
    }

    self.get_user_status_class = function(user) {
        if (!DataStore.asset_config) return "";
        var raw_key = (user && typeof user === "object") ? (user["key"] || user["id"] || user["username"] || "") : String(user || "");
        if (!raw_key) return "";

        function norm(s) {
            return String(s || "").toLowerCase().replace(/(%5f|_5f)/g, "_").trim();
        }

        var k = norm(raw_key);
        if (!k) return "";

        var cheaters = DataStore.asset_config["cheaters"] || [];
        for (var i = 0; i < cheaters.length; i++) {
            var c = norm(cheaters[i]);
            if (c && (c === k || k.indexOf(c) !== -1 || c.indexOf(k) !== -1)) {
                return "user-cheater";
            }
        }

        var unofficial_users = DataStore.asset_config["unofficial_users"] || [];
        for (var j = 0; j < unofficial_users.length; j++) {
            var u = norm(unofficial_users[j]);
            if (u && (u === k || k.indexOf(u) !== -1 || u.indexOf(k) !== -1)) {
                return "user-unofficial";
            }
        }

        return "";
    };

    self.has_full_score_task = function(user) {
        if (!user || typeof user !== "object" || !DataStore.tasks) return false;
        for (var t_key in DataStore.tasks) {
            var task = DataStore.tasks[t_key];
            var task_max = (task && task["max_score"] !== undefined) ? task["max_score"] : 100.0;
            var user_task_score = user["t_" + t_key];
            if (user_task_score !== undefined && user_task_score >= task_max && task_max > 0) {
                return true;
            }
        }
        return false;
    };

    self.get_medal = function(user) {
        if (!DataStore.asset_config || DataStore.asset_config["unofficial"] ||
            (!DataStore.asset_config["medals"] && !DataStore.asset_config["medal_ranks"])) {
            return "";
        }
        if (self.get_user_status_class(user) !== "") {
            return "";
        }

        // Some archives need specific medal positions rather than contiguous
        // cutoff ranges (for example, gold at rank 1 and bronze at rank 3).
        var explicit_medals = DataStore.asset_config["medal_ranks"];
        if (explicit_medals) {
            var explicit_rank = (user && typeof user === "object") ? user["rank"] : user;
            for (var medal_name in explicit_medals) {
                var ranks = explicit_medals[medal_name] || [];
                if (ranks.indexOf(explicit_rank) !== -1) {
                    return "medal-" + medal_name;
                }
            }
            return "";
        }

        var score = (user && typeof user === "object") ? user["global"] : null;
        if (score === null || score === undefined || score <= 0) {
            if (typeof user === "number") {
                var rank = user;
                var medals = DataStore.asset_config["medals"];
                if (rank <= medals["gold"]) return "medal-gold";
                if (rank <= medals["silver"]) return "medal-silver";
                if (rank <= medals["bronze"]) return "medal-bronze";
                if (medals["hm"] && rank <= medals["hm"]) return "medal-hm";
            }
            return "";
        }

        if (DataStore.gold_min_score !== undefined && score >= DataStore.gold_min_score) {
            return "medal-gold";
        }
        if (DataStore.silver_min_score !== undefined && score >= DataStore.silver_min_score) {
            return "medal-silver";
        }
        if (DataStore.bronze_min_score !== undefined && score >= DataStore.bronze_min_score) {
            return "medal-bronze";
        }
        if (DataStore.hm_min_score !== undefined && score >= DataStore.hm_min_score) {
            return "medal-hm";
        }
        if (DataStore.asset_config["ioi_hm"] && self.has_full_score_task(user)) {
            return "medal-hm";
        }

        return "";
    };
};
