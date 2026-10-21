#!/usr/bin/env python3
"""Unified Contest Management System (CMS) Ranking Archiver.

Crawls, imports, bundles, and exports scoreboards from CMS Ranking Web Server (RWS)
instances into static multi-round web portals or standalone archives.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from typing import Any, Dict, List, Optional, Set

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(ROOT_DIR, "site")
ARCHIVE_INPUTS_DIR = os.path.join(SITE_DIR, "archive-inputs")
CONTESTS_JSON_PATH = os.path.join(SITE_DIR, "src", "contests.json")


def log(msg: str) -> None:
    """Print standard operational log message."""
    print(f"[*] {msg}", flush=True)


def log_step(step: int, total: int, msg: str) -> None:
    """Print step progress message."""
    print(f"[{step}/{total}] {msg}", flush=True)


def log_warn(msg: str) -> None:
    """Print warning message."""
    print(f"[!] Warning: {msg}", file=sys.stderr, flush=True)


def log_error(msg: str) -> None:
    """Print error message."""
    print(f"[-] Error: {msg}", file=sys.stderr, flush=True)


def normalize_user_key(value: Any) -> str:
    """Normalize CMS user keys by resolving underscore encodings."""
    return str(value or "").lower().replace("%5f", "_").replace("_5f", "_").strip()


def parse_user_list(raw_list: Optional[List[str]]) -> List[str]:
    """Parse list of user keys from CLI arguments or config strings."""
    if not raw_list:
        return []
    result: List[str] = []
    for item in raw_list:
        norm = item.replace("%5f", "_").replace("%5F", "_")
        for u in norm.replace(",", " ").split():
            clean = u.strip()
            if clean and clean not in result:
                result.append(clean)
    return result


def resolve_user_keys(raw_list: Optional[List[str]], downloaded_users: Set[str]) -> List[str]:
    """Resolve requested user keys against downloaded keys case-insensitively."""
    requested = parse_user_list(raw_list)
    downloaded_map: Dict[str, str] = {
        normalize_user_key(k): k for k in downloaded_users
    }

    resolved: List[str] = []
    for key in requested:
        actual = downloaded_map.get(normalize_user_key(key), key)
        if actual not in resolved:
            resolved.append(actual)
    return resolved


def create_http_session(retries: int = 5, backoff_factor: float = 0.2) -> requests.Session:
    """Create HTTP session with retry strategies and connection pooling."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=32, pool_maxsize=32)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def download_file(
    session: requests.Session,
    url: str,
    target_path: str,
    timeout: int = 25,
) -> bool:
    """Download single endpoint to disk safely."""
    try:
        response = session.get(url, verify=False, timeout=timeout)
        if response.status_code == 200 and response.content:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(response.content)
            return True
        return False
    except requests.RequestException:
        return False


def crawl_cms(url: str, output_dir: str, args: argparse.Namespace) -> Dict[str, Any]:
    """Crawl live CMS Ranking Web Server endpoints concurrently into output_dir."""
    url = "http://" + url if not url.startswith("http") else url
    url = url.rstrip("/")
    if "Ranking.html" in url:
        url = url[:url.rfind("/")]

    os.makedirs(output_dir, exist_ok=True)
    num_sessions = max(1, args.sessions)
    session = create_http_session(retries=args.retry)

    log(f"Crawling CMS scoreboard from {url}")
    log(f"Concurrency: {num_sessions} worker threads | Retries: {args.retry}")

    # Step 1: Probe remote asset_config if existing
    remote_asset_cfg: Dict[str, Any] = {}
    try:
        cfg_resp = session.get(f"{url}/asset_config", verify=False, timeout=10)
        if cfg_resp.status_code == 200:
            remote_asset_cfg = cfg_resp.json()
            log("Detected existing asset_config on source server.")
    except Exception:
        pass

    # Step 2: Download core directories
    log_step(1, 4, "Fetching contest schema (contests, tasks, teams, users)...")
    dir_names = ["contests", "teams", "tasks", "users"]
    dir_data: Dict[str, Any] = {}

    for d in dir_names:
        target = os.path.join(output_dir, d, "index.html")
        d_url = f"{url}/{d}/"
        if download_file(session, d_url, target, timeout=args.timeout):
            try:
                with open(target, "r", encoding="utf-8") as f:
                    dir_data[d] = json.load(f)
            except Exception:
                dir_data[d] = {}
        else:
            log_error(f"Failed to fetch {d_url}")
            sys.exit(1)

    # Step 3: Fetch core files
    log_step(2, 4, "Fetching global ranking state (scores, history, logos)...")
    core_files = ["scores", "history", "logo", "img/favicon.ico"]
    if args.html:
        core_files.append("Ranking.html")

    for f_name in core_files:
        save_name = "index.html" if f_name == "Ranking.html" else f_name
        target = os.path.join(output_dir, save_name)
        download_file(session, f"{url}/{f_name}", target, timeout=args.timeout)

    # Step 4: Batch concurrent downloads (sublist, faces, flags)
    log_step(3, 4, "Downloading participant assets (submissions, avatars, flags)...")
    users = dir_data.get("users", {})
    teams = dir_data.get("teams", {})
    download_tasks = []

    if not args.nosublist:
        for u_key in users.keys():
            t_url = f"{url}/sublist/{u_key}"
            t_path = os.path.join(output_dir, "sublist", u_key)
            download_tasks.append((t_url, t_path))

    if not args.nofaces:
        for u_key in users.keys():
            t_url = f"{url}/faces/{u_key}"
            t_path = os.path.join(output_dir, "faces", u_key)
            download_tasks.append((t_url, t_path))

    if not args.noflags:
        for t_key in teams.keys():
            t_url = f"{url}/flags/{t_key}"
            t_path = os.path.join(output_dir, "flags", t_key)
            download_tasks.append((t_url, t_path))

    total_tasks = len(download_tasks)
    completed_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_sessions) as executor:
        futures = {
            executor.submit(download_file, session, item[0], item[1], args.timeout): item
            for item in download_tasks
        }
        for future in concurrent.futures.as_completed(futures):
            completed_count += 1
            if completed_count % 50 == 0 or completed_count == total_tasks:
                print(f"    Progress: {completed_count}/{total_tasks} assets retrieved", flush=True)

    # Step 5: Build asset_config metadata
    log_step(4, 4, "Applying contest metadata and award cutoffs...")
    user_keys_set = set(users.keys())

    unofficial_raw = (args.unofficial_users if args.unofficial_users is not None
                      else remote_asset_cfg.get("unofficial_users", []))
    cheaters_raw = (args.cheaters if args.cheaters is not None
                    else remote_asset_cfg.get("cheaters", []))

    unofficial_users = resolve_user_keys(unofficial_raw, user_keys_set)
    cheaters = resolve_user_keys(cheaters_raw, user_keys_set)

    # Zero cheater scores if explicitly requested
    if args.zero_cheater_scores and cheaters:
        scores_path = os.path.join(output_dir, "scores")
        if os.path.exists(scores_path):
            try:
                with open(scores_path, "r", encoding="utf-8") as sf:
                    scores_dict = json.load(sf)
                for ch in cheaters:
                    if ch in scores_dict:
                        for tk in scores_dict[ch]:
                            scores_dict[ch][tk] = 0.0
                with open(scores_path, "w", encoding="utf-8") as sf:
                    json.dump(scores_dict, sf)
                log(f"Zeroed task scores for {len(cheaters)} marked disqualified users.")
            except Exception as e:
                log_warn(f"Failed to zero cheater scores: {e}")

    asset_cfg = dict(remote_asset_cfg)
    asset_cfg.update({
        "nofaces": bool(args.nofaces if args.nofaces is not None else remote_asset_cfg.get("nofaces", False)),
        "noflags": bool(args.noflags if args.noflags is not None else remote_asset_cfg.get("noflags", False)),
        "nosublist": bool(args.nosublist if args.nosublist is not None else remote_asset_cfg.get("nosublist", False)),
        "nocontest": bool(args.nocontest if args.nocontest is not None else remote_asset_cfg.get("nocontest", False)),
        "noglobal": bool(args.noglobal if args.noglobal is not None else remote_asset_cfg.get("noglobal", False)),
        "unofficial": bool(args.unofficial if args.unofficial is not None else remote_asset_cfg.get("unofficial", False)),
        "unofficial_users": unofficial_users,
        "cheaters": cheaters,
    })

    if args.ioi_hm is not None:
        asset_cfg["ioi_hm"] = bool(args.ioi_hm)

    # Medal rules calculation
    has_cli_medals = any(v is not None for v in (args.gold, args.silver, args.bronze, args.hm))
    if args.medal_ranks:
        try:
            asset_cfg["medal_ranks"] = json.loads(args.medal_ranks)
            asset_cfg.pop("medals", None)
            log("Configured explicit rank-based medal awards.")
        except json.JSONDecodeError:
            log_error("Invalid JSON provided for --medal-ranks")
    elif args.no_medals:
        asset_cfg.pop("medals", None)
        asset_cfg.pop("medal_ranks", None)
        asset_cfg["no_medals"] = True
    elif not asset_cfg["unofficial"] and (has_cli_medals or ("medals" not in asset_cfg and "medal_ranks" not in asset_cfg)):
        user_count = len(users)
        source_medals = asset_cfg.get("medals", {})
        gold = args.gold if args.gold is not None else source_medals.get("gold", max(1, round(user_count / 12)))
        silver = args.silver if args.silver is not None else source_medals.get("silver", max(gold + 1, round(user_count / 4)))
        bronze = args.bronze if args.bronze is not None else source_medals.get("bronze", max(silver + 1, round(user_count / 2)))
        medals_dict = {"gold": gold, "silver": silver, "bronze": bronze}
        if args.hm is not None:
            medals_dict["hm"] = args.hm
        elif source_medals.get("hm") is not None:
            medals_dict["hm"] = source_medals["hm"]

        asset_cfg.pop("medal_ranks", None)
        asset_cfg["medals"] = medals_dict
        log(f"Medal cutoffs: Gold <= {gold}, Silver <= {silver}, Bronze <= {bronze} (out of {user_count} participants)")

    with open(os.path.join(output_dir, "asset_config"), "w", encoding="utf-8") as f:
        json.dump(asset_cfg, f, indent=2)

    return dir_data


def import_local_archive(source_dir: str, output_dir: str, args: argparse.Namespace) -> None:
    """Import an existing downloaded raw CMS archive folder."""
    if not os.path.isdir(source_dir):
        log_error(f"Source directory does not exist: {source_dir}")
        sys.exit(1)

    required = ["contests", "tasks", "teams", "users", "scores"]
    missing = [req for req in required if not os.path.exists(os.path.join(source_dir, req))]
    if missing:
        log_error(f"Source directory '{source_dir}' is missing required CMS endpoints: {missing}")
        sys.exit(1)

    log(f"Importing raw CMS archive from '{source_dir}' -> '{output_dir}'")
    shutil.copytree(source_dir, output_dir, dirs_exist_ok=True)

    # Apply metadata updates if flags provided
    config_file = os.path.join(output_dir, "asset_config")
    asset_cfg: Dict[str, Any] = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                asset_cfg = json.load(f)
        except Exception:
            pass

    users_file = os.path.join(output_dir, "users", "index.html")
    user_keys_set: Set[str] = set()
    if os.path.exists(users_file):
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                user_keys_set = set(json.load(f).keys())
        except Exception:
            pass

    if args.cheaters is not None:
        asset_cfg["cheaters"] = resolve_user_keys(args.cheaters, user_keys_set)
    if args.unofficial_users is not None:
        asset_cfg["unofficial_users"] = resolve_user_keys(args.unofficial_users, user_keys_set)
    if args.medal_ranks is not None:
        try:
            asset_cfg["medal_ranks"] = json.loads(args.medal_ranks)
            asset_cfg.pop("medals", None)
        except Exception as e:
            log_warn(f"Failed to parse --medal-ranks: {e}")
    elif any(v is not None for v in (args.gold, args.silver, args.bronze, args.hm)):
        user_count = len(user_keys_set)
        m = asset_cfg.get("medals", {})
        gold = args.gold if args.gold is not None else m.get("gold", max(1, round(user_count / 12)))
        silver = args.silver if args.silver is not None else m.get("silver", max(gold + 1, round(user_count / 4)))
        bronze = args.bronze if args.bronze is not None else m.get("bronze", max(silver + 1, round(user_count / 2)))
        m_dict = {"gold": gold, "silver": silver, "bronze": bronze}
        if args.hm is not None:
            m_dict["hm"] = args.hm
        asset_cfg["medals"] = m_dict
        asset_cfg.pop("medal_ranks", None)

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(asset_cfg, f, indent=2)


def register_contest_entry(
    slug: str,
    title: str,
    dir_name: str,
    description: Optional[str] = None,
) -> None:
    """Register or update contest entry in site/src/contests.json."""
    os.makedirs(os.path.dirname(CONTESTS_JSON_PATH), exist_ok=True)
    contests: List[Dict[str, Any]] = []
    if os.path.exists(CONTESTS_JSON_PATH):
        try:
            with open(CONTESTS_JSON_PATH, "r", encoding="utf-8") as f:
                contests = json.load(f)
        except Exception:
            contests = []

    existing = next((c for c in contests if c.get("slug") == slug), None)
    if existing:
        existing["title"] = title
        existing["dir"] = dir_name
        if description:
            existing["description"] = description
        log(f"Updated existing registry entry for '{slug}'.")
    else:
        new_entry: Dict[str, Any] = {
            "slug": slug,
            "title": title,
            "dir": dir_name,
        }
        if description:
            new_entry["description"] = description
        contests.append(new_entry)
        log(f"Registered new contest '{slug}' in catalog.")

    with open(CONTESTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(contests, f, indent=2)


def run_node_converter() -> bool:
    """Run site/scripts/convert-archive.mjs to bundle contests into data.json."""
    script_path = os.path.join(SITE_DIR, "scripts", "convert-archive.mjs")
    if not os.path.exists(script_path):
        log_error(f"Converter script not found at {script_path}")
        return False

    log("Converting raw archives into optimized static bundle (convert-archive.mjs)...")
    res = subprocess.run(["node", script_path], cwd=SITE_DIR)
    return res.returncode == 0


def run_site_build() -> bool:
    """Run npm run build inside site/."""
    log("Building static web application (vite build)...")
    res = subprocess.run(["npm", "run", "build"], cwd=SITE_DIR)
    return res.returncode == 0


def create_standalone_archive(source_archive_dir: str, standalone_dir: str) -> None:
    """Export a self-contained legacy static archive using cmsranking/ assets."""
    os.makedirs(standalone_dir, exist_ok=True)
    cmsranking_dir = os.path.join(ROOT_DIR, "cmsranking")
    if os.path.exists(cmsranking_dir):
        shutil.copytree(cmsranking_dir, standalone_dir, dirs_exist_ok=True)
    shutil.copytree(source_archive_dir, standalone_dir, dirs_exist_ok=True)
    log(f"Created standalone archive directory at '{standalone_dir}'.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Comprehensive CMS Ranking Archiver and static site generator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Source options
    parser.add_argument("url", nargs="?", help="URL of the CMS Ranking Web Server page")
    parser.add_argument("--import-dir", help="Import an existing local raw CMS archive directory")
    parser.add_argument("--slug", help="Unique URL slug for the contest (e.g. bdoids-round-4)")
    parser.add_argument("--title", help="Human-readable display title (e.g. 'BdOIDS Round 4')")
    parser.add_argument("--description", help="Contest description for the catalog")

    # Network and scraping options
    parser.add_argument("-s", "--sessions", type=int, default=16, help="Concurrent worker threads")
    parser.add_argument("-r", "--retry", type=int, default=5, help="HTTP retry count per request")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP request timeout in seconds")
    parser.add_argument("--html", action="store_true", help="Download original Ranking.html")
    parser.add_argument("--nofaces", action="store_true", default=None, help="Skip downloading user avatars")
    parser.add_argument("--noflags", action="store_true", default=None, help="Skip downloading team flags")
    parser.add_argument("--nosublist", action="store_true", default=None, help="Skip downloading submission logs")

    # Awards and medal options
    parser.add_argument("--gold", type=int, help="Gold medal cutoff rank")
    parser.add_argument("--silver", type=int, help="Silver medal cutoff rank")
    parser.add_argument("--bronze", type=int, help="Bronze medal cutoff rank")
    parser.add_argument("--hm", type=int, help="Honorable Mention cutoff rank")
    parser.add_argument("--medal-ranks", help="JSON map of specific ranks to medals (e.g. '{\"gold\":[1],\"bronze\":[3]}')")
    parser.add_argument("--ioi-hm", action="store_true", default=None, help="Enable IOI Honorable Mention rule")
    parser.add_argument("--no-medals", action="store_true", default=None, help="Disable medal highlights completely")
    parser.add_argument("--unofficial", action="store_true", default=None, help="Mark contest as unofficial")
    parser.add_argument("--unofficial-users", nargs="+", help="User keys highlighted in blue as unofficial")
    parser.add_argument("--cheaters", nargs="+", help="User keys highlighted in red as cheaters/disqualified")
    parser.add_argument("--zero-cheater-scores", action="store_true", help="Set cheater task scores to 0.0")

    # Layout toggles
    parser.add_argument("--nocontest", action="store_true", default=None, help="Hide contest total columns")
    parser.add_argument("--noglobal", action="store_true", default=None, help="Hide global total column")

    # Operational actions
    parser.add_argument("--no-bundle", action="store_true", help="Skip bundling into site/src/<slug>/data.json")
    parser.add_argument("--build", action="store_true", help="Compile production site bundle after archiving")
    parser.add_argument("--build-only", action="store_true", help="Re-convert and build site without scraping")
    parser.add_argument("--export-json", nargs="?", const="ranklist.json", help="Export ranklist to JSON")
    parser.add_argument("--export-csv", nargs="?", const="ranklist.csv", help="Export ranklist to CSV")
    parser.add_argument("--standalone-dir", help="Also generate legacy standalone directory")

    args = parser.parse_args()

    # Mode 1: Build-only
    if args.build_only:
        if not run_node_converter():
            sys.exit(1)
        if not run_site_build():
            sys.exit(1)
        log("Build-only routine completed.")
        return

    # Check for valid source
    if not args.url and not args.import_dir:
        parser.print_help()
        sys.exit(1)

    # Determine contest slug and title
    slug = args.slug
    title = args.title

    temp_staging = None
    if args.url:
        # Pre-assign slug if not specified
        slug_clean = slug or "contest"
        dest_raw_dir = os.path.join(ARCHIVE_INPUTS_DIR, slug_clean)
        crawled_data = crawl_cms(args.url, dest_raw_dir, args)

        # Derive slug and title from crawled contest name if not passed
        if not slug or not title:
            contests_meta = crawled_data.get("contests", {})
            if contests_meta:
                first_k = next(iter(contests_meta))
                raw_name = contests_meta[first_k].get("name", first_k)
                if not slug:
                    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_name).lower().strip("-")
                if not title:
                    title = raw_name.replace("_2d", "-").replace("-", " ")

            if not slug:
                slug = "archived-contest"
            if not title:
                title = slug.replace("-", " ").title()

            # Rename directory if slug was resolved after crawl
            final_raw_dir = os.path.join(ARCHIVE_INPUTS_DIR, slug)
            if dest_raw_dir != final_raw_dir:
                if os.path.exists(final_raw_dir):
                    shutil.rmtree(final_raw_dir)
                shutil.move(dest_raw_dir, final_raw_dir)
                dest_raw_dir = final_raw_dir
    else:
        # Import local directory
        if not slug:
            slug = os.path.basename(os.path.normpath(args.import_dir)).lower()
        if not title:
            title = slug.replace("-", " ").title()

        dest_raw_dir = os.path.join(ARCHIVE_INPUTS_DIR, slug)
        import_local_archive(args.import_dir, dest_raw_dir, args)

    # Register contest in site/src/contests.json
    register_contest_entry(slug, title, dir_name=slug, description=args.description)

    # Run conversion and bundling
    if not args.no_bundle:
        if not run_node_converter():
            log_error("Archive conversion failed.")
            sys.exit(1)

    # Run build if requested
    if args.build:
        if not run_site_build():
            log_error("Site build failed.")
            sys.exit(1)

    # Standalone export if requested
    if args.standalone_dir:
        create_standalone_archive(dest_raw_dir, args.standalone_dir)

    # Ranklist exports if requested
    if args.export_json:
        from export_json import export_ranklist
        out_f = args.export_json if isinstance(args.export_json, str) else os.path.join(dest_raw_dir, "ranklist.json")
        export_ranklist(dest_raw_dir, out_f, to_csv=False)

    if args.export_csv:
        from export_json import export_ranklist
        out_f = args.export_csv if isinstance(args.export_csv, str) else os.path.join(dest_raw_dir, "ranklist.csv")
        export_ranklist(dest_raw_dir, out_f, to_csv=True)

    log(f"Contest '{title}' (slug: {slug}) processed successfully.")


if __name__ == "__main__":
    main()
