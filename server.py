#!/usr/bin/env python3
"""
Lightweight Backend Server for LinkedIn Job Explorer & Application Tracker.
Provides:
 - Static file serving on port 8765
 - POST/GET /api/applications (save and load applied jobs tracking)
 - POST/GET /api/search (trigger LinkedIn job search with timeframe & deduplication)
 - GET /api/status (server and search status)
"""

import http.server
import json
import os
import re
import sys
import threading
import time
import urllib.parse
from typing import Dict, List, Set
import pandas as pd

# Add current dir to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from linkedin_job_search import LinkedInJobScraper, organize_and_export_spreadsheets
from build_gui import build_gui

APPLICATIONS_FILE = os.path.join(BASE_DIR, "Jobs", "applied_jobs.json")
APPLICATIONS_CSV = os.path.join(BASE_DIR, "Jobs", "Applied_Jobs_Tracker.csv")
ALL_JOBS_CSV = os.path.join(BASE_DIR, "Jobs", "All_Jobs.csv")

SEARCH_LOCK = threading.Lock()
IS_SEARCHING = False
SEARCH_PROGRESS = {"status": "idle", "message": "Ready", "new_jobs": 0}


def get_existing_job_ids() -> Set[str]:
    """Extract set of unique job IDs from All_Jobs.csv for deduplication."""
    ids = set()
    if not os.path.exists(ALL_JOBS_CSV):
        return ids
    try:
        df = pd.read_csv(ALL_JOBS_CSV)
        for _, row in df.iterrows():
            link = str(row.get("Link to Apply", ""))
            m = re.search(r"/view/(\d+)", link)
            if m:
                ids.add(m.group(1))
            else:
                jid = link.split("/")[-1].split("?")[0]
                if jid and jid != "nan":
                    ids.add(jid)
    except Exception as e:
        print(f"[!] Error reading existing job IDs: {e}")
    return ids


def get_job_descriptions_map() -> Dict[str, str]:
    """Extract mapping of job ID -> full description for enrichment and tracker exports."""
    desc_map = {}
    if not os.path.exists(ALL_JOBS_CSV):
        return desc_map
    try:
        df = pd.read_csv(ALL_JOBS_CSV)
        for _, row in df.iterrows():
            link = str(row.get("Link to Apply", ""))
            desc = str(row.get("Job Description", ""))
            m = re.search(r"/view/(\d+)", link)
            if m:
                desc_map[m.group(1)] = desc
            else:
                jid = link.split("/")[-1].split("?")[0]
                if jid and jid != "nan":
                    desc_map[jid] = desc
    except Exception as e:
        print(f"[!] Error reading job descriptions map: {e}")
    return desc_map


def run_linkedin_search_task(days: float = 1.0, limit: int = 150):
    global IS_SEARCHING, SEARCH_PROGRESS
    with SEARCH_LOCK:
        IS_SEARCHING = True
        SEARCH_PROGRESS = {"status": "running", "message": f"Searching LinkedIn for last {days} days...", "new_jobs": 0}

    try:
        hours_old = max(1, int(days * 24))
        existing_ids = get_existing_job_ids()
        print(f"\n[+] Triggered background search: {days} days ({hours_old} hours). Existing jobs: {len(existing_ids)}")

        scraper = LinkedInJobScraper()
        query_list = [
            "Senior AI Engineer",
            "Senior Generative AI Engineer",
            "Senior Data Scientist",
            "Senior Agentic AI Engineer"
        ]
        loc_list = [
            "United States",
            "United Kingdom",
            "Germany",
            "Canada",
            "Remote",
            "India"
        ]

        raw_candidates: List[Dict] = []
        seen_cand_ids: Set[str] = set()

        # 1. Fetch profile recommendations
        if scraper.cookie:
            prof_jobs = scraper.fetch_profile_recommended_jobs()
            for pj in prof_jobs:
                jid = str(pj.get("job_id", ""))
                if jid and jid not in existing_ids and jid not in seen_cand_ids:
                    seen_cand_ids.add(jid)
                    raw_candidates.append(pj)

        # 2. Search target keywords and regions
        for loc in loc_list:
            for kw in query_list:
                jobs = scraper.search_jobs(
                    keywords=kw,
                    hours_old=hours_old,
                    location=loc,
                    max_search_cards=25
                )
                for j in jobs:
                    jid = str(j.get("job_id", ""))
                    if jid and jid not in existing_ids and jid not in seen_cand_ids:
                        seen_cand_ids.add(jid)
                        raw_candidates.append(j)

                if len(raw_candidates) >= limit:
                    break
            if len(raw_candidates) >= limit:
                break

        print(f"[+] Found {len(raw_candidates)} NEW unseen jobs in the last {days} days.")

        if not raw_candidates:
            with SEARCH_LOCK:
                SEARCH_PROGRESS = {
                    "status": "completed",
                    "message": f"No new jobs found in the last {days} days. All postings are already saved in your dataset!",
                    "new_jobs": 0
                }
            return

        # 3. Enrich new jobs with details and Voyager ground truth
        SEARCH_PROGRESS["message"] = f"Enriching {len(raw_candidates)} new job postings with details..."
        enriched_new_jobs = scraper.enrich_jobs_with_details(raw_candidates, limit=limit)

        # 4. Load existing jobs to merge
        if os.path.exists(ALL_JOBS_CSV):
            existing_df = pd.read_csv(ALL_JOBS_CSV)
            existing_list = existing_df.to_dict(orient="records")
        else:
            existing_list = []

        # Convert enriched new jobs to standard format
        new_formatted = []
        for j in enriched_new_jobs:
            new_formatted.append({
                "Company Name": j.get("company_name", "") or j.get("company", ""),
                "Job Profile": j.get("job_profile", "") or j.get("title", ""),
                "Job Description": j.get("job_description", "") or j.get("description", ""),
                "Link to Apply": j.get("link_to_apply", "") or j.get("apply_link", ""),
                "Date of Job Posting": j.get("date_of_job_posting", "") or j.get("date_posted", ""),
                "Workplace Type": j.get("workplace_type", "On-site"),
                "Employment Type": j.get("employment_type", "Full-time"),
                "Location": j.get("location", ""),
                "Search Query": j.get("search_query", "GUI Search"),
            })

        all_merged = new_formatted + existing_list

        # 5. Export updated spreadsheets & re-build GUI
        SEARCH_PROGRESS["message"] = "Updating master spreadsheets and GUI..."
        organize_and_export_spreadsheets(all_merged, os.path.join(BASE_DIR, "Jobs"))
        build_gui()

        with SEARCH_LOCK:
            SEARCH_PROGRESS = {
                "status": "completed",
                "message": f"Successfully added {len(new_formatted)} new jobs! Total jobs: {len(all_merged)}.",
                "new_jobs": len(new_formatted),
                "total_jobs": len(all_merged)
            }
        print(f"[✓] Search completed: {len(new_formatted)} new jobs added. Total: {len(all_merged)}")

    except Exception as e:
        print(f"[!] Error during LinkedIn search task: {e}")
        with SEARCH_LOCK:
            SEARCH_PROGRESS = {"status": "error", "message": f"Search error: {str(e)}", "new_jobs": 0}
    finally:
        with SEARCH_LOCK:
            IS_SEARCHING = False


class JobSuiteRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def _send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status":
            with SEARCH_LOCK:
                total_jobs = len(get_existing_job_ids())
                self._send_json({
                    "is_searching": IS_SEARCHING,
                    "progress": SEARCH_PROGRESS,
                    "total_jobs": total_jobs
                })
            return

        elif path == "/api/applications":
            if os.path.exists(APPLICATIONS_FILE):
                try:
                    with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._send_json(data)
                    return
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
                    return
            else:
                self._send_json({})
                return

        elif path == "/api/search":
            days = float(params.get("days", [1.0])[0])
            with SEARCH_LOCK:
                if IS_SEARCHING:
                    self._send_json({"status": "busy", "message": "A search is already in progress."}, 429)
                    return

            thread = threading.Thread(target=run_linkedin_search_task, kwargs={"days": days}, daemon=True)
            thread.start()
            self._send_json({"status": "started", "message": f"Started search for last {days} days."})
            return

        # Root fallback to job_gui.html
        if path == "/" or path == "":
            self.path = "/job_gui.html"

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            req_data = json.loads(post_body)
        except Exception:
            req_data = {}

        if path == "/api/applications":
            try:
                os.makedirs(os.path.dirname(APPLICATIONS_FILE), exist_ok=True)
                desc_map = get_job_descriptions_map()

                # Ensure description is populated in req_data
                for jid, app in req_data.items():
                    if not app.get("description"):
                        app["description"] = desc_map.get(str(jid), "")

                with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(req_data, f, indent=2)

                # Export to CSV for Excel convenience with full Job Description
                rows = []
                for jid, app in req_data.items():
                    rows.append({
                        "Job ID": jid,
                        "Company": app.get("company", ""),
                        "Job Title": app.get("title", ""),
                        "Workplace Type": app.get("workplace_type", ""),
                        "Employment Type": app.get("employment_type", "Full-time"),
                        "Location": app.get("location", ""),
                        "Status": app.get("status", "Applied"),
                        "Applied Date": app.get("applied_date", ""),
                        "Match Score": f"{app.get('score', '')}%",
                        "Notes / Feedback": app.get("notes", ""),
                        "Apply Link": app.get("apply_link", ""),
                        "Job Description": app.get("description", "")
                    })
                if rows:
                    pd.DataFrame(rows).to_csv(APPLICATIONS_CSV, index=False, encoding="utf-8-sig")
                elif os.path.exists(APPLICATIONS_CSV):
                    os.remove(APPLICATIONS_CSV)

                self._send_json({"status": "ok", "saved_count": len(req_data)})
                return
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
                return

        elif path == "/api/search":
            days = float(req_data.get("days", 1.0))
            with SEARCH_LOCK:
                if IS_SEARCHING:
                    self._send_json({"status": "busy", "message": "A search is already in progress."}, 429)
                    return

            thread = threading.Thread(target=run_linkedin_search_task, kwargs={"days": days}, daemon=True)
            thread.start()
            self._send_json({"status": "started", "message": f"Started search for last {days} days."})
            return

        self._send_json({"error": "Endpoint not found"}, 404)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server_address = ("", port)
    httpd = http.server.ThreadingHTTPServer(server_address, JobSuiteRequestHandler)
    print(f"===========================================================")
    print(f" LinkedIn Job Suite & API Server Running on port {port}")
    print(f" Web UI:  http://localhost:{port}/")
    print(f"===========================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()


if __name__ == "__main__":
    main()
