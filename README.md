# BdOIDS Ranking Archiver 🏆

A feature-packed tool to crawl, archive, and export scoreboards from **Contest Management System (CMS) Ranking Web Server (RWS)** instances into static web applications or JSON datasets.

Host your archived contest scoreboards effortlessly on **GitHub Pages**, **Vercel**, **Netlify**, or any static web server (Nginx, Apache).

---

## 🌟 Key Features

- ⚡ **Asynchronous Crawling**: Downloads CMS API endpoints, submission histories, user avatars, and team flags in parallel using `grequests`.
- 🏅 **Flexible Medal Rules & Cutoffs**: Custom `--gold`, `--silver`, `--bronze`, and `--hm` (Honorable Mention) cutoff ranks, plus official **IOI Honorable Mention** rules (`--ioi-hm`).
- 🚩 **Participant Tagging & Rank Styling**:
  - **Cheater / Disqualified**: Highlight specific participants in red (`--cheaters`).
  - **Unofficial / Guest Users**: Highlight guest participants in blue (`--unofficial-users`).
  - **Unofficial Contests**: Easily toggle medal rendering off for unofficial rounds (`--unofficial` or `--no-medals`).
- 📊 **Custom Scoreboard Layouts**: Option to hide contest totals (`--nocontest`) or global totals (`--noglobal`).
- 📁 **JSON Data Exporter (`export_json.py`)**: Consolidates raw CMS archive files into a clean `ranklist.json` containing total scores, rank, individual task scores (with explicit `0.0` for missing/unattempted tasks), user full name, team, and cheater/unofficial tags.
- 🚀 **Deployment Ready**: Pre-configured with cache-busting static assets and `vercel.json` for instant deployment.

---

## 📋 Requirements

- **Python**: 3.7+
- Dependencies: `requests`, `grequests`, `urllib3`

```bash
pip install -r requirements.txt
```

---

## 🚀 Quick Start & Usage

### 1. Archiving a CMS Scoreboard

```bash
python3 rws-archiver.py <URL> [output_directory] [options]
```

#### Basic Example
```bash
python3 rws-archiver.py https://ranking.nabeul.ami.bd my_archive
```

#### Advanced Example (With Custom Medals & Cheater Tagging)
```bash
python3 rws-archiver.py https://ranking.nabeul.ami.bd bdoids_round1 \
  --gold 3 --silver 10 --bronze 19 --hm 25 \
  --cheaters cheater_user1 \
  --unofficial-users guest_user1 guest_user2 \
  --noglobal
```

---

## ⚙️ Command-Line Syntax & Options

### `rws-archiver.py`

| Argument | Description |
| :--- | :--- |
| `url` | **(Required)** URL of the CMS Ranking Web Server (e.g., `https://ranking.ioi2019.az`) |
| `output` | Output folder directory for static files (defaults to first contest name) |
| `-s`, `--sessions` | Number of concurrent HTTP sessions (default: `16`) |
| `-r`, `--retry` | Number of HTTP retries per request (default: `5`) |
| `--gold <RANK>` | Gold medal rank cutoff |
| `--silver <RANK>` | Silver medal rank cutoff |
| `--bronze <RANK>` | Bronze medal rank cutoff |
| `--hm <RANK>` | Honorable Mention rank cutoff |
| `--ioi-hm` | Enable official IOI Honorable Mention rule (non-medalist who solved at least 1 task completely) |
| `--no-medals` | Disable medal highlights completely |
| `--unofficial` | Mark entire contest as unofficial (disables medal highlights) |
| `--unofficial-users <KEYS...>` | Space-separated user keys to highlight in blue as unofficial |
| `--cheaters <KEYS...>` | Space-separated user keys to highlight in red as cheaters/disqualified |
| `--nocontest` | Hide contest total columns from scoreboard |
| `--noglobal` | Hide global total column from scoreboard |
| `--nofaces` | Skip downloading user avatars/faces |
| `--noflags` | Skip downloading team/country flags |
| `--nosublist` | Skip downloading detailed submission history per user |

---

## 📊 Exporting Data to JSON

To extract structured ranklist data from an archived contest directory:

```bash
python3 export_json.py <archive_folder> [output_json_file]
```

#### Example:
```bash
python3 export_json.py bdoids_round1
```

#### Sample `ranklist.json` Output:
```json
[
  {
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
    "is_cheater": false,
    "is_unofficial": false,
    "rank": 1
  },
  {
    "username": "antar0172",
    "first_name": "Antar",
    "last_name": "Banik",
    "full_name": "Antar Banik",
    "team": "BGD",
    "scores": {
      "blackmath": 100.0,
      "groupchat": 0.0,
      "summand": 15.0
    },
    "total": 115.0,
    "is_cheater": false,
    "is_unofficial": false,
    "rank": 11
  }
]
```

---

## 🌐 Hosting & Serving the Output

Once archived, the output folder is completely self-contained. You can serve it using:

### Local Web Server
```bash
python3 -m http.server 8000 -d my_archive
```

### Vercel Deployment
The archiver automatically includes `vercel.json` in the output folder. You can deploy it using the Vercel CLI:
```bash
cd my_archive
vercel --prod
```

### GitHub Pages
Copy the archived output folder into your repository root or `docs/` folder and enable GitHub Pages in your repository settings.

---

## 📄 License & Credits

- Archiver & Exporter scripts created for **BdOIDS (Bangladesh Olympiad in Informatics Development Squad)**.
- `cmsranking` frontend assets are modified from [cms-dev/cms](https://github.com/cms-dev/cms/tree/master/cmsranking/static).
- Released under the **AGPL v3 License**.