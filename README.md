# 🚀 LinkedIn AI Job Suite & Application Tracker

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Scraping Engine](https://img.shields.io/badge/Scraper-curl__cffi%20(Chrome%20Impersonation)-orange.svg)](https://github.com/lexiforest/curl_cffi)
[![UI](https://img.shields.io/badge/Dashboard-Responsive%20SPA%20GUI-emerald.svg)](#-interactive-web-dashboard)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

An intelligent, privacy-first automation platform that scours LinkedIn for high-relevance jobs, scores them against your resume/CV, deduplicates entries, and provides an interactive web dashboard with an end-to-end job application tracking pipeline.

---

## 🌟 Key Features

### 🕵️ 1. High-Speed Stealth Scraping
- **Browser Fingerprint Impersonation**: Uses `curl_cffi` to mimic authentic Chrome TLS/JA3 fingerprints (`chrome120`), effortlessly avoiding common anti-bot traps and 429 rate limits.
- **Configurable Time Filtering**: Scrapes postings within exact windows (e.g. 24 hours, 48 hours, 4 days, 10 days) using LinkedIn's native `f_TPR` filter.
- **Ground-Truth Workplace & Employment Types**: Queries LinkedIn's internal Voyager endpoints with a robust contextual fallback parser (prevents false positives like "hybrid cloud" or "remote sensing").
- **Domestic & International Segregation**: Automatically tags and segments postings from global tech hubs (US, Europe, Canada, Remote, India).

### 🎯 2. CV & Resume Relevancy Scoring
- **Dynamic Semantic Matching**: Parses your CV/resume (PDF or text) and weights key engineering capabilities (LLMs, Agentic AI, RAG, LangGraph, Python, FastAPI, PyTorch, Docker, etc.).
- **Match Score & Skill Highlights**: Displays a match percentage badge (e.g., `92% Match`) and visual tags of skills detected in each job description.
- **Scannable Summary Cards**: Unabridged job descriptions are accessible on-demand alongside instant "Direct Apply" links.

### 💻 3. Interactive Web Dashboard
- **Instant Search & Filters**: Live client-side filtering by workplace type (*Remote*, *Hybrid*, *On-site*), employment type (*Full-time*, *Contract*), location, match score, and keyword search.
- **Timeframe Search Runner**: Trigger new automated LinkedIn searches directly from the browser with strict deduplication against previously scraped postings.
- **Hide Applied Toggle**: Keep your inbox zero mindset by hiding jobs you've already applied for.

### 📋 4. End-to-End Application Pipeline Tracker
- **Kanban Pipeline Stages**: Track your pipeline across *Applied*, *Get Call / Screening*, *Interview*, *Issues / Rejection*, and *Offer*.
- **Application Notes & Dates**: Record customized notes (salary discussions, referral contact, recruiter names) and date applied.
- **Bidirectional Sync**: State automatically persists to `Jobs/applied_jobs.json` and syncs with `Jobs/Applied_Jobs_Tracker.csv` for reporting.

### 📊 5. Rich Multi-View Excel & CSV Reporting
- Exports automated spreadsheets with clickable URLs, freeze panes, auto-wrapped descriptions, and clean formatting:
  - `Master_LinkedIn_Jobs.xlsx` (Multi-tab structured workbook)
  - `Remote_FullTime_Jobs.csv`
  - `International_Jobs.csv`
  - `Hybrid_Jobs.csv`
  - `Onsite_Jobs.csv`
  - `Contract_Jobs.csv`

---

## 🏗️ Architecture

```
┌─────────────────────────┐       ┌──────────────────────────────┐
│  LinkedIn Guest/Session │ ───>  │  curl_cffi Stealth Scraper   │
└─────────────────────────┘       └──────────────┬───────────────┘
                                                 │
                                                 ▼
┌─────────────────────────┐       ┌──────────────────────────────┐
│ Candidate Resume (PDF)  │ ───>  │ AI / CV Relevancy Engine     │
└─────────────────────────┘       └──────────────┬───────────────┘
                                                 │
                                                 ▼
┌─────────────────────────┐       ┌──────────────────────────────┐
│  Clean SQLite/CSV Store │ <───  │ Local Backend Server (8765)  │
└─────────────────────────┘       └──────────────┬───────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │ Interactive Web Dashboard    │
                                  │  - Job Discovery & Filter    │
                                  │  - Status Pipeline Tracker   │
                                  └──────────────────────────────┘
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.10 or higher
- `pdftotext` (optional, for auto-extracting skills from PDF resumes)

### 2. Installation

Clone the repository and install dependencies:
```bash
git clone https://github.com/your-username/linkedin-job-suite.git
cd linkedin-job-suite
pip install -r requirements.txt
```

### 3. Configuration (Optional)
Copy the example environment configuration:
```bash
cp .env.example .env
```
Inside `.env`:
- `LinkedCookies`: *(Optional)* Your LinkedIn `li_at` cookie. Allows personalized recommendation feeds and higher API rate allowances. (The tool works completely fine in guest mode if omitted).
- `CV_PDF_PATH`: *(Optional)* Path to your custom resume PDF (e.g. `resume.pdf`) for automatic skill extraction and relevancy scoring.
- `PORT`: *(Optional)* Local web server port (default `8765`).

---

## 🖥️ Usage

### A. Launch the Interactive GUI Dashboard (Recommended)

Simply execute the GUI launcher:
```bash
./launch_gui.sh
```
Or start the Python server directly:
```bash
python3 server.py 8765
```
Open **[http://localhost:8765](http://localhost:8765)** in your browser:
- Discover jobs, filter by Remote/Full-time, sort by Resume Match.
- Click **Apply** to open the LinkedIn posting.
- Move applications into your **Application Tracker** to monitor interviews and offers.

---

### B. Run Search via Command-Line Interface (CLI)

Use the bash helper:
```bash
# Search postings from the last 24 hours (1 day)
./run_search.sh 1

# Search postings from the last 4 days
./run_search.sh 4

# Search custom query with limit
./run_search.sh 1 "Senior AI Engineer" 50
```

Or run Python directly:
```bash
python3 linkedin_job_search.py --days 1 --query "GenAI Senior Engineer, Agentic AI" --limit 100
```

#### CLI Options:
| Flag | Type | Description | Default |
|---|---|---|---|
| `-d`, `--days` | `float` | Number of days to search back (e.g. `1`, `2`, `7`) | `1.0` |
| `-H`, `--hours` | `int` | Search window in hours (e.g. `24`, `48`) | None |
| `-q`, `--query` | `str` | Job titles / keywords (comma-separated for multi-query) | `"GenAI Senior Engineer"` |
| `-l`, `--location`| `str` | Target location (e.g. `'Remote'`, `'United States'`) | `""` (Worldwide) |
| `-n`, `--limit` | `int` | Max number of jobs to fetch full details for | `50` |
| `-o`, `--output` | `str` | Output filename prefix | Auto-generated timestamp |

---

## 📁 Repository Structure

```
.
├── linkedin_job_search.py   # Core scraping engine & data organizer
├── build_gui.py             # Generates the standalone interactive HTML dashboard
├── server.py                # Lightweight HTTP server & REST API
├── launch_gui.sh            # One-click launcher for the web dashboard
├── run_search.sh            # CLI wrapper script for quick scraping runs
├── requirements.txt         # Python project dependencies
├── .env.example             # Configuration template
├── .gitignore               # Keeps credentials and scraped data private
└── Jobs/                    # Generated spreadsheets, CSVs, and tracker storage
    └── .gitkeep
```

---

## 🔒 Privacy & Ethical Note

- **Privacy First**: All data is stored completely locally on your machine (`Jobs/`). No telemetry, analytics, or third-party servers.
- **Stealth Rate Limiting**: Request cadences incorporate humanized jitter and randomized delays to respect web server capacity.
- **Educational / Personal Use**: This project is built for personal job search automation and productivity. Please adhere to LinkedIn's Terms of Service.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
