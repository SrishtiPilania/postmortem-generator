import os
import json
import time
import sys

from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "postmortems_with_raw_input.json")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "evaluation_results.json")

# Same generation prompt as your live backend, for consistency
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


def call_gemini_with_retry(prompt, max_retries=2):
    last_error = None
    for model_name in MODEL_CANDIDATES:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.strip("`")
                    if text.startswith("json"):
                        text = text[4:].strip()
                return text
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


def main(sample_size=30):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        all_entries = json.load(f)

    entries = all_entries[:sample_size]
    total = len(entries)

    results = []
    scores = []

    for i, entry in enumerate(entries):
        print(f"[{i+1}/{total}] {entry['company']} — {entry['category']}")

        # Step 1: Generate postmortem from raw_input
        gen_prompt = POSTMORTEM_PROMPT.format(raw_input=entry["raw_input"])
        gen_text = call_gemini_with_retry(gen_prompt)

        if not gen_text:
            print("  Skipping — generation failed")
            continue

        try:
            generated = json.loads(gen_text)
        except json.JSONDecodeError:
            print("  Skipping — generated postmortem was not valid JSON")
            continue

        time.sleep(1)

        # Step 2: Judge the generated postmortem against real ground truth
        judge_prompt = JUDGE_PROMPT.format(
            real_description=entry["description"],
            gen_summary=generated.get("summary", ""),
            gen_root_cause=generated.get("root_cause", ""),
            gen_impact=generated.get("impact", "")
        )
        judge_text = call_gemini_with_retry(judge_prompt)

        if not judge_text:
            print("  Skipping — judging failed")
            continue

        try:
            judgment = json.loads(judge_text)
        except json.JSONDecodeError:
            print("  Skipping — judge response was not valid JSON")
            continue

        score = judgment.get("score")
        reason = judgment.get("reason", "")
        print(f"  Score: {score}/5 — {reason}")

        results.append({
            "company": entry["company"],
            "category": entry["category"],
            "link": entry["link"],
            "real_description": entry["description"],
            "raw_input": entry["raw_input"],
            "generated_postmortem": generated,
            "score": score,
            "judge_reason": reason
        })

        if score is not None:
            scores.append(score)

        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        time.sleep(2)

    if scores:
        avg_score = sum(scores) / len(scores)
        print(f"\n{'='*50}")
        print(f"Evaluated {len(scores)}/{total} entries")
        print(f"Average score: {avg_score:.2f} / 5")
        print(f"{'='*50}")
        print(f"Full results saved to {RESULTS_FILE}")
    else:
        print("\nNo entries were successfully scored.")


if __name__ == "__main__":
    # optional arg to change sample size, e.g. python evaluate.py 50
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    main(sample_size=n)