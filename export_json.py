#!/usr/bin/env python3
"""Export archived CMS contest rankings to structured JSON or CSV format."""

import argparse
import csv
import json
import os
import sys


def resolve_archive_data(target_path):
    """Load contest data from either a raw archive directory or bundled data.json."""
    if os.path.isfile(target_path) and target_path.endswith(".json"):
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    # Check if target is a slug or directory inside site/
    candidates = [
        target_path,
        os.path.join("site", "src", target_path, "data.json"),
        os.path.join("site", "archive-inputs", target_path),
        os.path.join("site", "src", target_path),
    ]

    for cand in candidates:
        if os.path.isfile(cand) and cand.endswith(".json"):
            with open(cand, "r", encoding="utf-8") as f:
                return json.load(f)
        if os.path.isdir(cand):
            data_file = os.path.join(cand, "data.json")
            if os.path.exists(data_file):
                with open(data_file, "r", encoding="utf-8") as f:
                    return json.load(f)

            users_file = os.path.join(cand, "users", "index.html")
            scores_file = os.path.join(cand, "scores")
            if os.path.exists(users_file) and os.path.exists(scores_file):
                tasks_file = os.path.join(cand, "tasks", "index.html")
                config_file = os.path.join(cand, "asset_config")

                with open(users_file, "r", encoding="utf-8") as f:
                    users = json.load(f)
                with open(scores_file, "r", encoding="utf-8") as f:
                    scores = json.load(f)
                tasks = {}
                if os.path.exists(tasks_file):
                    with open(tasks_file, "r", encoding="utf-8") as f:
                        tasks = json.load(f)
                asset_cfg = {}
                if os.path.exists(config_file):
                    with open(config_file, "r", encoding="utf-8") as f:
                        asset_cfg = json.load(f)

                return {
                    "users": users,
                    "scores": scores,
                    "tasks": tasks,
                    "asset_config": asset_cfg,
                }

    raise FileNotFoundError(f"Could not locate contest data for path or slug: '{target_path}'")


def compute_ranklist(data):
    """Generate sorted ranklist with task scores, totals, ranks, and awards."""
    users = data.get("users", {})
    scores = data.get("scores", {})
    tasks_data = data.get("tasks", {})
    asset_cfg = data.get("asset_config", {})

    task_keys = sorted(tasks_data.keys(), key=lambda k: tasks_data[k].get("order", 0))

    cheaters = set(asset_cfg.get("cheaters", []))
    unofficial_users = set(asset_cfg.get("unofficial_users", []))
    is_unofficial_contest = bool(asset_cfg.get("unofficial", False))
    no_medals = bool(asset_cfg.get("no_medals", False))
    medal_ranks = asset_cfg.get("medal_ranks")
    medals = asset_cfg.get("medals", {})
    ioi_hm = bool(asset_cfg.get("ioi_hm", False))

    ranklist = []
    for u_key, u_info in users.items():
        raw_u_scores = scores.get(u_key, {})
        u_scores = {}
        is_cheater = u_key in cheaters
        is_unofficial = u_key in unofficial_users

        for t_key in task_keys:
            u_scores[t_key] = 0.0 if is_cheater else float(raw_u_scores.get(t_key, 0.0))
        for t_key, score_val in raw_u_scores.items():
            if t_key not in u_scores:
                u_scores[t_key] = 0.0 if is_cheater else float(score_val)

        total_score = round(sum(u_scores.values()), 2)
        ranklist.append({
            "username": u_key,
            "first_name": u_info.get("f_name", ""),
            "last_name": u_info.get("l_name", ""),
            "full_name": f"{u_info.get('f_name', '')} {u_info.get('l_name', '')}".strip(),
            "team": u_info.get("team", ""),
            "scores": u_scores,
            "total": total_score,
            "is_cheater": is_cheater,
            "is_unofficial": is_unofficial,
        })

    # Sort descending by total score, then ascending by username for stability
    ranklist.sort(key=lambda x: (-x["total"], x["username"]))

    # Assign ranks and determine awards
    for i, item in enumerate(ranklist, 1):
        item["rank"] = i
        award = ""

        if not is_unofficial_contest and not no_medals and not item["is_cheater"] and not item["is_unofficial"]:
            if medal_ranks:
                for award_name in ["gold", "silver", "bronze", "hm"]:
                    if i in medal_ranks.get(award_name, []):
                        award = award_name
                        break
            elif medals and item["total"] > 0:
                gold_cutoff = medals.get("gold", 0)
                silver_cutoff = medals.get("silver", 0)
                bronze_cutoff = medals.get("bronze", 0)
                hm_cutoff = medals.get("hm", 0)

                if i <= gold_cutoff:
                    award = "gold"
                elif i <= silver_cutoff:
                    award = "silver"
                elif i <= bronze_cutoff:
                    award = "bronze"
                elif hm_cutoff and i <= hm_cutoff:
                    award = "hm"

            if not award and ioi_hm:
                # Solved at least 1 task with full score
                solved_full = any(
                    tasks_data.get(t, {}).get("max_score", 100) > 0 and
                    u_scores.get(t, 0.0) >= tasks_data.get(t, {}).get("max_score", 100)
                    for t in task_keys
                )
                if solved_full:
                    award = "hm"

        item["award"] = award

    return ranklist, task_keys


def export_ranklist(target, output_path=None, to_csv=False):
    """Main export routine."""
    data = resolve_archive_data(target)
    ranklist, task_keys = compute_ranklist(data)

    if not output_path:
        ext = ".csv" if to_csv else ".json"
        base_dir = target if os.path.isdir(target) else "."
        output_path = os.path.join(base_dir, f"ranklist{ext}")

    is_csv_target = to_csv or output_path.lower().endswith(".csv")

    if is_csv_target:
        fieldnames = ["rank", "username", "full_name", "team"] + task_keys + [
            "total", "award", "is_cheater", "is_unofficial"
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in ranklist:
                flat_row = {
                    "rank": row["rank"],
                    "username": row["username"],
                    "full_name": row["full_name"],
                    "team": row["team"],
                    "total": row["total"],
                    "award": row["award"],
                    "is_cheater": row["is_cheater"],
                    "is_unofficial": row["is_unofficial"],
                }
                for t in task_keys:
                    flat_row[t] = row["scores"].get(t, 0.0)
                writer.writerow(flat_row)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ranklist, f, indent=2)

    print(f"Exported {len(ranklist)} contestants to '{output_path}'.")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Export CMS contest rankings to JSON or CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("archive", help="Path to archive directory, data.json, or contest slug")
    parser.add_argument("output", nargs="?", help="Output file path (default: ranklist.json or ranklist.csv)")
    parser.add_argument("--csv", action="store_true", help="Export to CSV format instead of JSON")

    args = parser.parse_args()
    try:
        export_ranklist(args.archive, args.output, to_csv=args.csv)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
