# BdOIDS Ranking Archiver

A production-grade toolchain to crawl, archive, bundle, and serve contest scoreboards from Contest Management System (CMS) Ranking Web Server (RWS) instances. Generates an interactive static multi-page application featuring contest replays, submission inspectors, performance graphs, customizable medal rules, and ranklist exporters.

## System Architecture

The archiver operates across four integrated stages:

1. **Ingestion (CMS Crawler / Importer)**: Concurrently downloads all standard CMS RWS endpoints (`contests`, `tasks`, `teams`, `users`, `scores`, `history`, `sublist`, `faces`, `flags`, and `asset_config`) using a thread pool with exponential backoff and retry handling. Alternatively, imports existing raw CMS dumps from disk.
2. **Catalog & Metadata**: Manages contest metadata, award thresholds (Gold, Silver, Bronze, Honorable Mention), disqualified/cheater tags, and guest user flags through a centralized catalog (`site/src/contests.json`).
3. **Data Bundling**: Consolidates hundreds of raw JSON files per contest into a single, optimized `data.json` loaded lazily via Vite module preloading for instantaneous client-side rendering.
4. **Replay Interface**: Serves an interactive scoreboard allowing full chronological timeline scrubbing, detailed subtask breakdowns, SVG score progression graphs, and multi-contest portal navigation.

## Prerequisites

- **Python**: 3.8 or higher
- **Node.js**: 18.0 or higher
- **Package Managers**: `pip` and `npm`

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd site
npm install
cd ..
```

## Quick Start

### 1. Archiving a Live CMS Scoreboard

To crawl a live CMS ranking server, register it in the portal, bundle its assets, and compile the production build:

```bash
python3 archive.py https://ranking.example.org \
  --slug bdoids-round-4 \
  --title "BdOIDS Round 4" \
  --gold 3 --silver 10 --bronze 19 \
  --build
```

### 2. Importing a Local Archive Folder

To import a previously downloaded CMS directory into the catalog and build:

```bash
python3 archive.py --import-dir ./raw_dump \
  --slug bdoids-round-4 \
  --title "BdOIDS Round 4" \
  --build
```

### 3. Re-building the Portal

To re-convert all registered contest archives in `site/archive-inputs/` and recompile the static frontend:

```bash
python3 archive.py --build-only
```

Or using npm directly:

```bash
cd site
node scripts/convert-archive.mjs
npm run build
```

### 4. Local Development and Preview

Start the Vite development server to test changes live with hot module replacement:

```bash
cd site
npm run dev
```

To preview the production build locally:

```bash
cd site
npm run preview
```

## Command-Line Reference

### `archive.py`

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `url` | Positional | `None` | URL of the live CMS Ranking Web Server |
| `--import-dir` | String | `None` | Path to a local raw CMS dump folder to import |
| `--slug` | String | Inferred | Unique URL identifier for the contest (e.g. `bdoids-round-4`) |
| `--title` | String | Inferred | Human-readable title displayed on the site and navigation |
| `--description` | String | `None` | Description recorded in `contests.json` |
| `-s`, `--sessions` | Integer | `16` | Number of concurrent download worker threads |
| `-r`, `--retry` | Integer | `5` | HTTP retry attempts per endpoint on transient failure |
| `--timeout` | Integer | `25` | HTTP request timeout in seconds |
| `--gold` | Integer | Calculated | Gold medal rank cutoff (defaults to standard ~1/12 ratio) |
| `--silver` | Integer | Calculated | Silver medal rank cutoff (defaults to standard ~1/4 ratio) |
| `--bronze` | Integer | Calculated | Bronze medal rank cutoff (defaults to standard ~1/2 ratio) |
| `--hm` | Integer | `None` | Custom Honorable Mention rank cutoff |
| `--medal-ranks` | JSON | `None` | JSON map for discrete medal positions (e.g. `'{"gold":[1],"bronze":[3]}'`) |
| `--ioi-hm` | Flag | `False` | Enable IOI Honorable Mention rule (non-medalist with 100 on >= 1 task) |
| `--no-medals` | Flag | `False` | Disable all medal badges and calculations |
| `--unofficial` | Flag | `False` | Mark contest as unofficial (disables medal styling) |
| `--unofficial-users` | List | `None` | User keys highlighted in blue as guest or unofficial participants |
| `--cheaters` | List | `None` | User keys highlighted in red as disqualified or cheaters |
| `--zero-cheater-scores`| Flag | `False` | Zero task scores for marked cheaters (preserves original scores by default) |
| `--nocontest` | Flag | `False` | Suppress contest total columns in the scoreboard |
| `--noglobal` | Flag | `False` | Suppress global total column in the scoreboard |
| `--nofaces` | Flag | `False` | Skip downloading contestant avatar images |
| `--noflags` | Flag | `False` | Skip downloading country and team flag images |
| `--nosublist` | Flag | `False` | Skip downloading individual submission history files |
| `--build` | Flag | `False` | Automatically run `convert-archive.mjs` and `npm run build` |
| `--build-only` | Flag | `False` | Skip crawling/importing; only re-bundle and compile existing archives |
| `--export-json` | String | `None` | Export computed ranklist to JSON file |
| `--export-csv` | String | `None` | Export computed ranklist to CSV file |
| `--standalone-dir` | String | `None` | Additionally output a standalone legacy archive folder using `cmsranking/` assets |

## Contest Catalog

All archived rounds are tracked in `site/src/contests.json`. This file acts as the single source of truth for Rollup build entries, navigation, and landing page rendering:

```json
[
  {
    "slug": "bdoids-round-1",
    "title": "BdOIDS Round 1",
    "dir": "round-1",
    "description": "BdOIDS Selection Contest - Round 1"
  },
  {
    "slug": "bdoids-round-2",
    "title": "BdOIDS Round 2",
    "dir": "round-2",
    "description": "BdOIDS Selection Contest - Round 2"
  },
  {
    "slug": "bdoids-round-3",
    "title": "BdOIDS Round 3",
    "dir": "round-3",
    "description": "BdOIDS Selection Contest - Round 3"
  }
]
```

When running `archive.py`, entries are added or updated automatically.

## Data Exporter

The repository includes a dedicated exporter (`export_json.py`) to convert raw or bundled archives into structured tabular datasets for analysis, ratings, or archival records.

### Usage

```bash
# Export from a contest slug or bundled data:
python3 export_json.py bdoids-round-1 ranklist.json

# Export directly to CSV format:
python3 export_json.py bdoids-round-1 ranklist.csv --csv
```

### Output Schema

```json
[
  {
    "rank": 1,
    "username": "marzuq4849",
    "first_name": "Mohammed Marzuq",
    "last_name": "Rahman",
    "full_name": "Mohammed Marzuq Rahman",
    "team": "BGD",
    "scores": {
      "blackmath": 100.0,
      "groupchat": 60.0,
      "summand": 86.0
    },
    "total": 246.0,
    "award": "gold",
    "is_cheater": false,
    "is_unofficial": false
  }
]
```

## Deployment

The static output is generated in `site/dist/` and requires no backend runtime.

### GitHub Pages

To deploy using GitHub Pages:

1. Configure your repository to publish from the `gh-pages` branch or root folder.
2. Build the production assets:
   ```bash
   python3 archive.py --build-only
   ```
3. Push the contents of `site/dist/` to your target branch.

### Vercel / Netlify

A `vercel.json` file is preconfigured in `site/`. Link the repository to your Vercel project with the Root Directory set to `site` and Build Command set to:

```bash
node scripts/convert-archive.mjs && npm run build
```

Output directory: `dist`.

### Standalone Web Server (Nginx / Apache)

Point your web server root directly to `site/dist/`. For Nginx:

```nginx
server {
    listen 80;
    server_name ranking.example.org;
    root /path/to/bdoids-ranking-archiver/site/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## License and Credits

- Archiver tooling and data pipeline developed for **BdOIDS (Bangladesh Olympiad in Informatics Development Squad)**.
- Replay interface architecture adapted from [ioi-rankings-archive](https://github.com/ryanbai1412/ioi-rankings-archive) by Ryan Bai.
- Base ranking UI components modified from [CMS (Contest Management System)](https://github.com/cms-dev/cms).
- Licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.
