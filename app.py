from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

# Primary URL fallback pattern requested: /a/team/{group-name}
TEAM_PATH_PATTERN = re.compile(r"/a/team/([A-Za-z0-9._-]+)")


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
    match = TEAM_PATH_PATTERN.search(raw_url)
    if match:
        return match.group(1)
    return None


@app.route("/", methods=["GET", "POST"])
def index():
    ant_group = None
    error = None
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
                error = f"Failed to fetch page: {exc}"
            else:
                ant_group = extract_group_from_text(html)
                if not ant_group:
                    ant_group = extract_group_from_url(submitted_url)

                if not ant_group:
                    error = "ANT group not found in page content or URL path."

    return render_template(
        "index.html",
        ant_group=ant_group,
        error=error,
        submitted_url=submitted_url,
    )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=True)
