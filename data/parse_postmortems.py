"""
parse_postmortems.py

What this does:
1. Downloads the raw README.md from danluu/post-mortems on GitHub
   (this file contains 200+ real incident postmortem entries)
2. Parses it into structured entries: category, company, description, link
3. Saves everything as a clean JSON file in data/postmortems.json
"""

import re
import json
import urllib.request

SOURCE_URL = "https://raw.githubusercontent.com/danluu/post-mortems/master/README.md"
OUTPUT_FILE = "postmortems.json"


def download_readme(url: str) -> str:
    print(f"Downloading dataset from {url} ...")
    with urllib.request.urlopen(url) as response:
        text = response.read().decode("utf-8")
    print(f"Downloaded {len(text)} characters.")
    return text


def parse_postmortems(markdown_text: str):
    entries = []
    current_category = "Uncategorized"
    entry_pattern = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)\.\s*(.*)$")

    for line in markdown_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading.lower() in (
                "table of contents", "other lists of postmortems",
                "analysis", "contributors",
            ):
                current_category = None
            else:
                current_category = heading
            continue
        if current_category is None:
            continue
        match = entry_pattern.match(line)
        if match:
            company, link, description = match.groups()
            entries.append({
                "category": current_category,
                "company": company.strip(),
                "link": link.strip(),
                "description": description.strip(),
            })
    print(f"Parsed {len(entries)} postmortem entries.")
    return entries


def main():
    raw_text = download_readme(SOURCE_URL)
    entries = parse_postmortems(raw_text)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(entries)} entries to {OUTPUT_FILE}")
    print("\n--- Example entries ---")
    for e in entries[:3]:
        print(f"[{e['category']}] {e['company']}: {e['description'][:80]}...")


if __name__ == "__main__":
    main()