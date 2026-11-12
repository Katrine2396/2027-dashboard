"""
Reads data/*.json and writes dashboard.html - one self-contained file,
no server needed, charts drawn with inline SVG + vanilla JS.
"""
import hashlib
import json
import os
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")

# ---- access gate (deterrent only, NOT real security - anyone with devtools can bypass it,
# this just stops casual link-sharing/crawling from exposing your data at a glance).
# Change this before pushing anywhere public. Can also be overridden via the
# DASHBOARD_GATE_PASSPHRASE environment variable so the real value never has to live in git.
GATE_PASSPHRASE = os.environ.get("DASHBOARD_GATE_PASSPHRASE", "endre-meg")

KM_PER_METER = 0.001

SPORT_MAP = {
    "strength_training": "Strength",
    "running": "Running",
    "treadmill_running": "Running",
    "trail_running": "Running",
    "track_running": "Running",
    "indoor_cycling": "Cycling",
    "cycling": "Cycling",
    "road_biking": "Cycling",
    "mountain_biking": "Cycling",
    "virtual_ride": "Cycling",
    "walking": "Walking",
    "hiking": "Walking",
}
SPORT_ORDER = ["Strength", "Cycling", "Running", "Walking", "Other"]
SPORT_COLORS = {
    "Strength": "#7a1f3d",
    "Cycling": "#9b3456",
    "Running": "#a46cc0",
    "Walking": "#e8a3b6",
    "Other": "#d9a441",
}

# ---- training program (general gym-based strength plan from 2026-11-09, "Grunnstyrke og stabilitet") ----
# Self-designed (not prescribed exercise-by-exercise by the naprapat): she was told she's generally
# weak and needs core/hip stability work, which is also likely why her knee reacts when running.
# Each strength day is full-body (push, pull, hip-hinge/glute, controlled knee-dominant, core,
# balance) so no single joint pattern gets stacked session after session, and knee-loading is spread
# across RDLs/leg press/goblet squat rather than concentrated in one heavy "leg day".
GS_START = date(2026, 11, 9)
PROGRAM = {
    0: {"key": "gsA", "label": "Styrke A: helkropp og kjerne", "type": "strength"},
    1: {"key": "cyc", "label": "Rolig sykling", "type": "cycling"},
    2: {"key": "gsB", "label": "Styrke B: helkropp og kjerne", "type": "strength"},
    3: {"key": "restW", "label": "Hvile eller rolig gåtur", "type": "rest"},
    4: {"key": "gsC", "label": "Styrke C: helkropp og kjerne", "type": "strength"},
    5: {"key": "cyc", "label": "Rolig sykling", "type": "cycling"},
    6: {"key": "rest", "label": "Hvile eller lett aktivitet", "type": "rest"},
}
GS_PROG = {
    1: {"sets": "2–3 sett", "cycle": "20–25 min", "focus": "Lær øvelsene, lett/moderat vekt, god teknikk og kontroll"},
    2: {"sets": "3 sett", "cycle": "20–30 min", "focus": "Øk vekten litt på øvelsene som føltes greie forrige uke"},
    3: {"sets": "3–4 sett", "cycle": "25–35 min", "focus": "Fortsett å øke vekt der kroppen tillater det"},
    4: {"sets": "3–4 sett", "cycle": "25–40 min", "focus": "Sikt på litt mer vekt eller reps der det er smertefritt"},
    5: {"sets": "1–2 sett", "cycle": "15–20 min", "focus": "Deload-uke: lavere vekt og volum, la kroppen hente seg inn før neste blokk", "deload": True},
}
PROG_EXERCISES = {
    "gsA": ["Glute bridge (aktivering - kjenn at rumpa jobber, ikke korsryggen) 2×12",
            "Beinpress, kontrollert dybde 3×10–12", "Benkpress i maskin 3×8–10", "Sittende roing (kabel) 3×10–12",
            "Hip thrust (stang/manualer) - pause og klem rumpa i toppen 3×10–12", "Pallof press (kabel) 3×8–10/side"],
    "gsB": ["Supersett aktivering: Glute bridge 2×12 + Fire hydrants 2×10–12/side + Donkey kicks (spark bak på 4 bein) 2×10–12/side",
            "Rumensk markløft (manualer) - skyv hoftene bak, nøytral rygg, kjenn baksiden av lår/rumpe 3×8–10",
            "Nedtrekk, bredt grep (kabel) 3×8–10", "Skulderpress (manualer) 3×8–10",
            "Sideplanke med hoftehev 3×8–10/side"],
    "gsC": ["Armhevinger mot benk/vegg (jobb mot gulvet over tid) 3×8–12",
            "Goblet squat, moderat dybde innenfor smertefri rekkevidde 3×10–12",
            "Stående kabelrad 3×10–12", "Step-up på lav kasse, kontrollert - skyv gjennom hælen, kjenn rumpa 3×8/side",
            "Dead bug med vekt 3×8/side", "Planke med skulderberøring 3×20–30 s"],
}
NUTRITION_PLAN = {
    "dailyKcal": 1750,
    "proteinMin": 140,
    "note": "Tallene er grove anslag basert på vanlige produktverdier (±10%) - sjekk egne etiketter (proteinpulver, YT-produkter) for mer nøyaktige tall.",
    "breakfast": {
        "label": "Frokost (fast)",
        "items": ["40 g havregryn", "20 g proteinpulver", "1 dl proteinmelk", "10 g chiafrø", "100 g gresk yoghurt"],
        "kcal": 450, "protein": 32,
    },
    "lunch": {
        "label": "Lunsj - velg én, rullér gjennom uken",
        "options": [
            {"name": "Kyllingfilet-wrap", "items": ["130 g kyllingfilet", "1 grovt pitabrød", "agurk og paprika", "1 ss lett rømme/yoghurtdressing"], "kcal": 400, "protein": 35},
            {"name": "Karbonadedeig med ris", "items": ["120 g karbonadedeig", "60 g ris (tørrvekt)", "agurk og paprika"], "kcal": 430, "protein": 28},
            {"name": "Kyllingkjøttdeig-taco", "items": ["130 g kyllingkjøttdeig", "2 extra thin tacolefser", "agurk og paprika", "litt mager kesam"], "kcal": 400, "protein": 32},
            {"name": "Proteinrundstykke med kyllingfilet", "items": ["1 proteinrundstykke", "80 g kyllingfilet-pålegg", "salat og tomat", "litt lett dressing"], "kcal": 350, "protein": 30},
            {"name": "Wrap med ferdigstekt kylling", "items": ["1 grov tortillalefse", "100 g ferdigstekt kyllingfilet (butikk)", "agurk og paprika", "litt lett dressing"], "kcal": 380, "protein": 30},
        ],
    },
    "snack": {
        "label": "Mellommåltid - velg én",
        "options": [
            {"name": "Yoghurt med bringebær og granola", "items": ["150 g høyprotein yoghurt/skyr", "20 g kakaogranola", "bringebær", "1 ts Biscoff"], "kcal": 230, "protein": 18},
            {"name": "YT proteinprodukt", "items": ["1 stk (sjekk etiketten for nøyaktige tall)"], "kcal": 180, "protein": 20},
            {"name": "Mager kesam med bringebær", "items": ["150 g mager kesam", "bringebær"], "kcal": 110, "protein": 18},
        ],
    },
    "dinner": {
        "label": "Middag - velg én, rullér gjennom uken",
        "options": [
            {"name": "Kyllingkjøttdeig-stekt ris", "items": ["150 g kyllingkjøttdeig", "70 g ris (tørrvekt)", "amerikansk grønnsaksblanding (frossen)", "litt soyasaus"], "kcal": 520, "protein": 42},
            {"name": "Pasta med kjøttsaus", "items": ["80 g pasta (tørrvekt)", "130 g karbonadedeig", "litt tomatsaus", "paprika"], "kcal": 560, "protein": 33},
            {"name": "Kylling med ris", "items": ["150 g kyllingfilet", "70 g ris (tørrvekt)", "agurk og paprika"], "kcal": 480, "protein": 44},
            {"name": "Laks med poteter", "items": ["150 g laksefilet", "200 g poteter", "brokkoli"], "kcal": 490, "protein": 38},
            {"name": "Taco-gryte", "items": ["150 g kyllingkjøttdeig", "100 g mais og bønner", "1 dl lettrømme", "liten porsjon tortillachips"], "kcal": 540, "protein": 36},
        ],
    },
}
# ---- budget (starting points - fully editable in the app; income 32k/mnd, husleie 13.5k/mnd) ----
BUDGET_DEFAULTS = {
    "income": 32000,
    "categories": [
        {"key": "bolig", "label": "Bolig/faste utgifter", "cap": 15000},
        {"key": "mat", "label": "Dagligvarer", "cap": 3800},
        {"key": "restaurant", "label": "Restaurant/take-away", "cap": 600},
        {"key": "transport", "label": "Transport", "cap": 900},
        {"key": "abonnement", "label": "Abonnementer", "cap": 500},
        {"key": "klaer", "label": "Klær/shopping", "cap": 700},
        {"key": "trening", "label": "Trening/helse", "cap": 600},
        {"key": "hundefond", "label": "Hundefond (sparing)", "cap": 2500},
        {"key": "annet", "label": "Annet", "cap": 1000},
    ],
}
DOG_FUND = {"target": 30000, "startSaved": 5000, "category": "hundefond"}

# ---- points / levels ----
POINTS_CONFIG = {
    "levelThreshold": 600,
    "perCompletedSession": 15,
    "perStepGoalDay": 5,
    "perWeightWeek": 10,
    "perMeasurementMonth": 15,
    "perNewRecord": 20,
    "perFundMilestone": 50,
    "levelNames": ["Frø", "Spire", "Knopp", "Blomst", "Bukett", "Hage", "Rosekongen"],
    "levelRewards": [
        "Start! 🌱", "Nye treningssokker eller fin hårklype",
        "Et lite sølvsmykke, f.eks. øredobber eller et armbånd",
        "Ny spilleliste og fin vannflaske til treningsbagen",
        "Manikyr eller en bukett blomster til deg selv",
        "Noe fint til leiligheten, f.eks. en plante eller pute",
        "En hel dag fri fra alt, akkurat som du vil 👑",
    ],
}
WEEKDAY_LABELS_NO = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"]
STRENGTH_TYPE_KEYS = {"strength_training"}
CYCLING_TYPE_KEYS = {"indoor_cycling", "cycling", "road_biking", "mountain_biking", "virtual_ride", "elliptical"}
WALK_TYPE_KEYS = {"walking", "hiking"}
TYPE_KEYS_BY_BUCKET = {"strength": STRENGTH_TYPE_KEYS, "cycling": CYCLING_TYPE_KEYS, "walk": WALK_TYPE_KEYS}

# swap options a session can be manually changed to, for the interactive plan
SESSION_CATALOG = {
    "gsA": {"label": PROGRAM[0]["label"], "type": "strength", "exercises": PROG_EXERCISES["gsA"]},
    "gsB": {"label": PROGRAM[2]["label"], "type": "strength", "exercises": PROG_EXERCISES["gsB"]},
    "gsC": {"label": PROGRAM[4]["label"], "type": "strength", "exercises": PROG_EXERCISES["gsC"]},
    "cyc": {"label": "Rolig sykling", "type": "cycling", "note": "Lett motstand, prat i hele setninger"},
    "walk": {"label": "Gåtur", "type": "walk"},
    "rest": {"label": "Hvile", "type": "rest"},
}


def gs_week(d):
    n = (d - GS_START).days // 7 + 1
    n = max(1, n)
    return (n - 1) % 5 + 1


def session_for(d):
    sess = dict(PROGRAM[d.weekday()])
    week = gs_week(d)
    if sess["key"] == "cyc":
        sess["label"] = f"Rolig sykling ({GS_PROG[week]['cycle']})"
    return sess


def load_json(name, default):
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def sport_for(type_key):
    return SPORT_MAP.get(type_key, "Other")


def iso_week_start(d):
    return d - timedelta(days=d.weekday())


def week_label(d):
    return d.strftime("%Y-%m-%d")


def safe_round(x, n=0):
    if x is None:
        return None
    return round(x, n) if n else int(round(x))


def main():
    activities = load_json("activities.json", [])
    daily = load_json("daily_summaries.json", {})
    sleep = load_json("sleep.json", {})
    hrv = load_json("hrv.json", {})
    weight = load_json("weight.json", {})

    # ---------------------------------------------------------------- dates
    all_dates = set(daily.keys()) | set(sleep.keys()) | set(hrv.keys())
    for a in activities:
        if a.get("startTimeLocal"):
            all_dates.add(a["startTimeLocal"][:10])
    if not all_dates:
        raise SystemExit("No data found in data/. Run pull.py first.")
    min_date, max_date = min(all_dates), max(all_dates)

    # -------------------------------------------------------- top stat cards
    def latest_entries(d, n=30):
        keys = sorted(d.keys())
        return keys[-n:]

    daily_keys = sorted(daily.keys())
    sleep_keys = sorted(sleep.keys())
    hrv_keys = sorted(hrv.keys())

    def trend_series(d, keys, extractor, n=30):
        out = []
        for k in keys[-n:]:
            v = extractor(d[k])
            out.append(v)
        return out

    top_stats = {}

    if hrv_keys:
        last_k = hrv_keys[-1]
        top_stats["hrv"] = {
            "value": safe_round(hrv[last_k].get("lastNightAvg")),
            "weeklyAvg": safe_round(hrv[last_k].get("weeklyAvg")),
            "status": hrv[last_k].get("status"),
            "date": last_k,
            "trend": trend_series(hrv, hrv_keys, lambda v: v.get("lastNightAvg")),
        }

    if sleep_keys:
        last_k = sleep_keys[-1]
        s = sleep[last_k]
        score = ((s.get("sleepScores") or {}).get("overall") or {}).get("value")
        top_stats["sleep"] = {
            "hours": safe_round((s.get("sleepTimeSeconds") or 0) / 3600, 1),
            "score": safe_round(score),
            "date": last_k,
            "trend": trend_series(
                sleep, sleep_keys, lambda v: safe_round((v.get("sleepTimeSeconds") or 0) / 3600, 1)
            ),
        }

    if daily_keys:
        last_k = daily_keys[-1]
        d0 = daily[last_k]
        cal = (d0.get("calories") or {}).get("burnedTotal")
        steps = (d0.get("movement") or {}).get("steps", {}).get("value")
        resting_hr = (d0.get("heartRate") or {}).get("restingValue")
        top_stats["calories"] = {
            "value": safe_round(cal),
            "date": last_k,
            "trend": trend_series(daily, daily_keys, lambda v: safe_round((v.get("calories") or {}).get("burnedTotal"))),
        }
        top_stats["steps"] = {
            "value": safe_round(steps),
            "date": last_k,
            "trend": trend_series(daily, daily_keys, lambda v: safe_round((v.get("movement") or {}).get("steps", {}).get("value"))),
        }
        top_stats["restingHR"] = {
            "value": safe_round(resting_hr),
            "date": last_k,
            "trend": trend_series(daily, daily_keys, lambda v: safe_round((v.get("heartRate") or {}).get("restingValue"))),
        }

    # ------------------------------------------------------ weekly by sport
    weekly_sport = defaultdict(lambda: defaultdict(lambda: {"sessions": 0, "minutes": 0.0, "distanceKm": 0.0, "calories": 0.0}))
    for a in activities:
        start = a.get("startTimeLocal")
        if not start:
            continue
        d = datetime.strptime(start[:10], "%Y-%m-%d").date()
        wk = week_label(iso_week_start(d))
        sport = sport_for((a.get("activityType") or {}).get("typeKey", ""))
        entry = weekly_sport[wk][sport]
        entry["sessions"] += 1
        entry["minutes"] += (a.get("duration") or 0) / 60
        entry["distanceKm"] += (a.get("distance") or 0) * KM_PER_METER
        entry["calories"] += a.get("calories") or 0

    sorted_weeks = sorted(weekly_sport.keys())
    recent_weeks = sorted_weeks[-10:]
    weekly_by_sport_out = []
    for wk in recent_weeks:
        sports_out = {}
        for sport in SPORT_ORDER:
            e = weekly_sport[wk].get(sport)
            if e:
                sports_out[sport] = {
                    "sessions": e["sessions"],
                    "minutes": safe_round(e["minutes"]),
                    "distanceKm": safe_round(e["distanceKm"], 1),
                    "calories": safe_round(e["calories"]),
                }
        weekly_by_sport_out.append({"week": wk, "sports": sports_out})

    # -------------------------------------------------------------- goal (leaner)
    def week_totals(weeks_slice):
        total_cal, total_sessions, total_minutes = 0, 0, 0
        for wk in weeks_slice:
            for sport, e in weekly_sport[wk].items():
                total_cal += e["calories"]
                total_sessions += e["sessions"]
                total_minutes += e["minutes"]
        n = max(len(weeks_slice), 1)
        return total_cal / n, total_sessions / n, total_minutes / n

    recent_8 = sorted_weeks[-8:]
    prior_8 = sorted_weeks[-16:-8]

    def daily_steps_avg(keys_slice):
        vals = [
            (daily[k].get("movement") or {}).get("steps", {}).get("value")
            for k in keys_slice
            if k in daily
        ]
        vals = [v for v in vals if v is not None]
        return statistics.mean(vals) if vals else None

    def week_dates(wk_label):
        start = datetime.strptime(wk_label, "%Y-%m-%d").date()
        return [week_label_date(start + timedelta(days=i)) for i in range(7)]

    def week_label_date(d):
        return d.strftime("%Y-%m-%d")

    recent_day_keys = [d for wk in recent_8 for d in week_dates(wk) if d in daily]
    prior_day_keys = [d for wk in prior_8 for d in week_dates(wk) if d in daily]

    recent_cal, recent_sessions, recent_minutes = week_totals(recent_8)
    prior_cal, prior_sessions, prior_minutes = week_totals(prior_8) if prior_8 else (None, None, None)
    recent_steps = daily_steps_avg(recent_day_keys)
    prior_steps = daily_steps_avg(prior_day_keys)

    def pct_change(new, old):
        if not old:
            return None
        return safe_round(100 * (new - old) / old)

    goal = {
        "type": "leaner",
        "recentActiveCaloriesPerWeek": safe_round(recent_cal),
        "priorActiveCaloriesPerWeek": safe_round(prior_cal) if prior_cal is not None else None,
        "caloriesPctChange": pct_change(recent_cal, prior_cal) if prior_cal else None,
        "recentSessionsPerWeek": safe_round(recent_sessions, 1),
        "priorSessionsPerWeek": safe_round(prior_sessions, 1) if prior_sessions is not None else None,
        "recentStepsPerDay": safe_round(recent_steps) if recent_steps else None,
        "priorStepsPerDay": safe_round(prior_steps) if prior_steps else None,
        "stepsPctChange": pct_change(recent_steps, prior_steps) if prior_steps else None,
    }

    # -------------------------------------------------------------- trends
    def week_of(date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return week_label(iso_week_start(d))

    def weekly_avg(data_dict, extractor, max_weeks=104):
        buckets = defaultdict(list)
        for k, v in data_dict.items():
            val = extractor(v)
            if val is not None:
                buckets[week_of(k)].append(val)
        weeks = sorted(buckets.keys())[-max_weeks:]
        return weeks, [safe_round(statistics.mean(buckets[w]), 1) for w in weeks]

    load_buckets = defaultdict(list)
    for a in activities:
        start = a.get("startTimeLocal")
        tl = a.get("activityTrainingLoad")
        if start and tl is not None:
            load_buckets[week_of(start[:10])].append(tl)
    load_weeks = sorted(load_buckets.keys())[-104:]
    training_load = [safe_round(sum(load_buckets[w])) for w in load_weeks]

    rhr_weeks, rhr_vals = weekly_avg(daily, lambda v: (v.get("heartRate") or {}).get("restingValue"))
    hrv_weeks, hrv_vals = weekly_avg(hrv, lambda v: v.get("lastNightAvg"))
    sleep_weeks, sleep_vals = weekly_avg(sleep, lambda v: (v.get("sleepTimeSeconds") or 0) / 3600)
    sleep_score_weeks, sleep_score_vals = weekly_avg(
        sleep, lambda v: ((v.get("sleepScores") or {}).get("overall") or {}).get("value")
    )

    # align all trend series onto the union of weeks present in training load / rhr (use rhr as backbone, it's most complete)
    trends = {
        "trainingLoad": {"weeks": load_weeks, "values": training_load},
        "restingHR": {"weeks": rhr_weeks, "values": rhr_vals},
        "hrv": {"weeks": hrv_weeks, "values": hrv_vals},
        "sleepHours": {"weeks": sleep_weeks, "values": sleep_vals},
        "sleepScore": {"weeks": sleep_score_weeks, "values": sleep_score_vals},
    }

    # -------------------------------------------------------------- records
    records = {}

    def best_activity(predicate_key, sport_filter=None, pick_max=True):
        candidates = [
            a for a in activities
            if a.get(predicate_key) is not None
            and (sport_filter is None or sport_for((a.get("activityType") or {}).get("typeKey", "")) == sport_filter)
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda a: a[predicate_key]) if pick_max else min(candidates, key=lambda a: a[predicate_key])
        return best

    # cycling in this dataset is all indoor (distance always 0), so measure rides by time instead
    cycling_activities = [a for a in activities if sport_for((a.get("activityType") or {}).get("typeKey", "")) == "Cycling"]
    any_ride_distance = any((a.get("distance") or 0) > 0 for a in cycling_activities)
    longest_ride = best_activity("distance" if any_ride_distance else "duration", sport_filter="Cycling")
    longest_run = best_activity("distance", sport_filter="Running")
    longest_strength = best_activity("duration", sport_filter="Strength")
    highest_load_activity = best_activity("activityTrainingLoad")

    def activity_record(a, value_key, unit, convert=lambda v: v):
        if not a:
            return None
        return {
            "value": convert(a[value_key]),
            "unit": unit,
            "date": (a.get("startTimeLocal") or "")[:10],
            "name": a.get("activityName"),
        }

    if any_ride_distance:
        records["longestRide"] = activity_record(longest_ride, "distance", "km", lambda v: safe_round(v * KM_PER_METER, 1))
    else:
        records["longestRide"] = activity_record(longest_ride, "duration", "min", lambda v: safe_round(v / 60))
    records["longestRun"] = activity_record(longest_run, "distance", "km", lambda v: safe_round(v * KM_PER_METER, 1))
    records["longestStrength"] = activity_record(longest_strength, "duration", "min", lambda v: safe_round(v / 60))
    records["highestTrainingLoad"] = activity_record(highest_load_activity, "activityTrainingLoad", "load", lambda v: safe_round(v))

    if daily_keys:
        best_steps_day = max(daily_keys, key=lambda k: (daily[k].get("movement") or {}).get("steps", {}).get("value") or 0)
        best_cal_day = max(daily_keys, key=lambda k: (daily[k].get("calories") or {}).get("burnedTotal") or 0)
        records["mostSteps"] = {
            "value": safe_round((daily[best_steps_day].get("movement") or {}).get("steps", {}).get("value")),
            "date": best_steps_day,
        }
        records["mostCalories"] = {
            "value": safe_round((daily[best_cal_day].get("calories") or {}).get("burnedTotal")),
            "date": best_cal_day,
        }

    if sleep_keys:
        longest_sleep_day = max(sleep_keys, key=lambda k: sleep[k].get("sleepTimeSeconds") or 0)
        records["longestSleep"] = {
            "value": safe_round((sleep[longest_sleep_day].get("sleepTimeSeconds") or 0) / 3600, 1),
            "date": longest_sleep_day,
        }

    if hrv_keys:
        best_hrv_day = max(hrv_keys, key=lambda k: hrv[k].get("lastNightAvg") or 0)
        records["bestHRV"] = {
            "value": safe_round(hrv[best_hrv_day].get("lastNightAvg")),
            "date": best_hrv_day,
        }

    # -------------------------------------------------------------- report metrics (morning/evening/weekly coach)
    def window_avg(d, keys_sorted, extractor, days, exclude_last=True):
        keys = keys_sorted[:-1] if (exclude_last and keys_sorted) else keys_sorted
        keys = keys[-days:]
        vals = [v for v in (extractor(d[k]) for k in keys) if v is not None]
        return safe_round(statistics.mean(vals), 1) if vals else None

    def latest_of(d, keys_sorted, extractor):
        return extractor(d[keys_sorted[-1]]) if keys_sorted else None

    REPORT_METRIC_DEFS = {
        "sleepHours": (sleep, sleep_keys, lambda v: safe_round((v.get("sleepTimeSeconds") or 0) / 3600, 2)),
        "deepSleepMin": (sleep, sleep_keys, lambda v: safe_round((v.get("deepSleepSeconds") or 0) / 60)),
        "remSleepMin": (sleep, sleep_keys, lambda v: safe_round((v.get("remSleepSeconds") or 0) / 60)),
        "lightSleepMin": (sleep, sleep_keys, lambda v: safe_round((v.get("lightSleepSeconds") or 0) / 60)),
        "sleepScore": (sleep, sleep_keys, lambda v: ((v.get("sleepScores") or {}).get("overall") or {}).get("value")),
        "bodyBatteryCharged": (daily, daily_keys, lambda v: (v.get("bodyBattery") or {}).get("chargedValue")),
        "bodyBatteryLatest": (daily, daily_keys, lambda v: (v.get("bodyBattery") or {}).get("latestValue")),
        "bodyBatteryMin": (daily, daily_keys, lambda v: (v.get("bodyBattery") or {}).get("minValue")),
        "restingHR": (daily, daily_keys, lambda v: (v.get("heartRate") or {}).get("restingValue")),
        "hrv": (hrv, hrv_keys, lambda v: v.get("lastNightAvg")),
        "steps": (daily, daily_keys, lambda v: (v.get("movement") or {}).get("steps", {}).get("value")),
        "stress": (daily, daily_keys, lambda v: (v.get("stress") or {}).get("avgLevel")),
        "calories": (daily, daily_keys, lambda v: (v.get("calories") or {}).get("burnedTotal")),
    }
    report_metrics = {}
    for rm_key, (rm_src, rm_keys, rm_extractor) in REPORT_METRIC_DEFS.items():
        report_metrics[rm_key] = {
            "today": latest_of(rm_src, rm_keys, rm_extractor),
            "avg7": window_avg(rm_src, rm_keys, rm_extractor, 7),
            "avg30": window_avg(rm_src, rm_keys, rm_extractor, 30),
        }

    # last ~5 weeks of per-day Garmin metrics, so the client can join them against
    # locally-logged training/food/budget data (which only lives in localStorage) to
    # find patterns for the weekly report.
    daily_history = []
    history_dates = sorted((set(daily_keys[-35:]) | set(sleep_keys[-35:]) | set(hrv_keys[-35:])))[-35:]
    for hk in history_dates:
        d_day = daily.get(hk, {})
        s_day = sleep.get(hk, {})
        h_day = hrv.get(hk, {})
        bb = d_day.get("bodyBattery") or {}
        daily_history.append({
            "date": hk,
            "weekday": datetime.strptime(hk, "%Y-%m-%d").date().weekday(),
            "sleepHours": safe_round((s_day.get("sleepTimeSeconds") or 0) / 3600, 2) if s_day else None,
            "deepSleepMin": safe_round((s_day.get("deepSleepSeconds") or 0) / 60) if s_day else None,
            "sleepScore": ((s_day.get("sleepScores") or {}).get("overall") or {}).get("value") if s_day else None,
            "bodyBatteryCharged": bb.get("chargedValue"),
            "bodyBatteryLatest": bb.get("latestValue"),
            "restingHR": (d_day.get("heartRate") or {}).get("restingValue") if d_day else None,
            "hrv": h_day.get("lastNightAvg") if h_day else None,
            "steps": (d_day.get("movement") or {}).get("steps", {}).get("value") if d_day else None,
            "stress": (d_day.get("stress") or {}).get("avgLevel") if d_day else None,
            "calories": (d_day.get("calories") or {}).get("burnedTotal") if d_day else None,
        })

    # -------------------------------------------------------------- training plan
    def trailing_baseline(d, keys_sorted, extractor, window=14):
        if not keys_sorted:
            return None, None
        latest_val = extractor(d[keys_sorted[-1]])
        prior_keys = keys_sorted[-(window + 1):-1]
        prior_vals = [v for v in (extractor(d[k]) for k in prior_keys) if v is not None]
        baseline = statistics.mean(prior_vals) if prior_vals else None
        return latest_val, baseline

    def activities_on(d):
        ds = d.isoformat()
        return [a for a in activities if (a.get("startTimeLocal") or "")[:10] == ds]

    def logged_activities_on(d):
        out = []
        for a in activities_on(d):
            tk = (a.get("activityType") or {}).get("typeKey", "")
            for bucket, keys in TYPE_KEYS_BY_BUCKET.items():
                if tk in keys:
                    out.append({
                        "type": bucket,
                        "name": a.get("activityName"),
                        "minutes": safe_round((a.get("duration") or 0) / 60),
                    })
                    break
        return out

    today = date.today()
    week_num = gs_week(today)
    prog_week = GS_PROG[week_num]

    hrv_latest, _ = trailing_baseline(hrv, hrv_keys, lambda v: v.get("lastNightAvg"))
    hrv_status = hrv[hrv_keys[-1]].get("status") if hrv_keys else None
    rhr_latest, rhr_baseline = trailing_baseline(daily, daily_keys, lambda v: (v.get("heartRate") or {}).get("restingValue"))
    sleep_hours_latest, _ = trailing_baseline(sleep, sleep_keys, lambda v: safe_round((v.get("sleepTimeSeconds") or 0) / 3600, 1))
    sleep_score_latest, _ = trailing_baseline(sleep, sleep_keys, lambda v: ((v.get("sleepScores") or {}).get("overall") or {}).get("value"))
    stress_latest, _ = trailing_baseline(daily, daily_keys, lambda v: (v.get("stress") or {}).get("avgLevel"))

    readiness_score = 0
    reasons = []
    if hrv_status in ("LOW", "UNBALANCED"):
        readiness_score -= 2
        reasons.append(f"HRV er {'lav' if hrv_status == 'LOW' else 'ubalansert'} i natt ({hrv_latest} ms)")
    elif hrv_status == "BALANCED" and hrv_latest is not None:
        reasons.append(f"HRV er balansert i natt ({hrv_latest} ms)")

    if rhr_latest is not None and rhr_baseline is not None and rhr_latest - rhr_baseline >= 4:
        readiness_score -= 1
        reasons.append(f"Hvilepuls er høyere enn vanlig ({rhr_latest} vs. snitt {safe_round(rhr_baseline)})")

    if sleep_hours_latest is not None and sleep_hours_latest < 6:
        readiness_score -= 1
        reasons.append(f"Lite søvn i natt ({sleep_hours_latest} t)")
    elif sleep_score_latest is not None and sleep_score_latest < 60:
        readiness_score -= 1
        reasons.append(f"Lav søvnscore i natt ({safe_round(sleep_score_latest)})")

    if stress_latest is not None and stress_latest >= 50:
        readiness_score -= 1
        reasons.append(f"Høyt stressnivå siste døgn ({safe_round(stress_latest)})")

    if not reasons:
        reasons.append("Ingen tegn til ekstra belastning i dataene dine")

    readiness = "light" if readiness_score <= -2 else "caution" if readiness_score == -1 else "go"

    week_start = iso_week_start(today)
    week_days_out = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        sess = session_for(d)
        week_days_out.append({
            "date": d.isoformat(),
            "weekday": WEEKDAY_LABELS_NO[i],
            "defaultKey": sess["key"],
            "sessionLabel": sess["label"],
            "sessionType": sess["type"],
            "isToday": d == today,
            "loggedActivities": logged_activities_on(d) if d <= today else [],
        })

    program = {
        "currentWeek": week_num,
        "weekFocus": prog_week["focus"],
        "weekSetsNote": prog_week["sets"],
        "weekCycleNote": prog_week["cycle"],
        "weekIsDeload": bool(prog_week.get("deload")),
        "today": {
            "date": today.isoformat(),
            "readiness": readiness,
            "reasons": reasons,
        },
        "week": week_days_out,
    }

    # ---------------------------------------------------- training history (for points)
    # Default plan only (ignores swap overrides, which live client-side) so points
    # reflect the program as prescribed, not whatever was last picked in the dropdown.
    training_history = []
    d = GS_START
    while d <= today:
        sess = session_for(d)
        logged = logged_activities_on(d)
        steps_goal = ((daily.get(d.isoformat()) or {}).get("movement") or {}).get("steps", {})
        training_history.append({
            "date": d.isoformat(),
            "sessionType": sess["type"],
            "loggedTypes": sorted({a["type"] for a in logged}),
            "stepGoalMet": bool(steps_goal.get("value") and steps_goal.get("goal") and steps_goal["value"] >= steps_goal["goal"]),
        })
        d += timedelta(days=1)

    dataset = {
        "meta": {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "dateRange": [min_date, max_date],
            "units": "km",
            "totalActivities": len(activities),
        },
        "topStats": top_stats,
        "reportMetrics": report_metrics,
        "dailyHistory": daily_history,
        "goal": goal,
        "program": program,
        "sessionCatalog": SESSION_CATALOG,
        "nutritionPlan": NUTRITION_PLAN,
        "weeklyBySport": weekly_by_sport_out,
        "trends": trends,
        "records": records,
        "sportColors": SPORT_COLORS,
        "sportOrder": SPORT_ORDER,
        "budgetDefaults": BUDGET_DEFAULTS,
        "dogFund": DOG_FUND,
        "pointsConfig": POINTS_CONFIG,
        "trainingHistory": training_history,
        "programStart": GS_START.isoformat(),
        "gateHash": hashlib.sha256(GATE_PASSPHRASE.encode()).hexdigest(),
    }

    html = render_html(dataset)
    with open(OUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote {OUT_PATH}")


def render_html(dataset):
    data_json = json.dumps(dataset)
    return TEMPLATE.replace("__DASHBOARD_DATA__", data_json)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>Katrine 2027</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #fff6f8;
    --card: #ffffff;
    --ink: #3d1d29;
    --muted: #8a6472;
    --line: #f0d5de;
    --accent: #7a1f3d;
    --accent2: #a46cc0;
    --accent3: #e8a3b6;
    --shadow: 0 2px 10px rgba(122, 31, 61, 0.07);
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: Nunito, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--ink);
    padding: 0 0 60px;
  }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 0 20px; }
  h1, h2, h3 { font-family: "Playfair Display", serif; }

  header.hero {
    background: linear-gradient(135deg, #7a1f3d 0%, #a8406a 100%);
    color: #fff;
    padding: 36px 20px 44px;
    margin-bottom: -28px;
  }
  header.hero .wrap { display: flex; flex-direction: column; gap: 6px; }
  header.hero .eyebrow {
    text-transform: uppercase;
    letter-spacing: .12em;
    font-size: 12px;
    color: #f6d3dd;
    font-weight: 600;
  }
  header.hero h1 { margin: 2px 0 6px; font-size: 30px; font-weight: 700; font-style: italic; }
  header.hero .sub { color: #fbe7ed; font-size: 14px; }

  .goal-row {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    margin-top: 18px;
  }
  .goal-chip {
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 13px;
    color: #fbe7ed;
  }
  .goal-chip b { font-size: 16px; display: block; color: #fff; }
  .goal-chip .delta-up { color: #f0cf7a; }
  .goal-chip .delta-down { color: #f6b8ca; }

  .plan-card {
    background: var(--card);
    border-radius: 16px;
    box-shadow: var(--shadow);
    padding: 22px;
    border-left: 5px solid var(--accent);
    margin-top: 16px;
  }
  .plan-card.caution { border-left-color: #d9a441; }
  .plan-card.light { border-left-color: var(--accent3); }
  .plan-card .plan-eyebrow { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
  .plan-card h3 { margin: 0; font-size: 20px; }
  .plan-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 4px 0 10px; }
  select.swap {
    font-family: Nunito, -apple-system, sans-serif;
    font-size: 12px;
    color: var(--ink);
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 6px 12px;
  }
  .week-day select.swap { margin-top: 8px; width: 100%; font-size: 11px; padding: 4px 4px; border-radius: 10px; }
  .plan-card .exercises { margin-top: 14px; font-size: 13px; }
  .plan-card .exercises > .exercise-row { padding: 8px 0; border-top: 1px solid var(--line); }
  .plan-card .exercises .exercise-name { padding: 0 0 6px; }
  .plan-card .exercises .exercise-suggestion { font-size: 11px; color: var(--muted); padding: 0 0 8px; }
  .plan-card .exercises .set-log-form { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .plan-card .exercises .set-log-form input { width: 70px; padding: 5px 8px; font-size: 12px; border: 1px solid var(--line); border-radius: 8px; font-family: Nunito, sans-serif; }
  .plan-card .exercises .set-log-today { margin-top: 6px; font-size: 11px; color: var(--muted); display: flex; gap: 6px; flex-wrap: wrap; }
  .plan-card .exercises .set-chip { background: var(--accent3); border-radius: 10px; padding: 2px 8px; display: inline-flex; align-items: center; gap: 4px; }
  .plan-card .exercises .set-chip-remove { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 11px; padding: 0; line-height: 1; }
  .pr-row { display: flex; justify-content: space-between; padding: 6px 0; border-top: 1px solid var(--line); font-size: 13px; }
  .pr-row:first-child { border-top: none; }
  .pr-row .pr-ex { color: var(--muted); flex: 1; margin-right: 10px; }
  .pr-row b { white-space: nowrap; }
  .rest-timer { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .rest-timer .rt-display { font-family: "Playfair Display", serif; font-size: 32px; font-weight: 700; min-width: 80px; }
  .rest-timer .rt-presets { display: flex; gap: 6px; flex-wrap: wrap; }
  .rt-presets { display: flex; gap: 6px; flex-wrap: wrap; }
  .rest-pref-select { font-size: 11px; padding: 2px 4px; border-radius: 6px; border: 1px solid var(--line); font-family: Nunito, sans-serif; color: var(--muted); }
  .rest-bubble {
    display: none; position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%);
    background: var(--ink); color: #fff; border-radius: 999px; padding: 10px 18px;
    align-items: center; gap: 14px; box-shadow: 0 8px 24px rgba(0,0,0,0.25); z-index: 500;
  }
  .rest-bubble.active { display: flex; }
  .rest-bubble .rt-bubble-label { font-size: 12px; opacity: 0.85; max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rest-bubble .rt-bubble-display { font-family: "Playfair Display", serif; font-size: 22px; font-weight: 700; min-width: 32px; text-align: center; }
  .rest-bubble .rt-bubble-actions { display: flex; gap: 6px; }
  .rest-bubble button { background: rgba(255,255,255,0.15); color: #fff; border: none; border-radius: 999px; padding: 6px 12px; font-size: 12px; font-family: Nunito, sans-serif; cursor: pointer; }
  .confetti-container { position: fixed; inset: 0; pointer-events: none; z-index: 999; overflow: hidden; }
  .confetti-piece { position: absolute; top: -10px; width: 8px; height: 14px; opacity: 0.9; animation: confetti-fall 1.8s ease-in forwards; }
  @keyframes confetti-fall { to { transform: translateY(100vh) rotate(360deg); opacity: 0; } }
  .plan-card .done-badge {
    display: inline-block;
    background: var(--accent);
    color: #fff;
    font-size: 12px;
    padding: 5px 12px;
    border-radius: 20px;
    margin-top: 4px;
  }
  .plan-card .plan-reasons { list-style: none; padding: 0; margin: 14px 0 0; font-size: 13px; color: var(--muted); }
  .plan-card .plan-reasons li { padding: 3px 0; }
  .plan-card .plan-reasons li::before { content: "– "; color: var(--accent2); }

  .week-row { display: flex; gap: 8px; margin-top: 16px; overflow-x: auto; }
  .week-day {
    flex: 1;
    min-width: 92px;
    background: var(--card);
    border-radius: 12px;
    box-shadow: var(--shadow);
    padding: 10px 8px;
    text-align: center;
  }
  .week-day.today { outline: 2px solid var(--accent); outline-offset: -1px; }
  .week-day .wd { color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: .04em; }
  .week-day .sess { font-size: 12px; margin: 6px 0; min-height: 30px; color: var(--ink); }
  .week-day .mark { font-size: 15px; color: var(--accent); }
  .week-day .mark.missed { color: var(--muted); font-size: 13px; }

  .kcal-row { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 14px; }
  .kcal-chip {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 12px;
    color: var(--muted);
  }
  .kcal-chip b { color: var(--ink); font-size: 14px; display: block; }

  .meal-group { margin-top: 18px; }
  .meal-group h4 { font-size: 14px; margin: 0 0 8px; color: var(--ink); }
  .meal-option {
    background: var(--card);
    border-radius: 14px;
    box-shadow: var(--shadow);
    padding: 14px 16px;
    margin-bottom: 8px;
  }
  .meal-option .meal-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  .meal-option .meal-head b { font-size: 14px; }
  .meal-option .meal-macro { font-size: 12px; color: var(--muted); white-space: nowrap; }
  .meal-option .meal-items { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .meal-option-remove { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 11px; padding: 0; margin-left: 6px; }
  .meal-add-form { margin-top: 2px; }
  .nutrition-note { font-size: 11px; color: var(--muted); margin-top: 14px; font-style: italic; }
  .meal-eaten-btn { margin-top: 8px; }
  .meal-option-eaten { border-left: 3px solid var(--accent); }

  .report-tabs { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
  .report-tab-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .report-card { line-height: 1.6; }
  .report-card:empty { display: none; }
  .report-card h3 { margin: 20px 0 8px; font-size: 17px; }
  .report-card .report-section:first-child h3 { margin-top: 0; }
  .report-card .report-section { margin-bottom: 20px; }
  .report-card .report-section:last-child { margin-bottom: 0; }
  .report-card p { font-size: 13.5px; margin: 0 0 10px; }
  .report-card ul { margin: 0 0 6px; padding-left: 20px; }
  .report-card li { margin-bottom: 7px; font-size: 13.5px; }
  .report-card .report-highlight { background: var(--bg); border-radius: 10px; padding: 10px 14px; font-size: 13px; margin: 10px 0; }
  .report-card .report-empty { font-size: 13px; color: var(--muted); }
  .report-card .report-title { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: 2px; }

  .stat-grid {
    position: relative;
    z-index: 2;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
  }
  .stat-card {
    background: var(--card);
    border-radius: 16px;
    box-shadow: var(--shadow);
    padding: 16px 18px;
  }
  .stat-card .label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
  .stat-card .value { font-size: 28px; font-weight: 700; margin: 4px 0 2px; }
  .stat-card .value small { font-size: 14px; font-weight: 500; color: var(--muted); }
  .stat-card .asof { font-size: 11px; color: var(--muted); }
  .stat-card svg { width: 100%; height: 36px; margin-top: 6px; display: block; }

  section { margin-top: 36px; }
  section h2 {
    font-size: 18px;
    margin: 0 0 4px;
  }
  section .section-sub { font-size: 13px; color: var(--muted); margin-bottom: 16px; }

  .card {
    background: var(--card);
    border-radius: 16px;
    box-shadow: var(--shadow);
    padding: 20px;
  }

  .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; font-size: 12px; color: var(--muted); }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }

  .tooltip {
    position: absolute;
    pointer-events: none;
    background: #7a1f3d;
    color: #fff;
    font-size: 12px;
    padding: 6px 10px;
    border-radius: 8px;
    transform: translate(-50%, -115%);
    white-space: nowrap;
    opacity: 0;
    transition: opacity .1s;
    z-index: 10;
  }
  .chart-wrap { position: relative; }

  .records-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }
  .record-card {
    background: var(--card);
    border-radius: 14px;
    box-shadow: var(--shadow);
    padding: 16px;
  }
  .record-card .label { font-size: 12px; color: var(--muted); }
  .record-card .value { font-size: 22px; font-weight: 700; margin: 4px 0 2px; }
  .record-card .date { font-size: 11px; color: var(--muted); }

  .trend-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

  footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 40px; }
  .settings-card { margin: 24px 0 0; }
  .settings-toggle-row { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-top: 10px; cursor: pointer; }
  .backup-card { margin: 16px 0 0; }
  .backup-actions { display: flex; gap: 8px; flex-wrap: wrap; }

  /* ---- fremgang / points / logging ---- */
  .snapshot-row { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 14px; }
  .snapshot-chip {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 8px 16px; font-size: 12px; color: var(--muted); flex: 1; min-width: 130px;
  }
  .snapshot-chip b { color: var(--ink); font-size: 16px; display: block; }

  .level-card { margin-top: 14px; }
  .level-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .level-head .level-name { font-family: "Playfair Display", serif; font-size: 20px; font-weight: 700; }
  .level-head .level-pts { font-size: 12px; color: var(--muted); }
  .level-bar { height: 10px; border-radius: 6px; background: var(--line); margin-top: 10px; overflow: hidden; }
  .level-bar > div { height: 100%; background: linear-gradient(90deg, var(--accent2), var(--accent)); border-radius: 6px; transition: width .3s; }
  .level-reward { font-size: 12px; color: var(--muted); margin-top: 8px; }

  .celebrate-banner {
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    color: #fff; border-radius: 14px; padding: 14px 18px; margin-top: 14px;
    font-size: 14px; font-weight: 700; box-shadow: var(--shadow);
  }

  .log-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 16px; }
  .log-form { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  .log-form input, .log-form select {
    font-family: Nunito, sans-serif; font-size: 13px; border: 1px solid var(--line);
    border-radius: 10px; padding: 8px 10px; background: var(--bg); color: var(--ink);
  }
  .log-form input[type="number"] { width: 90px; }
  .log-form input[type="date"] { width: 140px; }
  .log-form input[type="text"] { flex: 1; min-width: 120px; }
  .btn {
    font-family: Nunito, sans-serif; font-size: 13px; font-weight: 700; color: #fff;
    background: var(--accent); border: none; border-radius: 10px; padding: 8px 16px; cursor: pointer;
  }
  .btn.secondary { background: var(--accent3); color: var(--ink); }
  .btn.ghost { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  .btn.small { padding: 5px 10px; font-size: 11px; }
  .log-list { list-style: none; padding: 0; margin: 10px 0 0; font-size: 13px; }
  .log-list li { display: flex; justify-content: space-between; padding: 6px 0; border-top: 1px solid var(--line); color: var(--muted); }
  .log-list li b { color: var(--ink); }
  .log-delta { font-size: 11px; }
  .log-delta.down { color: #2f8a4e; }
  .log-delta.up { color: var(--accent); }
  .weight-trend-box { font-size: 13px; color: var(--muted); margin: 2px 0 10px; }
  .weight-trend-box b { color: var(--ink); }
  .buy-check-box { font-size: 13px; color: var(--muted); margin: 10px 0 0; }
  .buy-check-box b { color: var(--ink); }
  .buy-check-settings { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; }
  .buy-check-settings label { font-size: 12px; color: var(--muted); display: flex; flex-direction: column; gap: 3px; }
  .buy-check-settings input { width: 100px; padding: 5px 8px; font-size: 13px; border: 1px solid var(--line); border-radius: 8px; font-family: Nunito, sans-serif; }
  .buy-growth-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; }
  .buy-growth-chip {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 8px 16px; font-size: 12px; color: var(--muted); flex: 1; min-width: 100px;
  }
  .buy-growth-chip b { color: var(--ink); font-size: 15px; display: block; }
  .forgotten-savings-card { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  .forgotten-savings-card .fs-info { font-size: 13px; color: var(--muted); }
  .forgotten-savings-card .fs-amount { font-family: "Playfair Display", serif; font-size: 20px; font-weight: 700; color: var(--ink); }
  .forgotten-savings-card.pulse .fs-amount { animation: fs-pulse 0.6s ease; }
  @keyframes fs-pulse { 0% { transform: scale(1); color: var(--ink); } 40% { transform: scale(1.25); color: #2e8b57; } 100% { transform: scale(1); color: var(--ink); } }
  .save-presets { display: flex; align-items: center; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  .save-presets-label { font-size: 12px; color: var(--muted); }
  .extras-presets { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; flex-wrap: wrap; }

  /* ---- handleliste ---- */
  .shop-quickadd { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  .shop-list { list-style: none; padding: 0; margin: 14px 0 0; }
  .shop-list li {
    display: flex; align-items: center; gap: 10px; padding: 8px 4px;
    border-top: 1px solid var(--line); font-size: 14px;
  }
  .shop-list li.checked span { text-decoration: line-through; color: var(--muted); }
  .shop-list li button { margin-left: auto; background: none; border: none; color: var(--muted); cursor: pointer; font-size: 14px; }

  /* ---- budsjett ---- */
  .month-nav { display: flex; align-items: center; gap: 12px; margin-top: 10px; }
  .month-nav .btn { padding: 4px 12px; }
  .month-nav .month-label { font-weight: 700; font-size: 15px; min-width: 140px; text-align: center; }
  .cat-row { margin-top: 10px; }
  .cat-row .cat-head { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); }
  .cat-row .cat-head b { color: var(--ink); }
  .cat-bar { height: 8px; border-radius: 5px; background: var(--line); margin-top: 4px; overflow: hidden; }
  .cat-bar > div { height: 100%; border-radius: 5px; background: var(--accent2); }
  .cat-bar > div.over { background: var(--accent); }
  .cat-grace { font-size: 11px; color: var(--muted); margin-top: 4px; }
  .cat-row input.cap-edit {
    width: 64px; font-size: 11px; border: 1px solid var(--line); border-radius: 6px;
    padding: 2px 4px; background: var(--bg); color: var(--muted); text-align: right;
  }
  .fund-card { background: linear-gradient(135deg, #fff0f4, #fde6ee); border-radius: 16px; padding: 18px; margin-top: 14px; }
  .fund-card .fund-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }
  .fund-card .fund-amount { font-size: 24px; font-weight: 700; font-family: "Playfair Display", serif; }
  .fund-card .fund-eta { font-size: 12px; color: var(--muted); margin-top: 6px; }
  .fund-bar { height: 12px; border-radius: 7px; background: #fff; margin-top: 10px; overflow: hidden; }
  .fund-bar > div { height: 100%; border-radius: 7px; background: linear-gradient(90deg, var(--accent2), var(--accent)); }
  .budget-summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 16px; }

  /* ---- tabs ---- */
  .tab-nav {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    gap: 6px;
    overflow-x: auto;
    background: var(--bg);
    padding: 14px 0 10px;
    margin-top: -8px;
    border-bottom: 1px solid var(--line);
  }
  .tab-nav button {
    flex: 0 0 auto;
    font-family: Nunito, sans-serif;
    font-size: 13px;
    font-weight: 700;
    color: var(--muted);
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 8px 16px;
    cursor: pointer;
  }
  .tab-nav button.active { color: #fff; background: var(--accent); border-color: var(--accent); }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  .quiet-actions { display: flex; gap: 8px; margin: 14px 0 0; }
  .overwhelm-btn, .badday-btn { flex: 1; margin: 0; }
  .overwhelm-box {
    background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 16px; margin-top: 10px; line-height: 1.6; font-size: 14px;
  }
  #plateau-card:empty { display: none; }
  #nutrition-coach-card:empty { display: none; }

  .badday-panel { display: none; max-width: 420px; margin: 24px auto; text-align: center; }
  body.badday-active header,
  body.badday-active .wrap > *:not(.badday-panel) { display: none !important; }
  body.badday-active .badday-panel { display: block; }
  .badday-quickbtns { display: flex; flex-direction: column; gap: 12px; margin: 24px 0; }
  .badday-quickbtns > button { padding: 16px; font-size: 16px; }
  .badday-quickbtns #badday-trained-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .badday-expense-row { display: flex; gap: 8px; }
  .badday-expense-row input { flex: 1; min-width: 0; padding: 12px; font-size: 15px; border: 1px solid var(--line); border-radius: 10px; font-family: Nunito, sans-serif; box-sizing: border-box; }
  .badday-expense-row button { flex: 1; padding: 12px; font-size: 15px; }
  .badday-saved-msg { font-size: 12px; color: var(--muted); min-height: 16px; margin-top: 4px; }

  /* ---- Hjem dashboard (dark, mobile-first start page) ---- */
  body.tab-is-hjem header.hero,
  body.tab-is-hjem #stat-grid { display: none; }
  .hjem-dash {
    --hj-bg: #14151a; --hj-card: #1d1f26; --hj-card2: #23262f; --hj-ink: #f2f1f6;
    --hj-muted: #9a9bab; --hj-accent: #f6c667; --hj-accent2: #a46cc0; --hj-line: #2d2f3a;
    background: var(--hj-bg); color: var(--hj-ink); border-radius: 20px; padding: 16px;
    margin: 0 -2px 24px; font-family: Nunito, sans-serif;
  }
  .hjem-topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .hjem-greeting { font-family: "Playfair Display", serif; font-size: 19px; }
  .hjem-badday-toggle {
    background: var(--hj-card2); color: var(--hj-ink); border: 1px solid var(--hj-line);
    border-radius: 20px; padding: 6px 12px; font-size: 12px; cursor: pointer;
  }
  .hjem-why { font-size: 12px; color: var(--hj-muted); margin: -4px 0 12px; cursor: pointer; }
  .hjem-why.empty { font-style: italic; }
  .hjem-zone { margin-bottom: 18px; }
  .hjem-zone-title { font-size: 13px; color: var(--hj-muted); text-transform: uppercase; letter-spacing: .06em; margin: 0 0 8px; }
  .hjem-card {
    background: var(--hj-card); border: 1px solid var(--hj-line); border-radius: 14px;
    padding: 12px 14px; color: var(--hj-ink);
  }
  .hjem-card-title { font-size: 12px; color: var(--hj-muted); margin-bottom: 6px; }
  .hjem-briefing { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .hjem-session, .hjem-weather { grid-column: 1 / -1; }
  .hjem-session { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  .hjem-session .hs-label { font-size: 15px; font-weight: 700; }
  .hjem-session .hs-sub { font-size: 12px; color: var(--hj-muted); }
  .hjem-session .hs-readiness { font-size: 11px; padding: 3px 9px; border-radius: 12px; background: var(--hj-card2); }
  .hjem-session .hs-readiness.go { color: #7bd88f; }
  .hjem-session .hs-readiness.caution { color: var(--hj-accent); }
  .hjem-session .hs-readiness.light { color: #e37878; }
  .hjem-session .hs-link {
    background: none; border: 1px solid var(--hj-line); color: var(--hj-ink);
    border-radius: 10px; padding: 6px 10px; font-size: 12px; cursor: pointer;
  }
  .hjem-ring-card { display: flex; align-items: center; gap: 10px; }
  .hjem-ring {
    width: 56px; height: 56px; min-width: 56px; border-radius: 50%; display: flex;
    align-items: center; justify-content: center;
  }
  .hjem-ring-inner {
    width: 44px; height: 44px; border-radius: 50%; background: var(--hj-card);
    display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
  }
  .hjem-ring-label { font-size: 11px; color: var(--hj-muted); line-height: 1.4; }
  .hjem-weather { display: flex; align-items: center; justify-content: space-between; }
  .hjem-weather .hw-temp { font-size: 22px; font-weight: 700; }
  .hjem-weather .hw-desc { font-size: 12px; color: var(--hj-muted); }
  .hjem-body-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 10px; }
  .hjem-stat-chip {
    background: var(--hj-card); border: 1px solid var(--hj-line); border-radius: 12px;
    padding: 10px 12px;
  }
  .hjem-stat-chip .label { font-size: 11px; color: var(--hj-muted); text-transform: uppercase; }
  .hjem-stat-chip .value { font-size: 18px; font-weight: 700; margin-top: 2px; }
  .hjem-body .hjem-card { margin-bottom: 10px; }
  .hjem-body .hjem-card:last-child { margin-bottom: 0; }
  .hjem-autoreg ul { margin: 0; padding-left: 18px; font-size: 12px; color: var(--hj-muted); }
  .hjem-progress { padding-bottom: 86px; }
  .hjem-progress-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }
  .hjem-streak-num { font-size: 28px; font-weight: 700; font-family: "Playfair Display", serif; }
  .hjem-pr-ex { font-size: 13px; color: var(--hj-muted); }
  .hjem-pr-val { font-size: 16px; font-weight: 700; }
  .hjem-goal-bar { background: var(--hj-line); border-radius: 8px; height: 8px; overflow: hidden; margin-top: 8px; }
  .hjem-goal-bar > div { background: var(--hj-accent); height: 100%; }
  .hjem-streak-record { font-size: 12px; color: var(--hj-accent); font-weight: 700; margin-top: 2px; }
  .hjem-week-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 8px; text-align: center; }
  .hjem-week-grid b { display: block; font-size: 16px; }
  .hjem-week-grid span { display: block; font-size: 11px; color: var(--hj-muted); margin-top: 2px; }
  .hjem-reminder-banner {
    display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;
    background: rgba(246, 198, 103, 0.14); border: 1px solid var(--hj-accent); color: var(--hj-ink);
    border-radius: 12px; padding: 10px 12px; margin-bottom: 10px; font-size: 13px;
  }
  .hjem-reminder-banner button {
    background: var(--hj-accent); color: #14151a; border: none; border-radius: 8px;
    padding: 6px 12px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: Nunito, sans-serif;
  }

  .quicklog-bar {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 90;
    display: flex; background: #0f1014; border-top: 1px solid var(--hj-line, #2d2f3a);
    padding: 8px max(8px, env(safe-area-inset-left)) calc(8px + env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-right));
    gap: 6px;
  }
  .quicklog-bar button {
    flex: 1; background: none; border: none; color: #f2f1f6; display: flex;
    flex-direction: column; align-items: center; gap: 2px; padding: 8px 4px; border-radius: 12px;
    cursor: pointer; position: relative; font-family: Nunito, sans-serif;
  }
  .quicklog-bar button:active { background: #23262f; }
  .quicklog-bar .ql-icon { font-size: 20px; }
  .quicklog-bar .ql-label { font-size: 11px; color: #9a9bab; }
  .quicklog-bar .ql-badge {
    position: absolute; top: 2px; right: 18%; background: #f6c667; color: #14151a;
    font-size: 10px; font-weight: 700; border-radius: 10px; padding: 0 5px; min-width: 14px; text-align: center;
  }
  .quicklog-drawer {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 91; background: #1d1f26; color: #f2f1f6;
    border-top: 1px solid #2d2f3a; border-radius: 16px 16px 0 0; padding: 14px 16px;
    transform: translateY(100%); transition: transform .2s ease; max-height: 60vh; overflow-y: auto;
    padding-bottom: calc(76px + env(safe-area-inset-bottom));
  }
  .quicklog-drawer.open { transform: translateY(0); }
  .quicklog-drawer-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-weight: 700; }
  .quicklog-drawer-head button { background: none; border: none; color: #9a9bab; font-size: 16px; cursor: pointer; }
  .quicklog-drawer .ql-presets { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  .quicklog-drawer .ql-presets button {
    background: #23262f; border: 1px solid #2d2f3a; color: #f2f1f6; border-radius: 20px;
    padding: 8px 14px; font-size: 13px; cursor: pointer;
  }
  .quicklog-drawer input, .quicklog-drawer select {
    width: 100%; padding: 10px 12px; font-size: 14px; border: 1px solid #2d2f3a; border-radius: 10px;
    font-family: Nunito, sans-serif; background: #14151a; color: #f2f1f6; box-sizing: border-box; margin-bottom: 8px;
  }
  .quicklog-drawer .btn { width: 100%; }

  @media (max-width: 480px) {
    .hjem-briefing { grid-template-columns: 1fr 1fr; }
    .hjem-dash { padding: 14px; }
  }

  /* ---- access gate ---- */
  #gate-overlay {
    position: fixed; inset: 0; z-index: 1000;
    background: linear-gradient(135deg, #7a1f3d 0%, #a8406a 100%);
    display: flex; align-items: center; justify-content: center; padding: 20px;
  }
  #gate-overlay .gate-box {
    background: #fff; border-radius: 18px; padding: 28px 24px; max-width: 320px; width: 100%;
    text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.2);
  }
  #gate-overlay h2 { margin: 0 0 6px; font-size: 20px; color: var(--ink); }
  #gate-overlay p { font-size: 12px; color: var(--muted); margin: 0 0 16px; }
  #gate-overlay input {
    width: 100%; font-family: Nunito, sans-serif; font-size: 15px; text-align: center;
    border: 1px solid var(--line); border-radius: 10px; padding: 10px; margin-bottom: 10px;
    background: var(--bg); color: var(--ink);
  }
  #gate-overlay .btn { width: 100%; padding: 10px; }
  #gate-overlay .gate-error { color: #c0392b; font-size: 12px; margin-top: 8px; min-height: 16px; }
  #gate-overlay.shake .gate-box { animation: shake .3s; }
  @keyframes shake { 25% { transform: translateX(-6px); } 75% { transform: translateX(6px); } }

  @media (max-width: 720px) {
    .stat-grid { grid-template-columns: repeat(2, 1fr); }
    .records-grid { grid-template-columns: repeat(2, 1fr); }
    .trend-grid { grid-template-columns: 1fr; }
    header.hero h1 { font-size: 24px; }
    .week-row { overflow-x: scroll; }
    .week-day { min-width: 76px; }
    .log-grid { grid-template-columns: 1fr; }
    .budget-summary-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<div id="gate-overlay">
  <div class="gate-box">
    <h2>🔒 Privat dashboard</h2>
    <p>Dette er ikke ekte sikkerhet, bare en liten sperre mot tilfeldige besøk.</p>
    <input type="password" id="gate-input" placeholder="Passord" autocomplete="off">
    <button class="btn" id="gate-submit">Lås opp</button>
    <div class="gate-error" id="gate-error"></div>
  </div>
</div>

<header class="hero">
  <div class="wrap">
    <div class="eyebrow" id="goal-eyebrow">Training goal</div>
    <h1 id="goal-headline">Katrine 2027</h1>
    <div class="sub" id="date-range-sub"></div>
    <div class="goal-row" id="goal-chips"></div>
  </div>
</header>

<div class="wrap">
  <div class="stat-grid" id="stat-grid"></div>

  <nav class="tab-nav" id="tab-nav">
    <button data-tab="hjem">Hjem</button>
    <button data-tab="rapport">Rapport</button>
    <button data-tab="trening">Treningsplan</button>
    <button data-tab="rekorder">Rekorder</button>
    <button data-tab="kosthold">Kosthold</button>
    <button data-tab="fremgang">Fremgang</button>
    <button data-tab="handleliste">Handleliste</button>
    <button data-tab="budsjett">Budsjett</button>
    <button data-tab="statistikk">Statistikk</button>
  </nav>

  <div class="quiet-actions">
    <button class="btn ghost overwhelm-btn" id="overwhelm-btn">🫧 Jeg er overveldet</button>
    <button class="btn ghost badday-btn" id="badday-btn">🌧️ Dårlig dag</button>
  </div>
  <div id="overwhelm-out"></div>

  <div class="rest-bubble" id="rest-bubble">
    <div class="rt-bubble-label" id="rt-bubble-label">Hvile</div>
    <div class="rt-bubble-display" id="rt-bubble-display">90</div>
    <div class="rt-bubble-actions">
      <button id="rt-bubble-pause">Pause</button>
      <button id="rt-bubble-skip">Hopp over</button>
    </div>
  </div>

  <div class="badday-panel" id="badday-panel">
    <h2 style="margin-top:0;">Dårlig dag</h2>
    <div class="section-sub">Bare det viktigste i dag. Trykk en knapp for å logge, gå tilbake når du vil.</div>
    <div class="badday-quickbtns" id="badday-quickbtns"></div>
    <div class="badday-saved-msg" id="badday-saved-msg"></div>
    <button class="btn ghost" id="badday-exit" style="display:block;margin-top:24px;">Tilbake til vanlig visning</button>
  </div>

  <div class="tab-panel" data-tab="hjem">
  <div class="hjem-dash" id="hjem-dash">
    <div class="hjem-topbar">
      <div class="hjem-greeting" id="hjem-greeting"></div>
      <button class="hjem-badday-toggle" id="hjem-badday-toggle">🌧️ Dårlig dag</button>
    </div>
    <div class="hjem-why" id="hjem-why"></div>

    <div id="hjem-reminder"></div>
    <section class="hjem-zone hjem-briefing">
      <div class="hjem-card hjem-session" id="hjem-session"></div>
      <div class="hjem-card hjem-ring-card" id="hjem-kcal-ring"></div>
      <div class="hjem-card hjem-ring-card" id="hjem-savings-ring"></div>
      <div class="hjem-card hjem-weather" id="hjem-weather"></div>
    </section>

    <section class="hjem-zone hjem-body">
      <h3 class="hjem-zone-title">Kropp &amp; Form</h3>
      <div class="hjem-body-grid">
        <div class="hjem-stat-chip" id="hjem-stat-hrv"></div>
        <div class="hjem-stat-chip" id="hjem-stat-sleep"></div>
        <div class="hjem-stat-chip" id="hjem-stat-steps"></div>
        <div class="hjem-stat-chip" id="hjem-stat-rhr"></div>
      </div>
      <div class="hjem-card">
        <div class="hjem-card-title">Vekttrend</div>
        <div class="chart-wrap"><svg id="chart-weight-mini"></svg><div class="tooltip" id="tt-weight-mini"></div></div>
      </div>
      <div class="hjem-card" id="hjem-autoreg"></div>
    </section>

    <section class="hjem-zone hjem-progress">
      <h3 class="hjem-zone-title">Fremdrift</h3>
      <div class="hjem-progress-grid">
        <div class="hjem-card" id="hjem-streak"></div>
        <div class="hjem-card" id="hjem-latest-pr"></div>
        <div class="hjem-card" id="hjem-savings-goal"></div>
        <div class="hjem-card" id="hjem-week-summary"></div>
      </div>
    </section>

    <div class="quicklog-drawer" id="quicklog-drawer">
      <div class="quicklog-drawer-head">
        <span id="quicklog-drawer-title"></span>
        <button id="quicklog-drawer-close">✕</button>
      </div>
      <div id="quicklog-drawer-body"></div>
    </div>
    <nav class="quicklog-bar" id="quicklog-bar">
      <button data-ql="vann"><span class="ql-icon">💧</span><span class="ql-label">Vann</span><span class="ql-badge" id="ql-water-badge"></span></button>
      <button data-ql="mat"><span class="ql-icon">🍫</span><span class="ql-label">Mat</span></button>
      <button data-ql="utgift"><span class="ql-icon">💸</span><span class="ql-label">Utgift</span></button>
      <button data-ql="okt"><span class="ql-icon">🏋️</span><span class="ql-label">Økt</span></button>
    </nav>
  </div>
  </div>

  <div class="tab-panel" data-tab="rapport">
  <section>
    <h2>Rapport</h2>
    <div class="section-sub">Din personlige coach - en grundig gjennomgang av dataene dine, ikke bare tall og grafer.</div>
    <div class="report-tabs" id="report-tabs">
      <button class="btn secondary small report-tab-btn" data-report="morning">☀️ Morgenrapport</button>
      <button class="btn secondary small report-tab-btn" data-report="evening">🌙 Kveldsrapport</button>
      <button class="btn secondary small report-tab-btn" data-report="weekly">📊 Ukens innsikt</button>
    </div>
    <div class="card report-card" id="report-output"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="trening">
  <section>
    <h2>Treningsplan</h2>
    <div class="section-sub" id="plan-sub"></div>
    <div class="week-row" id="plan-week"></div>
    <div class="plan-card" id="plan-today"></div>
    <div class="card" id="rest-timer-card"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="rekorder">
  <section>
    <h2>Rekorder</h2>
    <div class="section-sub">Dine beste løft, oppdateres automatisk når du logger sett</div>
    <div class="card" id="pr-board-card"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="kosthold">
  <section>
    <h2>Kosthold</h2>
    <div class="section-sub">Faste, enkle alternativer - ingen logging nødvendig</div>
    <div class="kcal-row" id="kcal-row"></div>
    <div id="meal-plan"></div>
    <div class="card" id="extras-card" style="margin-top:14px;">
      <h3 style="margin:0 0 4px;font-size:15px;">Utenom planen</h3>
      <div class="section-sub" style="margin-bottom:10px;">Spiste eller drakk du noe ekstra - eller en hel lunsj/middag ute? Logg et anslag her, ingen fullstendig matdagbok nødvendig.</div>
      <div class="extras-presets">
        <button class="btn secondary small" data-extra-preset="Sjokolade" data-extra-kcal="250">+ Sjokolade</button>
        <button class="btn secondary small" data-extra-preset="Glass vin" data-extra-kcal="120">+ Glass vin</button>
        <button class="btn secondary small" data-extra-preset="Øl" data-extra-kcal="150">+ Øl</button>
      </div>
      <div class="log-form">
        <input type="text" id="extra-name" placeholder="Hva var det?">
        <input type="number" step="10" id="extra-kcal" placeholder="kcal (valgfritt)">
        <button class="btn" id="extra-add">Legg til</button>
      </div>
      <div id="extras-today-total"></div>
      <ul class="log-list" id="extras-list"></ul>
    </div>
    <div class="card" id="nutrition-coach-card" style="margin-top:14px;"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="fremgang">
  <section>
    <h2>Fremgang</h2>
    <div class="section-sub">Poeng, nivå og ukentlig snapshot - alt regnes ut fra ekte data, ingenting telles manuelt</div>
    <div id="celebrate-banner"></div>
    <div class="card level-card" id="level-card"></div>
    <div class="snapshot-row" id="weekly-snapshot"></div>
    <div class="card" id="plateau-card"></div>
    <div class="log-grid">
      <div class="card">
        <h3 style="margin:0 0 4px;font-size:15px;">Vekt</h3>
        <div class="section-sub" style="margin-bottom:0;">Logg hver uke</div>
        <div class="log-form">
          <input type="date" id="weight-date">
          <input type="number" step="0.1" id="weight-kg" placeholder="kg">
          <button class="btn" id="weight-add">Lagre</button>
        </div>
        <div id="weight-trend"></div>
        <div class="chart-wrap"><svg id="chart-weight"></svg><div class="tooltip" id="tt-weight"></div></div>
        <ul class="log-list" id="weight-list"></ul>
      </div>
      <div class="card">
        <h3 style="margin:0 0 4px;font-size:15px;">Kroppsmål</h3>
        <div class="section-sub" style="margin-bottom:0;">Logg den 1. hver måned</div>
        <div class="log-form">
          <input type="date" id="measure-date">
          <input type="number" step="0.5" id="measure-waist" placeholder="Mage (cm)">
          <input type="number" step="0.5" id="measure-hips" placeholder="Hofte (cm)">
          <input type="number" step="0.5" id="measure-arm" placeholder="Arm (cm)">
          <button class="btn" id="measure-add">Lagre</button>
        </div>
        <ul class="log-list" id="measure-list"></ul>
      </div>
    </div>
  </section>
  </div>

  <div class="tab-panel" data-tab="handleliste">
  <section>
    <h2>Handleliste</h2>
    <div class="section-sub">Bygget fra matplanen din - kryss av det du har kjøpt</div>
    <div class="card">
      <div class="log-form">
        <input type="text" id="shop-input" placeholder="Legg til vare...">
        <button class="btn" id="shop-add">Legg til</button>
      </div>
      <div class="shop-quickadd">
        <button class="btn secondary small" id="shop-quickadd-protein">+ Faste proteinvarer</button>
        <button class="btn secondary small" id="shop-quickadd-meals">+ Fra måltidsideene</button>
        <button class="btn ghost small" id="shop-clear-checked">Fjern det som er kjøpt</button>
      </div>
      <ul class="shop-list" id="shop-list"></ul>
    </div>
  </section>
  </div>

  <div class="tab-panel" data-tab="budsjett">
  <section>
    <h2>Budsjett</h2>
    <div class="section-sub">Alle transaksjoner logges manuelt, for full oversikt per kategori</div>
    <div class="card">
      <div class="month-nav">
        <button class="btn ghost small" id="month-prev">‹</button>
        <div class="month-label" id="month-label"></div>
        <button class="btn ghost small" id="month-next">›</button>
      </div>
      <div class="log-form">
        <input type="date" id="tx-date">
        <input type="number" step="1" id="tx-amount" placeholder="Beløp (kr)">
        <select id="tx-category"></select>
        <input type="text" id="tx-name" placeholder="Hva var det?">
        <button class="btn" id="tx-add">Legg til</button>
      </div>
      <div id="cat-breakdown"></div>
      <div class="budget-summary-grid" id="budget-summary"></div>
      <h3 style="margin:20px 0 4px;font-size:15px;">Transaksjoner denne måneden</h3>
      <ul class="log-list" id="tx-list"></ul>
    </div>

    <div class="fund-card" id="fund-card"></div>
    <div class="card forgotten-savings-card" id="forgotten-savings-card" style="margin-top:14px;"></div>
    <div class="card" style="margin-top:14px;">
      <h3 style="margin:0 0 4px;font-size:15px;">Kjøpe eller spare?</h3>
      <div class="section-sub" style="margin-bottom:0;">Var du fristet til å kjøpe noe? Sjekk hva det egentlig koster deg, og spar det i hundefondet i stedet hvis du lar være.</div>
      <div class="log-form">
        <input type="number" step="1" id="save-amount" placeholder="Beløp (kr)">
        <input type="text" id="save-name" placeholder="Fristet av hva?">
        <button class="btn ghost" id="buy-check">Sjekk</button>
        <button class="btn" id="save-add">Spar i hundefondet</button>
      </div>
      <div class="buy-check-settings">
        <label>Timelønn (kr)<input type="number" step="10" id="buy-wage" placeholder="f.eks. 250"></label>
        <label>Forventet årlig avkastning (%)<input type="number" step="0.5" id="buy-rate" placeholder="7"></label>
      </div>
      <div id="buy-check-out"></div>
      <div class="save-presets">
        <span class="save-presets-label">Rask sparing:</span>
        <button class="btn secondary small" data-preset="20">+20 kr</button>
        <button class="btn secondary small" data-preset="50">+50 kr</button>
        <button class="btn secondary small" data-preset="100">+100 kr</button>
      </div>
    </div>
  </section>
  </div>

  <div class="tab-panel" data-tab="statistikk">
  <section>
    <h2>This week vs. recent weeks</h2>
    <div class="section-sub">Sessions, time and distance by sport, last 10 weeks</div>
    <div class="card">
      <div class="legend" id="sport-legend"></div>
      <div class="chart-wrap"><svg id="chart-weekly-sport"></svg><div class="tooltip" id="tt-weekly"></div></div>
    </div>
  </section>

  <section>
    <h2>Trends</h2>
    <div class="section-sub">Weekly averages over your full history</div>
    <div class="trend-grid">
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Training load</div>
        <div class="chart-wrap"><svg id="chart-load"></svg><div class="tooltip" id="tt-load"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Resting heart rate</div>
        <div class="chart-wrap"><svg id="chart-rhr"></svg><div class="tooltip" id="tt-rhr"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">HRV (last night avg)</div>
        <div class="chart-wrap"><svg id="chart-hrv"></svg><div class="tooltip" id="tt-hrv"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Sleep (hours/night avg)</div>
        <div class="chart-wrap"><svg id="chart-sleep"></svg><div class="tooltip" id="tt-sleep"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Treningsvolum (vekt × reps per uke)</div>
        <div class="chart-wrap"><svg id="chart-volume"></svg><div class="tooltip" id="tt-volume"></div></div>
      </div>
    </div>
  </section>

  <section>
    <h2>Records</h2>
    <div class="section-sub">Your biggest days and sessions</div>
    <div class="records-grid" id="records-grid"></div>
  </section>
  </div>

  <div class="card settings-card" id="settings-card">
    <h3 style="margin:0 0 4px;font-size:15px;">Innstillinger</h3>
    <label class="settings-toggle-row">
      <input type="checkbox" id="settings-personality-toggle">
      <span>Personlighet (konfetti og påminnelser)</span>
    </label>
    <label class="settings-toggle-row">
      <input type="checkbox" id="settings-vacation-toggle">
      <span>Ferie/pause-modus - ingen påminnelser, streaken fryses</span>
    </label>
  </div>

  <div class="card backup-card" id="backup-card">
    <h3 style="margin:0 0 4px;font-size:15px;">Sikkerhetskopi</h3>
    <div class="section-sub" style="margin-bottom:10px;">Vekt, mål, treningssett, handleliste og transaksjoner lagres kun i denne nettleseren. Last ned en kopi jevnlig, eller gjenopprett den på en annen enhet.</div>
    <div class="backup-actions">
      <button class="btn secondary small" id="backup-export">Last ned kopi</button>
      <button class="btn ghost small" id="backup-import-btn">Gjenopprett fra fil</button>
      <input type="file" id="backup-import-file" accept="application/json" style="display:none;">
    </div>
    <div id="backup-status" class="section-sub" style="margin:8px 0 0;"></div>
  </div>

  <footer id="footer"></footer>
</div>

<script>
const DATA = __DASHBOARD_DATA__;

// ---------------------------------------------------------------- settings
const SETTINGS_KEY = "garminDashboardSettings_v1";
function loadSettings() {
  return Object.assign({
    dailyKcal: DATA.nutritionPlan.dailyKcal,
    savingsTarget: DATA.dogFund.target,
    personalityEnabled: true,
  }, loadLS(SETTINGS_KEY, {}));
}
function saveSettings(s) { saveLS(SETTINGS_KEY, s); }
(function applySettings() {
  const s = loadSettings();
  DATA.nutritionPlan.dailyKcal = s.dailyKcal;
  DATA.dogFund.target = s.savingsTarget;
})();

// ---------------------------------------------------------------- mitt hvorfor
const WHY_KEY = "garminDashboardWhy_v1";
function loadWhy() { return loadLS(WHY_KEY, ""); }
function saveWhy(v) { saveLS(WHY_KEY, v); }

// ---------------------------------------------------------------- ferie / pause-modus
const VACATION_KEY = "garminDashboardVacation_v1";
function loadVacationRanges() { return loadLS(VACATION_KEY, []); }
function saveVacationRanges(r) { saveLS(VACATION_KEY, r); }
function isVacationActive() {
  const r = loadVacationRanges();
  return r.length > 0 && !r[r.length - 1].end;
}
function setVacationActive(active) {
  const r = loadVacationRanges();
  const open = r.length && !r[r.length - 1].end;
  if (active && !open) r.push({ start: todayISO(), end: null });
  else if (!active && open) r[r.length - 1].end = todayISO();
  saveVacationRanges(r);
}
function inVacationRange(date) {
  return loadVacationRanges().some(r => date >= r.start && date <= (r.end || "9999-99-99"));
}

// ---------------------------------------------------------------- access gate
(function () {
  const GATE_KEY = "garminDashboardUnlocked_v1";
  const overlay = document.getElementById("gate-overlay");
  if (localStorage.getItem(GATE_KEY) === "1") { overlay.remove(); return; }

  async function sha256Hex(text) {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
  }
  async function tryUnlock() {
    const val = document.getElementById("gate-input").value;
    const hash = await sha256Hex(val);
    if (hash === DATA.gateHash) {
      localStorage.setItem(GATE_KEY, "1");
      overlay.remove();
    } else {
      document.getElementById("gate-error").textContent = "Feil passord";
      overlay.classList.remove("shake");
      void overlay.offsetWidth;
      overlay.classList.add("shake");
    }
  }
  document.getElementById("gate-submit").addEventListener("click", tryUnlock);
  document.getElementById("gate-input").addEventListener("keydown", e => {
    if (e.key === "Enter") tryUnlock();
  });
})();

function fmtDate(s) {
  if (!s) return "";
  const d = new Date(s + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
function fmtShort(s) {
  if (!s) return "";
  const d = new Date(s + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ---------------------------------------------------------------- header
document.getElementById("date-range-sub").textContent =
  `${DATA.meta.totalActivities} activities tracked, ${fmtDate(DATA.meta.dateRange[0])} - ${fmtDate(DATA.meta.dateRange[1])}`;

const goalChips = document.getElementById("goal-chips");
const g = DATA.goal;
function deltaSpan(pct) {
  if (pct === null || pct === undefined) return "";
  const cls = pct >= 0 ? "delta-up" : "delta-down";
  const sign = pct >= 0 ? "+" : "";
  return ` <span class="${cls}">${sign}${pct}%</span>`;
}
if (g.recentActiveCaloriesPerWeek) {
  goalChips.innerHTML += `<div class="goal-chip">Active calories / week<b>${g.recentActiveCaloriesPerWeek.toLocaleString()}${deltaSpan(g.caloriesPctChange)}</b></div>`;
}
if (g.recentSessionsPerWeek) {
  goalChips.innerHTML += `<div class="goal-chip">Sessions / week<b>${g.recentSessionsPerWeek}</b></div>`;
}
if (g.recentStepsPerDay) {
  goalChips.innerHTML += `<div class="goal-chip">Steps / day<b>${g.recentStepsPerDay.toLocaleString()}${deltaSpan(g.stepsPctChange)}</b></div>`;
}

// ---------------------------------------------------------------- tabs
const ACTIVE_TAB_KEY = "garminDashboardActiveTab_v1";
function showTab(tab) {
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.toggle("active", p.dataset.tab === tab));
  document.querySelectorAll("#tab-nav button").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  document.body.classList.toggle("tab-is-hjem", tab === "hjem");
  localStorage.setItem(ACTIVE_TAB_KEY, tab);
}
document.querySelectorAll("#tab-nav button").forEach(btn => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});
showTab(localStorage.getItem(ACTIVE_TAB_KEY) || "hjem");

// ---------------------------------------------------------------- training plan
const PLAN_OVERRIDES_KEY = "garminDashboardPlanOverrides_v1";
const SWAP_OPTIONS = ["gsA", "gsB", "gsC", "cyc", "walk", "rest"];
const SWAP_NAMES = { gsA: "Styrke A", gsB: "Styrke B", gsC: "Styrke C", cyc: "Sykling", walk: "Gåtur", rest: "Hvile" };

function loadPlanOverrides() {
  try { return JSON.parse(localStorage.getItem(PLAN_OVERRIDES_KEY) || "{}"); } catch (e) { return {}; }
}
function savePlanOverrides(o) { localStorage.setItem(PLAN_OVERRIDES_KEY, JSON.stringify(o)); }

function resolvePlanDay(d, overrides) {
  const ov = overrides[d.date];
  const cat = DATA.sessionCatalog;
  let key, label, type, exercises, cycleNote;
  if (ov && cat[ov]) {
    key = ov;
    label = cat[ov].label + (ov === "cyc" ? ` (${DATA.program.weekCycleNote})` : "");
    type = cat[ov].type;
    exercises = cat[ov].exercises || null;
    cycleNote = cat[ov].type === "cycling" ? cat[ov].note : null;
  } else {
    key = d.defaultKey;
    label = d.sessionLabel;
    type = d.sessionType;
    exercises = (cat[d.defaultKey] || {}).exercises || null;
    cycleNote = type === "cycling" ? cat.cyc.note : null;
  }
  const matched = type === "rest" ? null : (d.loggedActivities || []).find(a => a.type === type) || null;
  return { key, label, type, exercises, cycleNote, done: type === "rest" ? null : !!matched, matchedActivity: matched };
}

function swapSelectHtml(date, resolvedKey) {
  const selKey = SWAP_OPTIONS.includes(resolvedKey) ? resolvedKey : "rest";
  const opts = SWAP_OPTIONS.map(k => `<option value="${k}" ${k === selKey ? "selected" : ""}>${SWAP_NAMES[k]}</option>`).join("");
  return `<select class="swap" data-date="${date}" aria-label="Bytt økt">${opts}</select>`;
}

const SET_LOG_KEY = "garminDashboardSetLog_v1";
function loadSetLogAll() { return loadLS(SET_LOG_KEY, []); }
function loadSetLog() { return loadSetLogAll().filter(s => !s.deleted); }
function saveSetLog(l) { saveLS(SET_LOG_KEY, l); }
function addSet(exKey, label, date, weight, reps) {
  const log = loadSetLogAll();
  log.push({ id: "set-" + Date.now() + Math.random(), exercise: exKey, label, date, weight, reps });
  saveSetLog(log);
}
function softDeleteSet(id) {
  const all = loadSetLogAll();
  const item = all.find(s => s.id === id);
  if (item) { item.deleted = true; item.deletedAt = Date.now(); }
  saveSetLog(all);
}
function lastSetFor(exKey, date) {
  const entries = loadSetLog().filter(s => s.exercise === exKey).sort((a, b) => a.date.localeCompare(b.date));
  const upToToday = entries.filter(s => s.date <= date);
  return upToToday.length ? upToToday[upToToday.length - 1] : null;
}
function setsFor(exKey, date) { return loadSetLog().filter(s => s.exercise === exKey && s.date === date); }

// ---- rest timer: shared floating-bubble module ----
const REST_PREFS_KEY = "garminDashboardRestPrefs_v1";
function loadRestPrefs() { return loadLS(REST_PREFS_KEY, {}); }
function saveRestPrefs(p) { saveLS(REST_PREFS_KEY, p); }
function restDurationFor(exKey) { return loadRestPrefs()[exKey] || 90; }

let restTimerInterval = null;
let restTimerRemaining = 0;
let restTimerPaused = false;

function playRestBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    osc.connect(gain);
    gain.connect(ctx.destination);
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) { /* audio not available, vibration still fires */ }
}
function updateRestBubbleDisplay() {
  document.getElementById("rt-bubble-display").textContent = restTimerRemaining;
}
function stopRestTimer() {
  if (restTimerInterval) clearInterval(restTimerInterval);
  restTimerInterval = null;
  document.getElementById("rest-bubble").classList.remove("active");
}
function tickRestTimer() {
  if (restTimerPaused) return;
  restTimerRemaining--;
  updateRestBubbleDisplay();
  if (restTimerRemaining <= 0) {
    if (window.navigator.vibrate) window.navigator.vibrate([200, 100, 200]);
    playRestBeep();
    stopRestTimer();
  }
}
function startRestTimer(seconds, label) {
  stopRestTimer();
  restTimerRemaining = seconds;
  restTimerPaused = false;
  document.getElementById("rt-bubble-label").textContent = label || "Hvile";
  document.getElementById("rt-bubble-pause").textContent = "Pause";
  updateRestBubbleDisplay();
  document.getElementById("rest-bubble").classList.add("active");
  restTimerInterval = setInterval(tickRestTimer, 1000);
}
document.getElementById("rt-bubble-pause").addEventListener("click", () => {
  restTimerPaused = !restTimerPaused;
  document.getElementById("rt-bubble-pause").textContent = restTimerPaused ? "Fortsett" : "Pause";
});
document.getElementById("rt-bubble-skip").addEventListener("click", stopRestTimer);

function parseRepTarget(text) {
  const m = text.match(/(\d+)\s*[×x]\s*(\d+)(?:\s*[–\-]\s*(\d+))?/);
  if (!m) return null;
  const low = parseInt(m[2], 10);
  const high = m[3] ? parseInt(m[3], 10) : low;
  const after = text.slice(m.index + m[0].length).trimStart();
  const timeBased = after.startsWith("s") || after.startsWith("sek");
  return { low, high, timeBased };
}

function progressSuggestion(exKey, text, readiness) {
  const target = parseRepTarget(text);
  if (!target || target.timeBased) return null;
  const best = bestSetFor(exKey);
  if (!best || !best.reps) return null;
  const easing = readiness === "light" || readiness === "caution";
  if (best.reps >= target.high) {
    if (easing) return `Du klarte toppen av målet (${best.reps} reps) forrige gang, men hold vekten i dag siden kroppen signaliserer ekstra belastning.`;
    if (best.weight != null) return `Du klarte ${best.reps} reps forrige gang - prøv ${(best.weight + 2.5).toLocaleString()} kg i dag.`;
    return `Du klarte ${best.reps} reps forrige gang - prøv noen flere reps i dag.`;
  }
  if (best.reps < target.low) {
    return `Hold samme vekt og jobb mot ${target.low}+ reps i dag.`;
  }
  return `Du er i målsonen (${target.low}–${target.high} reps) - fortsett på samme vekt.`;
}

function exerciseRowHtml(sessKey, idx, text, date, readiness) {
  const exKey = sessKey + "::" + idx;
  const last = lastSetFor(exKey, date);
  const todaySets = setsFor(exKey, date);
  const pref = restDurationFor(exKey);
  const restOptions = [60, 90, 120, 180].map(s => `<option value="${s}" ${s === pref ? "selected" : ""}>${s}s</option>`).join("");
  const suggestion = progressSuggestion(exKey, text, readiness);
  return `<div class="exercise-row" data-ex="${exKey}">
    <div class="exercise-name">${text}</div>
    ${suggestion ? `<div class="exercise-suggestion">💡 ${suggestion}</div>` : ""}
    <div class="set-log-form">
      <input type="number" step="0.5" class="set-weight-input" placeholder="kg" ${last && last.weight != null ? `value="${last.weight}"` : ""}>
      <input type="number" class="set-reps-input" placeholder="reps" ${last ? `value="${last.reps}"` : ""}>
      <button class="btn secondary small set-log-add">+ Logg sett</button>
      ${last ? `<button class="btn ghost small set-log-fill" style="font-size:11px;">Bruk forrige: ${last.weight != null ? last.weight + " kg × " : ""}${last.reps} reps</button>` : `<span style="font-size:11px;color:var(--muted)">ingen tidligere logg</span>`}
      <select class="rest-pref-select" data-ex="${exKey}">${restOptions}</select>
    </div>
    <div class="set-log-today">${todaySets.map((s, i) => `<span class="set-chip">Sett ${i + 1}: ${s.weight != null ? s.weight + " kg × " : ""}${s.reps} reps<button class="set-chip-remove" data-set-remove="${s.id}">✕</button></span>`).join("")}</div>
  </div>`;
}

function isBetterSet(a, b) {
  if (!b) return true;
  if (a.weight != null && b.weight != null) {
    return a.weight > b.weight || (a.weight === b.weight && a.reps > b.reps);
  }
  return a.reps > b.reps;
}
function bestSetFor(exKey) {
  const entries = loadSetLog().filter(s => s.exercise === exKey);
  let best = null;
  entries.forEach(s => { if (isBetterSet(s, best)) best = s; });
  return best;
}
function triggerConfetti() {
  const colors = ["#7a1f3d", "#e8a3b6", "#a46cc0", "#f6c667", "#9b3456"];
  const container = document.createElement("div");
  container.className = "confetti-container";
  for (let i = 0; i < 24; i++) {
    const piece = document.createElement("div");
    piece.className = "confetti-piece";
    piece.style.left = Math.random() * 100 + "vw";
    piece.style.background = colors[Math.floor(Math.random() * colors.length)];
    piece.style.animationDelay = (Math.random() * 0.3) + "s";
    piece.style.transform = `rotate(${Math.random() * 360}deg)`;
    container.appendChild(piece);
  }
  document.body.appendChild(container);
  setTimeout(() => container.remove(), 2200);
}

function renderPrBoard() {
  const card = document.getElementById("pr-board-card");
  const log = loadSetLog();
  if (!log.length) {
    card.innerHTML = `<h3 style="margin:0 0 4px;font-size:15px;">Personlige rekorder</h3><div class="section-sub" style="margin:0;">Logg sett på treningsøktene for å se rekordene dine her.</div>`;
    return;
  }
  const byEx = {};
  log.forEach(s => {
    const cur = byEx[s.exercise];
    if (isBetterSet(s, cur)) byEx[s.exercise] = { label: s.label, weight: s.weight, reps: s.reps, date: s.date };
  });
  const rows = Object.values(byEx).sort((a, b) => b.date.localeCompare(a.date));
  card.innerHTML = `<h3 style="margin:0 0 10px;font-size:15px;">Personlige rekorder</h3>` +
    rows.map(r => `<div class="pr-row"><span class="pr-ex">${r.label}</span><b>${r.weight != null ? r.weight + " kg × " + r.reps : r.reps + " reps"}</b></div>`).join("");
}

function renderRestTimer() {
  const card = document.getElementById("rest-timer-card");
  card.innerHTML = `
    <h3 style="margin:0 0 4px;font-size:15px;">Hviletimer</h3>
    <div class="section-sub" style="margin:0 0 10px;">Starter automatisk når du logger et sett (lengden er satt per øvelse). Du kan også starte den manuelt her.</div>
    <div class="rt-presets">
      <button class="btn secondary small" data-rt="60">60 s</button>
      <button class="btn secondary small" data-rt="90">90 s</button>
      <button class="btn secondary small" data-rt="120">120 s</button>
      <button class="btn secondary small" data-rt="180">180 s</button>
      <button class="btn ghost small" id="rt-stop">Stopp</button>
    </div>
  `;
  card.querySelectorAll("[data-rt]").forEach(btn =>
    btn.addEventListener("click", () => startRestTimer(parseInt(btn.dataset.rt, 10), "Hviletimer")));
  document.getElementById("rt-stop").addEventListener("click", stopRestTimer);
}

function renderPlan() {
  const p = DATA.program;
  if (!p) return;
  const overrides = loadPlanOverrides();

  const weekTag = p.weekIsDeload ? `Uke ${p.currentWeek} · Deload` : `Uke ${p.currentWeek} av 4`;
  document.getElementById("plan-sub").textContent = `${weekTag} · ${p.weekFocus}`;

  const todayDay = p.week.find(d => d.isToday);
  const resolved = resolvePlanDay(todayDay, overrides);
  const readinessLabel = { go: "Klar for økta", caution: "Vurder en lettere variant", light: "Prioriter hvile i dag" }[p.today.readiness];
  const card = document.getElementById("plan-today");
  card.className = "plan-card " + p.today.readiness;

  let body = `<div class="plan-eyebrow">I dag · ${readinessLabel}</div>`;
  body += `<div class="plan-head"><h3>${resolved.label}</h3>${swapSelectHtml(todayDay.date, resolved.key)}</div>`;

  if (resolved.done) {
    const extra = resolved.matchedActivity ? `: ${resolved.matchedActivity.name} (${resolved.matchedActivity.minutes} min)` : "";
    body += `<div class="done-badge">✓ Gjort${extra}</div>`;
  } else if (resolved.type === "rest") {
    body += `<div style="color:var(--muted);font-size:13px">Ingen planlagt økt i dag. Ta en rolig tur hvis du har overskudd.</div>`;
  } else {
    if (resolved.exercises) {
      body += `<div class="exercises">${resolved.exercises.map((e, idx) => exerciseRowHtml(resolved.key, idx, e, todayDay.date, p.today.readiness)).join("")}</div>`;
    }
    if (resolved.cycleNote) {
      body += `<div class="exercises"><div>${resolved.cycleNote}</div></div>`;
    }
    if (resolved.type === "strength") {
      body += `<div style="margin-top:10px;font-size:13px;color:var(--muted)">Kjenner du det i kneet på en øvelse? Reduser bevegelsesutslaget eller bytt den ut - ikke press gjennom smerte.</div>`;
    }
  }

  body += `<ul class="plan-reasons">${p.today.reasons.map(r => `<li>${r}</li>`).join("")}</ul>`;
  card.innerHTML = body;

  card.querySelectorAll(".exercise-row").forEach(row => {
    const exKey = row.dataset.ex;
    const wIn = row.querySelector(".set-weight-input");
    const rIn = row.querySelector(".set-reps-input");
    const fillBtn = row.querySelector(".set-log-fill");
    if (fillBtn) {
      fillBtn.addEventListener("click", () => {
        const last = lastSetFor(exKey, todayDay.date);
        if (!last) return;
        if (last.weight != null) wIn.value = last.weight;
        rIn.value = last.reps;
      });
    }
    row.querySelectorAll("[data-set-remove]").forEach(delBtn => {
      delBtn.addEventListener("click", () => {
        softDeleteSet(delBtn.dataset.setRemove);
        renderPlan();
        renderPrBoard();
      });
    });
    const restSelect = row.querySelector(".rest-pref-select");
    if (restSelect) {
      restSelect.addEventListener("change", () => {
        const prefs = loadRestPrefs();
        prefs[exKey] = parseInt(restSelect.value, 10);
        saveRestPrefs(prefs);
      });
    }
    const addBtn = row.querySelector(".set-log-add");
    if (!addBtn) return;
    addBtn.addEventListener("click", () => {
      const weight = wIn.value ? parseFloat(wIn.value) : null;
      const reps = parseInt(rIn.value, 10);
      if (!reps) return;
      const label = row.querySelector(".exercise-name").textContent;
      const prevBest = bestSetFor(exKey);
      addSet(exKey, label, todayDay.date, weight, reps);
      if (isBetterSet({ weight, reps }, prevBest) && loadSettings().personalityEnabled) triggerConfetti();
      startRestTimer(restDurationFor(exKey), label);
      renderPlan();
      renderPrBoard();
    });
  });

  const weekEl = document.getElementById("plan-week");
  weekEl.innerHTML = p.week.map(d => {
    const r = resolvePlanDay(d, overrides);
    const missed = r.type !== "rest" && !d.isToday && d.date < p.today.date && r.done !== true;
    const mark = r.done === true ? "✓"
      : d.isToday ? "●"
      : r.type === "rest" ? "–"
      : missed ? "○"
      : "";
    return `<div class="week-day${d.isToday ? " today" : ""}">
      <div class="wd">${d.weekday}</div>
      <div class="sess">${r.label}</div>
      <div class="mark${missed ? " missed" : ""}" ${missed ? `title="Ikke logget - helt greit, fortsett i dag."` : ""}>${mark}</div>
      ${swapSelectHtml(d.date, r.key)}
    </div>`;
  }).join("");

  document.querySelectorAll("select.swap").forEach(sel => {
    sel.addEventListener("change", () => {
      const current = loadPlanOverrides();
      const day = p.week.find(x => x.date === sel.dataset.date);
      const isDefault = sel.value === day.defaultKey
        || (sel.value === "rest" && (day.defaultKey === "rest" || day.defaultKey === "restW"));
      if (isDefault) {
        delete current[sel.dataset.date];
      } else {
        current[sel.dataset.date] = sel.value;
      }
      savePlanOverrides(current);
      renderPlan();
    });
  });
}
renderPlan();
renderPrBoard();
renderRestTimer();

// ---------------------------------------------------------------- nutrition
const EXTRAS_KEY = "garminDashboardExtras_v1";
const CUSTOM_MEALS_KEY = "garminDashboardCustomMeals_v1";
const MEAL_LOG_KEY = "garminDashboardMealLog_v1";
function loadCustomMeals() { return Object.assign({ lunch: [], snack: [], dinner: [] }, loadLS(CUSTOM_MEALS_KEY, {})); }
function saveCustomMeals(m) { saveLS(CUSTOM_MEALS_KEY, m); }

function loadMealLog() { return loadLS(MEAL_LOG_KEY, []); }
function saveMealLog(l) { saveLS(MEAL_LOG_KEY, l); }
function mealLoggedFor(date, type) { return loadMealLog().find(m => m.date === date && m.type === type) || null; }
function logMealEaten(type, opt) {
  const log = loadMealLog().filter(m => !(m.date === todayISO() && m.type === type));
  log.push({ date: todayISO(), type, name: opt.name, kcal: opt.kcal, protein: opt.protein });
  saveMealLog(log);
}
function unlogMeal(type) {
  saveMealLog(loadMealLog().filter(m => !(m.date === todayISO() && m.type === type)));
}
function isMealEatenToday(type, name) {
  const m = mealLoggedFor(todayISO(), type);
  return !!m && m.name === name;
}
// totals actually eaten on a given date: fixed breakfast + whichever lunch/snack/dinner
// options were marked eaten that day + anything logged as an "extra"
function dayNutritionTotals(date) {
  const n = DATA.nutritionPlan;
  const meals = loadMealLog().filter(m => m.date === date);
  const extrasForDay = loadExtras().filter(e => e.date === date);
  const extrasTotal = extrasForDay.reduce((s, e) => s + (e.kcal || 0), 0);
  return {
    kcal: n.breakfast.kcal + meals.reduce((s, m) => s + (m.kcal || 0), 0) + extrasTotal,
    protein: n.breakfast.protein + meals.reduce((s, m) => s + (m.protein || 0), 0),
    mealsLogged: meals,
    extras: extrasForDay,
  };
}

function mealOptionHtml(opt, removeId, toggle) {
  const eaten = !!(toggle && toggle.eaten);
  return `<div class="meal-option${eaten ? " meal-option-eaten" : ""}">
    <div class="meal-head"><b>${opt.name}</b><span class="meal-macro">${opt.kcal} kcal · ${opt.protein} g protein${removeId ? `<button class="meal-option-remove" data-meal-remove="${removeId}">✕</button>` : ""}</span></div>
    ${opt.items && opt.items.length ? `<div class="meal-items">${opt.items.join(" · ")}</div>` : ""}
    ${toggle ? `<button class="btn ghost small meal-eaten-btn" data-meal-type="${toggle.type}" data-meal-idx="${toggle.idx}">${eaten ? "✓ Spist i dag" : "Merk som spist i dag"}</button>` : ""}
  </div>`;
}

function renderNutrition() {
  const n = DATA.nutritionPlan;
  if (!n) return;

  document.getElementById("kcal-row").innerHTML = `
    <div class="kcal-chip">Mål<b>${n.dailyKcal} kcal</b></div>
    <div class="kcal-chip">Protein<b>${n.proteinMin} g+</b></div>
    <div class="kcal-chip kcal-goal-edit">
      <input type="number" step="50" id="kcal-goal-input" value="${n.dailyKcal}" style="width:70px;">
      <button class="btn ghost small" id="kcal-goal-save">Lagre mål</button>
    </div>
  `;
  document.getElementById("kcal-goal-save").addEventListener("click", () => {
    const val = parseInt(document.getElementById("kcal-goal-input").value, 10);
    if (!val) return;
    const s = loadSettings();
    s.dailyKcal = val;
    saveSettings(s);
    DATA.nutritionPlan.dailyKcal = val;
    renderNutrition();
    renderExtras();
    renderHjemKcalRing();
  });

  const b = n.breakfast;
  let html = `<div class="meal-group"><h4>${b.label}</h4>${mealOptionHtml({ name: b.label, items: b.items, kcal: b.kcal, protein: b.protein })}</div>`;
  const custom = loadCustomMeals();
  ["lunch", "snack", "dinner"].forEach(key => {
    const group = n[key];
    const customOpts = custom[key] || [];
    html += `<div class="meal-group"><h4>${group.label}</h4>
      ${group.options.map((o, idx) => mealOptionHtml(o, null, { type: key, idx, eaten: isMealEatenToday(key, o.name) })).join("")}
      ${customOpts.map((o, i) => mealOptionHtml(o, o.id, { type: key, idx: group.options.length + i, eaten: isMealEatenToday(key, o.name) })).join("")}
      <div class="log-form meal-add-form">
        <input type="text" id="meal-add-name-${key}" placeholder="Eget forslag - navn">
        <input type="number" step="10" id="meal-add-kcal-${key}" placeholder="kcal">
        <input type="number" step="1" id="meal-add-protein-${key}" placeholder="protein g">
        <button class="btn ghost small" data-meal-add="${key}">Legg til</button>
      </div>
    </div>`;
  });
  html += `<div class="nutrition-note">${n.note}</div>`;
  document.getElementById("meal-plan").innerHTML = html;

  document.querySelectorAll(".meal-eaten-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const type = btn.dataset.mealType;
      const idx = parseInt(btn.dataset.mealIdx, 10);
      const combined = n[type].options.concat((loadCustomMeals()[type] || []));
      const opt = combined[idx];
      if (!opt) return;
      if (isMealEatenToday(type, opt.name)) unlogMeal(type); else logMealEaten(type, opt);
      renderNutrition();
      renderNutritionCoach();
    });
  });

  document.querySelectorAll("[data-meal-add]").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.mealAdd;
      const name = document.getElementById(`meal-add-name-${key}`).value.trim();
      const kcal = parseInt(document.getElementById(`meal-add-kcal-${key}`).value, 10);
      const protein = parseInt(document.getElementById(`meal-add-protein-${key}`).value, 10) || 0;
      if (!name || !kcal) return;
      const m = loadCustomMeals();
      m[key].push({ id: "meal-" + Date.now() + Math.random(), name, kcal, protein, items: [] });
      saveCustomMeals(m);
      renderNutrition();
    });
  });
  document.querySelectorAll("[data-meal-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.mealRemove;
      const m = loadCustomMeals();
      ["lunch", "snack", "dinner"].forEach(key => { m[key] = m[key].filter(o => o.id !== id); });
      saveCustomMeals(m);
      renderNutrition();
    });
  });
}
renderNutrition();

function loadExtrasAll() { return loadLS(EXTRAS_KEY, []); }
function loadExtras() { return loadExtrasAll().filter(e => !e.deleted); }
function saveExtras(l) { saveLS(EXTRAS_KEY, l); }
function softDeleteExtra(id) {
  const all = loadExtrasAll();
  const item = all.find(e => e.id === id);
  if (item) { item.deleted = true; item.deletedAt = Date.now(); }
  saveExtras(all);
}

function addExtra(name, kcal) {
  const list = loadExtras();
  list.push({ id: "extra-" + Date.now() + Math.random(), date: todayISO(), name, kcal: kcal || null });
  saveExtras(list);
  renderExtras();
  renderNutritionCoach();
}

function renderExtras() {
  const todays = loadExtras().filter(e => e.date === todayISO()).sort((a, b) => b.id.localeCompare(a.id));
  const total = todays.reduce((s, e) => s + (e.kcal || 0), 0);
  const n = DATA.nutritionPlan;
  document.getElementById("extras-today-total").innerHTML = todays.length
    ? `<div class="section-sub" style="margin:4px 0 10px;">I dag: <b>${total} kcal</b> utenom planen${n ? ` (planen var ${n.dailyKcal} kcal)` : ""}</div>`
    : "";
  document.getElementById("extras-list").innerHTML = todays.map(e => `
    <li data-id="${e.id}"><span>${e.name}${e.kcal ? ` · ${e.kcal} kcal` : ""}</span>
      <button data-extra-remove="${e.id}" style="background:none;border:none;color:var(--muted);cursor:pointer;">✕</button>
    </li>`).join("") || `<li style="border-top:none;color:var(--muted);">Ingenting logget i dag</li>`;

  document.querySelectorAll("#extras-list button[data-extra-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      softDeleteExtra(btn.dataset.extraRemove);
      renderExtras();
      renderNutritionCoach();
    });
  });
}

function renderNutritionCoach() {
  const card = document.getElementById("nutrition-coach-card");
  if (!card) return;
  const tips = [];

  const cfg = loadBudgetConfig();
  const restaurantCat = cfg.categories.find(c => c.key === "restaurant");
  if (restaurantCat && restaurantCat.cap) {
    const spent = loadTransactions()
      .filter(t => t.category === "restaurant" && monthOf(t.date) === currentMonth)
      .reduce((s, t) => s + t.amount, 0);
    if (spent >= restaurantCat.cap * 0.7) {
      tips.push("Du har brukt en del på restaurant/take-away denne måneden. Legg gjerne inn et par faste spise-ute-forslag under lunsj/middag (bruk \"Eget forslag\"), så er det lettere å planlegge neste gang.");
    }
  }

  const since = new Date();
  since.setDate(since.getDate() - 6);
  const sinceStr = since.toISOString().slice(0, 10);
  const extrasThisWeek = loadExtras().filter(e => e.date >= sinceStr);
  if (extrasThisWeek.length >= 4) {
    tips.push("Du har logget ekstra mat/drikke flere ganger denne uken - helt greit! Husk bare å legge det inn så kaloriringen stemmer.");
  }

  if (!tips.length) { card.innerHTML = ""; return; }
  card.innerHTML = `<h3 style="margin:0 0 8px;font-size:15px;">💡 Tips</h3>` +
    tips.map(t => `<div class="section-sub" style="margin:0 0 8px;">${t}</div>`).join("");
}

document.getElementById("extra-add").addEventListener("click", () => {
  const name = document.getElementById("extra-name").value.trim();
  if (!name) return;
  const kcal = parseInt(document.getElementById("extra-kcal").value, 10) || null;
  addExtra(name, kcal);
  document.getElementById("extra-name").value = "";
  document.getElementById("extra-kcal").value = "";
});

document.querySelectorAll("[data-extra-preset]").forEach(btn => {
  btn.addEventListener("click", () => addExtra(btn.dataset.extraPreset, parseInt(btn.dataset.extraKcal, 10)));
});

renderExtras();

// ---------------------------------------------------------------- shared storage helpers
const WEIGHT_LOG_KEY = "garminDashboardWeightLog_v1";
const MEASURE_LOG_KEY = "garminDashboardMeasureLog_v1";
const SHOP_LIST_KEY = "garminDashboardShoppingList_v1";
const TX_KEY = "garminDashboardTransactions_v1";
const BUDGET_CONFIG_KEY = "garminDashboardBudgetConfig_v1";
const SEEN_KEY = "garminDashboardSeen_v1";
const WAGE_KEY = "garminDashboardWage_v1";
const RATE_KEY = "garminDashboardInvestRate_v1";
const FORGOTTEN_SAVINGS_KEY = "garminDashboardForgottenSavings_v1";
const BADDAY_LOG_KEY = "garminDashboardBadDayLog_v1";
const BADDAY_MODE_KEY = "garminDashboardBadDayActive_v1";
const WATER_KEY = "garminDashboardWater_v1";
const WEATHER_CACHE_KEY = "garminDashboardWeatherCache_v1";
const STREAK_BEST_KEY = "garminDashboardStreakBest_v1";

function loadLS(key, fallback) {
  try {
    const v = JSON.parse(localStorage.getItem(key));
    return v === null || v === undefined ? fallback : v;
  } catch (e) { return fallback; }
}
function saveLS(key, val) { localStorage.setItem(key, JSON.stringify(val)); }
function todayISO() { return new Date().toISOString().slice(0, 10); }
function isoWeekOf(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  const day = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - day);
  return d.toISOString().slice(0, 10);
}
function monthOf(dateStr) { return dateStr.slice(0, 7); }

// ---- weight log ----
function loadWeightLog() { return loadLS(WEIGHT_LOG_KEY, []); }
function saveWeightLog(l) { saveLS(WEIGHT_LOG_KEY, l); }

// ---- measurement log ----
function loadMeasureLog() { return loadLS(MEASURE_LOG_KEY, []); }
function saveMeasureLog(l) { saveLS(MEASURE_LOG_KEY, l); }

// ---- shopping list ----
function loadShopList() { return loadLS(SHOP_LIST_KEY, []); }
function saveShopList(l) { saveLS(SHOP_LIST_KEY, l); }

// ---- budget config / transactions ----
function loadBudgetConfig() {
  const stored = loadLS(BUDGET_CONFIG_KEY, null);
  if (stored && stored.categories) return stored;
  return JSON.parse(JSON.stringify(DATA.budgetDefaults));
}
function saveBudgetConfig(c) { saveLS(BUDGET_CONFIG_KEY, c); }
function loadTransactions() { return loadLS(TX_KEY, []); }
function saveTransactions(t) { saveLS(TX_KEY, t); }

function fundBalance() {
  const tx = loadTransactions();
  const fundKey = DATA.dogFund.category;
  const sum = tx.filter(t => t.category === fundKey).reduce((s, t) => s + t.amount, 0);
  return DATA.dogFund.startSaved + sum;
}

// ---------------------------------------------------------------- points / level / snapshot
function computePoints() {
  const th = DATA.trainingHistory || [];
  let sessionPts = 0, stepPts = 0;
  th.forEach(day => {
    if (day.sessionType !== "rest" && day.loggedTypes.includes(day.sessionType)) sessionPts++;
    if (day.stepGoalMet) stepPts++;
  });
  const weightWeeks = new Set(loadWeightLog().map(e => isoWeekOf(e.date))).size;
  const measureMonths = new Set(loadMeasureLog().map(e => monthOf(e.date))).size;
  const newRecords = Object.values(DATA.records || {}).filter(r => r && r.date && r.date >= DATA.programStart).length;
  const balance = fundBalance();
  const pct = 100 * balance / DATA.dogFund.target;
  const milestonesCrossed = [25, 50, 75, 100].filter(m => pct >= m).length;

  const cfg = DATA.pointsConfig;
  const total =
    sessionPts * cfg.perCompletedSession +
    stepPts * cfg.perStepGoalDay +
    weightWeeks * cfg.perWeightWeek +
    measureMonths * cfg.perMeasurementMonth +
    newRecords * cfg.perNewRecord +
    milestonesCrossed * cfg.perFundMilestone;

  return { total, sessionPts, stepPts, weightWeeks, measureMonths, newRecords, milestonesCrossed };
}

function renderLevel() {
  const cfg = DATA.pointsConfig;
  const pts = computePoints();
  const levelIdx = Math.min(Math.floor(pts.total / cfg.levelThreshold), cfg.levelNames.length - 1);
  const inLevel = pts.total - levelIdx * cfg.levelThreshold;
  const pct = levelIdx >= cfg.levelNames.length - 1 ? 100 : Math.min(100, 100 * inLevel / cfg.levelThreshold);

  document.getElementById("level-card").innerHTML = `
    <div class="level-head">
      <div class="level-name">${cfg.levelNames[levelIdx]} · nivå ${levelIdx + 1}</div>
      <div class="level-pts">${pts.total} poeng</div>
    </div>
    <div class="level-bar"><div style="width:${pct}%"></div></div>
    <div class="level-reward">🎁 ${cfg.levelRewards[levelIdx]}</div>
  `;

  const seen = loadLS(SEEN_KEY, { level: 0, milestones: 0 });
  const msgs = [];
  if (levelIdx > seen.level) msgs.push(`Nytt nivå! Du er nå ${cfg.levelNames[levelIdx]} 🎉`);
  if (pts.milestonesCrossed > seen.milestones) msgs.push(`Hundefondet har passert en ny milepæl! 🐶`);
  document.getElementById("celebrate-banner").innerHTML = msgs.length
    ? `<div class="celebrate-banner">${msgs.join(" · ")}</div>` : "";
  saveLS(SEEN_KEY, { level: levelIdx, milestones: pts.milestonesCrossed });

  return pts;
}

// ---------------------------------------------------------------- streak / latest PR
function computeStreak() {
  const th = DATA.trainingHistory || [];
  if (!th.length) return 0;
  let i = th.length - 1;
  const last = th[i];
  const lastPending = last.sessionType !== "rest" && !last.loggedTypes.includes(last.sessionType) && !inVacationRange(last.date);
  if (lastPending) i--;
  let streak = 0;
  for (; i >= 0; i--) {
    const day = th[i];
    if (inVacationRange(day.date)) continue;
    const kept = day.sessionType === "rest" || day.loggedTypes.includes(day.sessionType);
    if (!kept) break;
    streak++;
  }
  return streak;
}

function latestPR() {
  const log = loadSetLog().slice().sort((a, b) => a.date === b.date ? a.id.localeCompare(b.id) : a.date.localeCompare(b.date));
  const bestByEx = {};
  let last = null;
  log.forEach(s => {
    if (isBetterSet(s, bestByEx[s.exercise])) {
      bestByEx[s.exercise] = s;
      last = s;
    }
  });
  return last;
}

function renderWeeklySnapshot() {
  const since = new Date();
  since.setDate(since.getDate() - 6);
  const sinceStr = since.toISOString().slice(0, 10);

  const th = (DATA.trainingHistory || []).filter(d => d.date >= sinceStr);
  const sessionsDone = th.filter(d => d.sessionType !== "rest" && d.loggedTypes.includes(d.sessionType)).length;
  const stepsDone = th.filter(d => d.stepGoalMet).length;

  const allWeights = loadWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  const recentWeights = allWeights.filter(e => e.date >= sinceStr);
  let kgChangeLabel = "–";
  if (recentWeights.length >= 2) {
    const diff = recentWeights[recentWeights.length - 1].kg - recentWeights[0].kg;
    kgChangeLabel = `${diff > 0 ? "+" : ""}${diff.toFixed(1)} kg`;
  }

  const krAdded = loadTransactions()
    .filter(t => t.date >= sinceStr && t.category === DATA.dogFund.category)
    .reduce((s, t) => s + t.amount, 0);

  document.getElementById("weekly-snapshot").innerHTML = `
    <div class="snapshot-chip">Økter gjort<b>${sessionsDone}</b></div>
    <div class="snapshot-chip">Stegmål nådd<b>${stepsDone} dager</b></div>
    <div class="snapshot-chip">Vektendring<b>${kgChangeLabel}</b></div>
    <div class="snapshot-chip">Lagt i hundefondet<b>${krAdded} kr</b></div>
  `;
}

// ---------------------------------------------------------------- weight / measurement logging
document.getElementById("weight-date").value = todayISO();
document.getElementById("measure-date").value = todayISO();

function renderPlateau() {
  const card = document.getElementById("plateau-card");
  const log = loadWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  if (log.length < 3) { card.innerHTML = ""; return; }

  const a = log[log.length - 3], z = log[log.length - 1];
  const daysBetween = (new Date(z.date) - new Date(a.date)) / 86400000;
  const stuck = daysBetween >= 14 && (a.kg - z.kg) < 0.3;
  if (!stuck) { card.innerHTML = ""; return; }

  const mlog = loadMeasureLog().filter(e => e.waist != null).sort((x, y) => x.date.localeCompare(y.date));
  let waistDown = false;
  if (mlog.length >= 2) {
    const first = mlog[mlog.length - 2], last = mlog[mlog.length - 1];
    const daysSinceLast = (new Date(z.date) - new Date(last.date)) / 86400000;
    waistDown = (first.waist - last.waist) >= 1 && daysSinceLast <= 35;
  }

  card.innerHTML = waistDown
    ? `<h3 style="margin:0 0 4px;font-size:15px;">Vekta står stille, men midjen går ned 🎉</h3><div class="section-sub" style="margin:0;">Det betyr at du mister fett og bygger muskler samtidig. Ikke endre noe, bare fortsett som nå.</div>`
    : `<h3 style="margin:0 0 4px;font-size:15px;">Vekta har stått stille i 2–3 uker</h3><div class="section-sub" style="margin:0;">Det er helt vanlig. Velg én liten justering og gi den 2 uker: spis litt mindre, eller gå litt mer hver dag. Sjekk også at du logger alt, særlig olje, saus og drikke.</div>`;
}

function weightRollingAvgSeries(log) {
  // log: ascending by date. 7-day trailing window, keyed by calendar date (not index),
  // so it stays correct whether entries are daily or more sparse.
  return log.map(entry => {
    const windowStart = new Date(entry.date + "T00:00:00");
    windowStart.setDate(windowStart.getDate() - 6);
    const ws = windowStart.toISOString().slice(0, 10);
    const inWindow = log.filter(e => e.date >= ws && e.date <= entry.date);
    return inWindow.reduce((s, e) => s + e.kg, 0) / inWindow.length;
  });
}

function renderWeightTrend() {
  const el = document.getElementById("weight-trend");
  if (!el) return;
  const log = loadWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  if (log.length < 3) { el.innerHTML = ""; return; }

  const series = weightRollingAvgSeries(log);
  const latest = series[series.length - 1];
  const prior = series[Math.max(0, series.length - 3)];
  const diff = latest - prior;
  el.innerHTML = `<div class="weight-trend-box">Trend (7-dagers snitt): <b>${latest.toFixed(1)} kg</b> <span class="log-delta ${diff <= 0 ? "down" : "up"}">${diff > 0 ? "+" : ""}${diff.toFixed(1)} kg siste par uker</span></div>`;
}

function renderWeightChart(svgId, tooltipId) {
  const svg = document.getElementById(svgId || "chart-weight");
  const tooltip = document.getElementById(tooltipId || "tt-weight");
  if (!svg) return;
  const log = loadWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  if (log.length < 2) { svg.innerHTML = ""; return; }

  const avgSeries = weightRollingAvgSeries(log);
  const w = 480, h = 180, padLeft = 36, padBottom = 20, padTop = 10, padRight = 10;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = "";
  const plotW = w - padLeft - padRight;
  const plotH = h - padBottom - padTop;

  const allVals = log.map(e => e.kg).concat(avgSeries);
  const min = Math.min(...allVals), max = Math.max(...allVals);
  const range = (max - min) || 1;
  const step = plotW / Math.max(log.length - 1, 1);
  const xAt = i => padLeft + i * step;
  const yAt = v => padTop + plotH - ((v - min) / range) * plotH;

  for (let i = 0; i <= 3; i++) {
    const y = padTop + plotH - (i / 3) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y}" x2="${w - padRight}" y2="${y}" stroke="#ece7e0" stroke-width="1"/>`;
    svg.innerHTML += `<text x="${padLeft - 6}" y="${y + 3}" font-size="9" fill="#8a8580" text-anchor="end">${(min + (i / 3) * range).toFixed(1)}</text>`;
  }

  let rawDots = "";
  log.forEach((e, i) => {
    rawDots += `<circle cx="${xAt(i).toFixed(1)}" cy="${yAt(e.kg).toFixed(1)}" r="2.5" fill="#7a1f3d" opacity="0.25"/>`;
  });
  svg.innerHTML += rawDots;

  const pathPts = avgSeries.map((v, i) => [xAt(i), yAt(v)]);
  const path = pathPts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  svg.innerHTML += `<path d="${path}" fill="none" stroke="#7a1f3d" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`;

  let avgDots = "";
  avgSeries.forEach((v, i) => {
    avgDots += `<circle cx="${xAt(i).toFixed(1)}" cy="${yAt(v).toFixed(1)}" r="3" fill="#7a1f3d" class="dot" data-date="${log[i].date}" data-val="${v.toFixed(1)}" opacity="0"/>`;
  });
  svg.innerHTML += avgDots;

  [0, Math.floor(log.length / 2), log.length - 1].forEach(i => {
    svg.innerHTML += `<text x="${xAt(i)}" y="${h - 4}" font-size="9" fill="#8a8580" text-anchor="middle">${fmtShort(log[i].date)}</text>`;
  });

  svg.querySelectorAll(".dot").forEach(dot => {
    const hit = dot.cloneNode();
    hit.setAttribute("r", 8);
    hit.setAttribute("opacity", 0);
    hit.classList.add("hit");
    svg.appendChild(hit);
    hit.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect();
      tooltip.style.opacity = 1;
      tooltip.style.left = (e.clientX - r.left) + "px";
      tooltip.style.top = (e.clientY - r.top) + "px";
      tooltip.textContent = `${fmtDate(hit.dataset.date)}: snitt ${hit.dataset.val} kg`;
    });
    hit.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
  });
}

function renderWeightLog() {
  const log = loadWeightLog().sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("weight-list").innerHTML = log.slice(0, 8).map((e, i) => {
    const prev = log[i + 1];
    let delta = "";
    if (prev) {
      const d = e.kg - prev.kg;
      delta = `<span class="log-delta ${d <= 0 ? "down" : "up"}">${d > 0 ? "+" : ""}${d.toFixed(1)} kg</span>`;
    }
    return `<li><span>${fmtShort(e.date)}</span><b>${e.kg} kg</b> ${delta}</li>`;
  }).join("") || `<li style="border-top:none;color:var(--muted);">Ingen målinger ennå</li>`;
}
document.getElementById("weight-add").addEventListener("click", () => {
  const date = document.getElementById("weight-date").value || todayISO();
  const kg = parseFloat(document.getElementById("weight-kg").value);
  if (!kg) return;
  const log = loadWeightLog().filter(e => e.date !== date);
  log.push({ date, kg });
  saveWeightLog(log);
  document.getElementById("weight-kg").value = "";
  renderWeightLog();
  renderWeightTrend();
  renderWeightChart();
  renderWeightChart("chart-weight-mini", "tt-weight-mini");
  renderLevel();
  renderWeeklySnapshot();
  renderPlateau();
});

function renderMeasureLog() {
  const log = loadMeasureLog().sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("measure-list").innerHTML = log.slice(0, 6).map(e =>
    `<li><span>${fmtShort(e.date)}</span><b>${e.waist ?? "–"} / ${e.hips ?? "–"} / ${e.arm ?? "–"} cm</b></li>`
  ).join("") || `<li style="border-top:none;color:var(--muted);">Ingen mål ennå</li>`;
}
document.getElementById("measure-add").addEventListener("click", () => {
  const date = document.getElementById("measure-date").value || todayISO();
  const waist = parseFloat(document.getElementById("measure-waist").value) || null;
  const hips = parseFloat(document.getElementById("measure-hips").value) || null;
  const arm = parseFloat(document.getElementById("measure-arm").value) || null;
  if (!waist && !hips && !arm) return;
  const log = loadMeasureLog().filter(e => e.date !== date);
  log.push({ date, waist, hips, arm });
  saveMeasureLog(log);
  document.getElementById("measure-waist").value = "";
  document.getElementById("measure-hips").value = "";
  document.getElementById("measure-arm").value = "";
  renderMeasureLog();
  renderLevel();
  renderPlateau();
});

document.getElementById("overwhelm-btn").addEventListener("click", () => {
  const out = document.getElementById("overwhelm-out");
  if (out.innerHTML) { out.innerHTML = ""; return; }
  out.innerHTML = `<div class="overwhelm-box">
    <b>1. Stopp og pust 🫧</b><br>Pust inn i 4 sekunder, ut i 6. Gjør det fem ganger.<br><br>
    <b>2. Velg bare én ting</b><br>Se på neste punkt på treningsplanen eller handlelista. Alt annet kan vente - det forsvinner ikke.<br><br>
    <b>3. Gjør den i 10 minutter</b><br>Etterpå har du lov til å stoppe. Ofte blir det lettere å fortsette.
  </div>`;
});

// ---------------------------------------------------------------- bad day mode
function loadBadDayLog() { return loadLS(BADDAY_LOG_KEY, {}); }
function saveBadDayLog(v) { saveLS(BADDAY_LOG_KEY, v); }

function flashBadDaySaved(msg) {
  const el = document.getElementById("badday-saved-msg");
  el.textContent = msg;
  clearTimeout(flashBadDaySaved._t);
  flashBadDaySaved._t = setTimeout(() => { el.textContent = ""; }, 2000);
}

function badDayMarkTrained() {
  const log = loadBadDayLog();
  const today = todayISO();
  log[today] = Object.assign({}, log[today], { trained: true });
  saveBadDayLog(log);
  renderBadDayPanel();
  flashBadDaySaved("Trening logget ✓");
}

function badDayLogFood() {
  addExtra("Mat/drikke (dårlig dag)", null);
  flashBadDaySaved("Mat/drikke logget ✓");
}

function badDayLogExpense() {
  const input = document.getElementById("badday-expense-amount");
  const amount = parseFloat(input.value);
  if (!amount) return;
  addTransactionWithRoundUp(todayISO(), amount, "annet", "Dårlig dag");
  input.value = "";
  flashBadDaySaved("Utgift logget ✓");
}

function renderBadDayPanel() {
  const entry = loadBadDayLog()[todayISO()] || {};
  document.getElementById("badday-quickbtns").innerHTML = `
    <button class="btn ${entry.trained ? "active" : ""}" id="badday-trained-btn">🏋️ ${entry.trained ? "Trent i dag ✓" : "Trente i dag"}</button>
    <button class="btn secondary" id="badday-food-btn">🍫 Logg mat/drikke</button>
    <div class="badday-expense-row">
      <input type="number" step="1" id="badday-expense-amount" placeholder="Beløp (kr)">
      <button class="btn secondary" id="badday-expense-btn">💸 Logg utgift</button>
    </div>
  `;
  document.getElementById("badday-trained-btn").addEventListener("click", badDayMarkTrained);
  document.getElementById("badday-food-btn").addEventListener("click", badDayLogFood);
  document.getElementById("badday-expense-btn").addEventListener("click", badDayLogExpense);
  document.getElementById("badday-saved-msg").textContent = "";
}

function setBadDayMode(active) {
  document.body.classList.toggle("badday-active", active);
  saveLS(BADDAY_MODE_KEY, active);
  if (active) renderBadDayPanel();
}

document.getElementById("badday-btn").addEventListener("click", () => setBadDayMode(true));
document.getElementById("hjem-badday-toggle").addEventListener("click", () => setBadDayMode(true));
document.getElementById("badday-exit").addEventListener("click", () => setBadDayMode(false));

if (loadLS(BADDAY_MODE_KEY, false)) setBadDayMode(true);

// ---------------------------------------------------------------- shopping list
function shopKey(name) { return name.trim().toLowerCase(); }
function addShopItems(names) {
  const list = loadShopList();
  const existing = new Set(list.map(i => shopKey(i.name)));
  names.forEach(n => {
    const k = shopKey(n);
    if (!existing.has(k)) {
      list.push({ id: k + "-" + Date.now() + Math.random(), name: n, checked: false });
      existing.add(k);
    }
  });
  saveShopList(list);
  renderShopList();
}
function renderShopList() {
  const list = loadShopList();
  document.getElementById("shop-list").innerHTML = list.map(i => `
    <li class="${i.checked ? "checked" : ""}" data-id="${i.id}">
      <input type="checkbox" ${i.checked ? "checked" : ""}>
      <span>${i.name}</span>
      <button data-remove="${i.id}">✕</button>
    </li>`).join("") || `<li style="border-top:none;color:var(--muted);">Listen er tom</li>`;

  document.querySelectorAll("#shop-list input[type=checkbox]").forEach(cb => {
    cb.addEventListener("change", () => {
      const id = cb.closest("li").dataset.id;
      const l = loadShopList();
      const item = l.find(x => x.id === id);
      if (item) item.checked = cb.checked;
      saveShopList(l);
      renderShopList();
    });
  });
  document.querySelectorAll("#shop-list button[data-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      saveShopList(loadShopList().filter(x => x.id !== btn.dataset.remove));
      renderShopList();
    });
  });
}
document.getElementById("shop-add").addEventListener("click", () => {
  const input = document.getElementById("shop-input");
  if (input.value.trim()) { addShopItems([input.value.trim()]); input.value = ""; }
});
document.getElementById("shop-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("shop-add").click();
});
document.getElementById("shop-quickadd-protein").addEventListener("click", () => {
  addShopItems(["Havregryn", "Proteinpulver", "Proteinmelk", "Chiafrø", "Gresk yoghurt", "Mager kesam"]);
});
document.getElementById("shop-quickadd-meals").addEventListener("click", () => {
  const n = DATA.nutritionPlan;
  const items = new Set();
  n.breakfast.items.forEach(i => items.add(i));
  ["lunch", "snack", "dinner"].forEach(key => n[key].options.forEach(o => o.items.forEach(i => items.add(i))));
  addShopItems(Array.from(items));
});
document.getElementById("shop-clear-checked").addEventListener("click", () => {
  saveShopList(loadShopList().filter(i => !i.checked));
  renderShopList();
});

// ---------------------------------------------------------------- budget
let currentMonth = todayISO().slice(0, 7);
function monthLabel(m) {
  const d = new Date(m + "-01T00:00:00");
  return d.toLocaleDateString("nb-NO", { month: "long", year: "numeric" });
}

document.getElementById("tx-date").value = todayISO();

function populateCategorySelect() {
  const cfg = loadBudgetConfig();
  document.getElementById("tx-category").innerHTML = cfg.categories.map(c => `<option value="${c.key}">${c.label}</option>`).join("");
}

function renderCategoryBreakdown() {
  const cfg = loadBudgetConfig();
  const tx = loadTransactions().filter(t => monthOf(t.date) === currentMonth);
  document.getElementById("cat-breakdown").innerHTML = cfg.categories.map(c => {
    const spent = tx.filter(t => t.category === c.key).reduce((s, t) => s + t.amount, 0);
    const pct = c.cap ? Math.min(100, 100 * spent / c.cap) : 0;
    const over = c.cap && spent > c.cap;
    return `<div class="cat-row" data-key="${c.key}">
      <div class="cat-head"><span>${c.label}</span><b>${spent} / <input class="cap-edit" type="number" value="${c.cap}" data-cat="${c.key}"> kr</b></div>
      <div class="cat-bar"><div class="${over ? "over" : ""}" style="width:${pct}%"></div></div>
      ${over ? `<div class="cat-grace">💛 Over budsjett denne måneden - det går bra, juster og fortsett.</div>` : ""}
    </div>`;
  }).join("");

  document.querySelectorAll("#cat-breakdown .cap-edit").forEach(inp => {
    inp.addEventListener("change", () => {
      const c = loadBudgetConfig();
      const cat = c.categories.find(x => x.key === inp.dataset.cat);
      if (cat) cat.cap = parseFloat(inp.value) || 0;
      saveBudgetConfig(c);
      renderCategoryBreakdown();
    });
  });
}

function renderBudgetSummary() {
  const cfg = loadBudgetConfig();
  const tx = loadTransactions().filter(t => monthOf(t.date) === currentMonth);
  const totalSpent = tx.reduce((s, t) => s + t.amount, 0);
  document.getElementById("budget-summary").innerHTML = `
    <div class="snapshot-chip">Inntekt<b>${cfg.income.toLocaleString()} kr</b></div>
    <div class="snapshot-chip">Brukt denne måneden<b>${totalSpent.toLocaleString()} kr</b></div>
    <div class="snapshot-chip">Igjen<b>${(cfg.income - totalSpent).toLocaleString()} kr</b></div>
  `;
}

function renderTxList() {
  const cfg = loadBudgetConfig();
  const catLabel = key => (cfg.categories.find(c => c.key === key) || {}).label || key;
  const tx = loadTransactions().filter(t => monthOf(t.date) === currentMonth).sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("tx-list").innerHTML = tx.map(t => `
    <li data-id="${t.id}"><span>${fmtShort(t.date)} · ${catLabel(t.category)} · ${t.name || ""}</span>
      <b>${t.amount} kr</b>
      <button data-tx-remove="${t.id}" style="background:none;border:none;color:var(--muted);cursor:pointer;">✕</button>
    </li>`).join("") || `<li style="border-top:none;color:var(--muted);">Ingen transaksjoner denne måneden</li>`;

  document.querySelectorAll("#tx-list button[data-tx-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      saveTransactions(loadTransactions().filter(t => t.id !== btn.dataset.txRemove));
      renderBudget();
    });
  });
}

function fundProgress() {
  const balance = fundBalance();
  const pct = Math.min(100, 100 * balance / DATA.dogFund.target);
  const tx = loadTransactions().filter(t => t.category === DATA.dogFund.category);
  const months = new Set(tx.map(t => monthOf(t.date))).size || 1;
  const avgPerMonth = tx.reduce((s, t) => s + t.amount, 0) / months;
  const remaining = DATA.dogFund.target - balance;

  let etaText = "Legg til sparing for å se et anslag";
  if (remaining <= 0) {
    etaText = "Målet er nådd! 🐶";
  } else if (avgPerMonth > 0) {
    const monthsLeft = Math.ceil(remaining / avgPerMonth);
    etaText = `I dagens tempo (~${Math.round(avgPerMonth)} kr/mnd): ca. ${monthsLeft} ${monthsLeft === 1 ? "måned" : "måneder"} igjen`;
  }
  return { balance, pct, remaining, etaText };
}

function renderFund() {
  const { balance, pct, etaText } = fundProgress();
  document.getElementById("fund-card").innerHTML = `
    <div class="fund-head">
      <div>🐶 Hundefond</div>
      <div class="fund-amount">${balance.toLocaleString()} / ${DATA.dogFund.target.toLocaleString()} kr</div>
    </div>
    <div class="fund-bar"><div style="width:${pct}%"></div></div>
    <div class="fund-eta">${etaText}</div>
    <div class="fund-goal-edit" style="margin-top:8px;display:flex;gap:6px;align-items:center;">
      <input type="number" step="500" id="fund-goal-input" value="${DATA.dogFund.target}" style="width:90px;">
      <button class="btn ghost small" id="fund-goal-save">Lagre sparemål</button>
    </div>
  `;
  document.getElementById("fund-goal-save").addEventListener("click", () => {
    const val = parseInt(document.getElementById("fund-goal-input").value, 10);
    if (!val) return;
    const s = loadSettings();
    s.savingsTarget = val;
    saveSettings(s);
    DATA.dogFund.target = val;
    renderBudget();
    renderHjemProgress();
    renderHjemSavingsRing();
  });
}

function loadForgottenSavings() { return loadLS(FORGOTTEN_SAVINGS_KEY, 0); }
function saveForgottenSavings(v) { saveLS(FORGOTTEN_SAVINGS_KEY, v); }

function renderForgottenSavings(animate) {
  const card = document.getElementById("forgotten-savings-card");
  const pot = loadForgottenSavings();
  card.innerHTML = `
    <div class="fs-info">🪙 Glemt sparing<br>Avrunding fra utgifter, samlet opp automatisk</div>
    <div class="fs-amount">${Math.round(pot).toLocaleString()} kr</div>
    <button class="btn secondary small" id="fs-move" ${pot > 0 ? "" : "disabled"}>Flytt til hundefondet</button>
  `;
  if (animate) {
    card.classList.add("pulse");
    setTimeout(() => card.classList.remove("pulse"), 650);
  }
  document.getElementById("fs-move").addEventListener("click", () => {
    const amount = loadForgottenSavings();
    if (!amount) return;
    const tx = loadTransactions();
    tx.push({ id: "save-" + Date.now() + Math.random(), date: todayISO(), amount, category: DATA.dogFund.category, name: "Glemt sparing" });
    saveTransactions(tx);
    saveForgottenSavings(0);
    renderBudget();
  });
}

function renderBudget() {
  renderCategoryBreakdown();
  renderBudgetSummary();
  renderTxList();
  renderFund();
  renderForgottenSavings();
  renderLevel();
  renderWeeklySnapshot();
}

document.getElementById("month-label").textContent = monthLabel(currentMonth);
function shiftMonth(delta) {
  const d = new Date(currentMonth + "-01T00:00:00");
  d.setMonth(d.getMonth() + delta);
  currentMonth = d.toISOString().slice(0, 7);
  document.getElementById("month-label").textContent = monthLabel(currentMonth);
  renderCategoryBreakdown();
  renderBudgetSummary();
  renderTxList();
}
document.getElementById("month-prev").addEventListener("click", () => shiftMonth(-1));
document.getElementById("month-next").addEventListener("click", () => shiftMonth(1));

populateCategorySelect();

function addTransactionWithRoundUp(date, amount, category, name) {
  const tx = loadTransactions();
  tx.push({ id: "tx-" + Date.now() + Math.random(), date, amount, category, name });
  saveTransactions(tx);
  let roundedUp = false;
  if (category !== DATA.dogFund.category) {
    const roundUp = Math.ceil(amount / 10) * 10 - amount;
    if (roundUp > 0) {
      saveForgottenSavings(loadForgottenSavings() + roundUp);
      roundedUp = true;
    }
  }
  renderNutritionCoach();
  return roundedUp;
}

document.getElementById("tx-add").addEventListener("click", () => {
  const date = document.getElementById("tx-date").value || todayISO();
  const amount = parseFloat(document.getElementById("tx-amount").value);
  const category = document.getElementById("tx-category").value;
  const name = document.getElementById("tx-name").value.trim();
  if (!amount) return;
  const roundedUp = addTransactionWithRoundUp(date, amount, category, name);
  document.getElementById("tx-amount").value = "";
  document.getElementById("tx-name").value = "";
  currentMonth = monthOf(date);
  document.getElementById("month-label").textContent = monthLabel(currentMonth);
  renderBudget();
  if (roundedUp) renderForgottenSavings(true);
});

document.getElementById("save-add").addEventListener("click", () => {
  const amount = parseFloat(document.getElementById("save-amount").value);
  const name = document.getElementById("save-name").value.trim();
  if (!amount) return;
  const tx = loadTransactions();
  tx.push({ id: "save-" + Date.now() + Math.random(), date: todayISO(), amount, category: DATA.dogFund.category, name: name || "Spar i stedet" });
  saveTransactions(tx);
  document.getElementById("save-amount").value = "";
  document.getElementById("save-name").value = "";
  document.getElementById("buy-check-out").innerHTML = "";
  renderBudget();
});

const wageInput = document.getElementById("buy-wage");
const rateInput = document.getElementById("buy-rate");
const savedWage = loadLS(WAGE_KEY, null);
const savedRate = loadLS(RATE_KEY, null);
if (savedWage != null) wageInput.value = savedWage;
if (savedRate != null) rateInput.value = savedRate;
wageInput.addEventListener("change", () => saveLS(WAGE_KEY, wageInput.value ? parseFloat(wageInput.value) : null));
rateInput.addEventListener("change", () => saveLS(RATE_KEY, rateInput.value ? parseFloat(rateInput.value) : null));

document.getElementById("buy-check").addEventListener("click", () => {
  const amount = parseFloat(document.getElementById("save-amount").value);
  const out = document.getElementById("buy-check-out");
  if (!amount) { out.innerHTML = ""; return; }
  const remaining = Math.max(0, DATA.dogFund.target - fundBalance());
  const pctOfFund = Math.min(100, 100 * amount / DATA.dogFund.target);
  const pctOfRemaining = remaining > 0 ? Math.min(100, 100 * amount / remaining) : 100;
  const wage = parseFloat(wageInput.value);
  const rate = parseFloat(rateInput.value);
  const hoursLine = wage ? `<div class="buy-check-box">Det er <b>${(amount / wage).toFixed(1)} timer</b> av arbeidstiden din.</div>` : "";
  let growthHtml = "";
  if (rate) {
    const chips = [5, 10, 20].map(years => {
      const grown = amount * Math.pow(1 + rate / 100, years);
      return `<div class="buy-growth-chip">${years} år<b>${Math.round(grown).toLocaleString()} kr</b></div>`;
    }).join("");
    growthHtml = `<div class="section-sub" style="margin:10px 0 0;">Hvis du sparer det i stedet og investerer til ${rate}% årlig avkastning:</div><div class="buy-growth-row">${chips}</div>`;
  }
  out.innerHTML = `<div class="buy-check-box">${amount.toLocaleString()} kr er <b>${pctOfFund.toFixed(1)}%</b> av hele hundefondmålet${remaining > 0 ? ` - <b>${pctOfRemaining.toFixed(1)}%</b> av det som gjenstår` : ""}.</div>${hoursLine}${growthHtml}`;
});

document.querySelectorAll(".save-presets button[data-preset]").forEach(btn => {
  btn.addEventListener("click", () => {
    const amount = parseFloat(btn.dataset.preset);
    const name = document.getElementById("save-name").value.trim();
    const tx = loadTransactions();
    tx.push({ id: "save-" + Date.now() + Math.random(), date: todayISO(), amount, category: DATA.dogFund.category, name: name || "Spar i stedet" });
    saveTransactions(tx);
    document.getElementById("save-name").value = "";
    document.getElementById("buy-check-out").innerHTML = "";
    renderBudget();
  });
});

renderWeightLog();
renderWeightTrend();
renderWeightChart();
renderWeightChart("chart-weight-mini", "tt-weight-mini");
renderMeasureLog();
renderPlateau();
renderShopList();
renderBudget();

// ---------------------------------------------------------------- stat cards
function sparkline(values) {
  const vals = values.filter(v => v !== null && v !== undefined);
  if (vals.length < 2) return "";
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = (max - min) || 1;
  const w = 200, h = 36;
  const step = w / (values.length - 1);
  let pts = [];
  values.forEach((v, i) => {
    if (v === null || v === undefined) return;
    const x = i * step;
    const y = h - ((v - min) / range) * (h - 6) - 3;
    pts.push([x, y]);
  });
  const path = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${path}" fill="none" stroke="#7a1f3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

const statGrid = document.getElementById("stat-grid");
const statsDef = [
  { key: "hrv", label: "HRV (last night)", unit: "ms", from: s => s.value },
  { key: "sleep", label: "Sleep", unit: "hrs", from: s => s.hours, extra: s => s.score ? `score ${s.score}` : "" },
  { key: "calories", label: "Calories burned", unit: "kcal", from: s => s.value },
  { key: "steps", label: "Steps", unit: "", from: s => s.value },
];
statsDef.forEach(def => {
  const s = DATA.topStats[def.key];
  if (!s) return;
  const val = def.from(s);
  const card = document.createElement("div");
  card.className = "stat-card";
  card.innerHTML = `
    <div class="label">${def.label}</div>
    <div class="value">${val !== null && val !== undefined ? val.toLocaleString() : "-"} <small>${def.unit}</small></div>
    <div class="asof">as of ${fmtDate(s.date)}${def.extra ? " · " + def.extra(s) : ""}</div>
    ${sparkline(s.trend)}
  `;
  statGrid.appendChild(card);
});

// ---------------------------------------------------------------- weekly by sport chart
(function renderWeeklySport() {
  const svg = document.getElementById("chart-weekly-sport");
  const tooltip = document.getElementById("tt-weekly");
  const legend = document.getElementById("sport-legend");
  const weeks = DATA.weeklyBySport;
  const sports = DATA.sportOrder;
  const colors = DATA.sportColors;

  sports.forEach(sp => {
    legend.innerHTML += `<span><i style="background:${colors[sp]}"></i>${sp}</span>`;
  });

  const w = 1000, h = 260, padLeft = 40, padBottom = 24, padTop = 10;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const plotW = w - padLeft - 10;
  const plotH = h - padBottom - padTop;
  const barGroupW = plotW / weeks.length;
  const barW = Math.min(14, barGroupW / (sports.length + 1));

  let maxMinutes = 0;
  weeks.forEach(wk => sports.forEach(sp => {
    const e = wk.sports[sp];
    if (e) maxMinutes = Math.max(maxMinutes, e.minutes);
  }));
  maxMinutes = maxMinutes || 60;

  // gridlines
  for (let i = 0; i <= 4; i++) {
    const y = padTop + plotH - (i / 4) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y}" x2="${w - 10}" y2="${y}" stroke="#ece7e0" stroke-width="1"/>`;
    svg.innerHTML += `<text x="${padLeft - 6}" y="${y + 3}" font-size="9" fill="#8a8580" text-anchor="end">${Math.round((i / 4) * maxMinutes)}</text>`;
  }

  weeks.forEach((wk, wi) => {
    const groupX = padLeft + wi * barGroupW + barGroupW / 2;
    sports.forEach((sp, si) => {
      const e = wk.sports[sp];
      const x = groupX - (sports.length * barW) / 2 + si * barW;
      if (e) {
        const bh = (e.minutes / maxMinutes) * plotH;
        const y = padTop + plotH - bh;
        svg.innerHTML += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW - 2}" height="${bh.toFixed(1)}" fill="${colors[sp]}" rx="2"
          data-week="${wk.week}" data-sport="${sp}" data-minutes="${e.minutes}" data-sessions="${e.sessions}" data-dist="${e.distanceKm}" class="bar"/>`;
      }
    });
    svg.innerHTML += `<text x="${groupX}" y="${h - 6}" font-size="9" fill="#8a8580" text-anchor="middle">${fmtShort(wk.week)}</text>`;
  });

  svg.querySelectorAll(".bar").forEach(bar => {
    bar.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect();
      tooltip.style.opacity = 1;
      tooltip.style.left = (e.clientX - r.left) + "px";
      tooltip.style.top = (e.clientY - r.top) + "px";
      tooltip.textContent = `${bar.dataset.sport}: ${bar.dataset.sessions} session(s), ${bar.dataset.minutes} min, ${bar.dataset.dist} km`;
    });
    bar.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
  });
})();

// ---------------------------------------------------------------- line charts
function renderLineChart(svgId, ttId, weeks, values, color, unit) {
  const svg = document.getElementById(svgId);
  const tooltip = document.getElementById(ttId);
  if (!weeks || !weeks.length) { svg.outerHTML = '<div style="color:#8a8580;font-size:13px;">No data yet</div>'; return; }

  const w = 480, h = 180, padLeft = 36, padBottom = 20, padTop = 10, padRight = 10;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const plotW = w - padLeft - padRight;
  const plotH = h - padBottom - padTop;

  const clean = values.map(v => (v === null || v === undefined ? null : v));
  const present = clean.filter(v => v !== null);
  const min = Math.min(...present), max = Math.max(...present);
  const range = (max - min) || 1;
  const step = plotW / Math.max(weeks.length - 1, 1);

  for (let i = 0; i <= 3; i++) {
    const y = padTop + plotH - (i / 3) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y}" x2="${w - padRight}" y2="${y}" stroke="#ece7e0" stroke-width="1"/>`;
    svg.innerHTML += `<text x="${padLeft - 6}" y="${y + 3}" font-size="9" fill="#8a8580" text-anchor="end">${(min + (i / 3) * range).toFixed(1)}</text>`;
  }

  let pathPts = [];
  let dots = "";
  clean.forEach((v, i) => {
    if (v === null) return;
    const x = padLeft + i * step;
    const y = padTop + plotH - ((v - min) / range) * plotH;
    pathPts.push([x, y]);
    dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${color}" data-week="${weeks[i]}" data-val="${v}" class="dot" opacity="0"/>`;
  });
  const path = pathPts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const areaPath = path + ` L ${pathPts[pathPts.length-1][0].toFixed(1)},${(padTop+plotH).toFixed(1)} L ${pathPts[0][0].toFixed(1)},${(padTop+plotH).toFixed(1)} Z`;

  svg.innerHTML += `<path d="${areaPath}" fill="${color}" opacity="0.08"/>`;
  svg.innerHTML += `<path d="${path}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`;
  svg.innerHTML += dots;

  // x labels: first, middle, last
  [0, Math.floor(weeks.length / 2), weeks.length - 1].forEach(i => {
    const x = padLeft + i * step;
    svg.innerHTML += `<text x="${x}" y="${h - 4}" font-size="9" fill="#8a8580" text-anchor="middle">${fmtShort(weeks[i])}</text>`;
  });

  svg.querySelectorAll(".dot").forEach(dot => {
    const hit = dot.cloneNode();
    hit.setAttribute("r", 8);
    hit.setAttribute("opacity", 0);
    hit.classList.add("hit");
    svg.appendChild(hit);
    hit.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect();
      tooltip.style.opacity = 1;
      tooltip.style.left = (e.clientX - r.left) + "px";
      tooltip.style.top = (e.clientY - r.top) + "px";
      tooltip.textContent = `${fmtDate(hit.dataset.week)}: ${hit.dataset.val} ${unit}`;
    });
    hit.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
  });
}

renderLineChart("chart-load", "tt-load", DATA.trends.trainingLoad.weeks, DATA.trends.trainingLoad.values, "#7a1f3d", "load");
renderLineChart("chart-rhr", "tt-rhr", DATA.trends.restingHR.weeks, DATA.trends.restingHR.values, "#9b3456", "bpm");
renderLineChart("chart-hrv", "tt-hrv", DATA.trends.hrv.weeks, DATA.trends.hrv.values, "#a46cc0", "ms");
renderLineChart("chart-sleep", "tt-sleep", DATA.trends.sleepHours.weeks, DATA.trends.sleepHours.values, "#e8a3b6", "hrs");

function isoAddDays(dateStr, days) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}
function weeklyVolumeSeries(numWeeks) {
  const log = loadSetLog();
  const byWeek = {};
  log.forEach(s => {
    if (!s.date || !s.reps) return;
    const wk = isoWeekOf(s.date);
    const vol = (s.weight != null ? s.weight : 1) * s.reps;
    byWeek[wk] = (byWeek[wk] || 0) + vol;
  });
  const base = isoWeekOf(todayISO());
  const weeks = [];
  const values = [];
  for (let i = numWeeks - 1; i >= 0; i--) {
    const key = isoAddDays(base, -i * 7);
    weeks.push(key);
    values.push(Math.round(byWeek[key] || 0));
  }
  return { weeks, values };
}
const volumeSeries = weeklyVolumeSeries(10);
renderLineChart("chart-volume", "tt-volume", volumeSeries.weeks, volumeSeries.values, "#f6c667", "vol");

// ---------------------------------------------------------------- records
const recordsGrid = document.getElementById("records-grid");
const recordDefs = [
  { key: "longestRide", label: "Longest ride", fmt: r => `${r.value} ${r.unit}` },
  { key: "longestRun", label: "Longest run", fmt: r => `${r.value} km` },
  { key: "longestStrength", label: "Longest strength session", fmt: r => `${r.value} min` },
  { key: "mostSteps", label: "Most steps in a day", fmt: r => `${r.value.toLocaleString()}` },
  { key: "mostCalories", label: "Most calories in a day", fmt: r => `${r.value.toLocaleString()} kcal` },
  { key: "longestSleep", label: "Longest night's sleep", fmt: r => `${r.value} hrs` },
  { key: "bestHRV", label: "Highest HRV night", fmt: r => `${r.value} ms` },
  { key: "highestTrainingLoad", label: "Biggest training load", fmt: r => `${r.value}` },
];
recordDefs.forEach(def => {
  const r = DATA.records[def.key];
  if (!r || r.value === null || r.value === undefined) return;
  const card = document.createElement("div");
  card.className = "record-card";
  card.innerHTML = `
    <div class="label">${def.label}</div>
    <div class="value">${def.fmt(r)}</div>
    <div class="date">${fmtDate(r.date)}</div>
  `;
  recordsGrid.appendChild(card);
});

// ---------------------------------------------------------------- hjem dashboard
function renderHjemGreeting() {
  const h = new Date().getHours();
  const greet = h < 10 ? "God morgen" : h < 17 ? "God dag" : "God kveld";
  document.getElementById("hjem-greeting").textContent = greet;
}

function renderHjemWhy() {
  const why = loadWhy();
  const el = document.getElementById("hjem-why");
  el.textContent = why ? `💛 ${why}` : "+ Legg til ditt Hvorfor";
  el.classList.toggle("empty", !why);
}
document.getElementById("hjem-why").addEventListener("click", () => {
  const next = prompt("Hvorfor gjør du dette? Vises som en liten påminnelse på Hjem.", loadWhy());
  if (next === null) return;
  saveWhy(next.trim());
  renderHjemWhy();
});

function renderHjemSession() {
  const p = DATA.program;
  const el = document.getElementById("hjem-session");
  if (!p) { el.innerHTML = ""; return; }
  if (isVacationActive()) {
    el.innerHTML = `
      <div>
        <div class="hs-label">🌴 Pause-modus</div>
        <div class="hs-sub">Ingen press i dag - streaken venter til du er tilbake.</div>
      </div>
    `;
    return;
  }
  const overrides = loadPlanOverrides();
  const todayDay = p.week.find(d => d.isToday);
  const resolved = resolvePlanDay(todayDay, overrides);
  const readinessLabel = { go: "Klar for økta", caution: "Vurder lettere", light: "Prioriter hvile" }[p.today.readiness];
  const doneBadge = resolved.done ? " · ✓ Gjort" : "";
  el.innerHTML = `
    <div>
      <div class="hs-label">${resolved.type === "rest" ? "Hviledag" : resolved.label}${doneBadge}</div>
      <div class="hs-sub">Uke ${p.currentWeek}${p.weekIsDeload ? " · Deload" : " av 4"} · ${p.weekFocus}</div>
    </div>
    <span class="hs-readiness ${p.today.readiness}">${readinessLabel}</span>
    <button class="hs-link" id="hjem-session-link">Til plan →</button>
  `;
  document.getElementById("hjem-session-link").addEventListener("click", () => {
    showTab("trening");
    setTimeout(() => {
      const target = document.getElementById("plan-today");
      if (target) target.scrollIntoView({ behavior: "smooth" });
    }, 50);
  });
}

function renderHjemKcalRing() {
  const n = DATA.nutritionPlan;
  const el = document.getElementById("hjem-kcal-ring");
  if (!n) { el.innerHTML = ""; return; }
  const extrasTotal = loadExtras().filter(e => e.date === todayISO()).reduce((s, e) => s + (e.kcal || 0), 0);
  const total = n.dailyKcal + extrasTotal;
  const pct = Math.round(100 * total / n.dailyKcal);
  const over = total > n.dailyKcal;
  el.innerHTML = `
    <div class="hjem-ring" style="background: conic-gradient(${over ? "var(--hj-accent2)" : "var(--hj-accent)"} ${Math.min(100, pct)}%, rgba(255,255,255,.12) 0);">
      <div class="hjem-ring-inner">${pct}%</div>
    </div>
    <div class="hjem-ring-label">Kalorier<br>${total} / ${n.dailyKcal} kcal</div>
  `;
}

function renderHjemSavingsRing() {
  const { pct, remaining } = fundProgress();
  const el = document.getElementById("hjem-savings-ring");
  el.innerHTML = `
    <div class="hjem-ring" style="background: conic-gradient(var(--hj-accent2) ${Math.min(100, Math.round(pct))}%, rgba(255,255,255,.12) 0);">
      <div class="hjem-ring-inner">${Math.round(pct)}%</div>
    </div>
    <div class="hjem-ring-label">Hundefond<br>${Math.max(0, Math.round(remaining)).toLocaleString()} kr igjen</div>
  `;
}

async function fetchWeather() {
  const cache = loadLS(WEATHER_CACHE_KEY, null);
  const now = Date.now();
  if (cache && now - cache.ts < 45 * 60 * 1000) return cache.data;
  try {
    const res = await fetch("https://wttr.in/Oslo?format=j1");
    if (!res.ok) throw new Error("weather fetch failed");
    const json = await res.json();
    const cur = json.current_condition[0];
    const data = { tempC: Math.round(parseFloat(cur.temp_C)), desc: cur.weatherDesc[0].value };
    saveLS(WEATHER_CACHE_KEY, { ts: now, data });
    return data;
  } catch (e) {
    return cache ? cache.data : null;
  }
}

function renderHjemWeather() {
  const el = document.getElementById("hjem-weather");
  el.innerHTML = `<div class="hw-desc">Henter vær…</div>`;
  fetchWeather().then(data => {
    if (!data) { el.innerHTML = ""; return; }
    el.innerHTML = `<div class="hw-temp">${data.tempC}°</div><div class="hw-desc">${data.desc}</div>`;
  });
}

function renderHjemBody() {
  const ts = DATA.topStats;
  function chip(id, label, val, unit) {
    const e = document.getElementById(id);
    if (!e) return;
    e.innerHTML = `<div class="label">${label}</div><div class="value">${val !== null && val !== undefined ? val : "–"}${val !== null && val !== undefined && unit ? " " + unit : ""}</div>`;
  }
  if (ts.hrv) chip("hjem-stat-hrv", "HRV", ts.hrv.value, "ms");
  if (ts.sleep) chip("hjem-stat-sleep", "Søvn", ts.sleep.hours, "t");
  if (ts.steps) chip("hjem-stat-steps", "Steg", ts.steps.value != null ? ts.steps.value.toLocaleString() : null, "");
  if (ts.restingHR) chip("hjem-stat-rhr", "Hvilepuls", ts.restingHR.value, "bpm");

  const autoregEl = document.getElementById("hjem-autoreg");
  const reasons = (DATA.program && DATA.program.today && DATA.program.today.reasons) || [];
  let html = `<div class="hjem-card-title">Autoregulering</div><ul>${reasons.map(r => `<li>${r}</li>`).join("")}</ul>`;

  const pr = latestPR();
  const recentSets = loadSetLog().filter(s => s.date >= isoAddDays(todayISO(), -14));
  if (pr && recentSets.length && (new Date(todayISO()) - new Date(pr.date)) / 86400000 >= 21) {
    html += `<div style="margin-top:8px;font-size:12px;color:var(--hj-muted);">💪 Ingen ny PR siste 3 ukene - vurder å øke vekten litt eller bytte øvelse.</div>`;
  }
  autoregEl.innerHTML = html;
}

function renderHjemProgress() {
  const streak = computeStreak();
  const best = loadLS(STREAK_BEST_KEY, 0);
  const isNewBest = streak > 0 && streak > best;
  if (isNewBest) saveLS(STREAK_BEST_KEY, streak);
  const bestShown = Math.max(best, streak);
  document.getElementById("hjem-streak").innerHTML = `
    <div class="hjem-card-title">Streak</div>
    <div class="hjem-streak-num">${streak} ${streak === 1 ? "dag" : "dager"}</div>
    ${isNewBest ? `<div class="hjem-streak-record">🔥 Ny personlig rekord!</div>` : `<div class="hjem-pr-ex">Rekord: ${bestShown} ${bestShown === 1 ? "dag" : "dager"}</div>`}
  `;

  const pr = latestPR();
  document.getElementById("hjem-latest-pr").innerHTML = pr ? `
    <div class="hjem-card-title">Siste PR</div>
    <div class="hjem-pr-ex">${pr.label}</div>
    <div class="hjem-pr-val">${pr.weight != null ? pr.weight + " kg × " : ""}${pr.reps} reps</div>
    <div class="hjem-pr-ex">${fmtShort(pr.date)}</div>
  ` : `<div class="hjem-card-title">Siste PR</div><div class="hjem-pr-ex">Ingen sett logget ennå</div>`;

  const { balance, pct, etaText } = fundProgress();
  document.getElementById("hjem-savings-goal").innerHTML = `
    <div class="hjem-card-title">Sparemål</div>
    <div class="hjem-pr-val">${balance.toLocaleString()} / ${DATA.dogFund.target.toLocaleString()} kr</div>
    <div class="hjem-goal-bar"><div style="width:${Math.min(100, pct)}%"></div></div>
    <div class="hjem-pr-ex" style="margin-top:6px;">${etaText}</div>
  `;

  renderHjemWeekSummary();
}

function renderHjemWeekSummary() {
  const p = DATA.program;
  const el = document.getElementById("hjem-week-summary");
  if (!p || !el) return;
  const overrides = loadPlanOverrides();
  const todayStr = p.today.date;
  const thByDate = {};
  (DATA.trainingHistory || []).forEach(d => { thByDate[d.date] = d; });

  let doneCount = 0, plannedCount = 0, stepDays = 0;
  p.week.forEach(day => {
    if (day.date > todayStr) return;
    const resolved = resolvePlanDay(day, overrides);
    if (resolved.type !== "rest") {
      plannedCount++;
      if (resolved.done) doneCount++;
    }
    const th = thByDate[day.date];
    if (th && th.stepGoalMet) stepDays++;
  });

  const weekStart = p.week[0].date;
  const savedThisWeek = loadTransactions()
    .filter(t => t.category === DATA.dogFund.category && t.date >= weekStart && t.date <= todayStr)
    .reduce((s, t) => s + t.amount, 0);

  el.innerHTML = `
    <div class="hjem-card-title">Denne uken</div>
    <div class="hjem-week-grid">
      <div><b>${doneCount}/${plannedCount}</b><span>økter</span></div>
      <div><b>${stepDays}</b><span>stegmål</span></div>
      <div><b>${Math.round(savedThisWeek)} kr</b><span>spart</span></div>
    </div>
  `;
}

function renderHjemReminder() {
  const el = document.getElementById("hjem-reminder");
  const p = DATA.program;
  if (!p || !el) { if (el) el.innerHTML = ""; return; }
  if (!loadSettings().personalityEnabled || isVacationActive()) { el.innerHTML = ""; return; }
  const overrides = loadPlanOverrides();
  const todayDay = p.week.find(d => d.isToday);
  if (!todayDay) { el.innerHTML = ""; return; }
  const resolved = resolvePlanDay(todayDay, overrides);
  const hour = new Date().getHours();
  const pending = resolved.type !== "rest" && !resolved.done;
  if (!pending || hour < 17) { el.innerHTML = ""; return; }

  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>⏰ Du har ikke logget ${resolved.label.toLowerCase()} ennå i dag.</span>
      <button id="hjem-reminder-link">Gå til økta</button>
    </div>
  `;
  document.getElementById("hjem-reminder-link").addEventListener("click", () => {
    showTab("trening");
    setTimeout(() => {
      const target = document.getElementById("plan-today");
      if (target) target.scrollIntoView({ behavior: "smooth" });
    }, 50);
  });
}

function renderHjem() {
  renderHjemGreeting();
  renderHjemWhy();
  renderHjemReminder();
  renderHjemSession();
  renderHjemKcalRing();
  renderHjemSavingsRing();
  renderHjemWeather();
  renderHjemBody();
  renderHjemProgress();
}

// ---- quick-log bottom bar & drawer ----
function openQuicklogDrawer(title, bodyHtml) {
  document.getElementById("quicklog-drawer-title").textContent = title;
  document.getElementById("quicklog-drawer-body").innerHTML = bodyHtml;
  document.getElementById("quicklog-drawer").classList.add("open");
}
function closeQuicklogDrawer() {
  document.getElementById("quicklog-drawer").classList.remove("open");
}
document.getElementById("quicklog-drawer-close").addEventListener("click", closeQuicklogDrawer);

function renderWaterBadge() {
  const count = loadLS(WATER_KEY, {})[todayISO()] || 0;
  document.getElementById("ql-water-badge").textContent = count > 0 ? count : "";
}
function logWater() {
  const water = loadLS(WATER_KEY, {});
  const today = todayISO();
  water[today] = (water[today] || 0) + 1;
  saveLS(WATER_KEY, water);
  renderWaterBadge();
}

function openMatDrawer() {
  openQuicklogDrawer("Logg mat/drikke", `
    <div class="ql-presets">
      <button data-extra-preset="Sjokolade" data-extra-kcal="250">🍫 Sjokolade</button>
      <button data-extra-preset="Glass vin" data-extra-kcal="120">🍷 Glass vin</button>
      <button data-extra-preset="Øl" data-extra-kcal="150">🍺 Øl</button>
    </div>
    <input type="text" id="ql-mat-name" placeholder="Navn">
    <input type="number" id="ql-mat-kcal" placeholder="kcal (valgfritt)">
    <button class="btn" id="ql-mat-save">Lagre</button>
  `);
  document.querySelectorAll("#quicklog-drawer-body [data-extra-preset]").forEach(btn => {
    btn.addEventListener("click", () => {
      addExtra(btn.dataset.extraPreset, parseInt(btn.dataset.extraKcal, 10));
      renderHjemKcalRing();
      closeQuicklogDrawer();
    });
  });
  document.getElementById("ql-mat-save").addEventListener("click", () => {
    const name = document.getElementById("ql-mat-name").value.trim();
    if (!name) return;
    const kcal = parseInt(document.getElementById("ql-mat-kcal").value, 10) || null;
    addExtra(name, kcal);
    renderHjemKcalRing();
    closeQuicklogDrawer();
  });
}

function openUtgiftDrawer() {
  const cfg = loadBudgetConfig();
  const opts = cfg.categories.map(c => `<option value="${c.key}">${c.label}</option>`).join("");
  openQuicklogDrawer("Logg utgift", `
    <input type="number" id="ql-tx-amount" placeholder="Beløp (kr)">
    <select id="ql-tx-category">${opts}</select>
    <input type="text" id="ql-tx-name" placeholder="Navn (valgfritt)">
    <button class="btn" id="ql-tx-save">Lagre</button>
  `);
  document.getElementById("ql-tx-save").addEventListener("click", () => {
    const amount = parseFloat(document.getElementById("ql-tx-amount").value);
    if (!amount) return;
    const category = document.getElementById("ql-tx-category").value;
    const name = document.getElementById("ql-tx-name").value.trim();
    addTransactionWithRoundUp(todayISO(), amount, category, name);
    renderBudget();
    renderHjemSavingsRing();
    renderHjemProgress();
    closeQuicklogDrawer();
  });
}

document.querySelectorAll("#quicklog-bar button[data-ql]").forEach(btn => {
  btn.addEventListener("click", () => {
    const action = btn.dataset.ql;
    if (action === "vann") { logWater(); return; }
    if (action === "mat") { openMatDrawer(); return; }
    if (action === "utgift") { openUtgiftDrawer(); return; }
    if (action === "okt") {
      showTab("trening");
      setTimeout(() => {
        const target = document.getElementById("plan-today");
        if (target) target.scrollIntoView({ behavior: "smooth" });
      }, 50);
    }
  });
});

renderWaterBadge();
renderHjem();
renderNutritionCoach();

// ---------------------------------------------------------------- rapport (personlig coach)
function reportMetric(key) {
  return (DATA.reportMetrics && DATA.reportMetrics[key]) || { today: null, avg7: null, avg30: null };
}
function minToHM(min) {
  if (min == null) return null;
  const h = Math.floor(min / 60), m = Math.round(min % 60);
  return h > 0 ? `${h}t ${m}min` : `${m}min`;
}
function diffPhrase(latest, baseline, unit) {
  if (latest == null || baseline == null) return "";
  const diff = Math.round((latest - baseline) * 10) / 10;
  if (Math.abs(diff) < 0.3) return "på linje med snittet ditt";
  const word = diff > 0 ? "mer enn" : "mindre enn";
  return `${Math.abs(diff)}${unit} ${word} snittet ditt`;
}
function prsToday() {
  const log = loadSetLog();
  const todays = log.filter(s => s.date === todayISO()).sort((a, b) => a.id.localeCompare(b.id));
  const prior = log.filter(s => s.date !== todayISO());
  const priorBest = {};
  prior.forEach(s => { if (isBetterSet(s, priorBest[s.exercise])) priorBest[s.exercise] = s; });
  const prs = [];
  const seenBest = {};
  todays.forEach(s => {
    const cur = seenBest[s.exercise] || priorBest[s.exercise];
    if (isBetterSet(s, cur)) { prs.push(s); seenBest[s.exercise] = s; }
  });
  return prs;
}

function renderMorningReport() {
  const out = document.getElementById("report-output");
  const sleepM = reportMetric("sleepHours");
  const deepM = reportMetric("deepSleepMin");
  const remM = reportMetric("remSleepMin");
  const bbCharged = reportMetric("bodyBatteryCharged");
  const bbLatest = reportMetric("bodyBatteryLatest");
  const rhrM = reportMetric("restingHR");
  const hrvM = reportMetric("hrv");

  const today = DATA.program.today;
  const todayPlanDay = (DATA.program.week || []).find(d => d.isToday);
  const vacation = isVacationActive();

  let sleepP;
  if (sleepM.today != null) {
    const parts = [];
    if (deepM.today != null) parts.push(`${minToHM(deepM.today)} dyp søvn`);
    if (remM.today != null) parts.push(`${minToHM(remM.today)} REM`);
    sleepP = `Du sov <b>${sleepM.today} t</b> i natt${parts.length ? ` (${parts.join(", ")})` : ""} - det er ${diffPhrase(sleepM.today, sleepM.avg7, "t")} siste 7 dager`;
    if (sleepM.avg30 != null) sleepP += ` og ${diffPhrase(sleepM.today, sleepM.avg30, "t")} siste 30 dager`;
    sleepP += ".";
  } else {
    sleepP = "Ingen søvndata for i natt ennå - sjekk at klokken har synkronisert.";
  }

  let bbP = "";
  if (bbLatest.today != null) {
    bbP = `Body Battery startet dagen på <b>${bbLatest.today}/100</b>`;
    if (bbCharged.today != null) bbP += `, etter å ha ladet ${bbCharged.today} poeng i natt`;
    bbP += ".";
  }

  const vitalsBits = [];
  if (hrvM.today != null) vitalsBits.push(`HRV i natt var ${hrvM.today} ms${hrvM.avg7 != null ? ` (snitt 7d: ${hrvM.avg7} ms)` : ""}`);
  if (rhrM.today != null) vitalsBits.push(`hvilepuls ${rhrM.today} bpm${rhrM.avg7 != null ? ` (snitt 7d: ${rhrM.avg7})` : ""}`);
  const vitalsP = vitalsBits.length ? vitalsBits.join(", ") + "." : "";

  let verdict;
  if (today.readiness === "go") verdict = "Alt i alt ser kroppen klar ut for en god økt i dag. 💪";
  else if (today.readiness === "caution") verdict = "Kroppen ber om litt ekstra oppmerksomhet i dag - ikke stress, bare justér.";
  else verdict = "Kroppen signaliserer at den trenger mer restitusjon i dag.";

  const sovnHtml = `
    <div class="report-section">
      <h3>😴 Søvn &amp; restitusjon</h3>
      <p>${sleepP}</p>
      ${bbP ? `<p>${bbP}</p>` : ""}
      ${vitalsP ? `<p>${vitalsP}</p>` : ""}
      <div class="report-highlight">${verdict}</div>
    </div>`;

  let trainingHtml;
  if (vacation) {
    trainingHtml = `
    <div class="report-section">
      <h3>🏋️ Dagens trening</h3>
      <p>Du er i pause-modus akkurat nå - ingen treningskrav i dag. Nyt pausen, kroppen tar den igjen senere. 🌴</p>
    </div>`;
  } else {
    const sessionLabel = todayPlanDay ? todayPlanDay.sessionLabel : null;
    const reasons = today.reasons || [];
    let advice;
    if (today.readiness === "go") {
      advice = `Kjør planen som normalt${sessionLabel ? `: <b>${sessionLabel}</b>` : ""}. Denne uken er fokuset «${DATA.program.weekFocus}» (${DATA.program.weekSetsNote}).`;
    } else if (today.readiness === "caution") {
      advice = `Gjør økten${sessionLabel ? ` (<b>${sessionLabel}</b>)` : ""}, men kutt gjerne siste sett på et par øvelser eller ta litt lavere vekt enn planlagt. Målet i dag er å bevege deg godt, ikke å sette rekord.`;
    } else {
      advice = `Vurder å bytte dagens ${sessionLabel ? `«${sessionLabel}»` : "økt"} til en rolig gåtur eller mobilitet, eller gjør bare aktiveringsdelen av økten. Kroppen trenger restitusjon mer enn volum i dag.`;
    }
    trainingHtml = `
    <div class="report-section">
      <h3>🏋️ Dagens trening</h3>
      <p>${advice}</p>
      ${reasons.length ? `<ul>${reasons.map(r => `<li>${r}</li>`).join("")}</ul>` : ""}
    </div>`;
  }

  const yISO = isoAddDays(todayISO(), -1);
  const yTotals = dayNutritionTotals(yISO);
  const n = DATA.nutritionPlan;
  const proteinGap = n.proteinMin - yTotals.protein;
  let nutritionP1 = `I går fikk du i deg rundt <b>${yTotals.kcal} kcal</b> og <b>${yTotals.protein} g protein</b> (mål: ${n.proteinMin} g+).`;
  if (!yTotals.mealsLogged.length && !yTotals.extras.length) {
    nutritionP1 = `Du logget ikke måltider i går, så dette er et grovt anslag basert på planen.`;
  }
  let nutritionP2;
  let suggestion = null;
  if (proteinGap > 20) {
    nutritionP2 = "Det er under proteinmålet - i dag bør du prioritere proteinrike valg.";
    suggestion = n.lunch.options.concat(n.dinner.options).slice().sort((a, b) => b.protein - a.protein)[0];
  } else {
    nutritionP2 = "Bra jobbet med proteinet i går! 🙌";
  }

  const nutritionHtml = `
    <div class="report-section">
      <h3>🍽️ Ernæring</h3>
      <p>${nutritionP1} ${nutritionP2}</p>
      ${suggestion ? `<div class="report-highlight">Forslag til i dag: <b>${suggestion.name}</b> (${suggestion.kcal} kcal, ${suggestion.protein} g protein)</div>` : ""}
      <p>Dagens kaloribudsjett er <b>${n.dailyKcal} kcal</b>.</p>
    </div>`;

  const why = loadWhy();
  const practicalHtml = `
    <div class="report-section">
      <h3>📋 Praktisk info</h3>
      <p id="report-weather-line">Henter vær…</p>
      ${why ? `<div class="report-highlight">💛 Husk hvorfor: ${why}</div>` : ""}
    </div>`;

  out.innerHTML = `
    <div class="report-title">Morgenrapport · ${fmtDate(todayISO())}</div>
    ${sovnHtml}${trainingHtml}${nutritionHtml}${practicalHtml}
  `;

  fetchWeather().then(w => {
    const el = document.getElementById("report-weather-line");
    if (!el) return;
    el.textContent = w ? `Ute er det ${w.tempC}° og ${w.desc.toLowerCase()} i dag.` : "Fant ikke værdata akkurat nå.";
  });
}

function renderEveningReport() {
  const out = document.getElementById("report-output");
  const vacation = isVacationActive();
  const todayStr = todayISO();
  const todayPlanDay = (DATA.program.week || []).find(d => d.isToday);

  const setsToday = loadSetLog().filter(s => s.date === todayStr);
  const trained = setsToday.length > 0;
  let trainingLine;
  if (vacation) {
    trainingLine = "Du er i pause-modus - ingen treningskrav i dag, og det er helt greit.";
  } else if (!todayPlanDay) {
    trainingLine = "Fant ikke dagens plan.";
  } else if (todayPlanDay.sessionType === "rest") {
    trainingLine = "I dag var en hviledag - nyt den.";
  } else if (trained) {
    trainingLine = `Du logget ${setsToday.length} sett på dagens økt (${todayPlanDay.sessionLabel}). Bra jobba!`;
  } else {
    trainingLine = `Dagens plan var «${todayPlanDay.sessionLabel}», men du har ikke logget noe ennå i dag - fortsatt tid til å få det inn, eller ta det igjen i morgen.`;
  }

  const totals = dayNutritionTotals(todayStr);
  const n = DATA.nutritionPlan;
  const overBudget = totals.kcal > n.dailyKcal;
  let nutritionLine;
  if (totals.extras.length) {
    const names = totals.extras.map(e => e.name).join(", ");
    nutritionLine = overBudget
      ? `Du logget ${names} i dag utenom planen, og endte på ${totals.kcal} kcal (budsjett ${n.dailyKcal}). Litt over i dag - helt greit, juster i morgen og fortsett.`
      : `Du logget ${names} i dag, men holdt deg likevel innenfor kaloribudsjettet (${totals.kcal} / ${n.dailyKcal} kcal). Bra kontroll! 👏`;
  } else {
    nutritionLine = overBudget
      ? `Du endte på rundt ${totals.kcal} kcal i dag, litt over budsjettet på ${n.dailyKcal}. Ingen grunn til dårlig samvittighet - bare ta det med i morgen.`
      : `Du holdt deg fint innenfor kaloribudsjettet i dag (${totals.kcal} / ${n.dailyKcal} kcal).`;
  }

  const logHtml = `
    <div class="report-section">
      <h3>📒 Dagens logg vs. plan</h3>
      <p>${trainingLine}</p>
      <p>${nutritionLine}</p>
    </div>`;

  const prs = prsToday();
  const totalVolume = setsToday.reduce((s, x) => s + (x.weight || 0) * x.reps, 0);
  const txToday = loadTransactions().filter(t => t.date === todayStr);
  const savedToday = txToday.filter(t => t.category === DATA.dogFund.category).reduce((s, t) => s + t.amount, 0);
  const spentToday = txToday.filter(t => t.category !== DATA.dogFund.category).reduce((s, t) => s + t.amount, 0);

  const progressBits = [];
  if (prs.length) progressBits.push(`🏆 Ny PR i dag: ${prs.map(p => `${p.label} (${p.weight != null ? p.weight + " kg × " + p.reps : p.reps + " reps"})`).join(", ")}!`);
  if (totalVolume > 0) progressBits.push(`Treningsvolum i dag: ca. ${Math.round(totalVolume)} kg totalt (vekt × reps).`);
  if (savedToday > 0) progressBits.push(`Du la ${Math.round(savedToday)} kr i hundefondet i dag. 🐶`);
  if (spentToday > 0) progressBits.push(`Du brukte ${Math.round(spentToday)} kr i dag.`);
  if (!progressBits.length) progressBits.push("Ingen ny aktivitet logget i dag - det er også helt ok.");

  const progressHtml = `
    <div class="report-section">
      <h3>📈 Fremgang</h3>
      <ul>${progressBits.map(b => `<li>${b}</li>`).join("")}</ul>
    </div>`;

  const tomorrowDate = isoAddDays(todayStr, 1);
  const tomorrowPlanDay = (DATA.program.week || []).find(d => d.date === tomorrowDate);
  const sleepM = reportMetric("sleepHours");
  let tip;
  if (sleepM.avg7 != null && sleepM.today != null && sleepM.today < sleepM.avg7 - 1) {
    tip = "Du sov mindre enn vanlig de siste dagene - prøv å legge deg litt tidligere i kveld.";
  } else if (tomorrowPlanDay && tomorrowPlanDay.sessionType === "strength" && todayPlanDay && todayPlanDay.sessionType === "strength" && !trained) {
    tip = `I morgen er det «${tomorrowPlanDay.sessionLabel}» - sett av tid til den nå som du vet du har en treningsdag.`;
  } else if (overBudget) {
    tip = "Siden dagens kaloribudsjett ble sprengt litt, kan det være greit å planlegge et roligere måltid i morgen.";
  } else if (totals.extras.length >= 2) {
    tip = "Du logget flere ting utenom planen i dag - sjekk om «Eget forslag» under lunsj/middag kan dekke noen av favorittene dine faste, så blir det lettere å planlegge.";
  } else {
    tip = "Fortsett som nå - ingenting som trenger justering i morgen.";
  }

  const tomorrowHtml = `
    <div class="report-section">
      <h3>🌱 Forberedelse til i morgen</h3>
      <p>${tip}</p>
    </div>`;

  out.innerHTML = `
    <div class="report-title">Kveldsrapport · ${fmtDate(todayStr)}</div>
    ${logHtml}${progressHtml}${tomorrowHtml}
  `;
}

function renderWeeklyReport() {
  const out = document.getElementById("report-output");
  const todayStr = todayISO();
  const weekStart = isoAddDays(todayStr, -6);

  const history = (DATA.dailyHistory || []).filter(d => d.date >= weekStart && d.date <= todayStr);
  const setLog = loadSetLog();
  const tx = loadTransactions();
  const extras = loadExtras();

  function volumeOn(date) {
    return setLog.filter(s => s.date === date).reduce((s, x) => s + (x.weight || 0) * x.reps, 0);
  }

  const patterns = [];
  const lowSleepDays = history.filter(d => d.sleepHours != null && d.sleepHours < 7);
  const okSleepDays = history.filter(d => d.sleepHours != null && d.sleepHours >= 7);
  if (lowSleepDays.length >= 2 && okSleepDays.length >= 2) {
    const avgLow = lowSleepDays.reduce((s, d) => s + volumeOn(d.date), 0) / lowSleepDays.length;
    const avgOk = okSleepDays.reduce((s, d) => s + volumeOn(d.date), 0) / okSleepDays.length;
    if (avgOk > 0) {
      const pctDrop = Math.round(100 * (avgOk - avgLow) / avgOk);
      if (Math.abs(pctDrop) >= 10) {
        patterns.push(pctDrop > 0
          ? `På dager med under 7 timer søvn trente du i snitt ${pctDrop}% mindre volum enn på dager med mer søvn.`
          : "Du trente faktisk mer på dager med mindre søvn denne uken - gøy å se, men følg med at det ikke går på bekostning av restitusjonen over tid.");
      }
    }
  }

  const spendByWeekday = {};
  tx.filter(t => t.date >= weekStart && t.category !== DATA.dogFund.category).forEach(t => {
    const wd = new Date(t.date + "T00:00:00").getDay();
    spendByWeekday[wd] = (spendByWeekday[wd] || 0) + t.amount;
  });
  const weekdayLabels = ["Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag"];
  const spendEntries = Object.entries(spendByWeekday).sort((a, b) => b[1] - a[1]);
  if (spendEntries.length && spendEntries[0][1] > 0) {
    patterns.push(`Du brukte mest penger på ${weekdayLabels[spendEntries[0][0]]} denne uken (${Math.round(spendEntries[0][1])} kr).`);
  }

  const extrasThisWeek = extras.filter(e => e.date >= weekStart);
  if (extrasThisWeek.length >= 5) {
    patterns.push(`Du logget noe utenom planen ${extrasThisWeek.length} ganger denne uken.`);
  }

  if (!patterns.length) {
    patterns.push("Ikke nok data til tydelige mønstre denne uken ennå - fortsett å logge, og du får dypere innsikt neste søndag.");
  }

  const patternsHtml = `
    <div class="report-section">
      <h3>🔍 Mønstre</h3>
      <ul>${patterns.map(p => `<li>${p}</li>`).join("")}</ul>
    </div>`;

  const highlights = [];
  const prsThisWeek = [];
  const priorBest = {};
  setLog.filter(s => s.date < weekStart).forEach(s => { if (isBetterSet(s, priorBest[s.exercise])) priorBest[s.exercise] = s; });
  setLog.filter(s => s.date >= weekStart).sort((a, b) => a.date === b.date ? a.id.localeCompare(b.id) : a.date.localeCompare(b.date)).forEach(s => {
    const cur = priorBest[s.exercise];
    if (isBetterSet(s, cur)) { prsThisWeek.push(s); priorBest[s.exercise] = s; }
  });
  if (prsThisWeek.length) {
    highlights.push(`🏆 ${prsThisWeek.length} ny${prsThisWeek.length > 1 ? "e" : ""} PR denne uken: ${prsThisWeek.map(p => p.label).join(", ")}.`);
  }
  const savedThisWeek = tx.filter(t => t.date >= weekStart && t.category === DATA.dogFund.category).reduce((s, t) => s + t.amount, 0);
  if (savedThisWeek > 0) highlights.push(`🐶 Du la ${Math.round(savedThisWeek)} kr i hundefondet denne uken.`);
  const bestSleepDay = history.filter(d => d.sleepScore != null).sort((a, b) => b.sleepScore - a.sleepScore)[0];
  if (bestSleepDay) highlights.push(`😴 Beste natt denne uken: ${fmtShort(bestSleepDay.date)} med søvnscore ${bestSleepDay.sleepScore}.`);
  const streak = computeStreak();
  if (streak >= 3) highlights.push(`🔥 Du har en streak på ${streak} dager akkurat nå.`);
  if (!highlights.length) highlights.push("En stille uke uten de store toppene - det er også en uke som teller.");

  const highlightsHtml = `
    <div class="report-section">
      <h3>🏆 Høydepunkter</h3>
      <ul>${highlights.map(h => `<li>${h}</li>`).join("")}</ul>
    </div>`;

  const learnings = [];
  const restaurantCat = (loadBudgetConfig().categories || []).find(c => c.key === "restaurant");
  if (restaurantCat && restaurantCat.cap) {
    const restSpend = tx.filter(t => t.date >= weekStart && t.category === "restaurant").reduce((s, t) => s + t.amount, 0);
    if (restSpend > restaurantCat.cap * 0.5) {
      learnings.push("Restaurant/take-away tar en del av budsjettet denne uken - prøv å legge inn et par faste spise-ute-forslag under «Eget forslag», så blir det enklere å styre neste uke.");
    }
  }
  const lowProteinDays = history.filter(d => dayNutritionTotals(d.date).protein < DATA.nutritionPlan.proteinMin * 0.8).length;
  if (lowProteinDays >= 3) {
    learnings.push(`Du lå under proteinmålet ${lowProteinDays} dager denne uken - sjekk ut proteinrundstykke-lunsjen eller en av kyllingmiddagene for et enkelt løft.`);
  }
  if (!learnings.length) learnings.push("Ingenting som trenger store endringer - hold kursen videre.");

  const learningsHtml = `
    <div class="report-section">
      <h3>📘 Læringspunkt</h3>
      <ul>${learnings.slice(0, 2).map(l => `<li>${l}</li>`).join("")}</ul>
    </div>`;

  const why = loadWhy();
  const sessionsThisWeek = (DATA.trainingHistory || []).filter(d => d.date >= weekStart && d.date <= todayStr && d.sessionType !== "rest" && d.loggedTypes.includes(d.sessionType)).length;
  let conclusion = `Denne uken fikk du gjennomført ${sessionsThisWeek} treningsøkt${sessionsThisWeek === 1 ? "" : "er"}`;
  if (streak > 0) conclusion += ` og holder en streak på ${streak} dager`;
  conclusion += `. ${why ? `Husk hvorfor du gjør dette: ${why}. ` : ""}Du bygger noe som varer - fortsett sånn inn i neste uke! 💪`;

  const conclusionHtml = `
    <div class="report-section">
      <h3>💬 Konklusjon</h3>
      <p>${conclusion}</p>
    </div>`;

  out.innerHTML = `
    <div class="report-title">Ukens innsikt · ${fmtShort(weekStart)} - ${fmtShort(todayStr)}</div>
    ${patternsHtml}${highlightsHtml}${learningsHtml}${conclusionHtml}
  `;
}

function showReport(key) {
  document.querySelectorAll(".report-tab-btn").forEach(b => b.classList.toggle("active", b.dataset.report === key));
  if (key === "morning") renderMorningReport();
  else if (key === "evening") renderEveningReport();
  else renderWeeklyReport();
}
document.querySelectorAll(".report-tab-btn").forEach(btn => {
  btn.addEventListener("click", () => showReport(btn.dataset.report));
});
showReport("morning");

// ---------------------------------------------------------------- settings toggles
const personalityToggle = document.getElementById("settings-personality-toggle");
personalityToggle.checked = loadSettings().personalityEnabled;
personalityToggle.addEventListener("change", () => {
  const s = loadSettings();
  s.personalityEnabled = personalityToggle.checked;
  saveSettings(s);
  renderHjemReminder();
});

const vacationToggle = document.getElementById("settings-vacation-toggle");
vacationToggle.checked = isVacationActive();
vacationToggle.addEventListener("change", () => {
  setVacationActive(vacationToggle.checked);
  renderHjem();
});

// ---------------------------------------------------------------- backup / export / import
const BACKUP_KEYS = [
  WEIGHT_LOG_KEY, MEASURE_LOG_KEY, SHOP_LIST_KEY, TX_KEY,
  BUDGET_CONFIG_KEY, PLAN_OVERRIDES_KEY, SET_LOG_KEY, SEEN_KEY, REST_PREFS_KEY,
  FORGOTTEN_SAVINGS_KEY, BADDAY_LOG_KEY, EXTRAS_KEY, WATER_KEY, STREAK_BEST_KEY,
  SETTINGS_KEY, WHY_KEY, VACATION_KEY, CUSTOM_MEALS_KEY, MEAL_LOG_KEY,
];

document.getElementById("backup-export").addEventListener("click", () => {
  const dump = {};
  BACKUP_KEYS.forEach(k => {
    const v = localStorage.getItem(k);
    if (v !== null) dump[k] = JSON.parse(v);
  });
  const blob = new Blob([JSON.stringify(dump, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `dashboard-backup-${todayISO()}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("backup-import-btn").addEventListener("click", () => {
  document.getElementById("backup-import-file").click();
});

document.getElementById("backup-import-file").addEventListener("change", (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  const status = document.getElementById("backup-status");
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      let count = 0;
      BACKUP_KEYS.forEach(k => {
        if (data[k] !== undefined) {
          localStorage.setItem(k, JSON.stringify(data[k]));
          count++;
        }
      });
      status.textContent = `Gjenopprettet ${count} datasett. Laster siden på nytt...`;
      setTimeout(() => location.reload(), 1200);
    } catch (err) {
      status.textContent = "Kunne ikke lese filen - er det en gyldig sikkerhetskopi fra dashbordet?";
    }
  };
  reader.readAsText(file);
});

document.getElementById("footer").textContent = `Generated ${new Date(DATA.meta.generated).toLocaleString()}`;

// ---------------------------------------------------------------- hidden debug page
// Not linked anywhere in the UI - visit dashboard.html#debug (after unlocking the gate)
// to dump DATA plus every localStorage key as raw JSON, for troubleshooting.
function renderDebugPage() {
  const ls = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    try { ls[k] = JSON.parse(localStorage.getItem(k)); } catch (e) { ls[k] = localStorage.getItem(k); }
  }
  document.body.innerHTML = "";
  const pre = document.createElement("pre");
  pre.style.cssText = "white-space:pre-wrap;word-break:break-word;padding:16px;font-size:12px;background:#0b0b0f;color:#8f8;min-height:100vh;margin:0;font-family:monospace;";
  pre.textContent = JSON.stringify({ DATA, localStorage: ls }, null, 2);
  document.body.appendChild(pre);
}
if (location.hash === "#debug" && localStorage.getItem("garminDashboardUnlocked_v1") === "1") {
  renderDebugPage();
}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
