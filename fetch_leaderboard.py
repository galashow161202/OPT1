#!/usr/bin/env python3
"""
OGC 2026 leaderboard snapshotter.

Runs once per invocation (GitHub Actions calls it hourly). It:
  1. Fetches the leaderboard JSON from the CDN
  2. Parses it into a list of {rank, team}  (this leaderboard has no public score;
     `group_rank` buckets teams into bands of ~10, so we track the band over time)
  3. Appends a timestamped snapshot to history.json (keyed on the source's own
     `generated_at`, so re-runs never create duplicate hourly entries)
  4. Refreshes a small static `teams` map (nationality / affiliation) for display
  5. Writes the raw response to latest_raw.json for debugging

Only the standard library is used, so no `pip install` step is needed.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 1) API endpoint.
#
# This is the leaderboard's data file on CloudFront. The `?_=` cache-buster is
# added automatically below. If you ever get stale data or a 403, re-copy the
# URL from DevTools (Network tab -> right-click the request -> Copy -> Copy URL).
#
#   >>> CONFIRM THIS EXACT URL <<<  (the middle of the path was hidden by the
#   context menu in your screenshot). Paste the real one here if it differs.
# ---------------------------------------------------------------------------
API_URL = "https://d32m8h9cownzsg.cloudfront.net/public/leaderboard_group/latest.json?_=1782902059573"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ogc-rank-tracker/1.0 (+https://github.com/)",
}

HISTORY_FILE = Path("history.json")
RAW_FILE = Path("latest_raw.json")
TIMEOUT_SECONDS = 30


def fetch_raw(url: str):
    bust = f"_={int(time.time() * 1000)}"
    full = url + ("&" if "?" in url else "?") + bust
    req = urllib.request.Request(full, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def parse_timestamp(data) -> str:
    """Prefer the source's own generated_at; fall back to fetch time. -> ISO 'Z'."""
    g = data.get("generated_at") if isinstance(data, dict) else None
    if isinstance(g, str):
        for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(g.strip(), fmt).replace(tzinfo=timezone.utc)
                return dt.isoformat().replace("+00:00", "Z")
            except ValueError:
                continue
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse(data):
    """Return (standings, teams_meta).

    standings: [{'rank': int, 'team': str}, ...] sorted by rank
    teams_meta: {team_name: {'nat': [...], 'aff': [...]}}
    """
    rows = data.get("leaderboard") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("No 'leaderboard' list in the response — check latest_raw.json.")

    standings, meta = [], {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        team = row.get("team_name") or row.get("team") or row.get("name")
        if not team:
            continue
        team = str(team).strip()
        # group_rank is the real (banded) rank on this leaderboard.
        rank = row.get("group_rank", row.get("rank"))
        try:
            rank = int(rank)
        except (TypeError, ValueError):
            rank = i + 1
        standings.append({"rank": rank, "team": team})
        meta[team] = {
            "nat": row.get("nationality", []),
            "aff": row.get("affiliation", []),
        }

    if not standings:
        raise ValueError("Leaderboard list had no team_name fields — check latest_raw.json.")

    standings.sort(key=lambda r: r["rank"])
    return standings, meta


def load_history():
    if HISTORY_FILE.exists():
        try:
            h = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            h.setdefault("snapshots", [])
            h.setdefault("teams", {})
            return h
        except json.JSONDecodeError:
            print("history.json was corrupt; starting fresh.", file=sys.stderr)
    return {"competition": "OGC 2026", "source": API_URL, "snapshots": [], "teams": {}}


def main():
    try:
        raw = fetch_raw(API_URL)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} from {API_URL}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Failed to fetch {API_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    RAW_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        standings, meta = parse(raw)
    except ValueError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    t = parse_timestamp(raw)
    history = load_history()
    history["source"] = API_URL
    history["teams"] = meta  # static-ish; overwrite each run

    # Skip if we already recorded this exact generated_at (avoids duplicate hours).
    if history["snapshots"] and history["snapshots"][-1].get("t") == t:
        print(f"Snapshot for {t} already recorded; nothing to do.")
        # still rewrite (teams meta / source may have changed) but without a new snapshot
    else:
        history["snapshots"].append({"t": t, "standings": standings})

    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"{t}: {len(standings)} teams, {len(history['snapshots'])} snapshots total.")


if __name__ == "__main__":
    main()
