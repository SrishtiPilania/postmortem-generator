import os
import json
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
CORS(app)

MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "postmortems_with_raw_input.json")

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
                    time.sleep(3)
                    continue
                else:
                    raise e
    raise last_error


@app.route("/api/generate-postmortem", methods=["POST"])
def generate_postmortem():
    data = request.get_json()
    raw_input = data.get("raw_input", "")

    if not raw_input.strip():
        return jsonify({"error": "raw_input is required"}), 400

    prompt = POSTMORTEM_PROMPT.format(raw_input=raw_input)

    try:
        text = call_gemini_with_retry(prompt)
        postmortem = json.loads(text)
        return jsonify(postmortem)
    except json.JSONDecodeError:
        return jsonify({"error": "Model did not return valid JSON"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/score", methods=["POST"])
def score_postmortem():
    data = request.get_json()
    real_description = data.get("real_description", "")
    generated = data.get("generated", {})

    if not real_description or not generated:
        return jsonify({"error": "real_description and generated are required"}), 400

    prompt = JUDGE_PROMPT.format(
        real_description=real_description,
        gen_summary=generated.get("summary", ""),
        gen_root_cause=generated.get("root_cause", ""),
        gen_impact=generated.get("impact", "")
    )

    try:
        text = call_gemini_with_retry(prompt)
        judgment = json.loads(text)
        return jsonify(judgment)
    except json.JSONDecodeError:
        return jsonify({"error": "Model did not return valid JSON"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incidents", methods=["GET"])
def get_incidents():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)