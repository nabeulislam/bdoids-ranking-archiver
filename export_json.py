#!/usr/bin/env python3
import json
import sys
import os

if len(sys.argv) < 2:
    print("Usage: python3 export_json.py <archive_folder> [output_json_file]")
    sys.exit(1)

archive_dir = sys.argv[1]
output_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(archive_dir, "ranklist.json")

users_file = os.path.join(archive_dir, "users", "index.html")
scores_file = os.path.join(archive_dir, "scores")
tasks_file = os.path.join(archive_dir, "tasks", "index.html")
config_file = os.path.join(archive_dir, "asset_config")

if not os.path.exists(users_file) or not os.path.exists(scores_file):
    print(f"Error: Could not find CMS archive data in '{archive_dir}'.")
    sys.exit(1)

with open(users_file, "r") as f:
    users = json.load(f)

with open(scores_file, "r") as f:
    scores = json.load(f)

task_keys = []
if os.path.exists(tasks_file):
    with open(tasks_file, "r") as f:
        tasks_data = json.load(f)
        task_keys = sorted(tasks_data.keys(), key=lambda k: tasks_data[k].get("order", 0))

asset_cfg = {}
if os.path.exists(config_file):
    with open(config_file, "r") as f:
        asset_cfg = json.load(f)

cheaters = asset_cfg.get("cheaters", [])
unofficial_users = asset_cfg.get("unofficial_users", [])

ranklist = []
for u_key, u_info in users.items():
    raw_u_scores = scores.get(u_key, {})
    u_scores = {}
    
    # Ensure all tasks are present, defaulting to 0.0 for missing scores
    for t_key in task_keys:
        u_scores[t_key] = float(raw_u_scores.get(t_key, 0.0))
    for t_key, score_val in raw_u_scores.items():
        if t_key not in u_scores:
            u_scores[t_key] = float(score_val)
            
    total_score = sum(u_scores.values())
    ranklist.append({
        "username": u_key,
        "first_name": u_info.get("f_name", ""),
        "last_name": u_info.get("l_name", ""),
        "full_name": f"{u_info.get('f_name', '')} {u_info.get('l_name', '')}".strip(),
        "team": u_info.get("team", ""),
        "scores": u_scores,
        "total": total_score,
        "is_cheater": u_key in cheaters,
        "is_unofficial": u_key in unofficial_users
    })

# Sort by total score descending
ranklist.sort(key=lambda x: x["total"], reverse=True)

# Assign ranks
for i, item in enumerate(ranklist, 1):
    item["rank"] = i

with open(output_file, "w") as f:
    json.dump(ranklist, f, indent=2)

print(f"Successfully exported {len(ranklist)} users to '{output_file}'!")
