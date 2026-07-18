import os
import json
import time
import sys

from google import genai

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]

INPUT_FILE = os.path.join(os.path.dirname(__file__), "postmortems.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "postmortems_with_raw_input.json")

RAW_INPUT_PROMPT = """
You are simulating what an on-call engineer might have jotted down DURING an incident, before any polished postmortem was written.

Below is a real, published postmortem summary describing what ultimately happened and why.

Your job: reverse-engineer a plausible RAW INCIDENT LOG that could have existed before this analysis — rough timestamps, alert-style notes, and observed symptoms (NOT the root cause conclusion, since that wasn't known yet during the incident).

Rules:
- Do NOT reveal the root cause explicitly — only what would have been OBSERVABLE in real time (symptoms, alerts, error rates, escalations).
- Use a realistic timeline format like "14:02 UTC - ...", "14:05 - ...".
- Keep it concise: 4-8 timeline entries.
- Output ONLY the raw log text, no labels, no markdown, no extra commentary.

Real postmortem summary:
{description}
"""

def call_gemini_with_retry(prompt, max_retries=2):
    last_error = None
    for model_name in MODEL_CANDIDATES:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str:
                    time.sleep(5)
                    continue
                else:
                    print(f"  Non-retryable error: {error_str[:150]}")
                    break
    print(f"  Failed after retries: {last_error}")
    return None


def main(limit=None):
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        postmortems = json.load(f)

    if limit:
        postmortems = postmortems[:limit]

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
        done_companies = {(r["company"], r["link"]) for r in results}
        print(f"Resuming — {len(results)} entries already processed.")
    else:
        results = []
        done_companies = set()

    total = len(postmortems)

    for i, entry in enumerate(postmortems):
        key = (entry["company"], entry["link"])
        if key in done_companies:
            continue

        print(f"[{i+1}/{total}] {entry['company']} — {entry['category']}")

        prompt = RAW_INPUT_PROMPT.format(description=entry["description"])
        raw_input = call_gemini_with_retry(prompt)

        if raw_input:
            new_entry = dict(entry)
            new_entry["raw_input"] = raw_input
            results.append(new_entry)
        else:
            print(f"  Skipping {entry['company']} due to repeated failure.")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        time.sleep(2)

    print(f"\nDone. {len(results)}/{total} entries processed.")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    # test mode: pass a number as arg to limit how many entries to process
    # e.g. python generate_raw_inputs.py 5
    test_limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=test_limit)