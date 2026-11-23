#!/usr/bin/env python3
"""
Generate the standalone interactive GUI dashboard for LinkedIn Jobs with:
 - Scannable jobs explorer with CV matching and ranking
 - Search with timeframe selector (1 day, 2 days, etc.) and strict deduplication
 - Applied jobs column with toggle and "Hide Applied" filter
 - Dedicated Application Tracker page with status pipeline (Applied, Get Call, Interview, Issues, Offer),
   editable dates, notes, and CSV export.
"""

import json
import os
import re
import subprocess
import pandas as pd

def build_gui():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    jobs_csv = os.path.join(base_dir, "Jobs", "All_Jobs.csv")
    # CV PDF candidates (custom env variable, local resume.pdf, or existing fallback)
    cv_pdf_env = os.environ.get("CV_PDF_PATH")
    cv_candidates = [
        cv_pdf_env if cv_pdf_env else None,
        os.path.join(base_dir, "resume.pdf"),
        "/media/parmpal/Data/Docs/Work/Resume/Parmpal_Singh.pdf"
    ]
    cv_pdf = next((p for p in cv_candidates if p and os.path.exists(p)), None)
    output_html_workspace = os.path.join(base_dir, "job_gui.html")
    output_html_index = os.path.join(base_dir, "index.html")
    artifact_dir = os.environ.get("ARTIFACT_DIR", "")
    output_html_artifact = os.path.join(artifact_dir, "job_gui.html") if artifact_dir else ""

    # 1. Read Jobs
    if os.path.exists(jobs_csv):
        df = pd.read_csv(jobs_csv)
    else:
        df = pd.DataFrame()

    # 2. Extract CV
    cv_text = ""
    if cv_pdf and os.path.exists(cv_pdf):
        try:
            res = subprocess.run(["pdftotext", cv_pdf, "-"], capture_output=True, text=True)
            cv_text = res.stdout.strip()
        except Exception:
            pass
    if not cv_text:
        cv_text = (
            "Parmpal Singh\nAI Engineer · LLMs, Agentic AI & RAG\n"
            "Lead AI Engineer at AIChunks. LangGraph, LangChain, Multi-Agent Systems, "
            "RAG, Voice AI, Python, FastAPI, pgvector, Docker, PyTorch."
        )

    cv_keywords = {
        "agentic": 7, "agent": 5, "agents": 5, "langgraph": 8, "langchain": 7,
        "llm": 6, "llms": 6, "rag": 7, "generative ai": 6, "genai": 6,
        "multi-agent": 7, "voice": 5, "mcp": 6, "python": 4, "fastapi": 4,
        "pytorch": 4, "tensorflow": 3, "transformers": 4, "hugging face": 4,
        "pgvector": 5, "vector": 4, "pinecone": 4, "docker": 3, "webrtc": 4,
        "reinforcement learning": 4, "nlp": 4, "data science": 4, "machine learning": 4,
        "deep learning": 4, "computer vision": 3, "sql": 3, "redis": 3
    }

    def calculate_match(title: str, desc: str):
        text = f"{title} {desc}".lower()
        score = 0
        matched = []

        t_low = str(title).lower()
        if any(k in t_low for k in ["agentic", "langgraph", "llm", "genai", "generative ai"]):
            score += 26
        elif "ai engineer" in t_low or "artificial intelligence" in t_low:
            score += 22
        elif "data scientist" in t_low or "machine learning" in t_low:
            score += 18

        for kw, weight in cv_keywords.items():
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                score += weight * 2.1
                if len(matched) < 6 and kw.title() not in matched:
                    matched.append(kw.title())

        final_score = min(99, max(28, int(score)))
        return final_score, matched[:5]

    def is_international(location: str) -> bool:
        loc = str(location).lower().strip()
        if not loc or loc in ["not specified"]:
            return False
        if re.search(r"\b(india|bengaluru|bangalore|hyderabad|mumbai|delhi|noida|gurugram|gurgaon|chennai|pune|chandigarh|panchkula|mohali|kerala|kochi|trivandrum|kolkata|calcutta|ahmedabad|jaipur)\b", loc):
            return False
        return True

    jobs_data = []
    seen_ids = set()

    for idx, r in df.iterrows():
        title = str(r.get("Job Profile", ""))
        desc = str(r.get("Job Description", ""))
        comp = str(r.get("Company Name", ""))
        loc = str(r.get("Location", ""))
        wp = str(r.get("Workplace Type", "On-site"))
        emp = str(r.get("Employment Type", "Full-time"))
        date_p = str(r.get("Date of Job Posting", ""))
        link = str(r.get("Link to Apply", ""))
        query = str(r.get("Search Query", ""))

        m = re.search(r"/view/(\d+)", link)
        if m:
            jid = m.group(1)
        else:
            jid = link.split("/")[-1].split("?")[0] if "/" in link else str(idx)

        if jid in seen_ids:
            continue
        seen_ids.add(jid)

        score, matched_skills = calculate_match(title, desc)
        is_int = is_international(loc)
        is_prof = "Profile" in query

        jobs_data.append({
            "id": jid,
            "company": comp,
            "title": title,
            "workplace_type": wp,
            "employment_type": emp,
            "location": loc,
            "date_posted": date_p,
            "apply_link": link,
            "description": desc,
            "search_query": query,
            "score": score,
            "matched_skills": matched_skills,
            "is_international": is_int,
            "is_profile": is_prof,
        })

    jobs_data.sort(key=lambda x: x["score"], reverse=True)

    json_jobs = json.dumps(jobs_data)
    json_cv = json.dumps(cv_text)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LinkedIn AI Job Suite & Application Tracker</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Custom scrollbars */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: rgba(150, 150, 150, 0.3); border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba(150, 150, 150, 0.5); }}
    .job-row {{ transition: all 0.15s ease-in-out; }}
    .job-row:hover {{ transform: translateY(-1px); }}
    .nav-tab.active {{ background: #2563eb; color: #ffffff; border-color: #3b82f6; }}
    .status-select {{ appearance: none; background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e"); background-repeat: no-repeat; background-position: right 0.5rem center; background-size: 1em; }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 antialiased font-sans h-screen flex flex-col overflow-hidden select-none">

  <!-- TOP HEADER / NAVBAR -->
  <header class="bg-slate-900/95 backdrop-blur border-b border-slate-800 px-4 py-2.5 shrink-0 z-20">
    <div class="max-w-[1700px] mx-auto flex flex-wrap items-center justify-between gap-3">
      
      <!-- Brand & View Switcher -->
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white font-bold text-sm">
            AI
          </div>
          <div>
            <h1 class="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              LinkedIn AI Job Suite
              <span id="headerTotalJobsCount" class="text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">{len(jobs_data)} Roles</span>
            </h1>
          </div>
        </div>

        <!-- View Switcher Tabs -->
        <div class="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-semibold">
          <button id="viewExplorerBtn" class="nav-tab active px-3 py-1 rounded-md transition flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            Job Explorer
          </button>
          <button id="viewTrackerBtn" class="nav-tab px-3 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path>
            </svg>
            Application Tracker
            <span id="navAppliedBadge" class="px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-500/20 text-emerald-300 font-bold ml-1">0</span>
          </button>
        </div>
      </div>

      <!-- LinkedIn Search Bar (Days Selector + Search Button) -->
      <div class="flex items-center gap-2 bg-slate-950/80 px-2.5 py-1 rounded-xl border border-slate-800 text-xs">
        <span class="text-slate-400 text-[11px] flex items-center gap-1">
          <svg class="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          Post Age:
        </span>
        <select id="searchDaysSelect" class="bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-slate-200 text-xs focus:outline-none focus:border-blue-500">
          <option value="1">1 Day (Past 24h)</option>
          <option value="2">2 Days</option>
          <option value="3">3 Days</option>
          <option value="7">7 Days (Past Week)</option>
          <option value="14">14 Days (Past 2 Weeks)</option>
          <option value="30">30 Days (Past Month)</option>
        </select>
        <button 
          id="runSearchBtn" 
          class="flex items-center gap-1.5 px-3 py-1 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white rounded-md text-xs font-semibold shadow-md shadow-blue-600/20 transition disabled:opacity-50 disabled:cursor-wait"
        >
          <span id="searchBtnIcon">🔍</span>
          <span id="searchBtnText">Fetch New Jobs</span>
        </button>
      </div>

      <!-- Utilities & Modals -->
      <div class="flex items-center gap-2">
        <button 
          id="openCvModalBtn" 
          class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-medium transition"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
          <span>CV Matcher</span>
        </button>

        <button 
          id="exportFilteredBtn" 
          class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 text-xs font-medium transition"
          title="Export All Filtered Roles to CSV (Includes Full Job Descriptions)"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
          <span>Export All (<span id="exportFilteredCount">0</span>)</span>
        </button>

        <button 
          id="exportShortlistBtn" 
          class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-medium transition"
          title="Export Shortlisted Roles to CSV (Includes Full Job Descriptions)"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
          </svg>
          <span>Shortlist (<span id="shortlistCountHeader">0</span>)</span>
        </button>
      </div>

    </div>

    <!-- NOTIFICATION / SEARCH BANNER -->
    <div id="searchBanner" class="hidden max-w-[1700px] mx-auto mt-2 px-3 py-1.5 rounded-lg bg-blue-900/30 border border-blue-500/30 text-blue-200 text-xs flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full" id="searchBannerSpinner"></span>
        <span id="searchBannerText">Searching LinkedIn for newly posted jobs... Deduplicating against current dataset.</span>
      </div>
      <button id="closeSearchBannerBtn" class="text-blue-300 hover:text-white text-xs font-bold">✕</button>
    </div>
  </header>

  <!-- ================= VIEW 1: JOB EXPLORER ================= -->
  <div id="viewExplorer" class="flex-1 flex flex-col overflow-hidden">
    
    <!-- EXPLORER SUB-HEADER / FILTERS ROW -->
    <div class="bg-slate-900/60 border-b border-slate-800 px-4 py-2 shrink-0">
      <div class="max-w-[1700px] mx-auto flex flex-wrap items-center justify-between gap-2 text-xs">
        
        <!-- Category Tabs -->
        <div class="flex items-center gap-1.5 overflow-x-auto pb-0.5" id="filterTabs">
          <button data-filter="all" class="filter-tab active px-2.5 py-1 rounded-md font-medium bg-blue-600 text-white">All (<span id="countAll">{len(jobs_data)}</span>)</button>
          <button data-filter="shortlist" class="filter-tab px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-amber-300">⭐ Selected (<span id="shortlistTabCount">0</span>)</button>
          <button data-filter="profile" class="filter-tab px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-purple-300">🎯 Profile Picks (7)</button>
          <button data-filter="international" class="filter-tab px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-blue-300">🌍 International (406)</button>
          <button data-filter="remote" class="filter-tab px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-emerald-300">🏠 Remote (70)</button>
          <button data-filter="hybrid" class="filter-tab px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-amber-300">🏢 Hybrid (208)</button>
          <button data-filter="onsite" class="filter-tab px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-slate-300">📍 On-site (320)</button>
        </div>

        <!-- Right Side: Hide Applied Toggle + Search + Sort -->
        <div class="flex items-center gap-3 ml-auto">
          
          <!-- HIDE APPLIED JOBS TOGGLE -->
          <label class="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-950 border border-slate-700/80 hover:border-slate-600 cursor-pointer text-slate-300 font-medium text-xs transition">
            <input type="checkbox" id="hideAppliedToggle" class="rounded bg-slate-800 border-slate-600 text-emerald-500 focus:ring-0 cursor-pointer" />
            <span>Hide Applied Jobs</span>
          </label>

          <!-- Search Input -->
          <div class="relative w-56">
            <input 
              id="searchInput" 
              type="text" 
              placeholder="Search title, company, skill..." 
              class="w-full bg-slate-950 border border-slate-700 rounded-md pl-7 pr-6 py-1 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <svg class="w-3.5 h-3.5 absolute left-2 top-2 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            <button id="clearSearchBtn" class="hidden absolute right-2 top-1.5 text-slate-500 hover:text-slate-300 text-xs">✕</button>
          </div>

          <!-- Sort Select -->
          <div class="flex items-center gap-1.5">
            <span class="text-slate-400">Sort:</span>
            <select id="sortSelect" class="bg-slate-950 border border-slate-700 rounded-md px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-blue-500">
              <option value="score_desc">⭐ Match Score (Highest)</option>
              <option value="date_desc">📅 Date Posted (Newest)</option>
              <option value="company_asc">🏢 Company (A-Z)</option>
              <option value="title_asc">💼 Title (A-Z)</option>
            </select>
          </div>

        </div>

      </div>
    </div>

    <!-- MAIN SPLIT WORKSPACE -->
    <main class="flex-1 flex overflow-hidden">

      <!-- LEFT / CENTER: JOBS TABLE -->
      <section class="flex-1 flex flex-col border-r border-slate-800/80 bg-slate-950/60 overflow-hidden">
        
        <!-- Table Header Bar -->
        <div class="bg-slate-900/60 border-b border-slate-800 px-4 py-2 flex items-center justify-between text-xs text-slate-400 font-semibold shrink-0">
          <div class="flex items-center gap-3">
            <input type="checkbox" id="selectAllCheckbox" class="rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0 cursor-pointer" title="Select all on current page" />
            <span>Showing <span id="showingStart">1</span>-<span id="showingEnd">25</span> of <span id="totalMatches">{len(jobs_data)}</span> jobs</span>
          </div>
          <div class="flex items-center gap-1.5">
            <button id="prevPageBtn" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed text-xs">◀ Prev</button>
            <span id="pageIndicator" class="text-slate-300 font-mono px-2">Page 1 / 24</span>
            <button id="nextPageBtn" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed text-xs">Next ▶</button>
          </div>
        </div>

        <!-- Scrollable Jobs Table -->
        <div class="flex-1 overflow-y-auto" id="jobsTableContainer">
          <table class="w-full text-left border-collapse text-xs">
            <thead class="sticky top-0 bg-slate-900 border-b border-slate-800 text-slate-400 font-semibold z-10">
              <tr>
                <th class="py-2.5 px-3 w-9 text-center">⭐</th>
                <th class="py-2.5 px-3 w-16 text-center">Match</th>
                <th class="py-2.5 px-3 w-36">Company</th>
                <th class="py-2.5 px-3">Job Profile</th>
                <th class="py-2.5 px-3 w-20 text-center">Workplace</th>
                <th class="py-2.5 px-3 w-36">Location</th>
                <th class="py-2.5 px-3 w-24 text-center">Posted</th>
                <th class="py-2.5 px-3 w-28 text-center">Applied</th>
                <th class="py-2.5 px-3 w-20 text-center">Apply</th>
              </tr>
            </thead>
            <tbody id="jobsTableBody" class="divide-y divide-slate-800/60">
              <!-- Rendered by JS -->
            </tbody>
          </table>
        </div>

      </section>

      <!-- RIGHT: JOB INSPECTOR DETAIL PANEL (Corner panel) -->
      <aside id="detailPanel" class="w-[450px] lg:w-[480px] flex flex-col bg-slate-900/40 border-l border-slate-800/80 shrink-0 overflow-hidden">
        
        <!-- Panel Header Bar -->
        <div class="bg-slate-900/80 border-b border-slate-800 px-4 py-2.5 flex items-center justify-between shrink-0">
          <h2 class="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
            </svg>
            Job Inspector
          </h2>
          <span id="detailJobId" class="text-[10px] font-mono text-slate-500">Select a job</span>
        </div>

        <!-- Detail Body (Scrollable) -->
        <div id="detailContent" class="flex-1 overflow-y-auto p-4 space-y-3.5">
          
          <!-- Placeholder State -->
          <div id="emptyDetailPlaceholder" class="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-3">
            <div class="w-12 h-12 rounded-full bg-slate-800/60 flex items-center justify-center text-slate-400">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
              </svg>
            </div>
            <div>
              <h3 class="text-sm font-medium text-slate-300">No Job Selected</h3>
              <p class="text-xs text-slate-500 mt-1 max-w-xs">Click any row in the table to inspect full description, match breakdown, and track applications.</p>
            </div>
          </div>

          <!-- Populated State -->
          <div id="populatedDetail" class="hidden space-y-3.5">
            
            <!-- Card Header Info -->
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-3.5 shadow-sm space-y-2.5">
              <div>
                <span id="detailCompany" class="text-xs font-bold text-blue-400 uppercase tracking-wide">Company Name</span>
                <h3 id="detailTitle" class="text-sm font-bold text-white mt-0.5 leading-snug">Senior AI Engineer</h3>
              </div>
              
              <div class="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span id="detailWorkplaceBadge" class="px-2 py-0.5 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Remote</span>
                <span id="detailEmploymentBadge" class="px-2 py-0.5 rounded-full font-medium bg-slate-800 text-slate-300 border border-slate-700">Full-time</span>
                <span id="detailLocation" class="px-2 py-0.5 rounded-full font-medium bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1">
                  📍 Location
                </span>
                <span id="detailPostedDate" class="text-slate-400 text-[10px] ml-auto">Posted: 2026-11-22</span>
              </div>

              <!-- Action Buttons Bar: Shortlist + Mark Applied + Apply LinkedIn -->
              <div class="pt-2 flex flex-col gap-2 border-t border-slate-800">
                <div class="flex items-center gap-2">
                  <button 
                    id="toggleShortlistBtn" 
                    class="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-semibold transition"
                  >
                    <span id="shortlistIcon">⭐</span>
                    <span id="shortlistBtnText">Add to Shortlist</span>
                  </button>
                  
                  <button 
                    id="detailToggleAppliedBtn" 
                    class="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-semibold transition"
                  >
                    <span id="detailAppliedIcon">📝</span>
                    <span id="detailAppliedBtnText">Mark as Applied</span>
                  </button>
                </div>

                <a 
                  id="detailApplyLink" 
                  href="#" 
                  target="_blank" 
                  class="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition shadow-lg shadow-blue-600/20"
                >
                  <span>Apply on LinkedIn</span>
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                  </svg>
                </a>
              </div>
            </div>

            <!-- CV Match Score Details -->
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-3 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-slate-300">CV Match Breakdown</span>
                <span id="detailScoreNumber" class="text-xs font-bold text-emerald-400">92%</span>
              </div>
              
              <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div id="detailScoreBar" class="bg-emerald-500 h-1.5 rounded-full transition-all duration-300" style="width: 92%"></div>
              </div>

              <div class="pt-1">
                <span class="text-[10px] text-slate-400 block mb-1">Key Matching Skills:</span>
                <div id="detailMatchedSkills" class="flex flex-wrap gap-1">
                  <!-- Pills -->
                </div>
              </div>
            </div>

            <!-- Full Unabridged Job Description -->
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-2">
              <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">Full Job Description</h4>
              <div id="detailDescriptionText" class="text-xs text-slate-300 leading-relaxed whitespace-pre-line font-sans select-text">
                <!-- Description text -->
              </div>
            </div>

          </div>

        </div>

      </aside>

    </main>
  </div>

  <!-- ================= VIEW 2: APPLICATION TRACKER ================= -->
  <div id="viewTracker" class="hidden flex-1 flex flex-col overflow-hidden bg-slate-950">
    
    <!-- TRACKER TOP STATS & ACTIONS BAR -->
    <div class="bg-slate-900/80 border-b border-slate-800 px-6 py-4 shrink-0">
      <div class="max-w-[1700px] mx-auto space-y-4">
        
        <!-- Header & Action Buttons -->
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="text-base font-bold text-white flex items-center gap-2">
              📋 Job Application Pipeline & Tracker
              <span id="trackerTotalBadge" class="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">0 Tracked</span>
            </h2>
            <p class="text-xs text-slate-400 mt-0.5">Manage your application stages, interview calls, feedback, and issues</p>
          </div>

          <div class="flex items-center gap-2">
            <button 
              id="exportAppliedCsvBtn" 
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
              </svg>
              <span>Export Applications CSV</span>
            </button>
          </div>
        </div>

        <!-- Metric Pipeline Summary Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2.5 text-xs">
          
          <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
            <span class="text-slate-400 font-medium">Total Applied</span>
            <span id="metricTotalApplied" class="text-xl font-bold text-blue-400 mt-1">0</span>
          </div>

          <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
            <span class="text-slate-400 font-medium">Pending Review</span>
            <span id="metricPending" class="text-xl font-bold text-slate-200 mt-1">0</span>
          </div>

          <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
            <span class="text-slate-400 font-medium">HR / Recruiter Call</span>
            <span id="metricCalls" class="text-xl font-bold text-amber-400 mt-1">0</span>
          </div>

          <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
            <span class="text-slate-400 font-medium">Tech Interview</span>
            <span id="metricInterviews" class="text-xl font-bold text-indigo-400 mt-1">0</span>
          </div>

          <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
            <span class="text-slate-400 font-medium">Issues / Follow-up</span>
            <span id="metricIssues" class="text-xl font-bold text-rose-400 mt-1">0</span>
          </div>

          <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
            <span class="text-slate-400 font-medium">Offer Received</span>
            <span id="metricOffers" class="text-xl font-bold text-emerald-400 mt-1">0</span>
          </div>

        </div>

        <!-- Status Filter Tabs & Search for Tracker -->
        <div class="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800/80 text-xs">
          <div class="flex items-center gap-1.5 overflow-x-auto" id="trackerStatusTabs">
            <button data-status="all" class="tracker-filter active px-2.5 py-1 rounded-md font-medium bg-blue-600 text-white">All (<span id="trkCountAll">0</span>)</button>
            <button data-status="Applied" class="tracker-filter px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700">📝 Applied</button>
            <button data-status="Get Call / HR Screen" class="tracker-filter px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-amber-300">📞 HR Screen</button>
            <button data-status="Technical Interview" class="tracker-filter px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-indigo-300">💻 Interview</button>
            <button data-status="Interview Issues" class="tracker-filter px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-rose-300">⚠️ Issues / Follow-up</button>
            <button data-status="Offer" class="tracker-filter px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-emerald-300">🎉 Offer</button>
            <button data-status="Rejected" class="tracker-filter px-2.5 py-1 rounded-md font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 text-slate-400">❌ Rejected</button>
          </div>

          <div class="relative w-64">
            <input 
              id="trackerSearchInput" 
              type="text" 
              placeholder="Filter applied companies or notes..." 
              class="w-full bg-slate-950 border border-slate-700 rounded-md pl-7 pr-3 py-1 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <svg class="w-3.5 h-3.5 absolute left-2 top-2 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
          </div>
        </div>

      </div>
    </div>

    <!-- TRACKER TABLE CONTENT -->
    <div class="flex-1 overflow-y-auto p-6" id="trackerTableContainer">
      <div class="max-w-[1700px] mx-auto bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <table class="w-full text-left border-collapse text-xs">
          <thead class="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-semibold">
            <tr>
              <th class="py-3 px-4 w-44">Company</th>
              <th class="py-3 px-4 w-64">Job Profile</th>
              <th class="py-3 px-4 w-52">Application Status</th>
              <th class="py-3 px-4 w-36">Applied Date</th>
              <th class="py-3 px-4 w-32">Workplace</th>
              <th class="py-3 px-4">Notes & Interview Response Log</th>
              <th class="py-3 px-4 w-28 text-center">Action</th>
            </tr>
          </thead>
          <tbody id="trackerTableBody" class="divide-y divide-slate-800/80">
            <!-- Rendered by JS -->
          </tbody>
        </table>

        <!-- Empty Tracker Placeholder -->
        <div id="trackerEmptyState" class="hidden py-16 text-center text-slate-400 space-y-3">
          <div class="w-12 h-12 rounded-full bg-slate-800/80 flex items-center justify-center mx-auto text-slate-400 text-xl">
            📋
          </div>
          <div>
            <h3 class="text-sm font-semibold text-slate-200">No Job Applications Tracked Yet</h3>
            <p class="text-xs text-slate-500 max-w-md mx-auto mt-1">
              Switch to the <strong>Job Explorer</strong> and click <strong>"+ Mark Applied"</strong> on any job you apply to. They will automatically appear here with full status tracking!
            </p>
          </div>
          <button id="emptyStateExploreBtn" class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition">
            Go to Job Explorer
          </button>
        </div>

      </div>
    </div>

  </div>

  <!-- ================= MODAL: CV MATCHER & RANKER ================= -->
  <div id="cvModal" class="hidden fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
      
      <!-- Modal Header -->
      <div class="px-5 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
          </div>
          <div>
            <h3 class="text-sm font-bold text-white">CV & Resume Matcher</h3>
            <p class="text-xs text-slate-400">Review or paste a new CV to re-rank all job posts instantly</p>
          </div>
        </div>
        <button id="closeCvModalBtn" class="text-slate-400 hover:text-white text-lg">✕</button>
      </div>

      <!-- Modal Body -->
      <div class="p-5 flex-1 overflow-y-auto space-y-4">
        <div>
          <label class="block text-xs font-semibold text-slate-300 mb-1.5">
            Your Active CV / Professional Summary:
          </label>
          <textarea 
            id="cvInputText" 
            rows="10" 
            class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-indigo-500 select-text"
            placeholder="Paste your resume or CV text here..."
          ></textarea>
        </div>

        <div class="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3 text-xs text-slate-400 space-y-1">
          <span class="font-semibold text-slate-300 block">How scoring works:</span>
          <p>The engine matches high-value keywords in the Job Profile & Description against your CV (Agentic AI, LangGraph, RAG, LLMs, Voice AI, Python, FastAPI, pgvector, etc.) and generates a normalized Match Score from 25% to 99%.</p>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-5 py-3 border-t border-slate-800 flex items-center justify-between bg-slate-900/80">
        <button id="resetCvBtn" class="text-xs text-slate-400 hover:text-slate-200">Reset to Default Resume</button>
        <div class="flex items-center gap-2">
          <button id="cancelCvBtn" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium">Cancel</button>
          <button id="reRankBtn" class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/20">Re-Rank All Jobs</button>
        </div>
      </div>

    </div>
  </div>

  <!-- EMBEDDED DATA & APPLICATION LOGIC -->
  <script>
    const INITIAL_JOBS = {json_jobs};
    const DEFAULT_CV = {json_cv};

    let allJobs = [...INITIAL_JOBS];
    let filteredJobs = [...INITIAL_JOBS];
    let selectedJob = null;
    let currentFilter = 'all';
    let currentSearch = '';
    let currentSort = 'score_desc';
    let currentPage = 1;
    const pageSize = 25;
    let hideApplied = false;

    // Shortlist Set
    let shortlistedIds = new Set(JSON.parse(localStorage.getItem('shortlisted_job_ids') || '[]'));

    // Applied Jobs State Object: {{ jid: {{ status, applied_date, notes, company, title, workplace_type, location, score, apply_link }} }}
    let appliedJobs = JSON.parse(localStorage.getItem('applied_jobs_data') || '{{}}');

    // DOM Elements - Navigation & Views
    const viewExplorer = document.getElementById('viewExplorer');
    const viewTracker = document.getElementById('viewTracker');
    const viewExplorerBtn = document.getElementById('viewExplorerBtn');
    const viewTrackerBtn = document.getElementById('viewTrackerBtn');
    const navAppliedBadge = document.getElementById('navAppliedBadge');
    const headerTotalJobsCount = document.getElementById('headerTotalJobsCount');
    const countAll = document.getElementById('countAll');

    // DOM Elements - Search Controls
    const searchDaysSelect = document.getElementById('searchDaysSelect');
    const runSearchBtn = document.getElementById('runSearchBtn');
    const searchBtnIcon = document.getElementById('searchBtnIcon');
    const searchBtnText = document.getElementById('searchBtnText');
    const searchBanner = document.getElementById('searchBanner');
    const searchBannerSpinner = document.getElementById('searchBannerSpinner');
    const searchBannerText = document.getElementById('searchBannerText');
    const closeSearchBannerBtn = document.getElementById('closeSearchBannerBtn');

    // DOM Elements - Explorer
    const hideAppliedToggle = document.getElementById('hideAppliedToggle');
    const searchInput = document.getElementById('searchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    const filterTabs = document.getElementById('filterTabs');
    const sortSelect = document.getElementById('sortSelect');
    const jobsTableBody = document.getElementById('jobsTableBody');
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    const pageIndicator = document.getElementById('pageIndicator');
    const showingStart = document.getElementById('showingStart');
    const showingEnd = document.getElementById('showingEnd');
    const totalMatches = document.getElementById('totalMatches');
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const shortlistCountHeader = document.getElementById('shortlistCountHeader');
    const shortlistTabCount = document.getElementById('shortlistTabCount');
    const exportShortlistBtn = document.getElementById('exportShortlistBtn');
    const exportFilteredBtn = document.getElementById('exportFilteredBtn');
    const exportFilteredCount = document.getElementById('exportFilteredCount');

    // Detail Panel Elements
    const emptyDetailPlaceholder = document.getElementById('emptyDetailPlaceholder');
    const populatedDetail = document.getElementById('populatedDetail');
    const detailJobId = document.getElementById('detailJobId');
    const detailCompany = document.getElementById('detailCompany');
    const detailTitle = document.getElementById('detailTitle');
    const detailWorkplaceBadge = document.getElementById('detailWorkplaceBadge');
    const detailEmploymentBadge = document.getElementById('detailEmploymentBadge');
    const detailLocation = document.getElementById('detailLocation');
    const detailPostedDate = document.getElementById('detailPostedDate');
    const toggleShortlistBtn = document.getElementById('toggleShortlistBtn');
    const shortlistBtnText = document.getElementById('shortlistBtnText');
    const shortlistIcon = document.getElementById('shortlistIcon');
    const detailToggleAppliedBtn = document.getElementById('detailToggleAppliedBtn');
    const detailAppliedIcon = document.getElementById('detailAppliedIcon');
    const detailAppliedBtnText = document.getElementById('detailAppliedBtnText');
    const detailApplyLink = document.getElementById('detailApplyLink');
    const detailScoreNumber = document.getElementById('detailScoreNumber');
    const detailScoreBar = document.getElementById('detailScoreBar');
    const detailMatchedSkills = document.getElementById('detailMatchedSkills');
    const detailDescriptionText = document.getElementById('detailDescriptionText');

    // Tracker Elements
    const trackerTotalBadge = document.getElementById('trackerTotalBadge');
    const metricTotalApplied = document.getElementById('metricTotalApplied');
    const metricPending = document.getElementById('metricPending');
    const metricCalls = document.getElementById('metricCalls');
    const metricInterviews = document.getElementById('metricInterviews');
    const metricIssues = document.getElementById('metricIssues');
    const metricOffers = document.getElementById('metricOffers');
    const trackerTableBody = document.getElementById('trackerTableBody');
    const trackerEmptyState = document.getElementById('trackerEmptyState');
    const trkCountAll = document.getElementById('trkCountAll');
    const trackerStatusTabs = document.getElementById('trackerStatusTabs');
    const trackerSearchInput = document.getElementById('trackerSearchInput');
    const exportAppliedCsvBtn = document.getElementById('exportAppliedCsvBtn');
    const emptyStateExploreBtn = document.getElementById('emptyStateExploreBtn');
    let currentTrackerStatus = 'all';

    // CV Modal Elements
    const cvModal = document.getElementById('cvModal');
    const openCvModalBtn = document.getElementById('openCvModalBtn');
    const closeCvModalBtn = document.getElementById('closeCvModalBtn');
    const cancelCvBtn = document.getElementById('cancelCvBtn');
    const cvInputText = document.getElementById('cvInputText');
    const reRankBtn = document.getElementById('reRankBtn');
    const resetCvBtn = document.getElementById('resetCvBtn');

    // Initialize CV text
    cvInputText.value = localStorage.getItem('user_cv_text') || DEFAULT_CV;

    // Load initial backend applied jobs data if available
    async function syncBackendApplications() {{
      try {{
        const res = await fetch('/api/applications');
        if (res.ok) {{
          const data = await res.json();
          if (data && typeof data === 'object') {{
            // Merge with local
            appliedJobs = {{ ...data, ...appliedJobs }};
            saveAppliedJobs();
          }}
        }}
      }} catch (err) {{
        // Local fallback is completely fine
      }}
    }}
    syncBackendApplications();

    function saveShortlist() {{
      localStorage.setItem('shortlisted_job_ids', JSON.stringify([...shortlistedIds]));
      updateShortlistCounters();
    }}

    function updateShortlistCounters() {{
      const count = shortlistedIds.size;
      shortlistCountHeader.textContent = count;
      shortlistTabCount.textContent = count;
    }}

    function saveAppliedJobs() {{
      localStorage.setItem('applied_jobs_data', JSON.stringify(appliedJobs));
      updateAppliedCounters();
      renderTrackerTable();

      // Background sync to backend server
      fetch('/api/applications', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(appliedJobs)
      }}).catch(() => {{}});
    }}

    function updateAppliedCounters() {{
      const keys = Object.keys(appliedJobs);
      const total = keys.length;
      navAppliedBadge.textContent = total;
      trackerTotalBadge.textContent = `${{total}} Tracked`;
      trkCountAll.textContent = total;

      let pending = 0, calls = 0, interviews = 0, issues = 0, offers = 0;
      keys.forEach(k => {{
        const st = (appliedJobs[k].status || 'Applied');
        if (st === 'Applied') pending++;
        else if (st === 'Get Call / HR Screen') calls++;
        else if (st === 'Technical Interview') interviews++;
        else if (st === 'Interview Issues') issues++;
        else if (st === 'Offer') offers++;
      }});

      metricTotalApplied.textContent = total;
      metricPending.textContent = pending;
      metricCalls.textContent = calls;
      metricInterviews.textContent = interviews;
      metricIssues.textContent = issues;
      metricOffers.textContent = offers;
    }}

    function toggleJobApplied(job) {{
      if (appliedJobs[job.id]) {{
        delete appliedJobs[job.id];
      }} else {{
        appliedJobs[job.id] = {{
          job_id: job.id,
          company: job.company,
          title: job.title,
          status: 'Applied',
          applied_date: new Date().toISOString().slice(0, 10),
          workplace_type: job.workplace_type,
          employment_type: job.employment_type,
          location: job.location,
          score: job.score,
          apply_link: job.apply_link,
          description: job.description || '',
          notes: ''
        }};
      }}
      saveAppliedJobs();
      if (selectedJob && selectedJob.id === job.id) updateAppliedBtnState();
      applyFilters();
    }}

    function getScoreBadge(score) {{
      if (score >= 85) {{
        return `<span class="px-2 py-0.5 rounded-full font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${{score}}%</span>`;
      }} else if (score >= 70) {{
        return `<span class="px-2 py-0.5 rounded-full font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">${{score}}%</span>`;
      }} else if (score >= 50) {{
        return `<span class="px-2 py-0.5 rounded-full font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">${{score}}%</span>`;
      }} else {{
        return `<span class="px-2 py-0.5 rounded-full font-medium bg-slate-800 text-slate-400 border border-slate-700">${{score}}%</span>`;
      }}
    }}

    function getWorkplaceBadge(wp) {{
      if (wp === 'Remote') {{
        return `<span class="px-2 py-0.5 rounded font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Remote</span>`;
      }} else if (wp === 'Hybrid') {{
        return `<span class="px-2 py-0.5 rounded font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">Hybrid</span>`;
      }} else {{
        return `<span class="px-2 py-0.5 rounded font-medium bg-slate-800 text-slate-300 border border-slate-700">On-site</span>`;
      }}
    }}

    function applyFilters() {{
      const q = currentSearch.toLowerCase().trim();

      filteredJobs = allJobs.filter(j => {{
        // Hide applied filter
        const isApplied = Boolean(appliedJobs[j.id]);
        if (hideApplied && isApplied) return false;

        // Filter tabs
        if (currentFilter === 'shortlist' && !shortlistedIds.has(j.id)) return false;
        if (currentFilter === 'profile' && !j.is_profile) return false;
        if (currentFilter === 'international' && !j.is_international) return false;
        if (currentFilter === 'remote' && j.workplace_type !== 'Remote') return false;
        if (currentFilter === 'hybrid' && j.workplace_type !== 'Hybrid') return false;
        if (currentFilter === 'onsite' && j.workplace_type !== 'On-site') return false;

        // Search box
        if (q) {{
          const comb = `${{j.title}} ${{j.company}} ${{j.location}} ${{j.matched_skills.join(' ')}}`.toLowerCase();
          if (!comb.includes(q)) return false;
        }}

        return true;
      }});

      // Sorting
      if (currentSort === 'score_desc') {{
        filteredJobs.sort((a, b) => b.score - a.score);
      }} else if (currentSort === 'date_desc') {{
        filteredJobs.sort((a, b) => (b.date_posted || '').localeCompare(a.date_posted || ''));
      }} else if (currentSort === 'company_asc') {{
        filteredJobs.sort((a, b) => a.company.localeCompare(b.company));
      }} else if (currentSort === 'title_asc') {{
        filteredJobs.sort((a, b) => a.title.localeCompare(b.title));
      }}

      currentPage = 1;
      renderTable();
    }}

    function renderTable() {{
      const total = filteredJobs.length;
      totalMatches.textContent = total;
      if (exportFilteredCount) exportFilteredCount.textContent = total;

      const totalPages = Math.max(1, Math.ceil(total / pageSize));
      if (currentPage > totalPages) currentPage = totalPages;

      const startIdx = (currentPage - 1) * pageSize;
      const endIdx = Math.min(startIdx + pageSize, total);
      const pageSlice = filteredJobs.slice(startIdx, endIdx);

      showingStart.textContent = total === 0 ? 0 : startIdx + 1;
      showingEnd.textContent = endIdx;
      pageIndicator.textContent = `Page ${{currentPage}} / ${{totalPages}}`;

      prevPageBtn.disabled = currentPage <= 1;
      nextPageBtn.disabled = currentPage >= totalPages;

      const allPageSelected = pageSlice.length > 0 && pageSlice.every(j => shortlistedIds.has(j.id));
      selectAllCheckbox.checked = allPageSelected;

      if (pageSlice.length === 0) {{
        jobsTableBody.innerHTML = `
          <tr>
            <td colspan="9" class="text-center py-12 text-slate-500">
              No jobs matching the current filter criteria.
            </td>
          </tr>
        `;
        return;
      }}

      jobsTableBody.innerHTML = pageSlice.map(j => {{
        const isSelected = selectedJob && selectedJob.id === j.id;
        const isShortlisted = shortlistedIds.has(j.id);
        const isApplied = Boolean(appliedJobs[j.id]);
        const activeClass = isSelected ? 'bg-blue-900/20 border-l-2 border-blue-500' : 'hover:bg-slate-900/70';

        const appliedBtnHtml = isApplied ? `
          <button 
            class="job-applied-btn px-2 py-0.5 rounded-full font-bold bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/40 text-[11px] transition inline-flex items-center gap-1 shadow-sm shadow-emerald-500/10" 
            data-id="${{j.id}}" 
            title="Marked as Applied! Click to unmark"
          >
            ✓ Applied
          </button>
        ` : `
          <button 
            class="job-applied-btn px-2 py-0.5 rounded-full font-medium bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700/80 text-[11px] transition inline-flex items-center gap-1" 
            data-id="${{j.id}}" 
            title="Mark as Applied"
          >
            + Mark Applied
          </button>
        `;

        return `
          <tr class="job-row cursor-pointer ${{activeClass}}" data-id="${{j.id}}">
            <td class="py-2.5 px-3 text-center" onclick="event.stopPropagation()">
              <input 
                type="checkbox" 
                class="job-checkbox rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0 cursor-pointer" 
                data-id="${{j.id}}" 
                ${{isShortlisted ? 'checked' : ''}} 
              />
            </td>
            <td class="py-2.5 px-3 text-center">
              ${{getScoreBadge(j.score)}}
            </td>
            <td class="py-2.5 px-3 font-semibold text-slate-200 truncate max-w-[130px]" title="${{j.company}}">
              ${{j.company}}
            </td>
            <td class="py-2.5 px-3">
              <div class="font-medium text-white truncate max-w-[220px]" title="${{j.title}}">${{j.title}}</div>
              <div class="text-[10px] text-slate-400 truncate max-w-[220px]">${{j.matched_skills.join(' · ') || 'General AI'}}</div>
            </td>
            <td class="py-2.5 px-3 text-center">
              ${{getWorkplaceBadge(j.workplace_type)}}
            </td>
            <td class="py-2.5 px-3 text-slate-300 truncate max-w-[140px]" title="${{j.location}}">
              ${{j.location}}
            </td>
            <td class="py-2.5 px-3 text-center text-slate-400 text-[11px]">
              ${{j.date_posted || 'Recent'}}
            </td>
            <td class="py-2.5 px-3 text-center" onclick="event.stopPropagation()">
              ${{appliedBtnHtml}}
            </td>
            <td class="py-2.5 px-3 text-center" onclick="event.stopPropagation()">
              <a 
                href="${{j.apply_link}}" 
                target="_blank" 
                class="px-2 py-0.5 rounded bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 border border-blue-500/30 font-medium text-[11px] transition inline-flex items-center gap-1"
              >
                Apply
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                </svg>
              </a>
            </td>
          </tr>
        `;
      }}).join('');

      if (!selectedJob && pageSlice.length > 0) {{
        selectJob(pageSlice[0]);
      }}
    }}

    function selectJob(job) {{
      selectedJob = job;
      emptyDetailPlaceholder.classList.add('hidden');
      populatedDetail.classList.remove('hidden');

      detailJobId.textContent = `ID: ${{job.id}}`;
      detailCompany.textContent = job.company;
      detailTitle.textContent = job.title;
      detailLocation.textContent = `📍 ${{job.location}}`;
      detailPostedDate.textContent = `Posted: ${{job.date_posted || 'Recent'}}`;

      detailWorkplaceBadge.className = 'px-2 py-0.5 rounded-full font-medium ' + 
        (job.workplace_type === 'Remote' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 
         job.workplace_type === 'Hybrid' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 
         'bg-slate-800 text-slate-300 border border-slate-700');
      detailWorkplaceBadge.textContent = job.workplace_type;

      detailEmploymentBadge.textContent = job.employment_type;
      detailApplyLink.href = job.apply_link;

      detailScoreNumber.textContent = `${{job.score}}% Match`;
      detailScoreBar.style.width = `${{job.score}}%`;
      detailScoreBar.className = job.score >= 80 ? 'bg-emerald-500 h-1.5 rounded-full' : (job.score >= 65 ? 'bg-cyan-500 h-1.5 rounded-full' : 'bg-amber-500 h-1.5 rounded-full');

      detailMatchedSkills.innerHTML = job.matched_skills.map(s => 
        `<span class="px-2 py-0.5 rounded bg-slate-800 text-indigo-300 border border-indigo-500/20 text-[10px] font-medium">${{s}}</span>`
      ).join('') || '<span class="text-slate-500 text-[10px]">General matching</span>';

      detailDescriptionText.textContent = job.description || 'Description unavailable';

      updateShortlistBtnState();
      updateAppliedBtnState();

      document.querySelectorAll('.job-row').forEach(row => {{
        if (row.getAttribute('data-id') === job.id) {{
          row.classList.add('bg-blue-900/20', 'border-l-2', 'border-blue-500');
        }} else {{
          row.classList.remove('bg-blue-900/20', 'border-l-2', 'border-blue-500');
        }}
      }});
    }}

    function updateShortlistBtnState() {{
      if (!selectedJob) return;
      const isShortlisted = shortlistedIds.has(selectedJob.id);
      if (isShortlisted) {{
        toggleShortlistBtn.className = 'flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg bg-amber-500 text-slate-950 font-bold text-xs transition shadow-lg shadow-amber-500/20';
        shortlistIcon.textContent = '✓';
        shortlistBtnText.textContent = 'Shortlisted (Click to Remove)';
      }} else {{
        toggleShortlistBtn.className = 'flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-semibold transition';
        shortlistIcon.textContent = '⭐';
        shortlistBtnText.textContent = 'Add to Shortlist';
      }}
    }}

    function updateAppliedBtnState() {{
      if (!selectedJob) return;
      const isApplied = Boolean(appliedJobs[selectedJob.id]);
      if (isApplied) {{
        detailToggleAppliedBtn.className = 'flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg bg-emerald-600 text-white font-bold text-xs transition shadow-lg shadow-emerald-600/20';
        detailAppliedIcon.textContent = '✓';
        detailAppliedBtnText.textContent = 'Applied (Click to Unmark)';
      }} else {{
        detailToggleAppliedBtn.className = 'flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-semibold transition';
        detailAppliedIcon.textContent = '📝';
        detailAppliedBtnText.textContent = 'Mark as Applied';
      }}
    }}

    // ================= APPLICATION TRACKER RENDERING =================
    function renderTrackerTable() {{
      const keys = Object.keys(appliedJobs);
      const q = (trackerSearchInput.value || '').toLowerCase().trim();

      const filteredKeys = keys.filter(k => {{
        const app = appliedJobs[k];
        if (currentTrackerStatus !== 'all' && (app.status || 'Applied') !== currentTrackerStatus) {{
          return false;
        }}
        if (q) {{
          const comb = `${{app.company}} ${{app.title}} ${{app.notes || ''}} ${{app.location}}`.toLowerCase();
          if (!comb.includes(q)) return false;
        }}
        return true;
      }});

      if (filteredKeys.length === 0) {{
        trackerTableBody.innerHTML = '';
        trackerEmptyState.classList.remove('hidden');
        return;
      }}

      trackerEmptyState.classList.add('hidden');

      trackerTableBody.innerHTML = filteredKeys.map(k => {{
        const app = appliedJobs[k];
        const status = app.status || 'Applied';
        
        let statusColor = 'bg-slate-800 text-slate-300 border-slate-700';
        if (status === 'Get Call / HR Screen') statusColor = 'bg-amber-500/10 text-amber-300 border-amber-500/30';
        else if (status === 'Technical Interview') statusColor = 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30';
        else if (status === 'Interview Issues') statusColor = 'bg-rose-500/10 text-rose-300 border-rose-500/30';
        else if (status === 'Offer') statusColor = 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30';
        else if (status === 'Rejected') statusColor = 'bg-slate-900 text-slate-500 border-slate-800';

        return `
          <tr class="hover:bg-slate-900/50 transition">
            <td class="py-3 px-4 font-bold text-white text-xs truncate max-w-[170px]" title="${{app.company}}">
              ${{app.company}}
            </td>
            <td class="py-3 px-4">
              <div class="font-semibold text-slate-200 truncate max-w-[240px]" title="${{app.title}}">${{app.title}}</div>
              <div class="text-[10px] text-slate-400 mt-0.5">${{app.location || ''}} · ${{app.score || 0}}% Match</div>
            </td>
            <td class="py-3 px-4">
              <select 
                class="status-select w-full bg-slate-950 border rounded-lg px-2.5 py-1 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer ${{statusColor}}" 
                data-id="${{app.job_id}}"
              >
                <option value="Applied" ${{status === 'Applied' ? 'selected' : ''}}>📝 Applied</option>
                <option value="Get Call / HR Screen" ${{status === 'Get Call / HR Screen' ? 'selected' : ''}}>📞 Get Call / HR Screen</option>
                <option value="Technical Interview" ${{status === 'Technical Interview' ? 'selected' : ''}}>💻 Technical Interview</option>
                <option value="Interview Issues" ${{status === 'Interview Issues' ? 'selected' : ''}}>⚠️ Interview Issues / Follow-up</option>
                <option value="Offer" ${{status === 'Offer' ? 'selected' : ''}}>🎉 Offer Received</option>
                <option value="Rejected" ${{status === 'Rejected' ? 'selected' : ''}}>❌ Rejected</option>
                <option value="Archived" ${{status === 'Archived' ? 'selected' : ''}}>📦 Archived</option>
              </select>
            </td>
            <td class="py-3 px-4">
              <input 
                type="date" 
                class="applied-date-input bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-blue-500 cursor-pointer" 
                value="${{app.applied_date || ''}}" 
                data-id="${{app.job_id}}" 
              />
            </td>
            <td class="py-3 px-4">
              ${{getWorkplaceBadge(app.workplace_type || 'On-site')}}
            </td>
            <td class="py-3 px-4">
              <input 
                type="text" 
                class="tracker-notes-input w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500" 
                placeholder="Log notes (e.g. Call with recruiter, prep for system design...)" 
                value="${{escapeHtml(app.notes || '')}}" 
                data-id="${{app.job_id}}" 
              />
            </td>
            <td class="py-3 px-4 text-center">
              <div class="flex items-center justify-center gap-2">
                <a 
                  href="${{app.apply_link}}" 
                  target="_blank" 
                  class="p-1 rounded bg-slate-800 hover:bg-slate-700 text-blue-400 hover:text-blue-300 transition" 
                  title="Open Job on LinkedIn"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                  </svg>
                </a>
                <button 
                  class="remove-applied-btn p-1 rounded bg-slate-800 hover:bg-rose-900/40 text-slate-400 hover:text-rose-400 transition" 
                  data-id="${{app.job_id}}" 
                  title="Remove from Applied Tracker"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                  </svg>
                </button>
              </div>
            </td>
          </tr>
        `;
      }}).join('');
    }}

    function escapeHtml(str) {{
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }}

    // ================= EVENT LISTENERS =================

    // View Navigation
    viewExplorerBtn.addEventListener('click', () => {{
      viewExplorerBtn.classList.add('active');
      viewTrackerBtn.classList.remove('active');
      viewExplorer.classList.remove('hidden');
      viewTracker.classList.add('hidden');
    }});

    viewTrackerBtn.addEventListener('click', () => {{
      viewTrackerBtn.classList.add('active');
      viewExplorerBtn.classList.remove('active');
      viewTracker.classList.remove('hidden');
      viewExplorer.classList.add('hidden');
      renderTrackerTable();
    }});

    emptyStateExploreBtn.addEventListener('click', () => {{
      viewExplorerBtn.click();
    }});

    // LinkedIn Live Search Trigger
    runSearchBtn.addEventListener('click', async () => {{
      const days = searchDaysSelect.value;
      runSearchBtn.disabled = true;
      searchBtnIcon.textContent = '⏳';
      searchBtnText.textContent = 'Searching...';

      searchBanner.classList.remove('hidden');
      searchBannerSpinner.classList.remove('hidden');
      searchBannerText.textContent = `Searching LinkedIn for jobs posted in the last ${{days}} days... Checking US, UK, Germany, Canada, Remote & India without duplicates.`;

      try {{
        const res = await fetch(`/api/search?days=${{days}}`);
        if (!res.ok) throw new Error('Search server busy or unavailable');

        // Poll search status every 3 seconds
        const pollInterval = setInterval(async () => {{
          try {{
            const stRes = await fetch('/api/status');
            const st = await stRes.json();
            if (st.progress) {{
              searchBannerText.textContent = st.progress.message;
            }}
            if (!st.is_searching) {{
              clearInterval(pollInterval);
              runSearchBtn.disabled = false;
              searchBtnIcon.textContent = '🔍';
              searchBtnText.textContent = 'Fetch New Jobs';
              searchBannerSpinner.classList.add('hidden');

              if (st.progress.new_jobs > 0) {{
                searchBannerText.textContent = `🎉 Completed: Found & added ${{st.progress.new_jobs}} brand new jobs! Reloading dashboard...`;
                setTimeout(() => window.location.reload(), 1500);
              }} else {{
                searchBannerText.textContent = `✓ Checked! ${{st.progress.message}}`;
              }}
            }}
          }} catch (e) {{
            clearInterval(pollInterval);
            runSearchBtn.disabled = false;
            searchBtnIcon.textContent = '🔍';
            searchBtnText.textContent = 'Fetch New Jobs';
          }}
        }}, 3000);

      }} catch (err) {{
        runSearchBtn.disabled = false;
        searchBtnIcon.textContent = '🔍';
        searchBtnText.textContent = 'Fetch New Jobs';
        searchBannerSpinner.classList.add('hidden');
        searchBannerText.textContent = `Notice: To search live, ensure backend server is running (./launch_gui.sh). Error: ${{err.message}}`;
      }}
    }});

    closeSearchBannerBtn.addEventListener('click', () => {{
      searchBanner.classList.add('hidden');
    }});

    // Hide Applied Toggle
    hideAppliedToggle.addEventListener('change', () => {{
      hideApplied = hideAppliedToggle.checked;
      applyFilters();
    }});

    // Table Row Click
    jobsTableBody.addEventListener('click', (e) => {{
      const appliedBtn = e.target.closest('.job-applied-btn');
      if (appliedBtn) {{
        const jid = appliedBtn.getAttribute('data-id');
        const job = allJobs.find(x => x.id === jid);
        if (job) toggleJobApplied(job);
        return;
      }}

      const row = e.target.closest('.job-row');
      if (row) {{
        const jid = row.getAttribute('data-id');
        const job = allJobs.find(x => x.id === jid);
        if (job) selectJob(job);
      }}
    }});

    // Row Checkbox
    jobsTableBody.addEventListener('change', (e) => {{
      if (e.target.classList.contains('job-checkbox')) {{
        const jid = e.target.getAttribute('data-id');
        if (e.target.checked) {{
          shortlistedIds.add(jid);
        }} else {{
          shortlistedIds.delete(jid);
        }}
        saveShortlist();
        if (selectedJob && selectedJob.id === jid) updateShortlistBtnState();
      }}
    }});

    // Select All
    selectAllCheckbox.addEventListener('change', () => {{
      const startIdx = (currentPage - 1) * pageSize;
      const endIdx = Math.min(startIdx + pageSize, filteredJobs.length);
      const pageSlice = filteredJobs.slice(startIdx, endIdx);

      pageSlice.forEach(j => {{
        if (selectAllCheckbox.checked) {{
          shortlistedIds.add(j.id);
        }} else {{
          shortlistedIds.delete(j.id);
        }}
      }});
      saveShortlist();
      renderTable();
      if (selectedJob) updateShortlistBtnState();
    }});

    // Detail Action Buttons
    toggleShortlistBtn.addEventListener('click', () => {{
      if (!selectedJob) return;
      if (shortlistedIds.has(selectedJob.id)) {{
        shortlistedIds.delete(selectedJob.id);
      }} else {{
        shortlistedIds.add(selectedJob.id);
      }}
      saveShortlist();
      updateShortlistBtnState();
      renderTable();
    }});

    detailToggleAppliedBtn.addEventListener('click', () => {{
      if (!selectedJob) return;
      toggleJobApplied(selectedJob);
    }});

    // Filter Tabs
    filterTabs.addEventListener('click', (e) => {{
      const btn = e.target.closest('.filter-tab');
      if (btn) {{
        document.querySelectorAll('.filter-tab').forEach(b => {{
          b.classList.remove('active', 'bg-blue-600', 'text-white');
          b.classList.add('bg-slate-800', 'text-slate-300');
        }});
        btn.classList.add('active', 'bg-blue-600', 'text-white');
        btn.classList.remove('bg-slate-800', 'text-slate-300');

        currentFilter = btn.getAttribute('data-filter');
        applyFilters();
      }}
    }});

    // Search Box
    searchInput.addEventListener('input', () => {{
      currentSearch = searchInput.value;
      clearSearchBtn.classList.toggle('hidden', !currentSearch);
      applyFilters();
    }});

    clearSearchBtn.addEventListener('click', () => {{
      searchInput.value = '';
      currentSearch = '';
      clearSearchBtn.classList.add('hidden');
      applyFilters();
    }});

    sortSelect.addEventListener('change', () => {{
      currentSort = sortSelect.value;
      applyFilters();
    }});

    prevPageBtn.addEventListener('click', () => {{
      if (currentPage > 1) {{
        currentPage--;
        renderTable();
        document.getElementById('jobsTableContainer').scrollTop = 0;
      }}
    }});

    nextPageBtn.addEventListener('click', () => {{
      const totalPages = Math.ceil(filteredJobs.length / pageSize);
      if (currentPage < totalPages) {{
        currentPage++;
        renderTable();
        document.getElementById('jobsTableContainer').scrollTop = 0;
      }}
    }});

    // Export All Filtered Jobs to CSV (with Full Descriptions)
    if (exportFilteredBtn) {{
      exportFilteredBtn.addEventListener('click', () => {{
        if (filteredJobs.length === 0) {{
          alert('No jobs match the current filters.');
          return;
        }}
        const headers = ['Company Name', 'Job Profile', 'Workplace Type', 'Employment Type', 'Location', 'Date Posted', 'Apply Link', 'Match Score', 'Job Description'];
        const rows = filteredJobs.map(j => [
          `"${{(j.company || '').replace(/"/g, '""')}}"`,
          `"${{(j.title || '').replace(/"/g, '""')}}"`,
          `"${{j.workplace_type || ''}}"`,
          `"${{j.employment_type || ''}}"`,
          `"${{(j.location || '').replace(/"/g, '""')}}"`,
          `"${{j.date_posted || ''}}"`,
          `"${{j.apply_link || ''}}"`,
          `"${{j.score || 0}}%"`,
          `"${{(j.description || '').replace(/"/g, '""')}}"`
        ]);
        const csvContent = '\\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\\r\\n');
        const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Filtered_LinkedIn_Jobs_${{new Date().toISOString().slice(0, 10)}}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      }});
    }}

    // Export Shortlist
    exportShortlistBtn.addEventListener('click', () => {{
      let selectedList = [];
      if (shortlistedIds.size > 0) {{
        selectedList = allJobs.filter(j => shortlistedIds.has(j.id));
      }} else {{
        if (confirm(`You have not checked individual boxes. Would you like to export all ${{filteredJobs.length}} filtered jobs currently shown (including full Job Descriptions)?`)) {{
          selectedList = filteredJobs;
        }} else {{
          return;
        }}
      }}
      const headers = ['Company Name', 'Job Profile', 'Workplace Type', 'Employment Type', 'Location', 'Date Posted', 'Apply Link', 'Match Score', 'Job Description'];
      const rows = selectedList.map(j => [
        `"${{(j.company || '').replace(/"/g, '""')}}"`,
        `"${{(j.title || '').replace(/"/g, '""')}}"`,
        `"${{j.workplace_type || ''}}"`,
        `"${{j.employment_type || ''}}"`,
        `"${{(j.location || '').replace(/"/g, '""')}}"`,
        `"${{j.date_posted || ''}}"`,
        `"${{j.apply_link || ''}}"`,
        `"${{j.score || 0}}%"`,
        `"${{(j.description || '').replace(/"/g, '""')}}"`
      ]);
      const csvContent = '\\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\\r\\n');
      const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Selected_LinkedIn_Jobs_${{new Date().toISOString().slice(0, 10)}}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }});

    // Export Applied Jobs Tracker CSV
    exportAppliedCsvBtn.addEventListener('click', () => {{
      const keys = Object.keys(appliedJobs);
      if (keys.length === 0) {{
        alert('No applied jobs tracked yet! Mark roles as applied in the Job Explorer first.');
        return;
      }}
      const headers = ['Company Name', 'Job Profile', 'Workplace Type', 'Employment Type', 'Location', 'Application Status', 'Applied Date', 'Match Score', 'Notes / Response Log', 'Apply Link', 'Job Description'];
      const rows = keys.map(k => {{
        const app = appliedJobs[k];
        const job = allJobs.find(j => j.id === k);
        const desc = app.description || (job ? job.description : '') || '';
        const empType = app.employment_type || (job ? job.employment_type : '') || '';
        const wpType = app.workplace_type || (job ? job.workplace_type : '') || '';
        return [
          `"${{(app.company || (job ? job.company : '') || '').replace(/"/g, '""')}}"`,
          `"${{(app.title || (job ? job.title : '') || '').replace(/"/g, '""')}}"`,
          `"${{wpType}}"`,
          `"${{empType}}"`,
          `"${{(app.location || (job ? job.location : '') || '').replace(/"/g, '""')}}"`,
          `"${{app.status || 'Applied'}}"`,
          `"${{app.applied_date || ''}}"`,
          `"${{app.score || (job ? job.score : 0)}}%"`,
          `"${{(app.notes || '').replace(/"/g, '""')}}"`,
          `"${{app.apply_link || (job ? job.apply_link : '') || ''}}"`,
          `"${{desc.replace(/"/g, '""')}}"`
        ];
      }});
      const csvContent = '\\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\\r\\n');
      const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Applied_Jobs_Tracker_${{new Date().toISOString().slice(0, 10)}}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }});

    // Tracker Status Filters
    trackerStatusTabs.addEventListener('click', (e) => {{
      const btn = e.target.closest('.tracker-filter');
      if (btn) {{
        document.querySelectorAll('.tracker-filter').forEach(b => {{
          b.classList.remove('active', 'bg-blue-600', 'text-white');
          b.classList.add('bg-slate-800', 'text-slate-300');
        }});
        btn.classList.add('active', 'bg-blue-600', 'text-white');
        btn.classList.remove('bg-slate-800', 'text-slate-300');

        currentTrackerStatus = btn.getAttribute('data-status');
        renderTrackerTable();
      }}
    }});

    trackerSearchInput.addEventListener('input', () => {{
      renderTrackerTable();
    }});

    // Tracker Table Inline Edits (Status, Date, Notes, Remove)
    trackerTableBody.addEventListener('change', (e) => {{
      if (e.target.classList.contains('status-select')) {{
        const jid = e.target.getAttribute('data-id');
        if (appliedJobs[jid]) {{
          appliedJobs[jid].status = e.target.value;
          saveAppliedJobs();
        }}
      }} else if (e.target.classList.contains('applied-date-input')) {{
        const jid = e.target.getAttribute('data-id');
        if (appliedJobs[jid]) {{
          appliedJobs[jid].applied_date = e.target.value;
          saveAppliedJobs();
        }}
      }}
    }});

    let notesDebounceTimer;
    trackerTableBody.addEventListener('input', (e) => {{
      if (e.target.classList.contains('tracker-notes-input')) {{
        const jid = e.target.getAttribute('data-id');
        const val = e.target.value;
        clearTimeout(notesDebounceTimer);
        notesDebounceTimer = setTimeout(() => {{
          if (appliedJobs[jid]) {{
            appliedJobs[jid].notes = val;
            saveAppliedJobs();
          }}
        }}, 400);
      }}
    }});

    trackerTableBody.addEventListener('click', (e) => {{
      const removeBtn = e.target.closest('.remove-applied-btn');
      if (removeBtn) {{
        const jid = removeBtn.getAttribute('data-id');
        if (confirm('Remove this job from your Applied Tracker?')) {{
          delete appliedJobs[jid];
          saveAppliedJobs();
          applyFilters();
        }}
      }}
    }});

    // CV Matcher Modal handlers
    openCvModalBtn.addEventListener('click', () => cvModal.classList.remove('hidden'));
    closeCvModalBtn.addEventListener('click', () => cvModal.classList.add('hidden'));
    cancelCvBtn.addEventListener('click', () => cvModal.classList.add('hidden'));

    resetCvBtn.addEventListener('click', () => {{
      cvInputText.value = DEFAULT_CV;
    }});

    reRankBtn.addEventListener('click', () => {{
      const text = cvInputText.value.trim();
      if (!text) {{
        alert('Please enter your CV text.');
        return;
      }}
      localStorage.setItem('user_cv_text', text);

      const lowerCv = text.toLowerCase();
      const cvTokens = new Set(lowerCv.match(/\\b[a-z]{{3,20}}\\b/g) || []);

      allJobs.forEach(j => {{
        const jText = `${{j.title}} ${{j.description}}`.toLowerCase();
        let matches = 0;
        let matched = [];

        if (/agentic|langgraph|llm|generative ai/i.test(j.title)) matches += 25;
        else if (/ai engineer/i.test(j.title)) matches += 20;
        else if (/data scientist/i.test(j.title)) matches += 16;

        cvTokens.forEach(t => {{
          if (t.length > 3 && new RegExp('\\\\b' + t + '\\\\b').test(jText)) {{
            matches += 3.5;
            if (matched.length < 5 && !['with', 'from', 'that', 'this', 'have', 'your', 'about'].includes(t)) {{
              matched.push(t.charAt(0).toUpperCase() + t.slice(1));
            }}
          }}
        }});

        j.score = Math.min(99, Math.max(25, Math.round(matches)));
        if (matched.length > 0) j.matched_skills = matched;
      }});

      cvModal.classList.add('hidden');
      currentSort = 'score_desc';
      sortSelect.value = 'score_desc';
      applyFilters();
      if (selectedJob) selectJob(allJobs.find(x => x.id === selectedJob.id) || allJobs[0]);
    }});

    // Initial render
    updateShortlistCounters();
    updateAppliedCounters();
    applyFilters();
    renderTrackerTable();
  </script>
</body>
</html>
"""

    with open(output_html_workspace, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(output_html_index, "w", encoding="utf-8") as f:
        f.write(html_content)
    if artifact_dir and os.path.exists(artifact_dir):
        try:
            with open(output_html_artifact, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Generated standalone HTML dashboard at:\n - {output_html_workspace}\n - {output_html_artifact}")
        except Exception:
            print(f"Generated standalone HTML dashboard at:\n - {output_html_workspace}")
    else:
        print(f"Generated standalone HTML dashboard at:\n - {output_html_workspace}")

if __name__ == "__main__":
    build_gui()
