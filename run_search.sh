#!/usr/bin/env bash
# Global LinkedIn Job Search Launcher
# Usage:
#   ./run_search.sh [DAYS] [LIMIT] [QUERY] [LOCATIONS]
# Examples:
#   ./run_search.sh 30 600
#   ./run_search.sh 1 100
#   ./run_search.sh 30 500 "Senior AI Engineer" "United States, United Kingdom, Remote"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
DAYS=${1:-30}
LIMIT=${2:-600}
QUERY=${3:-"Senior AI Engineer, Senior Generative AI Engineer, Senior Data Scientist, Senior Agentic AI Engineer"}
LOCATIONS=${4:-"United States, United Kingdom, Germany, Canada, Remote, India"}

echo "=================================================="
echo " Starting Global LinkedIn Job Search"
echo " Days:          ${DAYS} ($(( DAYS * 24 )) hours)"
echo " Limit:         ${LIMIT} jobs"
echo " Query:         ${QUERY}"
echo " Locations:     ${LOCATIONS}"
echo " Output Folder: ${DIR}/Jobs"
echo "=================================================="

python3 "${DIR}/linkedin_job_search.py" \
  --days "${DAYS}" \
  --limit "${LIMIT}" \
  --query "${QUERY}" \
  --locations "${LOCATIONS}" \
  --output-dir "${DIR}/Jobs"
