#!/usr/bin/env python3
"""
LinkedIn Job Search Scraper & Organizer
Searches LinkedIn for jobs posted within a specified timeframe (e.g. 30 days, 24 hours),
supports authenticated session with LinkedIn member cookies (fetching personalized profile recommendations),
searches both Domestic and International markets (United States, UK, Germany, Canada, Remote, India),
queries LinkedIn's native Voyager API for 100% authoritative Ground-Truth Workplace Type (Remote / Hybrid / On-site)
and Employment Type (Full-time, Contract, etc.), and exports organized, sorted spreadsheets.
"""

import argparse
import datetime
import glob
import os
import random
import re
import sys
import time
import urllib.parse
from typing import Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup
from curl_cffi import requests
import pandas as pd
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def is_international_location(location: str) -> bool:
    """Classify whether a location is outside India (US, UK, Europe, Canada, etc.)."""
    loc = str(location).lower().strip()
    if not loc or loc in ["not specified"]:
        return False
    # If explicitly India / Indian metros, not international
    if re.search(r"\b(india|bengaluru|bangalore|hyderabad|mumbai|delhi|noida|gurugram|gurgaon|chennai|pune|chandigarh|panchkula|mohali|kerala|kochi|trivandrum|kolkata|calcutta|ahmedabad|jaipur)\b", loc):
        return False
    return True


def parse_workplace_type_fallback(title: str, location: str, desc: str) -> str:
    """
    Robust fallback classifier for workplace type if Voyager API is unavailable.
    Explicitly prevents false positives from tech jargon like:
    - 'remote sensing', 'remote operations', 'remote teams', 'remote monitoring'
    - 'hybrid cloud', 'hybrid AI', 'hybrid model', 'hybrid search'
    """
    comb = f"{title} {location}".lower()

    # 1. Exact signals in Title or Location (highest precision)
    if any(k in comb for k in ["(remote)", "remote -", "- remote", "/ remote", "remote /", "remote only", "100% remote", "fully remote", "work from home", "wfh"]):
        return "Remote"
    if any(k in comb for k in ["(hybrid)", "hybrid -", "- hybrid", "/ hybrid", "hybrid /", "flexible hybrid"]):
        return "Hybrid"
    if any(k in comb for k in ["(on-site)", "(onsite)", "on-site -", "- on-site", "in-office"]):
        return "On-site"
    if "remote" in comb and "not remote" not in comb and "no remote" not in comb:
        return "Remote"
    if "hybrid" in comb:
        return "Hybrid"

    desc_lower = str(desc).lower()

    # 2. Strict description patterns for Hybrid work arrangements
    if re.search(r"\b(hybrid\s*(schedule|work\s*model|workplace|policy|setup|arrangement|role|position|environment)|flexible\s*hybrid|hybrid\s*\(?\d+\s*days|days\s*(in|per\s*week)\s*(the\s*)?office|\d+\s*days\s*in\s*office)\b", desc_lower):
        if not re.search(r"\b(hybrid\s*(cloud|search|ai|architecture|infrastructure|system|database))\b", desc_lower):
            return "Hybrid"

    # 3. Strict description patterns for Remote work arrangements
    if re.search(r"\b(100%\s*remote|fully\s*remote|work\s*from\s*home|work\s*remotely|remote\s*(first|opportunity|role|position|job|workplace|work\s*arrangement)|this\s*is\s*a\s*remote\s*(role|position|job)|position\s*is\s*remote|remote\s*eligible|eligible\s*for\s*remote)\b", desc_lower):
        if not re.search(r"\b(not\s*remote|no\s*remote|not\s*eligible\s*for\s*remote|remote\s*(sensing|operations|monitoring|control|teams|clients|devices|servers|access|execution))\b", desc_lower):
            return "Remote"

    return "On-site"


def parse_employment_type_fallback(criteria_emp_type: Optional[str], title: str, desc: str) -> str:
    """Determine employment type (Full-time, Contract, Part-time, Internship, etc.)."""
    if criteria_emp_type and criteria_emp_type.strip() and criteria_emp_type.lower() != "not specified":
        return criteria_emp_type.strip()

    comb = f"{title} {desc[:1000]}".lower()
    desc_full = str(desc).lower()

    if re.search(r"\b(full[\s-]time|ft)\b", comb):
        return "Full-time"
    if re.search(r"\b(contract(or)?|c2c|w2\s*contract|contract-to-hire|cth)\b", comb):
        return "Contract"
    if re.search(r"\b(part[\s-]time|pt)\b", comb):
        return "Part-time"
    if re.search(r"\bintern(ship)?\b", comb):
        return "Internship"

    if "full-time" in desc_full or "full time" in desc_full:
        return "Full-time"
    if "contract" in desc_full:
        return "Contract"
    if "part-time" in desc_full:
        return "Part-time"

    return "Full-time"


class LinkedInJobScraper:
    BASE_URL = "https://www.linkedin.com"
    SEARCH_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def __init__(self, cookie: Optional[str] = None, impersonate: str = "chrome120"):
        self.session = requests.Session(impersonate=impersonate)
        self.initialized = False
        self.cached_jobs: Dict[str, Dict] = {}
        self.cookie = cookie or self._find_cookie()

        if self.cookie:
            self.session.cookies.set("li_at", self.cookie, domain=".linkedin.com")

        self._load_cache()

    def _find_cookie(self) -> Optional[str]:
        """Load session cookie from environment or .env file."""
        for key in ["LinkedCookies", "LINKEDIN_COOKIE", "li_at", "LI_AT"]:
            if os.environ.get(key):
                val = os.environ[key].strip()
                if val:
                    return val

        base_dir = os.path.dirname(os.path.abspath(__file__))
        env_paths = [
            os.path.join(base_dir, ".env"),
            os.path.expanduser("~/.env")
        ]
        for p in env_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if "=" in line:
                                k, v = line.split("=", 1)
                                if k.strip().lower() in ["linkedcookies", "linkedin_cookie", "li_at", "cookie"]:
                                    val = v.strip().strip("'\"")
                                    if val:
                                        return val
                except Exception:
                    pass
        return None

    def _load_cache(self):
        """Preload cached descriptions only (workplace type will be authoritative from Voyager)."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        search_dirs = [
            base_dir,
            os.path.join(base_dir, "Jobs"),
            os.path.join(base_dir, "Jobs", "Raw_Exports")
        ]
        for d in search_dirs:
            if not os.path.exists(d):
                continue
            for f in glob.glob(os.path.join(d, "*.csv")):
                try:
                    df = pd.read_csv(f)
                    if "Link to Apply" in df.columns and "Job Description" in df.columns:
                        for _, row in df.iterrows():
                            link = str(row["Link to Apply"])
                            jid = link.split("/")[-1]
                            desc = str(row.get("Job Description", ""))
                            if jid and len(desc) > 100 and jid not in self.cached_jobs:
                                self.cached_jobs[jid] = {
                                    "description": desc,
                                    "workplace_type": None,  # Force authoritative re-check
                                    "employment_type": None
                                }
                except Exception:
                    pass
        if self.cached_jobs:
            print(f"[✓] Loaded {len(self.cached_jobs)} job descriptions from local cache.")

    def init_session(self, keywords: str = "Senior AI Engineer", location: str = ""):
        """Establish session (authenticated if cookie present, or guest cookies)."""
        try:
            target_url = f"{self.BASE_URL}/jobs/" if self.cookie else f"{self.BASE_URL}/jobs/search"
            params = {"keywords": keywords}
            if location:
                params["location"] = location

            resp = self.session.get(target_url, params=params, timeout=15)
            if resp.status_code == 200:
                self.initialized = True
                auth_status = "Authenticated Member Session" if self.cookie else "Guest Session"
                print(f"[✓] Initialized {auth_status} successfully (Cookies: {len(self.session.cookies)})")
            else:
                print(f"[!] Session init status {resp.status_code}, continuing...")
        except Exception as e:
            print(f"[!] Warning during session initialization: {e}")

    def _safe_get(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        max_retries: int = 4
    ) -> Optional[requests.Response]:
        """Fetch URL with exponential backoff on HTTP 429 / network errors."""
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=15)
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 429:
                    wait_time = (attempt + 1) * 3 + random.uniform(1.0, 2.5)
                    print(f"\n    [Rate limit / 429] Backing off for {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    time.sleep(1.5)
            except Exception as e:
                wait_time = (attempt + 1) * 2
                print(f"\n    [Network error: {e}] Retrying in {wait_time}s...")
                time.sleep(wait_time)
        return None

    def fetch_profile_recommended_jobs(self) -> List[Dict]:
        """Fetch personalized jobs displayed on the user's LinkedIn jobs dashboard."""
        if not self.cookie:
            return []

        print("\n[+] Fetching personalized job recommendations from your LinkedIn profile dashboard...")
        try:
            resp = self._safe_get(f"{self.BASE_URL}/jobs/")
            if not resp or resp.status_code != 200:
                print("    [!] Could not load LinkedIn jobs dashboard.")
                return []

            found_ids = set()

            # Pattern 1: currentJobId=(\d+)
            for m in re.findall(r'currentJobId=(\d+)', resp.text):
                found_ids.add(m)

            # Pattern 2: originToLandingJobPostings=
            for m in re.findall(r'originToLandingJobPostings=([0-9%C,]+)', resp.text):
                decoded = urllib.parse.unquote(m)
                for jid in decoded.split(','):
                    if jid.isdigit():
                        found_ids.add(jid)

            # Pattern 3: /jobs/view/(\d+)
            for m in re.findall(r'/jobs/view/(\d+)', resp.text):
                found_ids.add(m)

            print(f"    [✓] Discovered {len(found_ids)} personalized job posts directly from your LinkedIn profile.")

            profile_jobs = []
            for jid in sorted(found_ids):
                profile_jobs.append({
                    "job_id": jid,
                    "title": "Profile Pick",
                    "company": "LinkedIn Recommendation",
                    "location": "India / Remote",
                    "date_posted": datetime.date.today().isoformat(),
                    "time_text": "Profile Recommendation",
                    "apply_link": f"https://www.linkedin.com/jobs/view/{jid}",
                    "search_query": "LinkedIn Profile Recommendations",
                })

            return profile_jobs
        except Exception as e:
            print(f"    [!] Error fetching profile recommendations: {e}")
            return []

    def search_jobs(
        self,
        keywords: str,
        hours_old: int = 720,
        location: str = "",
        max_search_cards: int = 150
    ) -> List[Dict]:
        """Search for job postings matching query and timeframe."""
        if not self.initialized:
            self.init_session(keywords, location)

        seconds_old = hours_old * 3600
        params = {
            "keywords": keywords,
            "f_TPR": f"r{seconds_old}",
        }
        if location:
            params["location"] = location

        found_jobs = []
        seen_ids: Set[str] = set()
        start = 0
        consecutive_empty = 0

        loc_label = location if location else "Global/Personalized"
        print(f"\n[+] Searching LinkedIn: '{keywords}' | Region: '{loc_label}' | Window: {hours_old/24:.0f}d")

        while len(found_jobs) < max_search_cards and consecutive_empty < 2:
            current_params = {**params, "start": start}
            resp = self._safe_get(self.SEARCH_API, params=current_params)
            if not resp or resp.status_code != 200:
                print(f"    [!] Failed to get results at start={start}. Moving forward.")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            new_batch_count = 0
            for card in cards:
                div = card.find("div", class_="base-card")
                if not div or not div.get("data-entity-urn"):
                    continue

                job_id = div["data-entity-urn"].split(":")[-1]
                if not job_id or job_id in seen_ids:
                    continue

                seen_ids.add(job_id)

                title_el = card.find("h3", class_="base-search-card__title")
                comp_el = card.find("h4", class_="base-search-card__subtitle")
                loc_el = card.find("span", class_="job-search-card__location")
                time_el = card.find("time")

                title = title_el.get_text(strip=True) if title_el else "Unknown Title"
                company = comp_el.get_text(strip=True) if comp_el else "Unknown Company"
                job_loc = loc_el.get_text(strip=True) if loc_el else "Not specified"
                date_posted = time_el.get("datetime") if time_el else ""
                time_text = time_el.get_text(strip=True) if time_el else ""

                found_jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": job_loc,
                    "date_posted": date_posted or time_text,
                    "time_text": time_text,
                    "apply_link": f"https://www.linkedin.com/jobs/view/{job_id}",
                    "search_query": f"{keywords} ({loc_label})",
                })
                new_batch_count += 1

                if len(found_jobs) >= max_search_cards:
                    break

            print(f"    -> Offset start={start:3d}: Found {new_batch_count:2d} new jobs (Total collected: {len(found_jobs)})")

            if new_batch_count == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0

            start += 10
            time.sleep(random.uniform(0.7, 1.2))

        return found_jobs

    def fetch_job_details(self, job: Dict) -> Tuple[str, str, str]:
        """
        Fetch authoritative job details:
        1. Uses LinkedIn's native Voyager API when authenticated to retrieve the 100%
           exact Ground-Truth workplaceTypes ('urn:li:fs_workplaceType:1'=On-site,
           'urn:li:fs_workplaceType:2'=Remote, 'urn:li:fs_workplaceType:3'=Hybrid) and employmentStatus.
        2. Falls back to clean semantic HTML parsing with negative-keyword protected heuristics.
        """
        job_id = job["job_id"]
        title = job.get("title", "")
        location = job.get("location", "")

        # Check in-memory cache if workplace_type is already authoritative
        if job_id in self.cached_jobs:
            c = self.cached_jobs[job_id]
            if c.get("workplace_type") and job.get("title") not in ("Profile Pick", "Unknown Title", ""):
                return c["description"], c["workplace_type"], c["employment_type"]

        # -------------------------------------------------------------
        # METHOD 1: Authenticated Voyager API (Ground Truth)
        # -------------------------------------------------------------
        if self.cookie:
            jsessionid = self.session.cookies.get("JSESSIONID", "").replace('"', "")
            headers = {
                "csrf-token": jsessionid,
                "x-restli-protocol-version": "2.0.0",
                "accept": "application/vnd.linkedin.normalized+json+2.1"
            }
            v_url = f"{self.BASE_URL}/voyager/api/jobs/jobPostings/{job_id}"
            v_resp = self._safe_get(v_url, headers=headers)
            if v_resp and v_resp.status_code == 200:
                try:
                    v_data = v_resp.json()
                    d = v_data.get("data", {})

                    # 1. Authoritative Workplace Type
                    wp_urns = d.get("workplaceTypes", [])
                    wp_map = {
                        "urn:li:fs_workplaceType:1": "On-site",
                        "urn:li:fs_workplaceType:2": "Remote",
                        "urn:li:fs_workplaceType:3": "Hybrid"
                    }
                    if wp_urns and wp_urns[0] in wp_map:
                        workplace_type = wp_map[wp_urns[0]]
                    elif d.get("workRemoteAllowed"):
                        workplace_type = "Remote"
                    else:
                        workplace_type = parse_workplace_type_fallback(title, location, "")

                    # 2. Authoritative Employment Status
                    emp_map = {
                        "urn:li:fs_employmentStatus:FULL_TIME": "Full-time",
                        "urn:li:fs_employmentStatus:PART_TIME": "Part-time",
                        "urn:li:fs_employmentStatus:CONTRACT": "Contract",
                        "urn:li:fs_employmentStatus:TEMPORARY": "Temporary",
                        "urn:li:fs_employmentStatus:INTERNSHIP": "Internship",
                    }
                    employment_type = emp_map.get(d.get("employmentStatus"), "Full-time")

                    # 3. Description
                    desc_text = d.get("description", {}).get("text", "")
                    description = desc_text.strip() if desc_text else "Description unavailable"

                    # 4. Update metadata
                    if d.get("formattedLocation") and (job.get("location") in ("India / Remote", "Not specified", "") or not job.get("location")):
                        job["location"] = d.get("formattedLocation")
                    if d.get("title") and (job.get("title") in ("Profile Pick", "Unknown Title", "") or not job.get("title")):
                        job["title"] = d.get("title")
                    if d.get("listedAt") and (not job.get("date_posted") or job.get("date_posted") in ("", "Recent recommendation", "Profile Recommendation")):
                        job["date_posted"] = datetime.datetime.fromtimestamp(d["listedAt"] / 1000).strftime("%Y-%m-%d")

                    self.cached_jobs[job_id] = {
                        "description": description,
                        "workplace_type": workplace_type,
                        "employment_type": employment_type
                    }
                    return description, workplace_type, employment_type
                except Exception:
                    pass

        # -------------------------------------------------------------
        # METHOD 2: Semantic HTML API & Fallback
        # -------------------------------------------------------------
        api_url = f"{self.BASE_URL}/jobs-guest/jobs/api/jobPosting/{job_id}"
        resp = self._safe_get(api_url)
        if not resp or resp.status_code != 200:
            url = f"{self.BASE_URL}/jobs/view/{job_id}"
            resp = self._safe_get(url)
            if not resp or resp.status_code != 200:
                return "Description unavailable", parse_workplace_type_fallback(title, location, ""), "Full-time"

        soup = BeautifulSoup(resp.text, "html.parser")

        # Update metadata if job was discovered with placeholder values
        t_el = soup.find("h2", class_=re.compile(r"top-card-layout__title|topcard__title")) or soup.find("h1")
        c_el = soup.find("a", class_=re.compile(r"topcard__org-name-link|top-card-layout__first-subline")) or soup.find("span", class_="topcard__flavor")
        l_el = soup.find("span", class_=re.compile(r"topcard__flavor--bullet|top-card-layout__second-subline"))
        time_el = soup.find("time") or soup.find("span", class_=re.compile(r"posted-time-ago"))

        if t_el:
            job["title"] = t_el.get_text(strip=True)
            title = job["title"]
        elif soup.title and " | " in soup.title.string:
            parts = soup.title.string.split(" | ")
            job["title"] = parts[0].strip()
            title = job["title"]
            if len(parts) > 1 and parts[1].strip() != "LinkedIn":
                job["company"] = parts[1].strip()

        if c_el and (job.get("company") in ("LinkedIn Recommendation", "Unknown Company", "") or not job.get("company")):
            job["company"] = c_el.get_text(strip=True)
        if l_el and (job.get("location") in ("India / Remote", "Not specified", "") or not job.get("location")):
            job["location"] = l_el.get_text(strip=True)
            location = job["location"]
        if time_el and (not job.get("date_posted") or job.get("date_posted") in ("", "Recent recommendation", "Profile Recommendation")):
            job["date_posted"] = time_el.get("datetime") or time_el.get_text(strip=True)

        desc_el = soup.find("div", class_=re.compile(r"show-more-less-html__markup|description__text"))
        if not desc_el:
            desc_el = soup.find("section", class_=re.compile(r"show-more-less-html|description"))

        description = ""
        if desc_el:
            text = desc_el.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            description = "\n".join(lines)
        else:
            description = "Description unavailable"

        criteria = {}
        for li in soup.find_all("li", class_="description__job-criteria-item"):
            h = li.find(class_="description__job-criteria-subheader")
            t = li.find(class_="description__job-criteria-text")
            if h and t:
                criteria[h.get_text(strip=True).lower()] = t.get_text(strip=True)

        raw_emp_type = criteria.get("employment type")
        workplace_type = parse_workplace_type_fallback(title, location, description)
        employment_type = parse_employment_type_fallback(raw_emp_type, title, description)

        self.cached_jobs[job_id] = {
            "description": description,
            "workplace_type": workplace_type,
            "employment_type": employment_type
        }

        return description, workplace_type, employment_type

    def enrich_jobs_with_details(self, jobs: List[Dict], limit: Optional[int] = None) -> List[Dict]:
        """Fetch full descriptions and metadata for the retrieved jobs."""
        total = len(jobs) if limit is None else min(len(jobs), limit)
        target_jobs = jobs[:total]

        print(f"\n[+] Processing details for {total} jobs (using Voyager ground-truth)...")
        for i, job in enumerate(target_jobs, 1):
            jid = job["job_id"]
            title = job["title"]

            is_cached = jid in self.cached_jobs and self.cached_jobs[jid].get("workplace_type") is not None
            tag = "[Cached]" if is_cached else "[Fetching]"
            sys.stdout.write(f"\r    [{i:3d}/{total:3d}] {tag} {job['company'][:20]:<20} | {title[:30]:<30}")
            sys.stdout.flush()

            desc, workplace_type, employment_type = self.fetch_job_details(job)
            job["description"] = desc
            job["workplace_type"] = workplace_type
            job["employment_type"] = employment_type

            if not is_cached:
                time.sleep(random.uniform(0.4, 0.8))

        print("\n[✓] Finished processing all job details.")
        return target_jobs


def organize_and_export_spreadsheets(jobs: List[Dict], output_dir: str) -> str:
    """
    Generate:
    1. Multi-tab Master Excel workbook with styled category tabs
    2. Separate CSV files for each category (including International and Profile Recommended)
    3. Timestamped archive files
    """
    os.makedirs(output_dir, exist_ok=True)
    raw_dir = os.path.join(output_dir, "Raw_Exports")
    os.makedirs(raw_dir, exist_ok=True)

    rows = []
    for j in jobs:
        rows.append({
            "Company Name": j.get("Company Name") or j.get("company", "") or j.get("company_name", ""),
            "Job Profile": j.get("Job Profile") or j.get("title", "") or j.get("job_profile", ""),
            "Workplace Type": j.get("Workplace Type") or j.get("workplace_type", ""),
            "Employment Type": j.get("Employment Type") or j.get("employment_type", ""),
            "Location": j.get("Location") or j.get("location", ""),
            "Date of Job Posting": j.get("Date of Job Posting") or j.get("date_posted", "") or j.get("date_of_job_posting", ""),
            "Link to Apply": j.get("Link to Apply") or j.get("apply_link", "") or j.get("link_to_apply", ""),
            "Job Description": j.get("Job Description") or j.get("description", "") or j.get("job_description", ""),
            "Relative Time": j.get("Relative Time") or j.get("time_text", ""),
            "Search Query": j.get("Search Query") or j.get("search_query", ""),
        })

    master_df = pd.DataFrame(rows)

    # Sort master: Remote first, then Hybrid, then On-site, then newest date
    wp_rank = {"Remote": 1, "Hybrid": 2, "On-site": 3}
    master_df["_rank"] = master_df["Workplace Type"].map(lambda x: wp_rank.get(x, 4))
    master_df = master_df.sort_values(by=["_rank", "Date of Job Posting"], ascending=[True, False]).drop(columns=["_rank"])

    # Categorized datasets
    subsets = {
        "All Jobs": (master_df, "1F4E79"),
        "International (Global)": (master_df[master_df["Location"].apply(is_international_location)], "203864"),
        "Remote - Full-Time": (master_df[(master_df["Workplace Type"] == "Remote") & (master_df["Employment Type"] == "Full-time")], "1E6B38"),
        "Remote (All)": (master_df[master_df["Workplace Type"] == "Remote"], "2E75B6"),
        "Hybrid": (master_df[master_df["Workplace Type"] == "Hybrid"], "C65911"),
        "On-site": (master_df[master_df["Workplace Type"] == "On-site"], "418AB3"),
        "Contract": (master_df[master_df["Employment Type"] == "Contract"], "7030A0"),
    }

    # Add Profile Recommended tab if any exist
    profile_recs = master_df[master_df["Search Query"].str.contains("Profile", case=False, na=False)]
    if len(profile_recs) > 0:
        subsets["Profile Recommended"] = (profile_recs, "4B2E83")

    # 1. Master Excel Workbook (Multi-Tab)
    master_xlsx = os.path.join(output_dir, "Master_LinkedIn_Jobs.xlsx")
    with pd.ExcelWriter(master_xlsx, engine="openpyxl") as writer:
        for sheet_name, (df_sub, _) in subsets.items():
            df_sub.to_excel(writer, index=False, sheet_name=sheet_name)

    wb = openpyxl.load_workbook(master_xlsx)
    col_widths = {
        "A": 26, "B": 36, "C": 16, "D": 18, "E": 28,
        "F": 18, "G": 45, "H": 80, "I": 16, "J": 30
    }
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9")
    )
    data_font = Font(name="Calibri", size=10)

    for sheet_name, (_, hex_color) in subsets.items():
        ws = wb[sheet_name]
        header_fill = PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 28

        for col_letter, width in col_widths.items():
            ws.column_dimensions[col_letter].width = width

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
            for cell in row:
                cell.font = data_font
                cell.border = thin_border
                col_letter = get_column_letter(cell.column)
                if col_letter == "H":
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                elif col_letter in ["A", "B", "E", "J"]:
                    cell.alignment = Alignment(vertical="top")
                elif col_letter in ["C", "D"]:
                    cell.alignment = Alignment(horizontal="center", vertical="top")
                elif col_letter == "G":
                    cell.alignment = Alignment(vertical="top")
                    if cell.value and str(cell.value).startswith("http"):
                        cell.hyperlink = str(cell.value)
                        cell.font = Font(name="Calibri", size=10, color="0563C1", underline="single")
                else:
                    cell.alignment = Alignment(horizontal="center", vertical="top")
        ws.freeze_panes = "A2"

    wb.save(master_xlsx)
    print(f"[✓] Multi-tab Master Excel workbook saved: {master_xlsx}")

    # 2. Individual CSV files for each category
    csv_mapping = {
        "All_Jobs.csv": master_df,
        "International_Jobs.csv": subsets["International (Global)"][0],
        "Remote_FullTime_Jobs.csv": subsets["Remote - Full-Time"][0],
        "Remote_All_Jobs.csv": subsets["Remote (All)"][0],
        "Hybrid_Jobs.csv": subsets["Hybrid"][0],
        "Onsite_Jobs.csv": subsets["On-site"][0],
        "Contract_Jobs.csv": subsets["Contract"][0],
    }
    if len(profile_recs) > 0:
        csv_mapping["Profile_Recommended_Jobs.csv"] = profile_recs

    for fname, df_data in csv_mapping.items():
        csv_file = os.path.join(output_dir, fname)
        df_data.to_csv(csv_file, index=False, encoding="utf-8-sig")
        print(f"[✓] Exported: {fname:<30} ({len(df_data)} jobs)")

    # 3. Timestamped copy in Raw_Exports
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_base = os.path.join(raw_dir, f"linkedin_jobs_archive_{now_str}")
    master_df.to_csv(f"{archive_base}.csv", index=False, encoding="utf-8-sig")
    wb.save(f"{archive_base}.xlsx")
    print(f"[✓] Raw archive saved to: {archive_base}.xlsx/.csv")

    return master_xlsx


def main():
    parser = argparse.ArgumentParser(
        description="Search LinkedIn for job postings, extract full details & workplace/employment types, and save organized spreadsheets."
    )
    parser.add_argument(
        "-q", "--query", "--keywords",
        dest="keywords",
        default="Senior AI Engineer, Senior Generative AI Engineer, Senior Data Scientist, Senior Agentic AI Engineer",
        help="Job title or keywords (comma-separated for multiple queries)"
    )
    parser.add_argument(
        "-d", "--days",
        type=float,
        default=30.0,
        help="Time window in days (default: 30 for 1 month)"
    )
    parser.add_argument(
        "-H", "--hours",
        type=int,
        default=None,
        help="Time window in hours (overrides --days if provided, e.g. 720)"
    )
    parser.add_argument(
        "-l", "--locations", "--location",
        dest="locations",
        default="United States, United Kingdom, Germany, Canada, Remote, India",
        help="Locations to search (comma-separated for multi-location search, or single location)"
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=600,
        help="Maximum number of jobs to fetch full details for. Default: 600"
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="LinkedIn session cookie (li_at). If omitted, automatically checks .env"
    )
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser.add_argument(
        "--output-dir",
        default=os.path.join(script_dir, "Jobs"),
        help="Target folder for organized spreadsheets"
    )

    args = parser.parse_args()

    hours_old = args.hours if args.hours is not None else int(args.days * 24)
    query_list = [q.strip() for q in args.keywords.split(",") if q.strip()]
    loc_list = [l.strip() for l in args.locations.split(",") if l.strip()]

    scraper = LinkedInJobScraper(cookie=args.cookie)
    all_jobs: List[Dict] = []
    seen_ids: Set[str] = set()

    print(f"\n=======================================================")
    print(f" Starting Global LinkedIn Job Search (Target Limit: {args.limit})")
    print(f" Queries: {len(query_list)} target queries: {query_list}")
    print(f" Locations: {len(loc_list)} regions: {loc_list}")
    print(f" Timeframe: {args.days} days ({hours_old} hours)")
    print(f" Auth Mode: {'Authenticated (Profile & Voyager Enabled)' if scraper.cookie else 'Guest Session'}")
    print(f" Output folder: {args.output_dir}")
    print(f"=======================================================")

    # 1. Fetch Profile-Recommended Jobs if authenticated
    if scraper.cookie:
        profile_jobs = scraper.fetch_profile_recommended_jobs()
        for pj in profile_jobs:
            if pj["job_id"] not in seen_ids:
                seen_ids.add(pj["job_id"])
                all_jobs.append(pj)

    # 2. Search target titles across target locations
    total_searches = max(1, len(query_list) * len(loc_list))
    per_search_target = max(35, int(args.limit * 1.5 / total_searches))

    for loc in loc_list:
        for kw in query_list:
            jobs = scraper.search_jobs(
                keywords=kw,
                hours_old=hours_old,
                location=loc,
                max_search_cards=per_search_target
            )
            for j in jobs:
                if j["job_id"] not in seen_ids:
                    seen_ids.add(j["job_id"])
                    all_jobs.append(j)

            if len(all_jobs) >= args.limit * 1.4:
                break
        if len(all_jobs) >= args.limit * 1.4:
            break

    print(f"\n[+] Total unique job postings discovered: {len(all_jobs)}")

    if not all_jobs:
        print("[!] No job postings found matching the search criteria.")
        return

    enriched_jobs = scraper.enrich_jobs_with_details(all_jobs, limit=args.limit)
    organize_and_export_spreadsheets(enriched_jobs, args.output_dir)

    print("\n" + "=" * 70)
    print(f"🎉 Global Job search and categorization completed successfully!")
    print(f"📊 Total jobs processed: {len(enriched_jobs)}")
    print(f"📁 Files available in:   {args.output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
