#!/usr/bin/env python3
"""
OGC 2026 leaderboard snapshotter.

Runs once per invocation (GitHub Actions calls it hourly). It:
  1. Fetches the leaderboard API
  2. Parses it into a list of {rank, team, score}
  3. Appends a timestamped snapshot to history.json
  4. Writes the raw API response to latest_raw.json (for debugging / tuning the parser)

Only the standard library is used, so no `pip install` step is needed.
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 1) CONFIGURE THIS  --  put the real leaderboard API endpoint here.
#
# How to find it:
#   - Open https://optichallenge.com/leaderboard in Chrome
#   - Press F12 -> "Network" tab -> tick "Fetch/XHR" -> refresh the page
#   - Find the request that returns JSON containing team names + ranks/scores
#   - Right-click it -> Copy -> Copy link address, and paste it below.
#     (Also right-click -> Copy -> Copy response, so you can check the shape.)
# ---------------------------------------------------------------------------
API_URL = "https://d32m8h9cownzsg.cloudfront.net/public/leaderboard_group/latest.json?_=1782900656531"  # <-- REPLACE with the real endpoint

# Some APIs need a specific header (e.g. Accept: application/json) or reject
# requests without a browser-like User-Agent. Adjust if you get 403 / HTML back.
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ogc-rank-tracker/1.0 (+https://github.com/)",
}

HISTORY_FILE = Path("history.json")
RAW_FILE = Path("latest_raw.json")
TIMEOUT_SECONDS = 30


def fetch_raw(url: str):
    """GET the URL and return decoded JSON (or raise)."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


# ---------------------------------------------------------------------------
# 2) PARSING  --  turn whatever the API returns into a clean standings list.
#
# This tries several common shapes so it likely "just works". If your API is
# unusual, tune the field-name lists below (check latest_raw.json to see them).
# ---------------------------------------------------------------------------
LIST_KEYS = ["leaderboard", "standings", "rankings", "results",
             "data", "teams", "rows", "items", "entries"]
RANK_KEYS = ["rank", "position", "place", "ranking", "rankNo", "no"]
TEAM_KEYS = ["team", "teamName", "team_name", "name", "nickname",
             "displayName", "user", "username", "handle"]
SCORE_KEYS = ["score", "points", "objective", "value", "best",
              "bestScore", "best_score", "totalScore", "metric"]


def _first(d: dict, keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def parse_standings(data):
    """Return [{'rank': int, 'team': str, 'score': float|None}, ...]."""
    # Unwrap {"leaderboard": [...]} style envelopes.
    rows = data
    if isinstance(data, dict):
        for key in LIST_KEYS:
            if isinstance(data.get(key), list):
                rows = data[key]
                break
        else:
            # Sometimes it's nested one level deeper, e.g. {"data": {"standings": [...]}}
            for key in LIST_KEYS:
                inner = data.get(key)
                if isinstance(inner, dict):
                    for k2 in LIST_KEYS:
                        if isinstance(inner.get(k2), list):
                            rows = inner[k2]
                            break

    if not isinstance(rows, list):
        raise ValueError(
            "Could not find a list of teams in the response. "
            "Open latest_raw.json and adjust LIST_KEYS / the parser."
        )

    standings = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        team = _first(row, TEAM_KEYS)
        if team is None:
            continue
        rank = _first(row, RANK_KEYS)
        try:
            rank = int(rank)
        except (TypeError, ValueError):
            rank = i + 1  # fall back to list order
        score = _first(row, SCORE_KEYS)
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = None
        standings.append({"rank": rank, "team": str(team).strip(), "score": score})

    if not standings:
        raise ValueError(
            "Found a list but no team names in it. "
            "Check TEAM_KEYS against the fields in latest_raw.json."
        )

    standings.sort(key=lambda r: r["rank"])
    return standings


def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("history.json was corrupt; starting a fresh one.", file=sys.stderr)
    return {"competition": "OGC 2026", "source": API_URL, "snapshots": []}


def main():
    try:
        raw = fetch_raw(API_URL)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} from {API_URL}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Failed to fetch {API_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    # Always dump the raw response so you can inspect / tune the parser.
    RAW_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        standings = parse_standings(raw)
    except ValueError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    history = load_history()
    history["source"] = API_URL
    history["snapshots"].append({"t": now, "standings": standings})

    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Recorded {len(standings)} teams at {now} "
          f"(total snapshots: {len(history['snapshots'])}).")


if __name__ == "__main__":
    main()
