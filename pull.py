"""
Pulls your Garmin training history into data/*.json.
Re-running only fetches what's new since the last run.

Usage:
  python3 pull.py            # fetch last 12 months (first run) / new data since last run
  python3 pull.py --full     # fetch full history (first run only; re-runs are always incremental)
"""
import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

from garmin_client import api_get

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PAUSE = 0.3  # seconds between calls, be polite to the API


def load_json(name, default):
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def fmt(d):
    return d.strftime("%Y-%m-%d")


# ---------------------------------------------------------------- activities

def pull_activities():
    print("Activities:")
    existing = load_json("activities.json", [])
    known_ids = {a["activityId"] for a in existing if "activityId" in a}
    by_id = {a["activityId"]: a for a in existing if "activityId" in a}

    start = 0
    limit = 20
    new_count = 0
    stop = False
    while not stop:
        page = api_get(
            "/activitylist-service/activities/search/activities",
            {"start": start, "limit": limit},
        ) or []
        if not page:
            break

        page_had_new = False
        for act in page:
            aid = act.get("activityId")
            if aid is None:
                continue
            if aid not in known_ids:
                by_id[aid] = act
                known_ids.add(aid)
                new_count += 1
                page_had_new = True

        sys.stdout.write(f"\r  fetched {start + len(page)} activities, {new_count} new so far...")
        sys.stdout.flush()

        # Once we hit a page that's entirely already-known AND we already had
        # data before this run, we've caught up to last time - stop early.
        if existing and not page_had_new:
            stop = True
        elif len(page) < limit:
            stop = True
        else:
            start += limit
            time.sleep(PAUSE)

    print()
    all_activities = sorted(by_id.values(), key=lambda a: a.get("startTimeLocal", ""), reverse=True)
    save_json("activities.json", all_activities)

    earliest = None
    if all_activities:
        earliest = min(a.get("startTimeLocal", "")[:10] for a in all_activities if a.get("startTimeLocal"))
    print(f"  total activities: {len(all_activities)} ({new_count} new)")
    return all_activities, earliest


# ------------------------------------------------------------- date-range pulls

def fetch_range_with_halving(fetch_fn, start, end, initial_days, label):
    """Calls fetch_fn(chunk_start, chunk_end) across [start, end], halving the
    window on HTTP 500 (the API's ~256KB response-size limit)."""
    days = initial_days
    cur = start
    total_days = (end - start).days + 1
    done_days = 0
    results = []
    while cur <= end:
        chunk_end = min(cur + timedelta(days=days - 1), end)
        try:
            data = fetch_fn(cur, chunk_end)
            results.append((cur, chunk_end, data))
            done_days += (chunk_end - cur).days + 1
            pct = min(100, int(100 * done_days / max(total_days, 1)))
            sys.stdout.write(f"\r  {label}: {pct}% ({fmt(cur)} to {fmt(chunk_end)})      ")
            sys.stdout.flush()
            cur = chunk_end + timedelta(days=1)
            time.sleep(PAUSE)
        except RuntimeError as e:
            if "HTTP 500" in str(e) and days > 1:
                days = max(1, days // 2)
                continue
            raise
    print()
    return results


def pull_daily_summaries(start, end):
    print("Daily summaries:")
    existing = load_json("daily_summaries.json", {})

    def fetch(cs, ce):
        r = api_get("/usersummary-service/v2/dailysummaries", {"startDate": fmt(cs), "endDate": fmt(ce)})
        return (r or {}).get("data", [])

    chunks = fetch_range_with_halving(fetch, start, end, 60, "daily summaries")
    new_count = 0
    for _, _, items in chunks:
        for item in items:
            d = item.get("calendarDate")
            if not d:
                continue
            if d not in existing:
                new_count += 1
            existing[d] = item
    save_json("daily_summaries.json", existing)
    print(f"  total days: {len(existing)} ({new_count} new)")
    return existing


def pull_sleep(start, end):
    print("Sleep:")
    existing = load_json("sleep.json", {})

    def fetch(cs, ce):
        r = api_get("/sleep-service/sleep/dailySleepSummariesByDate", {"startDate": fmt(cs), "endDate": fmt(ce)})
        return r or []

    chunks = fetch_range_with_halving(fetch, start, end, 31, "sleep")
    new_count = 0
    for _, _, items in chunks:
        for item in items:
            d = item.get("calendarDate")
            if not d:
                continue
            if d not in existing:
                new_count += 1
            existing[d] = item
    save_json("sleep.json", existing)
    print(f"  total nights: {len(existing)} ({new_count} new)")
    return existing


def pull_hrv(start, end):
    print("HRV:")
    existing = load_json("hrv.json", {})

    def fetch(cs, ce):
        r = api_get(f"/hrv-service/hrv/daily/{fmt(cs)}/{fmt(ce)}")
        return (r or {}).get("hrvSummaries", [])

    chunks = fetch_range_with_halving(fetch, start, end, 365, "HRV")
    new_count = 0
    for _, _, items in chunks:
        for item in items:
            d = item.get("calendarDate")
            if not d:
                continue
            if d not in existing:
                new_count += 1
            existing[d] = item
    save_json("hrv.json", existing)
    print(f"  total nights: {len(existing)} ({new_count} new)")
    return existing


def pull_weight(start, end):
    print("Weight:")
    existing = load_json("weight.json", {})

    def fetch(cs, ce):
        r = api_get(f"/weight-service/weight/range/{fmt(cs)}/{fmt(ce)}")
        return (r or {}).get("dailyWeightSummaries", [])

    chunks = fetch_range_with_halving(fetch, start, end, 60, "weight")
    new_count = 0
    for _, _, items in chunks:
        for item in items:
            latest = item.get("latestWeight") or {}
            d = item.get("calendarDate") or item.get("date")
            if not d or latest.get("weight") is None:
                continue
            if d not in existing:
                new_count += 1
            existing[d] = {"weightGrams": latest["weight"]}
    save_json("weight.json", existing)
    print(f"  total weigh-ins: {len(existing)} ({new_count} new)")
    return existing


# ------------------------------------------------------------------ snapshots

def pull_snapshots():
    print("Fitness age & HR zones:")
    today = fmt(date.today())
    try:
        fa = api_get(f"/fitnessage-service/fitnessage/v2/{today}")
        if fa:
            save_json("fitness_age.json", {"date": today, "data": fa})
    except RuntimeError as e:
        print(f"  fitness age unavailable: {e}")
    time.sleep(PAUSE)
    try:
        zones = api_get("/biometric-service/heartRateZones/v2")
        if zones:
            save_json("hr_zones.json", zones)
    except RuntimeError as e:
        print(f"  HR zones unavailable: {e}")
    time.sleep(PAUSE)
    # Garmin's own Training Status (Productive/Peaking/Recovery/etc.) + VO2 max - this is an
    # unofficial, community-reverse-engineered endpoint (not documented by Garmin), so it may
    # not work or may change shape without notice. Fails soft like the two calls above.
    try:
        ts = api_get(f"/metrics-service/metrics/trainingstatus/aggregated/{today}")
        if ts:
            save_json("training_status.json", {"date": today, "data": ts})
    except RuntimeError as e:
        print(f"  training status unavailable: {e}")
    print("  done")


# ------------------------------------------------------------------------ main

def determine_window(full_history, earliest_activity_date, existing_data, last_checked):
    """Each dataset tracks its own resume point, since they can finish pulling
    at different times (e.g. one call fails partway through). last_checked
    covers datasets that came back empty (e.g. no weigh-ins), so we don't
    keep re-fetching the same empty range forever.

    The most recent day we have is always re-fetched (not just days after
    it), since today's data (steps, sleep, HRV) keeps changing as the day
    goes on and a same-day snapshot is never final."""
    today = date.today()
    anchor = None
    if existing_data:
        anchor = max(parse_date(d) for d in existing_data.keys())
    if last_checked:
        checked_date = parse_date(last_checked)
        if anchor is None or checked_date > anchor:
            anchor = checked_date

    if anchor is not None:
        start = min(anchor, today)
        return start, today

    if full_history:
        if earliest_activity_date:
            start = parse_date(earliest_activity_date)
        else:
            start = today - timedelta(days=5 * 365)
    else:
        start = today - timedelta(days=365)
    return start, today


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="fetch full history instead of last 12 months")
    args = parser.parse_args()

    print("Pulling your Garmin data. This can take a few minutes on the first run.\n")

    activities, earliest_activity_date = pull_activities()
    print()

    state = load_json("pull_state.json", {})
    for name, state_key, existing_file, pull_fn in [
        ("daily summaries", "daily_summaries", "daily_summaries.json", pull_daily_summaries),
        ("sleep", "sleep", "sleep.json", pull_sleep),
        ("HRV", "hrv", "hrv.json", pull_hrv),
        ("weight", "weight", "weight.json", pull_weight),
    ]:
        existing_data = load_json(existing_file, {})
        start, end = determine_window(args.full, earliest_activity_date, existing_data, state.get(state_key))
        if start is None:
            print(f"{name.capitalize()}: already up to date.\n")
        else:
            pull_fn(start, end)
            state[state_key] = fmt(end)
            save_json("pull_state.json", state)
            print()

    pull_snapshots()

    # summary
    days = load_json("daily_summaries.json", {})
    nights = load_json("sleep.json", {})
    all_dates = list(days.keys()) + list(nights.keys()) + [a.get("startTimeLocal", "")[:10] for a in activities]
    all_dates = [d for d in all_dates if d]
    date_range = f"{min(all_dates)} to {max(all_dates)}" if all_dates else "no data"

    print("\nDone.")
    print(f"  Activities: {len(activities)}")
    print(f"  Days of daily summaries: {len(days)}")
    print(f"  Nights of sleep data: {len(nights)}")
    print(f"  Date range: {date_range}")


if __name__ == "__main__":
    main()
