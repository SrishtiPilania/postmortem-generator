import os
import json
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "postmortems_with_raw_input.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "frontend", "demo_cache.json")

# Pick the companies you plan to demo live tomorrow
DEMO_COMPANIES = ["Cloudflare", "Google", "Amazon"]

POSTMORTEM_PROMPT = """
You are an expert Site Reliability Engineer writing an incident postmortem.

Given the following raw incident signals (timeline, logs, alerts, notes), generate a structured postmortem.

Respond ONLY with valid JSON in this exact format, no markdown, no extra text:

{{
  "summary": "1-2 sentence overview of what happened",
  "root_cause": "clear explanation of the underlying cause",
  "timeline": ["event 1", "event 2", "event 3"],
  "impact": "who/what was affected and how badly",
  "action_items": ["action 1", "action 2", "action 3"]
}}

Raw incident input:
{raw_input}
"""

JUDGE_PROMPT = """
You are evaluating an AI-generated incident postmortem against the REAL published postmortem for the same incident.

REAL PUBLISHED POSTMORTEM (ground truth):
{real_description}

AI-GENERATED POSTMORTEM:
Summary: {gen_summary}
Root Cause: {gen_root_cause}
Impact: {gen_impact}

Score the AI-generated postmortem from 1-5 on how well it captures the same core facts and root cause as the real one:
1 = completely wrong or unrelated
3 = partially correct, missing key details
5 = accurately captures the real root cause and impact

Respond ONLY with valid JSON, no markdown:
{{
  "score": <integer 1-5>,
  "reason": "one sentence explaining the score"
}}
"""


def call_gemini_with_retry(prompt, max_retries=3):
    last_error = None
    for model_name in MODEL_CANDIDATES:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.strip("`")
                    if text.startswith("json"):
                        text = text[4:].strip()
                return text
            except Exception as e:
                last_error = e
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
                    time.sleep(4)
                    continue
                else:
                    break
    print(f"Failed: {last_error}")
    return None


def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        all_incidents = json.load(f)

    cache = {}

    for company in DEMO_COMPANIES:
        match = next((inc for inc in all_incidents if inc["company"] == company), None)
        if not match:
            print(f"Could not find {company} in dataset, skipping.")
            continue

        print(f"Generating for {company}...")
        gen_text = call_gemini_with_retry(POSTMORTEM_PROMPT.format(raw_input=match["raw_input"]))
        if not gen_text:
            print(f"  Generation failed for {company}")
            continue

        try:
            generated = json.loads(gen_text)
        except json.JSONDecodeError:
            print(f"  Invalid JSON for {company}")
            continue

        time.sleep(1)

        judge_text = call_gemini_with_retry(JUDGE_PROMPT.format(
            real_description=match["description"],
            gen_summary=generated.get("summary", ""),
            gen_root_cause=generated.get("root_cause", ""),
            gen_impact=generated.get("impact", "")
        ))
        judgment = {}
        if judge_text:
            try:
                judgment = json.loads(judge_text)
            except json.JSONDecodeError:
                pass

        cache[company] = {
            "raw_input": match["raw_input"],
            "description": match["description"],
            "link": match["link"],
            "category": match["category"],
            "generated": generated,
            "score": judgment.get("score"),
            "reason": judgment.get("reason", "")
        }
        print(f"  Done — score {judgment.get('score')}")
        time.sleep(2)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    print(f"\nSaved demo cache to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()