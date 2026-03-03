from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request
from jinja2 import TemplateNotFound

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
ROOT_INDEX = Path(BASE_DIR) / "index.html"

# Matches team names in paths like /a/team/<group-name>
TEAM_PATH_PATTERN = re.compile(r"/a/team/([^/?#]+)")


def is_valid_url(raw_url: str) -> bool:
    try:
        parsed = urlparse(raw_url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def decode_value(value: str) -> str:
    # Decode one or two times for encoded redirect values.
    for _ in range(2):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    return value.strip()


def extract_group_from_text(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text(" ", strip=True)
    match = TEAM_PATH_PATTERN.search(text)
    if match:
        return decode_value(match.group(1))

    match = TEAM_PATH_PATTERN.search(html)
    if match:
        return decode_value(match.group(1))

    return None


def extract_group_from_url(raw_url: str) -> str | None:
    parsed = urlparse(raw_url)

    # Preferred: direct URL path
    match = TEAM_PATH_PATTERN.search(parsed.path or "")
    if match:
        return decode_value(match.group(1))

    # Fallback: search full URL (covers redirect_uri/state encoded content)
    match = TEAM_PATH_PATTERN.search(raw_url)
    if match:
        return decode_value(match.group(1))

    return None


def extract_ant_group(raw_url: str) -> tuple[str | None, str | None, str | None]:
    """
    Returns: (ant_group, note, error)
    """
    if not raw_url or not is_valid_url(raw_url):
        return None, None, "Please enter a valid URL (including http:// or https://)."

    try:
        response = requests.get(raw_url, timeout=15)
        response.raise_for_status()
        html = response.text
    except requests.RequestException as exc:
        ant_group = extract_group_from_url(raw_url)
        if ant_group:
            return (
                ant_group,
                "Fetched page requires authentication, so value was extracted from URL.",
                None,
            )
        return None, None, f"Failed to fetch page: {exc}"

    ant_group = extract_group_from_text(html)
    if ant_group:
        return ant_group, None, None

    ant_group = extract_group_from_url(raw_url)
    if ant_group:
        return ant_group, "ANT group was extracted from URL path.", None

    return None, None, "ANT group not found in page content or URL path."


@app.route("/", methods=["GET"])
def index():
    try:
        return render_template("index.html")
    except TemplateNotFound:
        if ROOT_INDEX.exists():
            return ROOT_INDEX.read_text(encoding="utf-8")
        return "Template missing: upload templates/index.html (or index.html)", 500


@app.route("/api/extract-ant", methods=["POST"])
def api_extract_ant():
    payload = request.get_json(silent=True) or {}
    raw_url = str(payload.get("url", "")).strip()

    ant_group, note, error = extract_ant_group(raw_url)
    if error:
        return jsonify({"ok": False, "error": error}), 400

    return jsonify({"ok": True, "ant_group": ant_group, "note": note})


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=True)
