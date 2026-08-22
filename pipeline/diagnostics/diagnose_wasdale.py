"""
diagnose_wasdale.py

Standalone script to see exactly what the Wasdale scraper is actually
extracting from the live page, and why. The fix in the last round should
have changed the incident count from 32, and it didn't — rather than
guess a fourth time, this prints the real intermediate data so we can
see precisely where it's going wrong.

Run from pipeline/: python diagnostics/diagnose_wasdale.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))

from scrape_wasdale import _get, _extract_page_text, _extract_entries, ENTRY_HEADER_RE

print("Fetching live page...")
resp = _get("https://www.wmrt.org.uk/report-page/")
print(f"Response status: {resp.status_code}, content length: {len(resp.text)} chars")

page_text = _extract_page_text(resp.text)
print(f"\nExtracted plain text length: {len(page_text)} chars")
print(f"\n--- First 2000 chars of extracted text ---")
print(page_text[:2000])
print("--- end excerpt ---\n")

# Count how many lines actually match the header regex, vs how many
# LOOK like they should (start with a digit and a period) but don't.
lines = [l.strip() for l in page_text.split("\n") if l.strip()]
digit_dot_lines = [l for l in lines if l[:1].isdigit() and ". " in l[:6]]
matched_lines = [l for l in lines if ENTRY_HEADER_RE.match(l)]

print(f"Total non-empty lines: {len(lines)}")
print(f"Lines starting with 'N. ' pattern: {len(digit_dot_lines)}")
print(f"Lines matching the full header regex: {len(matched_lines)}")

if len(digit_dot_lines) > len(matched_lines):
    print(f"\n{len(digit_dot_lines) - len(matched_lines)} lines look like incident headers "
          f"but didn't match the regex — printing the first 5 of these to see why:")
    non_matching = [l for l in digit_dot_lines if not ENTRY_HEADER_RE.match(l)]
    for l in non_matching[:5]:
        print(f"  MISS: {l!r}")

entries = _extract_entries(page_text)
print(f"\nFinal entry count: {len(entries)}")
if entries:
    print(f"First entry: {entries[0]}")
    print(f"Last entry: {entries[-1]}")