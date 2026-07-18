import os
import json
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

# Load API key from .env
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
CORS(app)  # allows React frontend to call this backend

# Try the primary model first, fall back to the lighter one if overloaded
MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]

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

def call_gemini_with_retry(prompt, max_retries=2):
    last_error = None
    for model_name in MODEL_CANDIDATES:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                return response
            except Exception as e:
                last_error = e
                error_str = str(e)
                # Only retry on overload/unavailable errors, not on real bugs
                if "503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str:
                    time.sleep(3)  # brief pause before retry
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
        response = call_gemini_with_retry(prompt)
        text = response.text.strip()

        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()

        postmortem = json.loads(text)
        return jsonify(postmortem)

    except json.JSONDecodeError:
        return jsonify({"error": "Model did not return valid JSON", "raw_response": text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)