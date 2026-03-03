from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from jinja2 import TemplateNotFound

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

# Primary URL fallback pattern requested: /a/team/{group-name}
TEAM_PATH_PATTERN = re.compile(r"/a/team/([^/?#]+)")

FALLBACK_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ANT Group Extractor</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f3f5f7; margin:0; padding:20px; }
    .card { max-width: 720px; margin: 40px auto; background:#fff; padding:20px; border:1px solid #ddd; border-radius:10px; }
    input { width:70%; padding:10px; border:1px solid #ccc; border-radius:8px; }
    button { padding:10px 14px; border:0; border-radius:8px; background:#0f766e; color:#fff; cursor:pointer; }
    .error { margin-top:12px; color:#b91c1c; }
    .result { margin-top:12px; padding:10px; border:1px solid #ddd; border-radius:8px; background:#f9fafb; }
    code { font-family: monospace; }
  </style>
</head>
<body>
  <div class="card">
    <h2>ANT Group Extractor</h2>
    <form method="POST" action="/">
      <input type="url" name="url" required placeholder="https://permissions.amazon.com/a/team/example-group" value="{{ submitted_url }}">
      <button type="submit">Submit</button>
    </form>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if ant_group %}
      <div class="result">
        <strong>Extracted ANT Group:</strong> <code id="antGroupValue">{{ ant_group }}</code>
        <button type="button" id="copyBtn">Copy</button>
        <div id="copyStatus"></div>
      </div>
    {% endif %}
  </div>
  <script>
    (function () {
      const btn = document.getElementById("copyBtn");
      const valueEl = document.getElementById("antGroupValue");
      const statusEl = document.getElementById("copyStatus");
      if (!btn || !valueEl) return;
      btn.addEventListener("click", async function () {
        try {
          await navigator.clipboard.writeText(valueEl.textContent.trim());
          if (statusEl) statusEl.textContent = "Copied.";
        } catch (e) {
          if (statusEl) statusEl.textContent = "Copy failed.";
        }
      });
    })();
  </script>
</body>
</html>
"""


def is_valid_url(raw_url: str) -> bool:
    try:
        parsed = urlparse(raw_url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def extract_group_from_text(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    # Parse full text content first (preferred), then fallback to raw HTML string.
    text = soup.get_text(" ", strip=True)
    match = TEAM_PATH_PATTERN.search(text)
    if match:
        return match.group(1)

    match = TEAM_PATH_PATTERN.search(html)
    if match:
        return match.group(1)

    return None


def extract_group_from_url(raw_url: str) -> str | None:
    parsed = urlparse(raw_url)
    match = TEAM_PATH_PATTERN.search(parsed.path or "")
    if not match:
        match = TEAM_PATH_PATTERN.search(raw_url)
    if match:
        value = match.group(1)
        # Handle encoded and double-encoded values from redirect URLs.
        for _ in range(2):
            decoded = unquote(value)
            if decoded == value:
                break
            value = decoded
        return value.strip()
    return None


@app.route("/", methods=["GET", "POST"])
def index():
    ant_group = None
    error = None
    note = None
    submitted_url = ""

    if request.method == "POST":
        submitted_url = (request.form.get("url") or "").strip()

        if not submitted_url or not is_valid_url(submitted_url):
            error = "Please enter a valid URL (including http:// or https://)."
        else:
            try:
                response = requests.get(submitted_url, timeout=15)
                response.raise_for_status()
                html = response.text
            except requests.RequestException as exc:
                ant_group = extract_group_from_url(submitted_url)
                if ant_group:
                    note = "Fetched page requires authentication, so value was extracted from URL."
                else:
                    error = f"Failed to fetch page: {exc}"
            else:
                ant_group = extract_group_from_text(html)
                if not ant_group:
                    ant_group = extract_group_from_url(submitted_url)

                if not ant_group:
                    error = "ANT group not found in page content or URL path."

    try:
        return render_template(
            "index.html",
            ant_group=ant_group,
            error=error,
            note=note,
            submitted_url=submitted_url,
        )
    except TemplateNotFound:
        # Vercel fallback when template files are not bundled.
        return app.jinja_env.from_string(FALLBACK_TEMPLATE).render(
            ant_group=ant_group,
            error=error,
            note=note,
            submitted_url=submitted_url,
        )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=True)
