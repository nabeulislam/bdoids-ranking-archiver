#!/usr/bin/env python
import grequests
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import os
import sys
import json
import urllib3
import argparse
import shutil

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser()
parser.add_argument("url", help="URL of the CMS Ranking Web Server page")
parser.add_argument("output", nargs="?", help="Directory to output static files")
parser.add_argument("-s", "--sessions", help="Number of sessions", type=int, default=16)
parser.add_argument("-r", "--retry", help="Times to retry for each response", type=int, default=5)
parser.add_argument("--html", help="Crawl the page's HTML", action="store_true")
parser.add_argument("--css", help="Crawl the page's CSS", action="store_true")
parser.add_argument("--nofaces", help="Don't crawl user faces", action="store_true")
parser.add_argument("--noflags", help="Don't crawl team flags", action="store_true")
parser.add_argument("--nosublist", help="Don't crawl detailed submission info", action="store_true")
parser.add_argument("--gold", help="Gold medal rank cutoff (default: IOI standard ~1/12 of participants)", type=int)
parser.add_argument("--silver", help="Silver medal rank cutoff (default: IOI standard ~1/4 of participants)", type=int)
parser.add_argument("--bronze", help="Bronze medal rank cutoff (default: IOI standard ~1/2 of participants)", type=int)
parser.add_argument("--hm", help="Honorable Mention rank cutoff", type=int)
parser.add_argument("--ioi-hm", help="Enable official IOI Honorable Mention rule (non-medalist who solved at least 1 task completely)", action="store_true")
parser.add_argument("--no-medals", help="Disable medal colors entirely", action="store_true")
parser.add_argument("--unofficial", help="Mark contest as unofficial (disables medal highlights)", action="store_true")
parser.add_argument("--unofficial-users", help="List of unofficial user keys (highlighted in blue)", nargs="+")
parser.add_argument("--cheaters", help="List of cheater/disqualified user keys (highlighted in red)", nargs="+")
parser.add_argument("--nocontest", help="Remove contest total columns from scoreboard", action="store_true")
parser.add_argument("--noglobal", help="Remove global total column from scoreboard", action="store_true")

args = parser.parse_args()

url = args.url
url = 'http://' + url if url.find('http') < 0 else url
if url.endswith("/"):
    url = url[:-1]
if "Ranking.html" in url:
    url = url[:url.rfind("/")]

dir_names = ["contests", "teams", "tasks", "users"]
file_names = ["logo", "scores", "history", "img/favicon.ico"]
sub_names = ["sublist", "faces", "flags"]
sub_items = [[], [], []]

NUM_SESSIONS = args.sessions
sessions = [requests.Session() for i in range(NUM_SESSIONS)]
retries = Retry(total=5,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504])
for s in sessions:
    s.mount('http://', HTTPAdapter(max_retries=retries))
    s.mount('https://', HTTPAdapter(max_retries=retries))

print("Archiving CMS scoreboard from %s" % url)
print("Using %d sessions" % NUM_SESSIONS)

if args.nofaces:
    sub_names.remove("faces")
if args.noflags:
    sub_names.remove("flags")
if args.nosublist:
    sub_names.remove("sublist")
if args.html:
    file_names.append("Ranking.html")
if args.css:
    file_names.append("Ranking.css")


print("Saving directories...")
rs = [grequests.get(url + "/" + dir_names[i] + "/",
                    verify=False,
                    stream=False,
                    session=sessions[i % NUM_SESSIONS]) for i in range(len(dir_names))]
dir_reqs = grequests.map(rs)

output = args.output
if output is None:
    output = list(dir_reqs[dir_names.index("contests")].json().keys())[0]

print("Copying static files...")
shutil.copytree("cmsranking", output, dirs_exist_ok=True)

for i in range(len(dir_names)):
    if dir_reqs[i] is not None:
        os.makedirs(output + "/" + dir_names[i], exist_ok=True)
        open(output + "/" + dir_names[i] + "/" + "index.html", "wb").write(dir_reqs[i].content)
    else:
        print("Failed to receive directory: %s!" % dir_names[i])


print("Saving files...")
rs = [grequests.get(url + "/" + file_names[i],
                    verify=False,
                    stream=False,
                    session=sessions[i % NUM_SESSIONS]) for i in range(len(file_names))]
file_reqs = grequests.map(rs)

for i in range(len(file_names)):
    if file_reqs[i] is not None:
        if file_names[i] == "Ranking.html":
            file_names[i] = "index.html"
        open(output + "/" + file_names[i], "wb").write(file_reqs[i].content)
    else:
        print("Failed to receive file: %s!" % file_names[i])


user_req = dir_reqs[dir_names.index("users")]
team_req = dir_reqs[dir_names.index("teams")]
if not args.nosublist:
    sub_items[sub_names.index("sublist")] = list(user_req.json().keys())
if not args.nofaces:
    sub_items[sub_names.index("faces")] = list(user_req.json().keys())
if not args.noflags:
    sub_items[sub_names.index("flags")] = list(team_req.json().keys())


for i in range(len(sub_names)):
    print("Saving %s..." % sub_names[i])
    rs = [grequests.get(url + "/" + sub_names[i] + "/" + sub_items[i][j],
                        verify=False,
                        stream=False,
                        session=sessions[j % NUM_SESSIONS]) for j in range(len(sub_items[i]))]
    req = grequests.map(rs)
    os.makedirs(output + "/" + sub_names[i], exist_ok=True)
    for j in range(len(sub_items[i])):
        if req[j] is not None:
            open(output + "/" + sub_names[i] + "/" + sub_items[i][j], "wb").write(req[j].content)
        else:
            print("Failed to receive %s/%s!" % (sub_names[i], sub_items[i][j]))


def parse_user_list(raw_list):
    if not raw_list:
        return []
    result = []
    for item in raw_list:
        item_norm = item.replace("%5f", "_").replace("%5F", "_")
        for u in item_norm.replace(",", " ").split():
            u_clean = u.strip()
            if u_clean and u_clean not in result:
                result.append(u_clean)
    return result

def normalize_user_key(value):
    """Normalize the underscore encoding used by CMS/RWS user keys."""
    return str(value or "").lower().replace("%5f", "_").replace("_5f", "_").strip()


def resolve_user_keys(raw_list, users):
    """Store the actual downloaded key so the archive matches it exactly."""
    requested = parse_user_list(raw_list)
    downloaded = {}
    for key in users:
        downloaded.setdefault(normalize_user_key(key), key)

    resolved = []
    for key in requested:
        actual_key = downloaded.get(normalize_user_key(key), key)
        if actual_key not in resolved:
            resolved.append(actual_key)
        if actual_key != key:
            print("Resolved user key %s -> %s" % (key, actual_key))
    return resolved


downloaded_user_keys = list(user_req.json().keys())
unofficial_users = resolve_user_keys(args.unofficial_users, downloaded_user_keys)
cheaters = resolve_user_keys(args.cheaters, downloaded_user_keys)

# Build asset_config
asset_cfg = {
    "nofaces": args.nofaces,
    "noflags": args.noflags,
    "nosublist": args.nosublist,
    "nocontest": args.nocontest,
    "noglobal": args.noglobal,
    "unofficial": args.unofficial,
    "unofficial_users": unofficial_users,
    "cheaters": cheaters
}

# Medal cutoffs: IOI standard proportions by default (disabled if --no-medals or --unofficial)
if not args.no_medals and not args.unofficial:
    user_count = len(user_req.json())
    gold = args.gold if args.gold is not None else max(1, round(user_count / 12))
    silver = args.silver if args.silver is not None else max(gold + 1, round(user_count / 4))
    bronze = args.bronze if args.bronze is not None else max(silver + 1, round(user_count / 2))
    medals_dict = {"gold": gold, "silver": silver, "bronze": bronze}
    if args.hm is not None:
        medals_dict["hm"] = args.hm
    asset_cfg["medals"] = medals_dict
    asset_cfg["ioi_hm"] = args.ioi_hm
    print("Medal cutoffs: Gold ≤ %d, Silver ≤ %d, Bronze ≤ %d (of %d users)" % (gold, silver, bronze, user_count))
elif args.unofficial:
    print("Unofficial contest mode: Medal highlights disabled.")

open(output + "/asset_config", "w").write(json.dumps(asset_cfg))

print("Cheaters in archive: %s" % (", ".join(cheaters) if cheaters else "none"))
print("Archive output: %s" % os.path.abspath(output))
print("The source URL is read-only; serve/deploy the archive output to view these settings.")

# Copy custom archiver static files to root output directory
shutil.copytree("cmsranking", output, dirs_exist_ok=True)

print("%s Archived!" % url)
print("You can now use any web server (eg. nginx) to serve %s!" % output)
