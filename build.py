"""
Reads data/*.json and writes dashboard.html - one self-contained file,
no server needed, charts drawn with inline SVG + vanilla JS.
"""
import json
import os
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")

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
# Built-in ingredient catalog: kcal/protein per 100g, used for the "bytt ingrediens" feature
# in the meal plan. Values are standard reference estimates (±10%, same spirit as the rest
# of the nutrition numbers in this app) - she can add her own ingredients or correct these
# in the app itself (stored in localStorage, layered on top of this list).
INGREDIENT_CATALOG = {
    "kyllingfilet": {"label": "Kyllingfilet", "kcal100": 165, "protein100": 31},
    "kyllingkjottdeig": {"label": "Kyllingkjøttdeig", "kcal100": 143, "protein100": 18},
    "karbonadedeig": {"label": "Karbonadedeig", "kcal100": 220, "protein100": 18},
    "kalkunfilet": {"label": "Kalkunfilet", "kcal100": 135, "protein100": 29},
    "laksefilet": {"label": "Laksefilet", "kcal100": 208, "protein100": 20},
    "torsk": {"label": "Torsk/hvit fisk", "kcal100": 82, "protein100": 18},
    "egg": {"label": "Egg", "kcal100": 155, "protein100": 13},
    "ris": {"label": "Ris (tørrvekt)", "kcal100": 360, "protein100": 7},
    "quinoa": {"label": "Quinoa (tørrvekt)", "kcal100": 368, "protein100": 14},
    "pasta": {"label": "Pasta (tørrvekt)", "kcal100": 350, "protein100": 12},
    "poteter": {"label": "Poteter", "kcal100": 77, "protein100": 2},
    "havregryn": {"label": "Havregryn", "kcal100": 375, "protein100": 13},
    "proteinpulver": {"label": "Proteinpulver", "kcal100": 380, "protein100": 75},
    "proteinmelk": {"label": "Proteinmelk", "kcal100": 55, "protein100": 8},
    "gresk_yoghurt": {"label": "Gresk yoghurt", "kcal100": 97, "protein100": 9},
    "mager_kesam": {"label": "Mager kesam", "kcal100": 70, "protein100": 12},
    "cottage_cheese": {"label": "Cottage cheese", "kcal100": 98, "protein100": 11},
    "skyr": {"label": "Høyprotein yoghurt/skyr", "kcal100": 60, "protein100": 10},
    "kakaogranola": {"label": "Kakaogranola", "kcal100": 450, "protein100": 8},
    "chiafro": {"label": "Chiafrø", "kcal100": 486, "protein100": 17},
}

# Each recipe's "items" are either a structured, swappable ingredient line
# ({"ing": <catalog key>, "amount": grams, optionally "display": "<custom label>"})
# or a plain non-swappable display line ({"text": "..."}) for garnish/sauces that
# aren't worth a full macro breakdown. "kcal"/"protein" stay the original hand-estimated
# totals for the recipe; _finalize_nutrition_plan() below backs out how much of that total
# isn't explained by the structured ingredients ("extraKcal"/"extraProtein" - covers the
# text-only lines), so swapping a structured ingredient recalculates the total correctly
# without needing to re-type every recipe's numbers by hand.
NUTRITION_PLAN = {
    "dailyKcal": 1750,
    "proteinMin": 140,
    "note": "Tallene er grove anslag basert på vanlige produktverdier (±10%) - sjekk egne etiketter (proteinpulver, YT-produkter) for mer nøyaktige tall.",
    "breakfast": {
        "label": "Frokost - standard, eller velg et eget forslag",
        "options": [
            {"name": "Havregrøt med protein", "items": [
                {"ing": "havregryn", "amount": 40},
                {"ing": "proteinpulver", "amount": 20},
                {"ing": "proteinmelk", "amount": 100, "display": "1 dl proteinmelk"},
                {"ing": "chiafro", "amount": 10},
                {"ing": "gresk_yoghurt", "amount": 100},
            ], "kcal": 450, "protein": 32},
        ],
    },
    "lunch": {
        "label": "Lunsj - velg én, rullér gjennom uken",
        "options": [
            {"name": "Kyllingfilet-wrap", "items": [
                {"ing": "kyllingfilet", "amount": 130},
                {"text": "1 grovt pitabrød"},
                {"text": "agurk og paprika"},
                {"text": "1 ss lett rømme/yoghurtdressing"},
            ], "kcal": 400, "protein": 35},
            {"name": "Karbonadedeig med ris", "items": [
                {"ing": "karbonadedeig", "amount": 120},
                {"ing": "ris", "amount": 60, "display": "60 g ris (tørrvekt)"},
                {"text": "agurk og paprika"},
            ], "kcal": 430, "protein": 28},
            {"name": "Kyllingkjøttdeig-taco", "items": [
                {"ing": "kyllingkjottdeig", "amount": 130},
                {"text": "2 extra thin tacolefser"},
                {"text": "agurk og paprika"},
                {"text": "litt mager kesam"},
            ], "kcal": 400, "protein": 32},
            {"name": "Proteinrundstykke med kyllingfilet", "items": [
                {"text": "1 proteinrundstykke"},
                {"ing": "kyllingfilet", "amount": 80, "display": "80 g kyllingfilet-pålegg"},
                {"text": "salat og tomat"},
                {"text": "litt lett dressing"},
            ], "kcal": 350, "protein": 30},
            {"name": "Wrap med ferdigstekt kylling", "items": [
                {"text": "1 grov tortillalefse"},
                {"ing": "kyllingfilet", "amount": 100, "display": "100 g ferdigstekt kyllingfilet (butikk)"},
                {"text": "agurk og paprika"},
                {"text": "litt lett dressing"},
            ], "kcal": 380, "protein": 30},
        ],
    },
    "snack": {
        "label": "Mellommåltid - velg én",
        "options": [
            {"name": "Yoghurt med bringebær og granola", "items": [
                {"ing": "skyr", "amount": 150, "display": "150 g høyprotein yoghurt/skyr"},
                {"ing": "kakaogranola", "amount": 20},
                {"text": "bringebær"},
                {"text": "1 ts Biscoff"},
            ], "kcal": 230, "protein": 18},
            {"name": "YT proteinprodukt", "items": [
                {"text": "1 stk (sjekk etiketten for nøyaktige tall)"},
            ], "kcal": 180, "protein": 20},
            {"name": "Mager kesam med bringebær", "items": [
                {"ing": "mager_kesam", "amount": 150},
                {"text": "bringebær"},
            ], "kcal": 110, "protein": 18},
        ],
    },
    "dinner": {
        "label": "Middag - velg én, rullér gjennom uken",
        "options": [
            {"name": "Kyllingkjøttdeig-stekt ris", "items": [
                {"ing": "kyllingkjottdeig", "amount": 150},
                {"ing": "ris", "amount": 70, "display": "70 g ris (tørrvekt)"},
                {"text": "amerikansk grønnsaksblanding (frossen)"},
                {"text": "litt soyasaus"},
            ], "kcal": 520, "protein": 42},
            {"name": "Pasta med kjøttsaus", "items": [
                {"ing": "pasta", "amount": 80, "display": "80 g pasta (tørrvekt)"},
                {"ing": "karbonadedeig", "amount": 130},
                {"text": "litt tomatsaus"},
                {"text": "paprika"},
            ], "kcal": 560, "protein": 33},
            {"name": "Kylling med ris", "items": [
                {"ing": "kyllingfilet", "amount": 150},
                {"ing": "ris", "amount": 70, "display": "70 g ris (tørrvekt)"},
                {"text": "agurk og paprika"},
            ], "kcal": 480, "protein": 44},
            {"name": "Laks med poteter", "items": [
                {"ing": "laksefilet", "amount": 150},
                {"ing": "poteter", "amount": 200},
                {"text": "brokkoli"},
            ], "kcal": 490, "protein": 38},
            {"name": "Taco-gryte", "items": [
                {"ing": "kyllingkjottdeig", "amount": 150},
                {"text": "100 g mais og bønner"},
                {"text": "1 dl lettrømme"},
                {"text": "liten porsjon tortillachips"},
            ], "kcal": 540, "protein": 36},
        ],
    },
}


def _finalize_nutrition_plan(plan, catalog):
    for group_key in ("breakfast", "lunch", "snack", "dinner"):
        for opt in plan[group_key]["options"]:
            structured_kcal = sum(catalog[i["ing"]]["kcal100"] * i["amount"] / 100 for i in opt["items"] if "ing" in i)
            structured_protein = sum(catalog[i["ing"]]["protein100"] * i["amount"] / 100 for i in opt["items"] if "ing" in i)
            opt["extraKcal"] = round(opt["kcal"] - structured_kcal)
            opt["extraProtein"] = round(opt["protein"] - structured_protein, 1)
    return plan


NUTRITION_PLAN = _finalize_nutrition_plan(NUTRITION_PLAN, INGREDIENT_CATALOG)
# ---- budget (starting points - fully editable in the app; income 32k/mnd) ----
# Økonomimåned: 16.-15. (lønn kommer den 16.). "cap" is the initial budget amount;
# the app converts this to a capHistory (effective-dated) list on first load so that
# later edits only affect the economic month they were made in, and onward.
BUDGET_DEFAULTS = {
    "income": 32000,
    "categories": [
        # faste utgifter
        {"key": "husleie", "label": "Husleie", "type": "fixed", "icon": "🏠", "cap": 13500},
        {"key": "strom", "label": "Strøm", "type": "fixed", "icon": "⚡", "cap": 1200},
        {"key": "forsikring", "label": "Forsikring", "type": "fixed", "icon": "🛡️", "cap": 400},
        {"key": "mobil_internett", "label": "Mobil og internett", "type": "fixed", "icon": "📱", "cap": 500},
        {"key": "abonnementer", "label": "Abonnementer", "type": "fixed", "icon": "🔁", "cap": 400},
        {"key": "treningssenter", "label": "Treningssenter", "type": "fixed", "icon": "🏋️", "cap": 500},
        {"key": "studielan", "label": "Studielån", "type": "fixed", "icon": "🎓", "cap": 2000},
        {"key": "ruter", "label": "Ruter", "type": "fixed", "icon": "🚌", "cap": 800},
        # variable utgifter
        {"key": "mat", "label": "Mat og dagligvarer", "type": "variable", "icon": "🛒", "cap": 3800},
        {"key": "transport", "label": "Transport", "type": "variable", "icon": "🚗", "cap": 900},
        {"key": "klaer_velvare", "label": "Klær og velvære", "type": "variable", "icon": "👗", "cap": 700},
        {"key": "fritid_sosialt", "label": "Fritid og sosialt", "type": "variable", "icon": "🎉", "cap": 800},
        {"key": "annet", "label": "Annet", "type": "variable", "icon": "📦", "cap": 500},
        # sparing (egne linjer, men regnes som variable utgifter)
        {"key": "hundefond", "label": "Sparing: Hund", "type": "variable", "savings": True, "icon": "🐶", "cap": 1000},
        {"key": "sparing_pensjon", "label": "Sparing: Pensjon", "type": "variable", "savings": True, "icon": "👵", "cap": 1000},
        {"key": "sparing_hoyrente", "label": "Sparing: Høyrente", "type": "variable", "savings": True, "icon": "💰", "cap": 1000},
    ],
}
DOG_FUND = {"target": 30000, "startSaved": 5000, "category": "hundefond"}
ACTIVE_CAL_GOAL_DEFAULT = 400

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
            "goal": safe_round((d0.get("movement") or {}).get("steps", {}).get("goal")),
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
    steps_weeks, steps_vals = weekly_avg(daily, lambda v: (v.get("movement") or {}).get("steps", {}).get("value"))
    active_cal_weeks, active_cal_vals = weekly_avg(daily, lambda v: (v.get("calories") or {}).get("burnedActive"))
    stress_weeks, stress_vals = weekly_avg(daily, lambda v: (v.get("stress") or {}).get("avgLevel"))

    # align all trend series onto the union of weeks present in training load / rhr (use rhr as backbone, it's most complete)
    trends = {
        "trainingLoad": {"weeks": load_weeks, "values": training_load},
        "restingHR": {"weeks": rhr_weeks, "values": rhr_vals},
        "hrv": {"weeks": hrv_weeks, "values": hrv_vals},
        "sleepHours": {"weeks": sleep_weeks, "values": sleep_vals},
        "sleepScore": {"weeks": sleep_score_weeks, "values": sleep_score_vals},
        "steps": {"weeks": steps_weeks, "values": steps_vals},
        "activeCalories": {"weeks": active_cal_weeks, "values": active_cal_vals},
        "stress": {"weeks": stress_weeks, "values": stress_vals},
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
        "activeCalories": (daily, daily_keys, lambda v: (v.get("calories") or {}).get("burnedActive")),
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

    hrv_latest, hrv_baseline = trailing_baseline(hrv, hrv_keys, lambda v: v.get("lastNightAvg"))
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

    # ------------------------------------------------------- recovery / strain scores (Sonar-style)
    def sub_score(value, baseline, higher_is_better, swing):
        """0-100, where 50 = exactly at your personal baseline. swing is the fractional
        deviation from baseline that reaches 0 or 100 (e.g. 0.3 = 30% off baseline)."""
        if value is None or baseline is None or baseline == 0:
            return None
        diff = (value - baseline) / baseline
        if not higher_is_better:
            diff = -diff
        return max(0, min(100, round(50 + diff / swing * 50)))

    hrv_sub = sub_score(hrv_latest, hrv_baseline, higher_is_better=True, swing=0.3)
    rhr_sub = sub_score(rhr_latest, rhr_baseline, higher_is_better=False, swing=0.12)
    sleep_sub = round(sleep_score_latest) if sleep_score_latest is not None else None
    stress_sub = round(100 - stress_latest) if stress_latest is not None else None
    recovery_parts = [(v, w) for v, w in (
        (hrv_sub, 0.30), (rhr_sub, 0.20), (sleep_sub, 0.30), (stress_sub, 0.20),
    ) if v is not None]
    recovery_score = (
        round(sum(v * w for v, w in recovery_parts) / sum(w for _, w in recovery_parts))
        if recovery_parts else None
    )

    daily_load = defaultdict(float)
    for a in activities:
        start = a.get("startTimeLocal")
        tl = a.get("activityTrainingLoad")
        if start and tl is not None:
            daily_load[start.split("T")[0]] += tl
    today_load = daily_load.get(today.isoformat(), 0)
    load_window_start = (today - timedelta(days=90)).isoformat()
    recent_loads = [v for k, v in daily_load.items() if k >= load_window_start and v > 0]
    load_reference = max(recent_loads) if recent_loads else None
    if load_reference:
        strain_score = round(min(100, 100 * today_load / load_reference))
    else:
        strain_score = 0 if today_load == 0 else None

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
            "recoveryScore": recovery_score,
            "strainScore": strain_score,
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
        "ingredientCatalog": INGREDIENT_CATALOG,
        "weeklyBySport": weekly_by_sport_out,
        "trends": trends,
        "records": records,
        "sportColors": SPORT_COLORS,
        "sportOrder": SPORT_ORDER,
        "budgetDefaults": BUDGET_DEFAULTS,
        "dogFund": DOG_FUND,
        "activeCalGoalDefault": ACTIVE_CAL_GOAL_DEFAULT,
        "pointsConfig": POINTS_CONFIG,
        "trainingHistory": training_history,
        "programStart": GS_START.isoformat(),
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
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>Katrine 2027</title>
<link rel="icon" href="icons/favicon-32.png" sizes="32x32">
<link rel="icon" href="icons/favicon-16.png" sizes="16x16">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#7a1f3d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Katrine 2027">
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
  html { -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0;
    font-family: Nunito, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--ink);
    padding: 0 0 90px;
    overflow-x: hidden;
  }
  button, .btn, a { touch-action: manipulation; }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 0 20px; }
  h1, h2, h3 { font-family: "Playfair Display", serif; }

  header.hero {
    background: linear-gradient(135deg, #7a1f3d 0%, #a8406a 100%);
    color: #fff;
    padding: calc(14px + env(safe-area-inset-top)) 20px 14px;
  }
  header.hero .wrap { display: flex; flex-direction: column; gap: 2px; }
  header.hero .hero-greeting { font-family: "Playfair Display", serif; font-style: italic; font-weight: 700; font-size: 21px; }
  header.hero .hero-datetime { color: #fbe7ed; font-size: 12.5px; font-weight: 500; }
  .hero-status-strip { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; }
  .hss-chip { display: flex; flex-direction: column; gap: 3px; }
  .hss-main { font-size: 13px; font-weight: 700; color: #fff; white-space: nowrap; }
  .hss-spark { width: 46px; height: 12px; display: block; color: #f6b8ca; opacity: .85; }

  .goal-row {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    margin: 10px 0 24px;
  }
  .goal-chip {
    background: #fff0f4;
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 13px;
    color: var(--muted);
  }
  .goal-chip b { font-size: 16px; display: block; color: var(--ink); }
  .goal-chip .delta-up { color: #2f8a4e; }
  .goal-chip .delta-down { color: #c0392b; }

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
  .week-day .wd { color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: .04em; display: flex; align-items: center; justify-content: space-between; gap: 4px; }
  .week-day .sess { font-size: 12px; margin: 6px 0; min-height: 30px; color: var(--ink); }
  .week-day .mark { font-size: 15px; color: var(--accent); }
  .week-day .mark.missed { color: var(--muted); font-size: 13px; }
  .week-day-handle {
    cursor: grab; color: var(--muted); font-size: 13px; line-height: 1; padding: 2px 4px;
    touch-action: none; user-select: none; -webkit-user-select: none;
  }
  .week-day.dragging { opacity: 0.4; }
  .week-day.drop-target { outline: 2px dashed var(--accent2); outline-offset: -1px; }

  .missed-day-box {
    background: #fff0f4; border: 1px solid var(--line); border-radius: 12px;
    padding: 12px 14px; margin: 10px 0 14px; font-size: 13px; color: var(--ink);
  }
  .missed-day-actions { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }

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
  .meal-option .meal-items { font-size: 12px; color: var(--muted); margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px 10px; }
  .meal-item-text { white-space: nowrap; }
  .meal-item-ing { white-space: nowrap; }
  .meal-item-ing.meal-item-overridden { color: var(--accent); font-weight: 700; }
  .meal-ing-swap-btn, .meal-ing-reset-btn {
    background: none; border: none; color: var(--accent2); cursor: pointer;
    font-size: 11px; padding: 0; margin-left: 3px; text-decoration: underline;
  }
  .meal-option-remove { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 11px; padding: 0; margin-left: 6px; }
  .meal-add-form { margin-top: 2px; }
  .ing-swap-form {
    background: var(--bg); border: 1px solid var(--line); border-radius: 10px;
    padding: 10px; margin-top: 6px; display: flex; flex-direction: column; gap: 8px;
  }
  .ing-swap-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .ing-swap-row select { font-family: inherit; font-size: 13px; border: 1px solid var(--line); border-radius: 8px; padding: 5px 6px; background: #fff; }
  .ing-swap-row input { width: 64px; font-family: inherit; font-size: 13px; border: 1px solid var(--line); border-radius: 8px; padding: 5px 6px; }
  .ing-new-form { display: flex; gap: 6px; flex-wrap: wrap; }
  .ing-new-form input { font-family: inherit; font-size: 13px; border: 1px solid var(--line); border-radius: 8px; padding: 5px 6px; }
  .ing-new-form input[type="text"] { width: 140px; }
  .ing-new-form input[type="number"] { width: 90px; }
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
  .chart-wrap svg { display: block; width: 100%; height: auto; }

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
  .sync-card { margin: 16px 0 0; }
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
  .log-form { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
  .log-form input, .log-form select {
    font-family: Nunito, sans-serif; font-size: 14px; border: 1px solid var(--line);
    border-radius: 10px; padding: 11px 12px; background: var(--bg); color: var(--ink); min-height: 44px;
  }
  .log-form input[type="number"] { width: 100px; }
  .log-form input[type="date"] { width: 150px; }
  .log-form input[type="text"] { flex: 1; min-width: 120px; }
  .btn {
    font-family: Nunito, sans-serif; font-size: 14px; font-weight: 700; color: #fff;
    background: var(--accent); border: none; border-radius: 10px; padding: 12px 20px;
    min-height: 44px; cursor: pointer;
  }
  .btn.secondary { background: var(--accent3); color: var(--ink); }
  .btn.ghost { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  .btn.small { padding: 6px 12px; font-size: 12px; min-height: 0; }
  .btn-big { width: 100%; padding: 15px; font-size: 16px; margin-top: 2px; }
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
  .budget-section-title { margin: 0 0 12px; font-size: 14px; color: var(--accent); display: flex; align-items: center; gap: 6px; }
  .budget-cat-list { display: flex; flex-direction: column; gap: 14px; }
  .cat-row { margin-top: 0; }
  .cat-row .cat-head { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); }
  .cat-row .cat-head b { color: var(--ink); }
  .cat-bar { height: 8px; border-radius: 5px; background: var(--line); margin-top: 4px; overflow: hidden; }
  .cat-bar > div { height: 100%; border-radius: 5px; background: var(--accent2); }
  .cat-bar > div.good { background: #7bd88f; }
  .cat-bar > div.warn { background: #f6c667; }
  .cat-bar > div.over { background: #e37878; }
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

  /* ---- fremgang (long-term trends/goals) ---- */
  .fremgang-section { margin: 36px 0; }
  .fremgang-section:first-of-type { margin-top: 18px; }
  .fremgang-section h3 { margin: 0 0 4px; font-size: 16px; }
  .fremgang-section .section-sub { margin-bottom: 14px; }
  .period-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  .period-btn, .measure-select-btn {
    border: 1px solid var(--line); background: #fff; color: var(--ink);
    border-radius: 999px; padding: 6px 14px; font-size: 12.5px; font-family: inherit;
    cursor: pointer; transition: background .15s, color .15s, border-color .15s;
  }
  .period-btn.active, .measure-select-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .context-note {
    background: #fff0f4; border-radius: 10px; padding: 10px 14px;
    font-size: 13px; color: var(--ink); margin-top: 10px; line-height: 1.5;
  }
  .tooltip.ml { white-space: normal; text-align: left; line-height: 1.5; transform: translate(-50%, -108%); }
  .weight-goal-row { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
  .weight-goal-row input { width: 70px; border: 1px solid var(--line); border-radius: 8px; padding: 4px 6px; font-family: inherit; font-size: 13px; }
  .savings-goal-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .savings-goal-card { background: #fff0f4; border-radius: 14px; padding: 16px; }
  .savings-goal-card .sg-label { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
  .savings-goal-card .sg-amount { font-size: 19px; font-weight: 700; font-family: "Playfair Display", serif; margin-top: 4px; }
  .savings-goal-card .sg-goal-row { display: flex; align-items: center; gap: 6px; margin-top: 10px; font-size: 12px; color: var(--muted); }
  .savings-goal-card .sg-goal-row input { width: 92px; border: 1px solid var(--line); border-radius: 8px; padding: 3px 6px; font-family: inherit; font-size: 12px; }
  .savings-goal-card .sg-eta { font-size: 12px; color: var(--muted); margin-top: 8px; }
  .fund-summary-row { display: flex; gap: 22px; flex-wrap: wrap; margin-top: 14px; }
  .fund-summary-row .fs-item { font-size: 13px; }
  .fund-summary-row .fs-item b { display: block; font-size: 17px; font-family: "Playfair Display", serif; }
  .fund-summary-row .fs-item b.pos { color: #3f9a5a; }
  .fund-summary-row .fs-item b.neg { color: #c24545; }
  .expense-totals-list { display: flex; flex-direction: column; gap: 6px; margin-top: 14px; }
  .expense-totals-list .et-row { display: flex; justify-content: space-between; font-size: 13px; border-top: 1px solid var(--line); padding-top: 6px; }
  .expense-totals-list .et-row:first-child { border-top: none; padding-top: 0; }

  /* ---- tabs ---- */
  .tab-nav {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    gap: 8px;
    overflow-x: auto;
    background: var(--bg);
    padding: calc(14px + env(safe-area-inset-top)) 0 12px;
    margin-top: -8px;
    border-bottom: 1px solid var(--line);
  }
  .tab-nav button {
    flex: 0 0 auto;
    font-family: Nunito, sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: var(--muted);
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 24px;
    padding: 13px 22px;
    min-height: 46px;
    cursor: pointer;
  }
  .tab-nav button.active { color: #fff; background: var(--accent); border-color: var(--accent); font-weight: 800; }
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

  /* ---- Hjem dashboard (light, mobile-first start page) ---- */
  .hjem-dash {
    --hj-bg: var(--bg); --hj-card: var(--card); --hj-card2: #fff0f4; --hj-ink: var(--ink);
    --hj-muted: var(--muted); --hj-accent: #f6c667; --hj-accent2: var(--accent2); --hj-line: var(--line);
    margin: 0 0 24px; font-family: Nunito, sans-serif;
  }
  .hjem-topbar { display: flex; align-items: center; justify-content: flex-end; margin-bottom: 12px; }
  .hjem-greeting { font-family: "Playfair Display", serif; font-size: 19px; }
  .hjem-datetime { font-size: 12px; color: var(--hj-muted); margin-top: 2px; }
  .hjem-badday-toggle {
    background: var(--hj-card2); color: var(--hj-ink); border: 1px solid var(--hj-line);
    border-radius: 20px; padding: 6px 12px; font-size: 12px; cursor: pointer;
  }
  .hjem-why { font-size: 12px; color: var(--hj-muted); margin: -4px 0 12px; cursor: pointer; }
  .hjem-why.empty { font-style: italic; }
  .hjem-zone { margin-bottom: 18px; }
  .hjem-zone-title { font-size: 13px; color: var(--hj-muted); text-transform: uppercase; letter-spacing: .06em; margin: 0 0 8px; }
  .hjem-card {
    background: var(--hj-card); box-shadow: var(--shadow); border-radius: 14px;
    padding: 12px 14px; color: var(--hj-ink);
  }
  .hjem-card-title { font-size: 12px; color: var(--hj-muted); margin-bottom: 6px; }
  .hjem-topbar-btns { display: flex; align-items: center; gap: 6px; }
  .hjem-refresh-btn {
    background: var(--hj-card2); color: var(--hj-ink); border: 1px solid var(--hj-line);
    border-radius: 50%; width: 30px; height: 30px; font-size: 15px; line-height: 1; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }
  .hjem-refresh-btn.spinning { animation: hjem-spin .6s linear; }
  @keyframes hjem-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .hjem-section-1 .hjem-card { margin-bottom: 10px; }
  .hjem-section-1 .hjem-card:last-child { margin-bottom: 0; }
  .hjem-session { display: flex; flex-direction: column; gap: 12px; }
  .hs-top { display: flex; align-items: center; gap: 14px; }
  .hs-info { flex: 1; min-width: 0; }
  .hjem-session .hs-label { font-size: 15px; font-weight: 700; }
  .hjem-session .hs-sub { font-size: 12px; color: var(--hj-muted); margin-bottom: 6px; }
  .score-ring { position: relative; display: flex; align-items: center; justify-content: center; flex: 0 0 auto; }
  .score-ring svg { display: block; }
  .score-ring-num { position: absolute; font-family: "Playfair Display", serif; font-weight: 700; line-height: 1; }
  .hs-score-block { display: flex; flex-direction: column; align-items: center; gap: 4px; }
  .hs-score-block .hs-score-label { font-size: 10px; color: var(--hj-muted); text-transform: uppercase; letter-spacing: .04em; }
  .hs-recovery-note { font-size: 12px; color: var(--hj-muted); line-height: 1.45; }
  .hs-secondary-scores { display: flex; flex-direction: column; gap: 10px; }
  .hs-mini-score { display: flex; align-items: flex-start; gap: 10px; }
  .hs-mini-score .hs-mini-label { font-size: 11px; color: var(--hj-muted); flex: 1; min-width: 0; padding-top: 3px; }
  .hs-mini-score .hs-mini-label b { display: block; font-size: 13px; color: var(--hj-ink); font-weight: 700; }
  .hs-mini-note { display: block; font-size: 10.5px; color: var(--hj-muted); margin-top: 2px; line-height: 1.3; }
  .hjem-session .hs-status { font-size: 11px; padding: 3px 9px; border-radius: 12px; font-weight: 700; }
  .hjem-session .hs-status.notstarted { background: var(--hj-card2); color: var(--hj-muted); }
  .hjem-session .hs-status.inprogress { background: rgba(246,198,103,.18); color: #b8860b; }
  .hjem-session .hs-status.done { background: rgba(123,216,143,.16); color: #2f8a4e; }
  .hjem-session .hs-link {
    background: none; border: 1px solid var(--hj-line); color: var(--hj-ink);
    border-radius: 10px; padding: 6px 10px; font-size: 12px; cursor: pointer; font-family: Nunito, sans-serif;
  }
  .hjem-nutri-quick { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  .hjem-nutri-quick .hnq-label { font-size: 12px; color: var(--hj-muted); }
  .hjem-nutri-quick .hnq-val { font-size: 17px; font-weight: 700; margin-top: 2px; }
  .hjem-nutri-quick .hnq-val.over { color: #c0392b; }
  .hjem-nutri-quick .hnq-macro { font-size: 11px; color: var(--hj-muted); margin-top: 2px; }
  .hjem-nutri-quick .hnq-balance { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--hj-line); font-size: 11px; color: var(--hj-muted); display: flex; flex-direction: column; gap: 2px; }
  .hjem-nutri-quick .hnq-balance-diff { font-size: 13px; font-weight: 700; color: #2f8a4e; }
  .hjem-nutri-quick .hnq-balance-diff.over { color: #c0392b; }
  .hjem-nutri-quick button {
    background: var(--hj-accent); color: var(--ink); border: none; border-radius: 10px;
    padding: 8px 12px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: Nunito, sans-serif; white-space: nowrap;
  }
  .hjem-tx-list { list-style: none; margin: 0; padding: 0; font-size: 13px; max-height: 120px; overflow-y: auto; }
  .hjem-tx-list li { display: flex; justify-content: space-between; gap: 8px; padding: 5px 0; border-top: 1px solid var(--hj-line); }
  .hjem-tx-list li:first-child { border-top: none; }
  .hjem-tx-list .tx-name { color: var(--hj-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hjem-tx-empty { color: var(--hj-muted); }
  .hjem-tx-total { display: flex; justify-content: space-between; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--hj-line); font-weight: 700; font-size: 13px; }
  .hjem-body-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .hjem-bigstat .hbs-label { font-size: 11px; color: var(--hj-muted); text-transform: uppercase; }
  .hjem-bigstat .hbs-num { font-size: 24px; font-weight: 700; margin: 2px 0 6px; font-family: "Playfair Display", serif; }
  .hjem-bigstat .hbs-bar { background: var(--hj-line); border-radius: 8px; height: 7px; overflow: hidden; }
  .hjem-bigstat .hbs-bar > div { background: var(--hj-accent); height: 100%; }
  .hjem-bigstat .hbs-bar > div.goalmet { background: #7bd88f; }
  .hjem-minirow { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; grid-column: 1 / -1; }
  .hjem-minicard .label { font-size: 11px; color: var(--hj-muted); text-transform: uppercase; }
  .hjem-minicard .value { font-size: 15px; font-weight: 700; margin-top: 3px; display: flex; align-items: center; }
  .hjem-minicard .sub { font-size: 11px; color: var(--hj-muted); margin-top: 1px; min-height: 13px; }
  .stress-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; flex: 0 0 auto; }
  .stress-dot.green { background: #7bd88f; }
  .stress-dot.yellow { background: var(--hj-accent); }
  .stress-dot.red { background: #e37878; }
  .hjem-finance-row { margin-bottom: 10px; cursor: default; }
  .hjem-finance-row:last-child { margin-bottom: 0; }
  .hjem-finance-row .hf-label { font-size: 12px; color: var(--hj-muted); display: flex; justify-content: space-between; }
  .hjem-finance-row .hf-val { font-size: 15px; font-weight: 700; margin-top: 2px; }
  .hjem-finance-bar { background: var(--hj-line); border-radius: 8px; height: 8px; overflow: hidden; margin-top: 6px; }
  .hjem-finance-bar > div { background: var(--hj-accent); height: 100%; }
  .hjem-finance-bar > div.over { background: #e37878; }
  .hjem-invest-change { font-size: 12px; font-weight: 700; margin-left: 6px; }
  .hjem-invest-change.pos { color: #2f8a4e; }
  .hjem-invest-change.neg { color: #c0392b; }
  .hjem-reminder-banner {
    display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;
    background: rgba(246, 198, 103, 0.14); border: 1px solid var(--hj-accent); color: var(--hj-ink);
    border-radius: 12px; padding: 10px 12px; margin-bottom: 10px; font-size: 13px;
  }
  .hjem-reminder-banner button {
    background: var(--hj-accent); color: var(--ink); border: none; border-radius: 8px;
    padding: 6px 12px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: Nunito, sans-serif;
  }

  .quicklog-bar {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 90;
    display: flex; justify-content: center; background: var(--card); border-top: 1px solid var(--line);
    box-shadow: 0 -2px 10px rgba(122, 31, 61, 0.07);
    padding: 8px max(8px, env(safe-area-inset-left)) calc(8px + env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-right));
  }
  .quicklog-bar button {
    background: none; border: none; color: var(--ink); display: flex;
    flex-direction: row; align-items: center; gap: 8px; padding: 8px 32px; border-radius: 999px;
    cursor: pointer; font-family: Nunito, sans-serif; font-weight: 700; font-size: 14px;
  }
  .quicklog-bar button:active { background: var(--line); }
  .quicklog-bar .ql-icon { font-size: 18px; }
  .quicklog-drawer {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 91; background: var(--card); color: var(--ink);
    border-top: 1px solid var(--line); border-radius: 16px 16px 0 0; padding: 14px 16px;
    box-shadow: 0 -2px 16px rgba(122, 31, 61, 0.1);
    transform: translateY(100%); transition: transform .2s ease; max-height: 60vh; overflow-y: auto;
    padding-bottom: calc(76px + env(safe-area-inset-bottom));
  }
  .quicklog-drawer.open { transform: translateY(0); }
  .quicklog-drawer-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-weight: 700; }
  .quicklog-drawer-head button { background: none; border: none; color: var(--muted); font-size: 16px; cursor: pointer; }
  .quicklog-drawer .ql-presets { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  .quicklog-drawer .ql-presets button {
    background: var(--bg); border: 1px solid var(--line); color: var(--ink); border-radius: 20px;
    padding: 8px 14px; font-size: 13px; cursor: pointer;
  }
  .quicklog-drawer input, .quicklog-drawer select {
    width: 100%; padding: 10px 12px; font-size: 14px; border: 1px solid var(--line); border-radius: 10px;
    font-family: Nunito, sans-serif; background: var(--bg); color: var(--ink); box-sizing: border-box; margin-bottom: 8px;
  }
  .quicklog-drawer .btn { width: 100%; }

  @media (max-width: 480px) {
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
    .records-grid { grid-template-columns: repeat(2, 1fr); }
    .trend-grid { grid-template-columns: 1fr; }
    .week-row { overflow-x: scroll; }
    .week-day { min-width: 76px; }
    .log-grid { grid-template-columns: 1fr; }
    .budget-summary-grid { grid-template-columns: 1fr; }
    .savings-goal-grid { grid-template-columns: 1fr; }

    /* inputs/selects under 16px make iOS Safari auto-zoom the page on focus */
    input, select, textarea { font-size: 16px !important; }
    .cat-row .cat-head { flex-wrap: wrap; row-gap: 4px; }
    .cat-row input.cap-edit { width: 72px; }
    .tab-nav { scrollbar-width: none; -webkit-overflow-scrolling: touch; }
    .tab-nav::-webkit-scrollbar { display: none; }
  }
</style>
</head>
<body>

<div id="gate-overlay">
  <div class="gate-box">
    <h2>🔒 Logg inn</h2>
    <p>Logg inn for å åpne dashbordet og synkronisere data på tvers av enhetene dine.</p>
    <input type="email" id="gate-email" placeholder="E-post" autocomplete="username" autocapitalize="off" autocorrect="off" spellcheck="false">
    <input type="password" id="gate-input" placeholder="Passord" autocomplete="current-password">
    <button class="btn" id="gate-submit">Logg inn</button>
    <div class="gate-error" id="gate-error"></div>
  </div>
</div>

<header class="hero">
  <div class="wrap">
    <div class="hero-greeting" id="hero-greeting"></div>
    <div class="hero-datetime" id="hero-datetime"></div>
    <div class="hero-status-strip" id="hero-status-strip"></div>
  </div>
</header>

<div class="wrap">
  <nav class="tab-nav" id="tab-nav">
    <button data-tab="hjem">Hjem</button>
    <button data-tab="kosthold">Kosthold</button>
    <button data-tab="budsjett">Budsjett</button>
    <button data-tab="trening">Treningsplan</button>
    <button data-tab="fremgang">Fremgang</button>
    <button data-tab="handleliste">Handleliste</button>
    <button data-tab="rapport">Rapport</button>
    <button data-tab="statistikk">Statistikk</button>
    <button data-tab="innstillinger">Innstillinger</button>
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
      <div class="hjem-topbar-btns">
        <button class="hjem-refresh-btn" id="hjem-refresh-btn" title="Oppdater">⟳</button>
        <button class="hjem-badday-toggle" id="hjem-badday-toggle">🌧️ Dårlig dag</button>
      </div>
    </div>
    <div class="hjem-why" id="hjem-why"></div>

    <div id="hjem-reminder"></div>

    <section class="hjem-zone hjem-section-1">
      <h3 class="hjem-zone-title">Dagens Plan &amp; Handling</h3>
      <div class="hjem-card hjem-session" id="hjem-session"></div>
      <div class="hjem-card hjem-nutri-quick" id="hjem-kcal-ring"></div>
      <div class="hjem-card" id="hjem-tx-today"></div>
    </section>

    <section class="hjem-zone hjem-section-2">
      <h3 class="hjem-zone-title">Dagens Kropp</h3>
      <div id="hjem-body-today"></div>
    </section>

    <section class="hjem-zone hjem-section-3">
      <h3 class="hjem-zone-title">Månedens Økonomi</h3>
      <div class="hjem-card" id="hjem-finance"></div>
    </section>

    <section class="hjem-zone hjem-section-4">
      <h3 class="hjem-zone-title">Poeng &amp; Nivå</h3>
      <div id="celebrate-banner"></div>
      <div class="card level-card" id="level-card"></div>
      <div class="snapshot-row" id="weekly-snapshot"></div>
      <div class="card" id="plateau-card"></div>
    </section>

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
    <div id="missed-day-banner"></div>
    <div class="section-sub" style="margin-top:-8px;">Dra i ⠿-håndtaket på et kort for å bytte økt med en annen dag denne uken</div>
    <div class="week-row" id="plan-week"></div>
    <div class="plan-card" id="plan-today"></div>
    <div class="card" id="rest-timer-card"></div>
  </section>

  <section style="margin-top:28px;">
    <h2>🏆 Rekorder</h2>
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
    <div class="section-sub">Langsiktige mål, trender og historikk - i motsetning til dashbordet, som bare viser dagens status</div>
    <div class="section-sub" id="fremgang-meta" style="margin-top:-8px;"></div>
    <div class="goal-row" id="goal-chips"></div>

    <div class="fremgang-section card">
      <h3>⚖️ Kropp &amp; mål</h3>
      <div class="section-sub">Vekt (glattet 7-dagers snitt) sammen med et kroppsmål, i samme tidslinje</div>
      <div class="weight-goal-row">Målvekt: <input type="number" step="0.5" id="weight-goal-input"> kg <button class="btn ghost small" id="weight-goal-save">Lagre</button></div>
      <div class="period-tabs" id="body-period-tabs">
        <button class="period-btn" data-period="1">1 mnd</button>
        <button class="period-btn" data-period="3">3 mnd</button>
        <button class="period-btn active" data-period="12">1 år</button>
      </div>
      <div class="period-tabs" id="body-measure-tabs">
        <button class="measure-select-btn active" data-measure="waist">Mage</button>
        <button class="measure-select-btn" data-measure="hips">Hofte</button>
        <button class="measure-select-btn" data-measure="arm">Arm</button>
        <button class="measure-select-btn" data-measure="thigh">Lår</button>
        <button class="measure-select-btn" data-measure="chest">Bryst</button>
      </div>
      <div class="legend" id="legend-body"></div>
      <div class="chart-wrap"><svg id="chart-body"></svg><div class="tooltip ml" id="tt-body"></div></div>
      <div class="context-note" id="body-context-note"></div>
      <div id="calorie-calibration-note"></div>

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
            <input type="number" step="0.5" id="measure-thigh" placeholder="Lår (cm)">
            <input type="number" step="0.5" id="measure-chest" placeholder="Bryst (cm)">
            <button class="btn" id="measure-add">Lagre</button>
          </div>
          <ul class="log-list" id="measure-list"></ul>
        </div>
      </div>
    </div>

    <div class="fremgang-section card">
      <h3>🏃 Aktivitets-trender</h3>
      <div class="section-sub">Ukentlige snitt fra klokken, over tid</div>
      <div class="trend-grid">
        <div>
          <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Skritt &amp; aktive kalorier</div>
          <div class="legend" id="legend-activity"></div>
          <div class="chart-wrap"><svg id="chart-activity"></svg><div class="tooltip ml" id="tt-activity"></div></div>
        </div>
        <div>
          <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Stressnivå &amp; søvnkvalitet</div>
          <div class="legend" id="legend-stress-sleep"></div>
          <div class="chart-wrap"><svg id="chart-stress-sleep"></svg><div class="tooltip ml" id="tt-stress-sleep"></div></div>
        </div>
      </div>
      <div class="context-note" id="activity-context-note"></div>
    </div>

    <div class="fremgang-section card">
      <h3>💰 Faste vs. variable utgifter</h3>
      <div class="section-sub">Per økonomimåned (16.–15.), siste 12 måneder</div>
      <div class="legend" id="legend-expenses"></div>
      <div class="chart-wrap"><svg id="chart-expenses"></svg><div class="tooltip ml" id="tt-expenses"></div></div>
      <div id="fixed-expense-totals"></div>
    </div>

    <div class="fremgang-section card">
      <h3>🐶 Sparemål</h3>
      <div class="section-sub">De tre faste sparekategoriene fra budsjettet</div>
      <div class="savings-goal-grid" id="savings-goals"></div>
    </div>

    <div class="fremgang-section card">
      <h3>📈 Fond-utvikling</h3>
      <div class="section-sub">Innskutt kapital vs. faktisk verdi, slik at du ser avkastningen</div>
      <div class="log-form">
        <input type="date" id="fund-log-date">
        <input type="number" step="100" id="fund-log-contributed" placeholder="Innskutt totalt (kr)">
        <input type="number" step="100" id="fund-log-value" placeholder="Fondsverdi i dag (kr)">
        <button class="btn" id="fund-log-add">Lagre</button>
      </div>
      <div class="legend" id="legend-fund"></div>
      <div class="chart-wrap"><svg id="chart-fund"></svg><div class="tooltip ml" id="tt-fund"></div></div>
      <div class="fund-summary-row" id="fund-summary"></div>
    </div>

    <div class="fremgang-section card" id="fremgang-weekly-report"></div>
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
        <button class="btn ghost small" id="em-prev">‹</button>
        <div class="month-label" id="em-label"></div>
        <button class="btn ghost small" id="em-next">›</button>
      </div>
      <h3 style="margin:10px 0 2px;font-size:15px;">Logg utgift</h3>
      <div class="log-form">
        <input type="date" id="tx-date">
        <input type="number" step="1" id="tx-amount" placeholder="Beløp (kr)">
        <select id="tx-category"></select>
        <input type="text" id="tx-name" placeholder="Hva var det?">
        <button class="btn btn-big" id="tx-add">Legg til</button>
      </div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 class="budget-section-title">🏠 Faste utgifter</h3>
      <div class="budget-cat-list" id="fixed-cat-list"></div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 class="budget-section-title">🛍️ Variable utgifter</h3>
      <div class="budget-cat-list" id="variable-cat-list"></div>
    </div>

    <div class="budget-summary-grid" id="budget-summary"></div>

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

    <div class="card" style="margin-top:14px;">
      <h3 style="margin:0 0 4px;font-size:15px;">📜 Historikk</h3>
      <div class="section-sub" style="margin-bottom:0;">Transaksjoner denne økonomimåneden</div>
      <ul class="log-list" id="tx-list"></ul>
    </div>
  </section>
  </div>

  <div class="tab-panel" data-tab="statistikk">
  <section>
    <h2>Denne uken vs. nylige uker</h2>
    <div class="section-sub">Økter, tid og distanse per idrett, siste 10 uker</div>
    <div class="card">
      <div class="legend" id="sport-legend"></div>
      <div class="chart-wrap"><svg id="chart-weekly-sport"></svg><div class="tooltip" id="tt-weekly"></div></div>
    </div>
  </section>

  <section>
    <h2>Trender</h2>
    <div class="section-sub">Ukentlig snitt, siste 6 måneder</div>
    <div class="trend-grid">
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Treningsbelastning</div>
        <div class="chart-wrap"><svg id="chart-load"></svg><div class="tooltip" id="tt-load"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Hvilepuls</div>
        <div class="chart-wrap"><svg id="chart-rhr"></svg><div class="tooltip" id="tt-rhr"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">HRV (nattlig snitt)</div>
        <div class="chart-wrap"><svg id="chart-hrv"></svg><div class="tooltip" id="tt-hrv"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Søvn (timer/natt, snitt)</div>
        <div class="chart-wrap"><svg id="chart-sleep"></svg><div class="tooltip" id="tt-sleep"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Treningsvolum (vekt × reps per uke)</div>
        <div class="chart-wrap"><svg id="chart-volume"></svg><div class="tooltip" id="tt-volume"></div></div>
      </div>
    </div>
  </section>

  <section>
    <h2>Toppnoteringer</h2>
    <div class="section-sub">Dine største dager og økter</div>
    <div class="records-grid" id="records-grid"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="innstillinger">
  <section>
    <h2>Innstillinger</h2>

    <div class="card settings-card" id="settings-card">
      <h3 style="margin:0 0 4px;font-size:15px;">Generelt</h3>
      <label class="settings-toggle-row">
        <input type="checkbox" id="settings-personality-toggle">
        <span>Personlighet (konfetti og påminnelser)</span>
      </label>
      <label class="settings-toggle-row">
        <input type="checkbox" id="settings-vacation-toggle">
        <span>Ferie/pause-modus - ingen påminnelser, streaken fryses</span>
      </label>
    </div>

    <div class="card sync-card" id="sync-card">
      <h3 style="margin:0 0 4px;font-size:15px;">Skylagring</h3>
      <div class="section-sub" style="margin-bottom:10px;">Data synkroniseres automatisk med kontoen din i bakgrunnen. Bruk knappen under om noe virker bakpå, f.eks. rett etter du har gjort endringer på en annen enhet.</div>
      <div class="backup-actions">
        <button class="btn secondary small" id="sync-now-btn">Synk nå</button>
        <button class="btn ghost small" id="sync-logout-btn">Logg ut</button>
      </div>
      <div id="sync-status" class="section-sub" style="margin:8px 0 0;"></div>
    </div>

    <div class="card backup-card" id="backup-card">
      <h3 style="margin:0 0 4px;font-size:15px;">Sikkerhetskopi (fil)</h3>
      <div class="section-sub" style="margin-bottom:10px;">Et ekstra trygghetsnett i tillegg til skylagringen over - last ned en kopi innimellom, eller bruk den til å gjenopprette data manuelt.</div>
      <div class="backup-actions">
        <button class="btn secondary small" id="backup-export">Last ned kopi</button>
        <button class="btn ghost small" id="backup-import-btn">Gjenopprett fra fil</button>
        <input type="file" id="backup-import-file" accept="application/json" style="display:none;">
      </div>
      <div id="backup-status" class="section-sub" style="margin:8px 0 0;"></div>
    </div>
  </section>
  </div>

  <footer id="footer"></footer>
</div>

<div class="quicklog-drawer" id="quicklog-drawer">
  <div class="quicklog-drawer-head">
    <span id="quicklog-drawer-title"></span>
    <button id="quicklog-drawer-close">✕</button>
  </div>
  <div id="quicklog-drawer-body"></div>
</div>
<nav class="quicklog-bar" id="quicklog-bar">
  <button data-ql="hjem"><span class="ql-icon">🏠</span><span class="ql-label">Hjem</span></button>
</nav>

<script>
const DATA = __DASHBOARD_DATA__;

// ---------------------------------------------------------------- settings
const SETTINGS_KEY = "garminDashboardSettings_v1";
function loadSettings() {
  return Object.assign({
    dailyKcal: DATA.nutritionPlan.dailyKcal,
    proteinMin: DATA.nutritionPlan.proteinMin,
    savingsTarget: DATA.dogFund.target,
    weightGoal: null,
    personalityEnabled: true,
  }, loadLS(SETTINGS_KEY, {}));
}
function saveSettings(s) { saveLS(SETTINGS_KEY, s); }
(function applySettings() {
  const s = loadSettings();
  DATA.nutritionPlan.dailyKcal = s.dailyKcal;
  DATA.nutritionPlan.proteinMin = s.proteinMin;
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

// ---------------------------------------------------------------- access gate / cloud auth
// The actual Firebase auth + Firestore sync logic lives in the <script type="module"> at the
// bottom of the page (modules need their own scope for the Firebase imports) and talks to this
// classic script through window.__cloudAuth (calls into the module) and the two callbacks below
// (calls from the module back into here). window.__cloudAuth may not exist yet if this code runs
// before that module has finished loading, so every call into it is guarded.
const overlay = document.getElementById("gate-overlay");

function setSyncStatus(msg) {
  const el = document.getElementById("sync-status");
  if (el) el.textContent = msg;
}
window.__cloudSyncStatus = setSyncStatus;

window.__onAuthStateChanged = function (user) {
  if (user) {
    overlay.style.display = "none";
    window.__cloudAuth.pullNow();
    if (location.hash === "#debug") renderDebugPage();
  } else {
    overlay.style.display = "flex";
  }
};

async function tryLogin() {
  const email = document.getElementById("gate-email").value.trim();
  const password = document.getElementById("gate-input").value;
  const errEl = document.getElementById("gate-error");
  if (!email || !password) return;
  if (!window.__cloudAuth) { errEl.textContent = "Laster innloggingen ennå - prøv igjen om et par sekunder."; return; }
  try {
    await window.__cloudAuth.signIn(email, password);
    errEl.textContent = "";
  } catch (e) {
    const code = e && e.code || "";
    const messages = {
      "auth/user-not-found": "Finner ingen bruker med den e-posten - sjekk at den er skrevet nøyaktig som i Firebase-konsollen (Authentication → Users).",
      "auth/wrong-password": "Feil passord for denne e-posten.",
      "auth/invalid-credential": "Feil e-post eller passord.",
      "auth/invalid-email": "Det ser ikke ut som en gyldig e-postadresse.",
      "auth/too-many-requests": "For mange forsøk - vent litt og prøv igjen.",
      "auth/network-request-failed": "Ingen nettverksforbindelse - sjekk internett og prøv igjen.",
    };
    errEl.textContent = (messages[code] || "Innlogging feilet") + (code ? ` (${code})` : "");
    overlay.classList.remove("shake");
    void overlay.offsetWidth;
    overlay.classList.add("shake");
  }
}
document.getElementById("gate-submit").addEventListener("click", tryLogin);
["gate-email", "gate-input"].forEach(id => {
  document.getElementById(id).addEventListener("keydown", e => {
    if (e.key === "Enter") tryLogin();
  });
});

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
const NO_WEEKDAYS_FULL = ["Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag"];
const NO_MONTHS_FULL = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "desember"];
function nowDateTimeLabel() {
  const now = new Date();
  const weekday = NO_WEEKDAYS_FULL[now.getDay()];
  const day = now.getDate();
  const month = NO_MONTHS_FULL[now.getMonth()];
  const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  return { full: `${weekday} ${day}. ${month}`, time };
}
function renderHeroGreeting() {
  const h = new Date().getHours();
  const greet = h < 10 ? "God morgen" : h < 17 ? "God dag" : "God kveld";
  const el = document.getElementById("hero-greeting");
  if (el) el.textContent = `${greet}, Katrine`;
  const dt = nowDateTimeLabel();
  const sub = document.getElementById("hero-datetime");
  if (sub) sub.textContent = `${dt.full} · ${dt.time}`;
}
renderHeroGreeting();
setInterval(renderHeroGreeting, 30000);

function heroSparkline(values) {
  const vals = (values || []).filter(v => v !== null && v !== undefined);
  if (vals.length < 2) return "";
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = (max - min) || 1;
  const w = 50, h = 14;
  const step = w / (values.length - 1);
  const pts = [];
  values.forEach((v, i) => {
    if (v === null || v === undefined) return;
    pts.push([i * step, h - ((v - min) / range) * (h - 3) - 1.5]);
  });
  const path = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  return `<svg class="hss-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${path}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
function renderHeroStatusStrip() {
  const el = document.getElementById("hero-status-strip");
  if (!el) return;
  const ts = DATA.topStats || {};
  const items = [
    ts.sleep ? { icon: "😴", text: `${ts.sleep.hours.toLocaleString("no-NO")}t`, trend: ts.sleep.trend } : null,
    ts.hrv ? { icon: "❤️", text: `${ts.hrv.value} ms`, trend: ts.hrv.trend } : null,
    ts.calories ? { icon: "🔥", text: `${ts.calories.value.toLocaleString("no-NO")} kcal`, trend: ts.calories.trend } : null,
    ts.steps ? { icon: "👣", text: `${ts.steps.value.toLocaleString("no-NO")}`, trend: ts.steps.trend } : null,
  ].filter(Boolean);
  el.innerHTML = items.map(i => `
    <div class="hss-chip">
      <span class="hss-main">${i.icon} ${i.text}</span>
      ${heroSparkline(i.trend)}
    </div>
  `).join("");
}
renderHeroStatusStrip();

// activity-count + weekly goal chips used to live in the header - moved to Fremgang,
// since they're long-term trend info, not something needed on every screen.
function renderFremgangMeta() {
  const metaEl = document.getElementById("fremgang-meta");
  if (metaEl) {
    metaEl.textContent = `${DATA.meta.totalActivities} aktiviteter registrert, ${fmtDate(DATA.meta.dateRange[0])} – ${fmtDate(DATA.meta.dateRange[1])}`;
  }
  const goalChips = document.getElementById("goal-chips");
  if (!goalChips) return;
  const g = DATA.goal;
  function deltaSpan(pct) {
    if (pct === null || pct === undefined) return "";
    const cls = pct >= 0 ? "delta-up" : "delta-down";
    const sign = pct >= 0 ? "+" : "";
    return ` <span class="${cls}">${sign}${pct}%</span>`;
  }
  let html = "";
  if (g.recentActiveCaloriesPerWeek) {
    html += `<div class="goal-chip">Aktive kalorier/uke<b>${g.recentActiveCaloriesPerWeek.toLocaleString()}${deltaSpan(g.caloriesPctChange)}</b></div>`;
  }
  if (g.recentSessionsPerWeek) {
    html += `<div class="goal-chip">Økter/uke<b>${g.recentSessionsPerWeek}</b></div>`;
  }
  if (g.recentStepsPerDay) {
    html += `<div class="goal-chip">Skritt/dag<b>${g.recentStepsPerDay.toLocaleString()}${deltaSpan(g.stepsPctChange)}</b></div>`;
  }
  goalChips.innerHTML = html;
}
renderFremgangMeta();

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
const rememberedTab = localStorage.getItem(ACTIVE_TAB_KEY);
const validTabs = Array.from(document.querySelectorAll(".tab-panel")).map(p => p.dataset.tab);
showTab(validTabs.includes(rememberedTab) ? rememberedTab : "hjem");

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
function normalizeSwapKey(key) { return SWAP_OPTIONS.includes(key) ? key : "rest"; }
function isDefaultKeyForDay(day, key) {
  return key === day.defaultKey || (key === "rest" && (day.defaultKey === "rest" || day.defaultKey === "restW"));
}
// swaps which session is planned on two days of the current week (drag-and-drop), for
// this week only - each day's override is set to the other's resolved session, or cleared
// if that happens to already be that day's own default.
function swapPlanDays(dateA, dateB) {
  const p = DATA.program;
  const dayA = p.week.find(d => d.date === dateA);
  const dayB = p.week.find(d => d.date === dateB);
  if (!dayA || !dayB || dateA === dateB) return;
  const overrides = loadPlanOverrides();
  const keyA = normalizeSwapKey(resolvePlanDay(dayA, overrides).key);
  const keyB = normalizeSwapKey(resolvePlanDay(dayB, overrides).key);
  if (isDefaultKeyForDay(dayA, keyB)) delete overrides[dateA]; else overrides[dateA] = keyB;
  if (isDefaultKeyForDay(dayB, keyA)) delete overrides[dateB]; else overrides[dateB] = keyA;
  savePlanOverrides(overrides);
  renderPlan();
  renderMissedDayPrompt();
}
// touch/mouse-friendly drag via Pointer Events (native HTML5 drag-and-drop doesn't work on
// iOS touch) - dragging is only initiated from the small ⠿ handle, not the whole card, so
// the week row's own horizontal swipe-scroll still works everywhere else on the card.
function setupWeekDrag() {
  const todayStr = DATA.program.today.date;
  const isDroppable = dateStr => !!dateStr && dateStr >= todayStr;
  document.querySelectorAll(".week-day-handle").forEach(handle => {
    handle.addEventListener("pointerdown", startEvt => {
      const card = handle.closest(".week-day");
      const fromDate = card.dataset.date;
      const startX = startEvt.clientX, startY = startEvt.clientY;
      let dragging = false;

      function clearTargets() {
        document.querySelectorAll(".week-day.drop-target").forEach(c => c.classList.remove("drop-target"));
      }
      function onMove(ev) {
        if (!dragging) {
          if (Math.abs(ev.clientX - startX) < 8 && Math.abs(ev.clientY - startY) < 8) return;
          dragging = true;
          card.classList.add("dragging");
          handle.setPointerCapture(startEvt.pointerId);
        }
        ev.preventDefault();
        clearTargets();
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        const target = el && el.closest(".week-day");
        if (target && target !== card && isDroppable(target.dataset.date)) target.classList.add("drop-target");
      }
      function onUp(ev) {
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onUp);
        handle.removeEventListener("pointercancel", onUp);
        card.classList.remove("dragging");
        clearTargets();
        if (!dragging) return;
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        const target = el && el.closest(".week-day");
        if (target && target.dataset.date && target.dataset.date !== fromDate && isDroppable(target.dataset.date)) {
          swapPlanDays(fromDate, target.dataset.date);
        }
      }
      handle.addEventListener("pointermove", onMove, { passive: false });
      handle.addEventListener("pointerup", onUp);
      handle.addEventListener("pointercancel", onUp);
    });
  });
}

// ---- "du hoppet over en dag" - offer to move it to tomorrow, or drop it for this week ----
const MISSED_DAY_ACK_KEY = "garminDashboardMissedDayAck_v1";
function loadMissedDayAck() { return loadLS(MISSED_DAY_ACK_KEY, []); }
function ackMissedDay(dateStr) {
  const a = loadMissedDayAck();
  if (!a.includes(dateStr)) { a.push(dateStr); saveLS(MISSED_DAY_ACK_KEY, a); }
}
function renderMissedDayPrompt() {
  const el = document.getElementById("missed-day-banner");
  const p = DATA.program;
  if (!el || !p) return;
  const overrides = loadPlanOverrides();
  const ack = loadMissedDayAck();
  const missedDay = p.week.slice().reverse().find(d => {
    if (d.date >= p.today.date || ack.includes(d.date)) return false;
    const r = resolvePlanDay(d, overrides);
    return r.type !== "rest" && r.done !== true;
  });
  if (!missedDay) { el.innerHTML = ""; return; }
  const r = resolvePlanDay(missedDay, overrides);
  el.innerHTML = `<div class="missed-day-box">
    Du hoppet over <b>${r.label}</b> (${fmtShort(missedDay.date)}) - vil du flytte den til i morgen, eller droppe den denne uken?
    <div class="missed-day-actions">
      <button class="btn small" id="missed-day-move">Flytt til i morgen</button>
      <button class="btn ghost small" id="missed-day-skip">Dropp denne uken</button>
    </div>
  </div>`;
  document.getElementById("missed-day-move").addEventListener("click", () => {
    const tomorrow = isoAddDays(todayISO(), 1);
    const current = loadPlanOverrides();
    current[tomorrow] = normalizeSwapKey(r.key);
    savePlanOverrides(current);
    ackMissedDay(missedDay.date);
    renderPlan();
    renderMissedDayPrompt();
  });
  document.getElementById("missed-day-skip").addEventListener("click", () => {
    ackMissedDay(missedDay.date);
    renderMissedDayPrompt();
  });
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
let restTimerEndsAt = 0; // absolute timestamp (ms) the timer finishes at - not a tick counter,
                          // since mobile browsers throttle/pause setInterval while backgrounded
let restTimerPausedRemaining = null; // seconds left, frozen while paused; null while running

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
function restTimerSecondsLeft() {
  if (restTimerPausedRemaining != null) return restTimerPausedRemaining;
  return Math.max(0, Math.ceil((restTimerEndsAt - Date.now()) / 1000));
}
function updateRestBubbleDisplay() {
  document.getElementById("rt-bubble-display").textContent = restTimerSecondsLeft();
}
function stopRestTimer() {
  if (restTimerInterval) clearInterval(restTimerInterval);
  restTimerInterval = null;
  restTimerPausedRemaining = null;
  document.getElementById("rest-bubble").classList.remove("active");
}
function tickRestTimer() {
  if (restTimerPausedRemaining != null) return;
  const left = restTimerSecondsLeft();
  updateRestBubbleDisplay();
  if (left <= 0) {
    if (window.navigator.vibrate) window.navigator.vibrate([200, 100, 200]);
    playRestBeep();
    stopRestTimer();
  }
}
function startRestTimer(seconds, label) {
  stopRestTimer();
  restTimerEndsAt = Date.now() + seconds * 1000;
  restTimerPausedRemaining = null;
  document.getElementById("rt-bubble-label").textContent = label || "Hvile";
  document.getElementById("rt-bubble-pause").textContent = "Pause";
  updateRestBubbleDisplay();
  document.getElementById("rest-bubble").classList.add("active");
  restTimerInterval = setInterval(tickRestTimer, 1000);
}
document.getElementById("rt-bubble-pause").addEventListener("click", () => {
  if (restTimerPausedRemaining != null) {
    restTimerEndsAt = Date.now() + restTimerPausedRemaining * 1000;
    restTimerPausedRemaining = null;
    document.getElementById("rt-bubble-pause").textContent = "Pause";
  } else {
    restTimerPausedRemaining = restTimerSecondsLeft();
    document.getElementById("rt-bubble-pause").textContent = "Fortsett";
  }
});
document.getElementById("rt-bubble-skip").addEventListener("click", stopRestTimer);
// background tabs/apps throttle or fully pause setInterval (especially on iOS), so the display
// can go stale while you're away - catch up the instant you come back instead of waiting for
// the next (possibly delayed) tick, so a finished rest shows "ferdig" right away, not a frozen number.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && restTimerInterval) tickRestTimer();
});

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
      const hasRepeatable = resolved.exercises.some((e, idx) => {
        const exKey = resolved.key + "::" + idx;
        return lastSetFor(exKey, todayDay.date) && setsFor(exKey, todayDay.date).length === 0;
      });
      if (hasRepeatable) {
        body += `<button class="btn ghost small repeat-session-btn" style="margin-bottom:10px;">🔁 Gjenta forrige økt</button>`;
      }
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

  const repeatBtn = card.querySelector(".repeat-session-btn");
  if (repeatBtn) {
    repeatBtn.addEventListener("click", () => {
      let anyPR = false;
      resolved.exercises.forEach((e, idx) => {
        const exKey = resolved.key + "::" + idx;
        if (setsFor(exKey, todayDay.date).length > 0) return;
        const last = lastSetFor(exKey, todayDay.date);
        if (!last) return;
        const prevBest = bestSetFor(exKey);
        addSet(exKey, e, todayDay.date, last.weight, last.reps);
        if (isBetterSet({ weight: last.weight, reps: last.reps }, prevBest)) anyPR = true;
      });
      if (anyPR && loadSettings().personalityEnabled) triggerConfetti();
      renderPlan();
      renderPrBoard();
      renderHjemSession();
    });
  }

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
      renderHjemSession();
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
    return `<div class="week-day${d.isToday ? " today" : ""}" data-date="${d.date}">
      <div class="wd"><span>${d.weekday}</span>${d.date >= p.today.date ? `<span class="week-day-handle" title="Dra for å bytte dag">⠿</span>` : ""}</div>
      <div class="sess">${r.label}</div>
      <div class="mark${missed ? " missed" : ""}" ${missed ? `title="Ikke logget - helt greit, fortsett i dag."` : ""}>${mark}</div>
      ${swapSelectHtml(d.date, r.key)}
    </div>`;
  }).join("");

  document.querySelectorAll("select.swap").forEach(sel => {
    sel.addEventListener("change", () => {
      const current = loadPlanOverrides();
      const day = p.week.find(x => x.date === sel.dataset.date);
      if (isDefaultKeyForDay(day, sel.value)) {
        delete current[sel.dataset.date];
      } else {
        current[sel.dataset.date] = sel.value;
      }
      savePlanOverrides(current);
      renderPlan();
    });
  });

  setupWeekDrag();
}
renderPlan();
renderMissedDayPrompt();
renderPrBoard();
renderRestTimer();

// ---------------------------------------------------------------- nutrition
const EXTRAS_KEY = "garminDashboardExtras_v1";
const CUSTOM_MEALS_KEY = "garminDashboardCustomMeals_v1";
const MEAL_LOG_KEY = "garminDashboardMealLog_v1";
const CUSTOM_INGREDIENTS_KEY = "garminDashboardCustomIngredients_v1";
const MEAL_ING_OVERRIDES_KEY = "garminDashboardMealIngOverrides_v1";
function loadCustomMeals() { return Object.assign({ breakfast: [], lunch: [], snack: [], dinner: [] }, loadLS(CUSTOM_MEALS_KEY, {})); }
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

// ---- ingredient catalog (built-in + her own additions) and per-day swap overrides ----
function loadCustomIngredients() { return loadLS(CUSTOM_INGREDIENTS_KEY, {}); }
function saveCustomIngredients(c) { saveLS(CUSTOM_INGREDIENTS_KEY, c); }
function getIngredient(key) {
  const custom = loadCustomIngredients();
  return custom[key] || DATA.ingredientCatalog[key] || null;
}
function ingredientOptionsForSelect(selectedKey) {
  const all = Object.assign({}, DATA.ingredientCatalog, loadCustomIngredients());
  const keys = Object.keys(all).sort((a, b) => all[a].label.localeCompare(all[b].label, "no"));
  return keys.map(k => `<option value="${k}" ${k === selectedKey ? "selected" : ""}>${all[k].label}</option>`).join("");
}
function ingOverrideKey(date, type, optIdx, itemIdx) { return `${date}|${type}|${optIdx}|${itemIdx}`; }
function loadMealIngOverrides() { return loadLS(MEAL_ING_OVERRIDES_KEY, {}); }
function saveMealIngOverrides(o) { saveLS(MEAL_ING_OVERRIDES_KEY, o); }
function getIngOverride(date, type, optIdx, itemIdx) {
  return loadMealIngOverrides()[ingOverrideKey(date, type, optIdx, itemIdx)] || null;
}
function setIngOverride(date, type, optIdx, itemIdx, ing, amount) {
  const o = loadMealIngOverrides();
  o[ingOverrideKey(date, type, optIdx, itemIdx)] = { ing, amount };
  saveMealIngOverrides(o);
}
function clearIngOverride(date, type, optIdx, itemIdx) {
  const o = loadMealIngOverrides();
  delete o[ingOverrideKey(date, type, optIdx, itemIdx)];
  saveMealIngOverrides(o);
}
// recomputes a built-in option's macros for the given date, applying any ingredient
// swaps logged for that day - custom (no-ingredient) meals pass through unchanged.
function effectiveMealOption(type, optIdx, opt, date) {
  if (!opt.items || !opt.items.some(i => i.ing)) {
    return Object.assign({}, opt, { effectiveItems: (opt.items || []).map(i => ({ text: i.text })) });
  }
  let kcal = opt.extraKcal || 0;
  let protein = opt.extraProtein || 0;
  const effectiveItems = opt.items.map((item, itemIdx) => {
    if (!item.ing) return { text: item.text };
    const override = getIngOverride(date, type, optIdx, itemIdx);
    const ing = override ? override.ing : item.ing;
    const amount = override ? override.amount : item.amount;
    const data = getIngredient(ing);
    if (data) {
      kcal += data.kcal100 * amount / 100;
      protein += data.protein100 * amount / 100;
    }
    return {
      ing, amount, itemIdx,
      label: data ? data.label : ing,
      display: override ? `${amount} g` : (item.display || `${amount} g`),
      overridden: !!override,
    };
  });
  return { name: opt.name, kcal: Math.round(kcal), protein: Math.round(protein), effectiveItems };
}

// totals actually eaten on a given date: breakfast (the standard one, unless a different
// breakfast option was marked eaten that day, or its ingredients were swapped for the day)
// + whichever lunch/snack/dinner options were marked eaten that day + anything logged as an "extra"
function dayNutritionTotals(date) {
  const n = DATA.nutritionPlan;
  const meals = loadMealLog().filter(m => m.date === date);
  const extrasForDay = loadExtras().filter(e => e.date === date);
  const extrasTotal = extrasForDay.reduce((s, e) => s + (e.kcal || 0), 0);
  const loggedBreakfast = meals.find(m => m.type === "breakfast");
  const breakfast = loggedBreakfast || effectiveMealOption("breakfast", 0, n.breakfast.options[0], date);
  const otherMeals = meals.filter(m => m.type !== "breakfast");
  return {
    kcal: breakfast.kcal + otherMeals.reduce((s, m) => s + (m.kcal || 0), 0) + extrasTotal,
    protein: breakfast.protein + otherMeals.reduce((s, m) => s + (m.protein || 0), 0),
    mealsLogged: meals,
    extras: extrasForDay,
  };
}

// transient UI state (not persisted) for which ingredient's swap-form is open
let openIngSwapKey = null;
let openIngSwapShowCustomForm = false;

function mealOptionHtml(opt, removeId, toggle, swapCtx) {
  const eaten = !!(toggle && toggle.eaten);
  const itemsHtml = (opt.effectiveItems || []).map(item => {
    if (item.text) return `<span class="meal-item-text">${item.text}</span>`;
    if (!swapCtx) return `<span class="meal-item-ing">${item.display} ${item.label}</span>`;
    const key = ingOverrideKey(todayISO(), swapCtx.type, swapCtx.optIdx, item.itemIdx);
    return `<span class="meal-item-ing${item.overridden ? " meal-item-overridden" : ""}">
      ${item.display} ${item.label}
      <button class="meal-ing-swap-btn" data-swap-key="${key}">Bytt</button>
      ${item.overridden ? `<button class="meal-ing-reset-btn" data-type="${swapCtx.type}" data-opt-idx="${swapCtx.optIdx}" data-item-idx="${item.itemIdx}">↺</button>` : ""}
    </span>`;
  }).join("");

  let swapFormHtml = "";
  if (swapCtx) {
    (opt.effectiveItems || []).forEach(item => {
      if (item.text) return;
      const key = ingOverrideKey(todayISO(), swapCtx.type, swapCtx.optIdx, item.itemIdx);
      if (openIngSwapKey !== key) return;
      swapFormHtml = `<div class="ing-swap-form">
        <div class="ing-swap-row">
          <select class="ing-swap-select">${ingredientOptionsForSelect(item.ing)}</select>
          <input type="number" class="ing-swap-amount" value="${item.amount}"> g
          <button class="btn small ing-swap-save" data-type="${swapCtx.type}" data-opt-idx="${swapCtx.optIdx}" data-item-idx="${item.itemIdx}">Lagre</button>
          <button class="btn ghost small ing-swap-cancel">Avbryt</button>
        </div>
        ${openIngSwapShowCustomForm
          ? `<div class="ing-new-form">
              <input type="text" class="ing-new-name" placeholder="Navn på ny ingrediens">
              <input type="number" class="ing-new-kcal" placeholder="kcal/100g">
              <input type="number" class="ing-new-protein" placeholder="protein/100g">
              <button class="btn ghost small ing-new-save" data-type="${swapCtx.type}" data-opt-idx="${swapCtx.optIdx}" data-item-idx="${item.itemIdx}">Legg til og bruk</button>
            </div>`
          : `<button class="btn ghost small ing-swap-new-toggle">+ Legg til ny ingrediens</button>`}
      </div>`;
    });
  }

  return `<div class="meal-option${eaten ? " meal-option-eaten" : ""}">
    <div class="meal-head"><b>${opt.name}</b><span class="meal-macro">${opt.kcal} kcal · ${opt.protein} g protein${removeId ? `<button class="meal-option-remove" data-meal-remove="${removeId}">✕</button>` : ""}</span></div>
    ${itemsHtml ? `<div class="meal-items">${itemsHtml}</div>` : ""}
    ${swapFormHtml}
    ${toggle ? `<button class="btn ghost small meal-eaten-btn" data-meal-type="${toggle.type}" data-meal-idx="${toggle.idx}">${eaten ? "✓ Spist i dag" : "Merk som spist i dag"}</button>` : ""}
  </div>`;
}

function renderNutrition() {
  const n = DATA.nutritionPlan;
  if (!n) return;
  const today = todayISO();

  document.getElementById("kcal-row").innerHTML = `
    <div class="kcal-chip">Mål<b>${n.dailyKcal} kcal</b></div>
    <div class="kcal-chip">Protein<b>${n.proteinMin} g+</b></div>
    <div class="kcal-chip kcal-goal-edit">
      <input type="number" step="50" id="kcal-goal-input" value="${n.dailyKcal}" style="width:70px;">
      <button class="btn ghost small" id="kcal-goal-save">Lagre kcal-mål</button>
    </div>
    <div class="kcal-chip kcal-goal-edit">
      <input type="number" step="5" id="protein-goal-input" value="${n.proteinMin}" style="width:70px;">
      <button class="btn ghost small" id="protein-goal-save">Lagre proteinmål</button>
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
  document.getElementById("protein-goal-save").addEventListener("click", () => {
    const val = parseInt(document.getElementById("protein-goal-input").value, 10);
    if (!val) return;
    const s = loadSettings();
    s.proteinMin = val;
    saveSettings(s);
    DATA.nutritionPlan.proteinMin = val;
    renderNutrition();
  });

  let html = "";
  const custom = loadCustomMeals();
  const yesterday = isoAddDays(today, -1);
  ["breakfast", "lunch", "snack", "dinner"].forEach(key => {
    const group = n[key];
    const customOpts = custom[key] || [];
    const yesterdayMeal = mealLoggedFor(yesterday, key);
    const repeatHtml = (yesterdayMeal && !mealLoggedFor(today, key))
      ? `<button class="btn ghost small meal-repeat-btn" data-repeat-type="${key}" style="margin-bottom:8px;">🔁 Gjenta ${yesterdayMeal.name} fra i går</button>`
      : "";
    html += `<div class="meal-group"><h4>${group.label}</h4>
      ${repeatHtml}
      ${group.options.map((o, idx) => mealOptionHtml(effectiveMealOption(key, idx, o, today), null, { type: key, idx, eaten: isMealEatenToday(key, o.name) }, { type: key, optIdx: idx })).join("")}
      ${customOpts.map((o, i) => mealOptionHtml(effectiveMealOption(key, group.options.length + i, o, today), o.id, { type: key, idx: group.options.length + i, eaten: isMealEatenToday(key, o.name) }, null)).join("")}
      ${key === "breakfast" ? `<div class="section-sub" style="margin:4px 0 10px;">Standardfrokosten over telles automatisk hver dag, med mindre du merker en annen frokost som spist i dag.</div>` : ""}
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
      const combinedRaw = n[type].options.concat((loadCustomMeals()[type] || []));
      const raw = combinedRaw[idx];
      if (!raw) return;
      const opt = idx < n[type].options.length ? effectiveMealOption(type, idx, raw, today) : raw;
      if (isMealEatenToday(type, opt.name)) unlogMeal(type); else logMealEaten(type, opt);
      renderNutrition();
      renderNutritionCoach();
      renderHjemKcalRing();
    });
  });

  document.querySelectorAll(".meal-repeat-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const type = btn.dataset.repeatType;
      const y = mealLoggedFor(isoAddDays(today, -1), type);
      if (!y) return;
      logMealEaten(type, y);
      renderNutrition();
      renderNutritionCoach();
      renderHjemKcalRing();
    });
  });

  document.querySelectorAll(".meal-ing-swap-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      openIngSwapKey = openIngSwapKey === btn.dataset.swapKey ? null : btn.dataset.swapKey;
      openIngSwapShowCustomForm = false;
      renderNutrition();
    });
  });
  document.querySelectorAll(".meal-ing-reset-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      clearIngOverride(today, btn.dataset.type, parseInt(btn.dataset.optIdx, 10), parseInt(btn.dataset.itemIdx, 10));
      renderNutrition();
      renderNutritionCoach();
      renderHjemKcalRing();
    });
  });
  document.querySelectorAll(".ing-swap-cancel").forEach(btn => {
    btn.addEventListener("click", () => { openIngSwapKey = null; renderNutrition(); });
  });
  document.querySelectorAll(".ing-swap-new-toggle").forEach(btn => {
    btn.addEventListener("click", () => { openIngSwapShowCustomForm = true; renderNutrition(); });
  });
  document.querySelectorAll(".ing-swap-save").forEach(btn => {
    btn.addEventListener("click", () => {
      const form = btn.closest(".ing-swap-form");
      const ing = form.querySelector(".ing-swap-select").value;
      const amount = parseFloat(form.querySelector(".ing-swap-amount").value) || 0;
      setIngOverride(today, btn.dataset.type, parseInt(btn.dataset.optIdx, 10), parseInt(btn.dataset.itemIdx, 10), ing, amount);
      openIngSwapKey = null;
      openIngSwapShowCustomForm = false;
      renderNutrition();
      renderNutritionCoach();
      renderHjemKcalRing();
    });
  });
  document.querySelectorAll(".ing-new-save").forEach(btn => {
    btn.addEventListener("click", () => {
      const form = btn.closest(".ing-swap-form");
      const name = form.querySelector(".ing-new-name").value.trim();
      const kcal100 = parseFloat(form.querySelector(".ing-new-kcal").value);
      const protein100 = parseFloat(form.querySelector(".ing-new-protein").value) || 0;
      if (!name || !kcal100) return;
      const amount = parseFloat(form.querySelector(".ing-swap-amount").value) || 100;
      const key = "custom_" + Date.now();
      const customIng = loadCustomIngredients();
      customIng[key] = { label: name, kcal100, protein100 };
      saveCustomIngredients(customIng);
      setIngOverride(today, btn.dataset.type, parseInt(btn.dataset.optIdx, 10), parseInt(btn.dataset.itemIdx, 10), key, amount);
      openIngSwapKey = null;
      openIngSwapShowCustomForm = false;
      renderNutrition();
      renderNutritionCoach();
      renderHjemKcalRing();
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
      ["breakfast", "lunch", "snack", "dinner"].forEach(key => { m[key] = m[key].filter(o => o.id !== id); });
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
  renderHjemKcalRing();
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
      renderHjemKcalRing();
    });
  });
}

function renderNutritionCoach() {
  const card = document.getElementById("nutrition-coach-card");
  if (!card) return;
  const tips = [];

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
const INVEST_FUND_KEY = "garminDashboardInvestFund_v1";
const SAVINGS_GOALS_KEY = "garminDashboardSavingsGoals_v1";
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
function saveLS(key, val) {
  localStorage.setItem(key, JSON.stringify(val));
  if (window.__cloudAuth) window.__cloudAuth.schedulePush();
}
function todayISO() { return new Date().toISOString().slice(0, 10); }
function isoWeekOf(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  const day = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - day);
  return d.toISOString().slice(0, 10);
}
function monthOf(dateStr) { return dateStr.slice(0, 7); }

// ---- økonomimåned: 16. i hver måned til 15. i neste (lønn kommer den 16.) ----
const NO_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Des"];
function emKeyForDate(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  let y = d.getFullYear(), m = d.getMonth();
  if (d.getDate() <= 15) { m -= 1; if (m < 0) { m = 11; y -= 1; } }
  return `${y}-${String(m + 1).padStart(2, "0")}`;
}
function emAddMonths(emKey, delta) {
  let [y, m] = emKey.split("-").map(Number);
  m = m - 1 + delta;
  y += Math.floor(m / 12);
  m = ((m % 12) + 12) % 12;
  return `${y}-${String(m + 1).padStart(2, "0")}`;
}
function emStart(emKey) { return `${emKey}-16`; }
function emEnd(emKey) { return `${emAddMonths(emKey, 1)}-15`; }
function emLabel(emKey) {
  const [, m] = emKey.split("-").map(Number);
  const [, nm] = emAddMonths(emKey, 1).split("-").map(Number);
  return `Økonomimåned: 16. ${NO_MONTHS_SHORT[m - 1]} – 15. ${NO_MONTHS_SHORT[nm - 1]}`;
}
function emShortLabel(emKey) {
  const [y, m] = emKey.split("-").map(Number);
  return `${NO_MONTHS_SHORT[m - 1]} ${y}`;
}
function emKeysBack(n) {
  // the trailing n economic months up to and including the current one, oldest first
  const current = emKeyForDate(todayISO());
  const keys = [];
  for (let i = n - 1; i >= 0; i--) keys.push(emAddMonths(current, -i));
  return keys;
}

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
// one-time migration from the old flat-cap/calendar-month category set to the new
// fixed/variable/sparing categories + økonomimåned (16.-15.) model. Carries over
// cap customizations and re-tags existing transactions where a direct equivalent exists.
function migrateBudgetConfig(stored) {
  const fresh = JSON.parse(JSON.stringify(DATA.budgetDefaults));
  const OLD_KEY_MAP = {
    bolig: "husleie", mat: "mat", restaurant: "fritid_sosialt", transport: "transport",
    abonnement: "abonnementer", klaer: "klaer_velvare", trening: "treningssenter",
    hundefond: "hundefond", annet: "annet",
  };
  (stored.categories || []).forEach(oldCat => {
    const newKey = OLD_KEY_MAP[oldCat.key];
    const freshCat = newKey && fresh.categories.find(c => c.key === newKey);
    if (freshCat && oldCat.cap != null) freshCat.cap = oldCat.cap;
  });
  saveTransactions(loadTransactions().map(t => ({ ...t, category: OLD_KEY_MAP[t.category] || t.category })));
  fresh.income = stored.income != null ? stored.income : fresh.income;
  fresh.migratedV2 = true;
  return fresh;
}
function loadBudgetConfig() {
  let stored = loadLS(BUDGET_CONFIG_KEY, null);
  let changed = false;
  if (!stored || !stored.categories) {
    stored = JSON.parse(JSON.stringify(DATA.budgetDefaults));
    stored.migratedV2 = true;
    changed = true;
  } else if (!stored.migratedV2) {
    stored = migrateBudgetConfig(stored);
    changed = true;
  }
  stored.categories.forEach(c => {
    if (!c.capHistory) {
      c.capHistory = [{ from: "2000-01-01", amount: c.cap != null ? c.cap : 0 }];
      delete c.cap;
      changed = true;
    }
  });
  if (changed) saveBudgetConfig(stored);
  return stored;
}
function saveBudgetConfig(c) { saveLS(BUDGET_CONFIG_KEY, c); }
function getCategoryCap(cat, emKey) {
  const monthStart = emStart(emKey);
  let amount = 0;
  (cat.capHistory || []).forEach(h => { if (h.from <= monthStart) amount = h.amount; });
  return amount;
}
function setCategoryCap(catKey, emKey, amount) {
  const cfg = loadBudgetConfig();
  const cat = cfg.categories.find(c => c.key === catKey);
  if (!cat) return;
  const monthStart = emStart(emKey);
  cat.capHistory = cat.capHistory.filter(h => h.from !== monthStart);
  cat.capHistory.push({ from: monthStart, amount });
  cat.capHistory.sort((a, b) => a.from.localeCompare(b.from));
  saveBudgetConfig(cfg);
}
function categorySpent(key, emKey) {
  const start = emStart(emKey), end = emEnd(emKey);
  return loadTransactions().filter(t => t.category === key && t.date >= start && t.date <= end).reduce((s, t) => s + t.amount, 0);
}
function isSavingsCategory(key) {
  const cat = loadBudgetConfig().categories.find(c => c.key === key);
  return !!(cat && cat.savings);
}

// ---- savings goals (generalizes the hundefond target to all three savings categories) ----
function loadSavingsGoals() {
  const defaults = {};
  (loadBudgetConfig().categories || []).filter(c => c.savings).forEach(c => {
    defaults[c.key] = { target: 20000, startSaved: 0 };
  });
  return Object.assign(defaults, loadLS(SAVINGS_GOALS_KEY, {}));
}
function saveSavingsGoals(g) { saveLS(SAVINGS_GOALS_KEY, g); }
function savingsBalance(key) {
  if (key === DATA.dogFund.category) return fundBalance();
  const goals = loadSavingsGoals();
  const startSaved = (goals[key] && goals[key].startSaved) || 0;
  const sum = loadTransactions().filter(t => t.category === key).reduce((s, t) => s + t.amount, 0);
  return startSaved + sum;
}
function savingsTarget(key) {
  if (key === DATA.dogFund.category) return DATA.dogFund.target;
  const goals = loadSavingsGoals();
  return (goals[key] && goals[key].target) || 0;
}
function setSavingsTarget(key, target) {
  if (key === DATA.dogFund.category) {
    const s = loadSettings();
    s.savingsTarget = target;
    saveSettings(s);
    DATA.dogFund.target = target;
    return;
  }
  const goals = loadSavingsGoals();
  goals[key] = Object.assign({ startSaved: 0 }, goals[key], { target });
  saveSavingsGoals(goals);
}
function setSavingsCurrentBalance(key, currentBalance) {
  // lets you correct the balance to match what's actually on the account right now
  // (e.g. pension/høyrente accounts that existed before this app tracked them, or that
  // earn interest/returns beyond what's logged as transactions) - backs out the
  // startSaved offset needed so savingsBalance() reads exactly currentBalance today.
  const sum = loadTransactions().filter(t => t.category === key).reduce((s, t) => s + t.amount, 0);
  const goals = loadSavingsGoals();
  goals[key] = Object.assign({ target: savingsTarget(key) }, goals[key], { startSaved: currentBalance - sum });
  saveSavingsGoals(goals);
}
function savingsMonthlyRate(key, months) {
  months = months || 3;
  const tx = loadTransactions();
  const totals = emKeysBack(months).map(ek => {
    const start = emStart(ek), end = emEnd(ek);
    return tx.filter(t => t.category === key && t.date >= start && t.date <= end).reduce((s, t) => s + t.amount, 0);
  });
  return totals.reduce((s, t) => s + t, 0) / months;
}
function projectSavingsMilestone(key) {
  const target = savingsTarget(key);
  const balance = savingsBalance(key);
  if (!target || balance >= target) return null;
  const rate = savingsMonthlyRate(key);
  if (rate <= 0) return null;
  const monthsNeeded = Math.ceil((target - balance) / rate);
  return { monthsNeeded, emKey: emAddMonths(emKeyForDate(todayISO()), monthsNeeded), rate };
}
function categoryOptionsHtml(cfg) {
  const fixed = cfg.categories.filter(c => c.type === "fixed");
  const variable = cfg.categories.filter(c => c.type === "variable" && !c.savings);
  const savings = cfg.categories.filter(c => c.savings);
  const opt = c => `<option value="${c.key}">${c.icon ? c.icon + " " : ""}${c.label}</option>`;
  return `<optgroup label="Faste utgifter">${fixed.map(opt).join("")}</optgroup>` +
    `<optgroup label="Variable utgifter">${variable.map(opt).join("")}</optgroup>` +
    `<optgroup label="Sparing">${savings.map(opt).join("")}</optgroup>`;
}
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
  renderLevel();
  renderWeeklySnapshot();
  renderPlateau();
  renderBodyGoalChart();
  renderCalorieCalibration();
});

function renderMeasureLog() {
  const log = loadMeasureLog().sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("measure-list").innerHTML = log.slice(0, 6).map(e =>
    `<li><span>${fmtShort(e.date)}</span><b>${e.waist ?? "–"} / ${e.hips ?? "–"} / ${e.arm ?? "–"} / ${e.thigh ?? "–"} / ${e.chest ?? "–"} cm</b></li>`
  ).join("") || `<li style="border-top:none;color:var(--muted);">Ingen mål ennå</li>`;
}
document.getElementById("measure-add").addEventListener("click", () => {
  const date = document.getElementById("measure-date").value || todayISO();
  const waist = parseFloat(document.getElementById("measure-waist").value) || null;
  const hips = parseFloat(document.getElementById("measure-hips").value) || null;
  const arm = parseFloat(document.getElementById("measure-arm").value) || null;
  const thigh = parseFloat(document.getElementById("measure-thigh").value) || null;
  const chest = parseFloat(document.getElementById("measure-chest").value) || null;
  if (!waist && !hips && !arm && !thigh && !chest) return;
  const log = loadMeasureLog().filter(e => e.date !== date);
  log.push({ date, waist, hips, arm, thigh, chest });
  saveMeasureLog(log);
  document.getElementById("measure-waist").value = "";
  document.getElementById("measure-hips").value = "";
  document.getElementById("measure-arm").value = "";
  document.getElementById("measure-thigh").value = "";
  document.getElementById("measure-chest").value = "";
  renderMeasureLog();
  renderLevel();
  renderPlateau();
  renderBodyGoalChart();
  renderCalorieCalibration();
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
  ["breakfast", "lunch", "snack", "dinner"].forEach(key => n[key].options.forEach(o => o.items.forEach(i => {
    items.add(i.text || `${i.display || i.amount + " g"} ${(getIngredient(i.ing) || {}).label || i.ing}`);
  })));
  addShopItems(Array.from(items));
});
document.getElementById("shop-clear-checked").addEventListener("click", () => {
  saveShopList(loadShopList().filter(i => !i.checked));
  renderShopList();
});

// ---------------------------------------------------------------- budget
let currentEconMonth = emKeyForDate(todayISO());

document.getElementById("tx-date").value = todayISO();

function populateCategorySelect() {
  document.getElementById("tx-category").innerHTML = categoryOptionsHtml(loadBudgetConfig());
}

function categoryRowHtml(c, emKey) {
  const cap = getCategoryCap(c, emKey);
  const spent = categorySpent(c.key, emKey);
  const pct = cap ? 100 * spent / cap : (spent > 0 ? 100 : 0);
  const barWidth = Math.min(100, pct);
  const cls = pct >= 100 ? "over" : pct >= 80 ? "warn" : "good";
  const over = spent > cap;
  return `<div class="cat-row" data-key="${c.key}">
    <div class="cat-head"><span>${c.icon ? c.icon + " " : ""}${c.label}</span><b>${spent.toLocaleString()} / <input class="cap-edit" type="number" value="${cap}" data-cat="${c.key}"> kr</b></div>
    <div class="cat-bar"><div class="${cls}" style="width:${barWidth}%"></div></div>
    ${over ? `<div class="cat-grace">💛 Over budsjett denne økonomimåneden - det går bra, juster og fortsett.</div>` : ""}
  </div>`;
}

function renderCategoryBreakdown() {
  const cfg = loadBudgetConfig();
  const fixed = cfg.categories.filter(c => c.type === "fixed");
  const variable = cfg.categories.filter(c => c.type === "variable");
  document.getElementById("fixed-cat-list").innerHTML = fixed.map(c => categoryRowHtml(c, currentEconMonth)).join("");
  document.getElementById("variable-cat-list").innerHTML = variable.map(c => categoryRowHtml(c, currentEconMonth)).join("");

  document.querySelectorAll(".budget-cat-list .cap-edit").forEach(inp => {
    inp.addEventListener("change", () => {
      setCategoryCap(inp.dataset.cat, currentEconMonth, parseFloat(inp.value) || 0);
      renderBudget();
    });
  });
}

function renderBudgetSummary() {
  const cfg = loadBudgetConfig();
  const start = emStart(currentEconMonth), end = emEnd(currentEconMonth);
  const totalSpent = loadTransactions().filter(t => t.date >= start && t.date <= end).reduce((s, t) => s + t.amount, 0);
  document.getElementById("budget-summary").innerHTML = `
    <div class="snapshot-chip">Inntekt<b>${cfg.income.toLocaleString()} kr</b></div>
    <div class="snapshot-chip">Brukt denne måneden<b>${totalSpent.toLocaleString()} kr</b></div>
    <div class="snapshot-chip">Igjen<b>${(cfg.income - totalSpent).toLocaleString()} kr</b></div>
  `;
}

function renderTxList() {
  const cfg = loadBudgetConfig();
  const catLabel = key => (cfg.categories.find(c => c.key === key) || {}).label || key;
  const start = emStart(currentEconMonth), end = emEnd(currentEconMonth);
  const tx = loadTransactions().filter(t => t.date >= start && t.date <= end).sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("tx-list").innerHTML = tx.map(t => `
    <li data-id="${t.id}"><span>${fmtShort(t.date)} · ${catLabel(t.category)} · ${t.name || ""}</span>
      <b>${t.amount} kr</b>
      <button data-tx-remove="${t.id}" style="background:none;border:none;color:var(--muted);cursor:pointer;">✕</button>
    </li>`).join("") || `<li style="border-top:none;color:var(--muted);">Ingen transaksjoner denne økonomimåneden</li>`;

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
  renderHjemTodayTx();
  renderHjemFinance();
  renderSavingsGoals();
  renderExpenseTrends();
}

document.getElementById("em-label").textContent = emLabel(currentEconMonth);
function shiftEconMonth(delta) {
  currentEconMonth = emAddMonths(currentEconMonth, delta);
  document.getElementById("em-label").textContent = emLabel(currentEconMonth);
  renderCategoryBreakdown();
  renderBudgetSummary();
  renderTxList();
}
document.getElementById("em-prev").addEventListener("click", () => shiftEconMonth(-1));
document.getElementById("em-next").addEventListener("click", () => shiftEconMonth(1));

populateCategorySelect();

function addTransactionWithRoundUp(date, amount, category, name) {
  const tx = loadTransactions();
  tx.push({ id: "tx-" + Date.now() + Math.random(), date, amount, category, name });
  saveTransactions(tx);
  let roundedUp = false;
  if (!isSavingsCategory(category)) {
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
  currentEconMonth = emKeyForDate(date);
  document.getElementById("em-label").textContent = emLabel(currentEconMonth);
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
renderMeasureLog();
renderPlateau();
renderShopList();
renderBudget();

// ---------------------------------------------------------------- stat cards

// ---------------------------------------------------------------- weekly by sport chart
const SPORT_LABELS_NO = { Strength: "Styrke", Cycling: "Sykling", Running: "Løping", Walking: "Gange", Other: "Annet" };

(function renderWeeklySport() {
  const svg = document.getElementById("chart-weekly-sport");
  const tooltip = document.getElementById("tt-weekly");
  const legend = document.getElementById("sport-legend");
  const weeks = DATA.weeklyBySport;
  const sports = DATA.sportOrder;
  const colors = DATA.sportColors;

  sports.forEach(sp => {
    legend.innerHTML += `<span><i style="background:${colors[sp]}"></i>${SPORT_LABELS_NO[sp] || sp}</span>`;
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
      tooltip.textContent = `${SPORT_LABELS_NO[bar.dataset.sport] || bar.dataset.sport}: ${bar.dataset.sessions} økt(er), ${bar.dataset.minutes} min, ${bar.dataset.dist} km`;
    });
    bar.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
  });
})();

// ---------------------------------------------------------------- line charts
function renderLineChart(svgId, ttId, weeks, values, color, unit) {
  const svg = document.getElementById(svgId);
  const tooltip = document.getElementById(ttId);
  if (!weeks || !weeks.length) { svg.outerHTML = '<div style="color:#8a8580;font-size:13px;">Ingen data ennå</div>'; return; }

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

const TREND_WEEKS_SHOWN = 26; // ~6 months - full history is overkill for these charts
renderLineChart("chart-load", "tt-load", DATA.trends.trainingLoad.weeks.slice(-TREND_WEEKS_SHOWN), DATA.trends.trainingLoad.values.slice(-TREND_WEEKS_SHOWN), "#7a1f3d", "load");
renderLineChart("chart-rhr", "tt-rhr", DATA.trends.restingHR.weeks.slice(-TREND_WEEKS_SHOWN), DATA.trends.restingHR.values.slice(-TREND_WEEKS_SHOWN), "#9b3456", "bpm");
renderLineChart("chart-hrv", "tt-hrv", DATA.trends.hrv.weeks.slice(-TREND_WEEKS_SHOWN), DATA.trends.hrv.values.slice(-TREND_WEEKS_SHOWN), "#a46cc0", "ms");
renderLineChart("chart-sleep", "tt-sleep", DATA.trends.sleepHours.weeks.slice(-TREND_WEEKS_SHOWN), DATA.trends.sleepHours.values.slice(-TREND_WEEKS_SHOWN), "#e8a3b6", "hrs");

// ---------------------------------------------------------------- generic multi-series trend chart (Fremgang)
// series: [{ name, color, values, unit, axis: "left"|"right", decimals }], shared x-axis labels.
// Used wherever two differently-scaled metrics need to sit on one timeline (dual y-axis),
// or several same-unit series need to be compared directly (shared y-axis).
function renderTrendChart(svgId, ttId, labels, series, opts) {
  opts = opts || {};
  const svg = document.getElementById(svgId);
  const tooltip = document.getElementById(ttId);
  if (!svg) return;
  const hasData = labels && labels.length && series.some(s => s.values.some(v => v != null));
  if (!hasData) {
    svg.outerHTML = '<div style="color:#8a8580;font-size:13px;padding:30px 0;text-align:center;">Ikke nok data ennå</div>';
    if (tooltip) tooltip.style.opacity = 0;
    return;
  }
  svg.classList.add("ml-chart");
  if (tooltip) tooltip.classList.add("ml");

  const hasRight = series.some(s => s.axis === "right");
  const w = 480, h = 190, padLeft = 38, padRight = hasRight ? 38 : 12, padTop = 14, padBottom = 22;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = "";
  const plotW = w - padLeft - padRight, plotH = h - padTop - padBottom;
  const step = plotW / Math.max(labels.length - 1, 1);
  const xAt = i => padLeft + i * step;

  function scaleFor(vals) {
    const present = vals.filter(v => v != null);
    if (!present.length) return { min: 0, max: 1 };
    let min = Math.min(...present), max = Math.max(...present);
    if (min === max) { min -= 1; max += 1; }
    const pad = (max - min) * 0.12;
    return { min: min - pad, max: max + pad };
  }
  const leftSeries = series.filter(s => s.axis !== "right");
  const rightSeries = series.filter(s => s.axis === "right");
  const leftScale = scaleFor(leftSeries.flatMap(s => s.values));
  const rightScale = rightSeries.length ? scaleFor(rightSeries.flatMap(s => s.values)) : null;
  const yAt = (v, axis) => {
    const sc = axis === "right" ? rightScale : leftScale;
    return padTop + plotH - ((v - sc.min) / (sc.max - sc.min)) * plotH;
  };

  for (let i = 0; i <= 3; i++) {
    const y = padTop + plotH - (i / 3) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y.toFixed(1)}" x2="${w - padRight}" y2="${y.toFixed(1)}" stroke="#ece7e0" stroke-width="1"/>`;
    const leftVal = leftScale.min + (i / 3) * (leftScale.max - leftScale.min);
    svg.innerHTML += `<text x="${padLeft - 6}" y="${(y + 3).toFixed(1)}" font-size="9" fill="#8a8580" text-anchor="end">${leftVal.toFixed(opts.leftDecimals ?? 0)}</text>`;
    if (rightScale) {
      const rightVal = rightScale.min + (i / 3) * (rightScale.max - rightScale.min);
      svg.innerHTML += `<text x="${w - padRight + 6}" y="${(y + 3).toFixed(1)}" font-size="9" fill="#8a8580" text-anchor="start">${rightVal.toFixed(opts.rightDecimals ?? 0)}</text>`;
    }
  }

  series.forEach(s => {
    const pathPts = [];
    let dots = "";
    s.values.forEach((v, i) => {
      if (v == null) return;
      const x = xAt(i), y = yAt(v, s.axis);
      pathPts.push([x, y]);
      dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${s.color}" opacity="0.9"/>`;
    });
    if (pathPts.length) {
      const path = pathPts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      svg.innerHTML += `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`;
    }
    svg.innerHTML += dots;
  });

  const labelIdxs = labels.length > 1 ? [0, Math.floor(labels.length / 2), labels.length - 1] : [0];
  labelIdxs.forEach(i => {
    const x = xAt(i);
    svg.innerHTML += `<text x="${x.toFixed(1)}" y="${h - 4}" font-size="9" fill="#8a8580" text-anchor="middle">${opts.fmtLabel ? opts.fmtLabel(labels[i]) : fmtShort(labels[i])}</text>`;
  });

  if (tooltip) {
    labels.forEach((lab, i) => {
      const x = xAt(i);
      const hit = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      hit.setAttribute("x", (x - step / 2).toFixed(1));
      hit.setAttribute("y", padTop);
      hit.setAttribute("width", Math.max(step, 4).toFixed(1));
      hit.setAttribute("height", plotH);
      hit.setAttribute("fill", "transparent");
      svg.appendChild(hit);
      hit.addEventListener("mousemove", e => {
        const r = svg.getBoundingClientRect();
        tooltip.style.opacity = 1;
        tooltip.style.left = (e.clientX - r.left) + "px";
        tooltip.style.top = (e.clientY - r.top) + "px";
        const lines = series.filter(s => s.values[i] != null).map(s =>
          `${s.name}: <b>${s.values[i].toLocaleString()}${s.unit ? " " + s.unit : ""}</b>`
        );
        tooltip.innerHTML = `${opts.fmtLabel ? opts.fmtLabel(lab) : fmtDate(lab)}<br>${lines.join("<br>")}`;
      });
      hit.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
    });
  }

  if (opts.legendId) {
    const el = document.getElementById(opts.legendId);
    if (el) el.innerHTML = series.map(s => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("");
  }
}

function alignWeeklySeries(seriesList) {
  // seriesList: [{weeks, values}, ...] from DATA.trends - different metrics can have
  // slightly different week coverage, so align them onto their combined week list.
  const allWeeks = Array.from(new Set(seriesList.flatMap(s => s.weeks))).sort();
  const valuesList = seriesList.map(s => {
    const byWeek = {};
    s.weeks.forEach((w, i) => { byWeek[w] = s.values[i]; });
    return allWeeks.map(w => (byWeek[w] != null ? byWeek[w] : null));
  });
  return { weeks: allWeeks, valuesList };
}

// ---------------------------------------------------------------- fremgang: kropp & mål
const BODY_MEASURE_LABELS = { waist: "Mage", hips: "Hofte", arm: "Arm", thigh: "Lår", chest: "Bryst" };
let bodyChartPeriodMonths = 12;
let bodyChartMeasure = "waist";

function renderWeightGoalInput() {
  const inp = document.getElementById("weight-goal-input");
  if (!inp) return;
  const goal = loadSettings().weightGoal;
  inp.value = goal != null ? goal : "";
  document.getElementById("weight-goal-save").addEventListener("click", () => {
    const val = parseFloat(inp.value);
    const s = loadSettings();
    s.weightGoal = Number.isNaN(val) ? null : val;
    saveSettings(s);
    renderBodyGoalChart();
  });
}

// ---- calorie calibration: does logged intake/burn actually match real weight change? ----
function computeCalorieCalibration() {
  const history = (DATA.dailyHistory || []).filter(d => d.calories != null);
  if (history.length < 10) return null;

  const weightLog = loadWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  if (weightLog.length < 2) return null;
  const avgSeries = weightRollingAvgSeries(weightLog);

  function weightNear(targetDate) {
    let best = null, bestDiff = Infinity;
    weightLog.forEach((e, i) => {
      const diff = Math.abs(new Date(e.date + "T00:00:00") - new Date(targetDate + "T00:00:00"));
      if (diff < bestDiff) { bestDiff = diff; best = avgSeries[i]; }
    });
    return bestDiff <= 10 * 24 * 3600 * 1000 ? best : null;
  }
  const startWeight = weightNear(history[0].date);
  const endWeight = weightNear(history[history.length - 1].date);
  if (startWeight == null || endWeight == null) return null;

  let totalDeficit = 0, loggedDays = 0;
  history.forEach(d => {
    const totals = dayNutritionTotals(d.date);
    if (totals.mealsLogged.length < 2) return; // skip days that weren't really logged
    totalDeficit += d.calories - totals.kcal;
    loggedDays++;
  });
  if (loggedDays < 7) return null;

  const KCAL_PER_KG = 7700;
  const impliedChangeKg = -totalDeficit / KCAL_PER_KG;
  const actualChangeKg = endWeight - startWeight;
  const extraDailyDeficitKcal = Math.round(((impliedChangeKg - actualChangeKg) * KCAL_PER_KG) / loggedDays);

  return {
    loggedDays, impliedChangeKg, actualChangeKg, extraDailyDeficitKcal,
    startDate: history[0].date, endDate: history[history.length - 1].date,
  };
}

function renderCalorieCalibration() {
  const el = document.getElementById("calorie-calibration-note");
  if (!el) return;
  const c = computeCalorieCalibration();
  if (!c) { el.innerHTML = ""; return; }

  const impliedTxt = `${c.impliedChangeKg >= 0 ? "+" : ""}${c.impliedChangeKg.toFixed(1)} kg`;
  const actualTxt = `${c.actualChangeKg >= 0 ? "+" : ""}${c.actualChangeKg.toFixed(1)} kg`;
  let verdict;
  if (Math.abs(c.extraDailyDeficitKcal) < 80) {
    verdict = "Loggen din stemmer godt med faktisk vektendring - ingen justering nødvendig akkurat nå.";
  } else if (c.extraDailyDeficitKcal > 0) {
    verdict = `Du har i snitt hatt et ${Math.abs(c.extraDailyDeficitKcal)} kcal/dag <b>større</b> underskudd enn loggen viser - kroppen din ser ut til å forbrenne litt mer enn Garmin-tallene antyder, eller du har fått i deg litt mindre enn det som er logget.`;
  } else {
    verdict = `Du har i snitt hatt et ${Math.abs(c.extraDailyDeficitKcal)} kcal/dag <b>mindre</b> underskudd enn loggen viser - sjekk om noe blir spist uten å bli logget, eller om Garmin overvurderer forbrenningen din litt.`;
  }
  el.innerHTML = `<div class="context-note">
    <b>Kalorikalibrering</b> (siste ${c.loggedDays} fullt loggede dager, ${fmtShort(c.startDate)}–${fmtShort(c.endDate)}): loggen antydet ${impliedTxt}, du gikk faktisk ${actualTxt}. ${verdict}
  </div>`;
}

function renderBodyGoalChart() {
  if (!document.getElementById("chart-body")) return;
  const cutoff = isoAddDays(todayISO(), -bodyChartPeriodMonths * 30);
  const weightInRange = loadWeightLog().filter(e => e.date >= cutoff).sort((a, b) => a.date.localeCompare(b.date));
  const measureInRange = loadMeasureLog()
    .filter(e => e.date >= cutoff && e[bodyChartMeasure] != null)
    .sort((a, b) => a.date.localeCompare(b.date));

  const weightAvgSeries = weightInRange.length ? weightRollingAvgSeries(weightInRange) : [];
  const allDates = Array.from(new Set([...weightInRange.map(e => e.date), ...measureInRange.map(e => e.date)])).sort();
  const weightByDate = {};
  weightInRange.forEach((e, i) => { weightByDate[e.date] = weightAvgSeries[i]; });
  const measureByDate = {};
  measureInRange.forEach(e => { measureByDate[e.date] = e[bodyChartMeasure]; });

  const weightVals = allDates.map(d => (weightByDate[d] != null ? weightByDate[d] : null));
  const measureVals = allDates.map(d => (measureByDate[d] != null ? measureByDate[d] : null));
  const measureLabel = BODY_MEASURE_LABELS[bodyChartMeasure];

  renderTrendChart("chart-body", "tt-body", allDates, [
    { name: "Vekt", color: "#7a1f3d", values: weightVals, unit: "kg", axis: "left" },
    { name: measureLabel, color: "#a46cc0", values: measureVals, unit: "cm", axis: "right" },
  ], { legendId: "legend-body", leftDecimals: 1, rightDecimals: 1 });

  const note = document.getElementById("body-context-note");
  if (!note) return;
  const wVals = weightVals.filter(v => v != null);
  const mVals = measureVals.filter(v => v != null);

  const weightGoal = loadSettings().weightGoal;
  let goalPhrase = "";
  if (weightGoal != null && wVals.length) {
    const latest = wVals[wVals.length - 1];
    const gap = latest - weightGoal;
    goalPhrase = Math.abs(gap) < 0.3
      ? ` Du er på målvekten din (${weightGoal} kg)! 🎉`
      : ` Du er ${Math.abs(gap).toFixed(1)} kg ${gap > 0 ? "over" : "under"} målvekten din på ${weightGoal} kg.`;
  }

  if (wVals.length < 2 && mVals.length < 2) {
    note.textContent = `Ikke nok logget data i denne perioden ennå til å si noe om trenden.${goalPhrase}`;
    return;
  }
  const weightDiff = wVals.length >= 2 ? wVals[wVals.length - 1] - wVals[0] : null;
  const measureDiff = mVals.length >= 2 ? mVals[mVals.length - 1] - mVals[0] : null;
  const weightPhrase = weightDiff == null ? "Ikke nok vektdata ennå i perioden"
    : Math.abs(weightDiff) < 0.3 ? "Vekten er stabil"
    : weightDiff < 0 ? `Vekten har gått ned ${Math.abs(weightDiff).toFixed(1)} kg` : `Vekten har gått opp ${weightDiff.toFixed(1)} kg`;
  const lcLabel = measureLabel.toLowerCase();
  const measurePhrase = measureDiff == null ? `ingen ${lcLabel}-mål nok ennå i perioden`
    : Math.abs(measureDiff) < 0.5 ? `${lcLabel}en er uendret`
    : measureDiff < 0 ? `${lcLabel}en har krympet ${Math.abs(measureDiff).toFixed(1)} cm` : `${lcLabel}en har økt ${measureDiff.toFixed(1)} cm`;
  note.textContent = `${weightPhrase}, og ${measurePhrase}.${goalPhrase}`;
}

// ---------------------------------------------------------------- fremgang: aktivitets-trender
function renderActivityTrends() {
  if (!document.getElementById("chart-activity")) return;
  const act = alignWeeklySeries([DATA.trends.steps, DATA.trends.activeCalories]);
  renderTrendChart("chart-activity", "tt-activity", act.weeks, [
    { name: "Skritt", color: "#7a1f3d", values: act.valuesList[0], unit: "skritt", axis: "left" },
    { name: "Aktive kalorier", color: "#f6c667", values: act.valuesList[1], unit: "kcal", axis: "right" },
  ], { legendId: "legend-activity" });

  const ss = alignWeeklySeries([DATA.trends.stress, DATA.trends.sleepScore]);
  renderTrendChart("chart-stress-sleep", "tt-stress-sleep", ss.weeks, [
    { name: "Stress", color: "#e37878", values: ss.valuesList[0], unit: "", axis: "left" },
    { name: "Søvnscore", color: "#a46cc0", values: ss.valuesList[1], unit: "", axis: "right" },
  ], { legendId: "legend-stress-sleep" });

  const note = document.getElementById("activity-context-note");
  if (!note) return;
  const pairs = ss.weeks.map((w, i) => ({ stress: ss.valuesList[0][i], sleep: ss.valuesList[1][i] }))
    .filter(p => p.stress != null && p.sleep != null);
  if (pairs.length < 4) {
    note.textContent = "Ikke nok uker med både stress- og søvndata ennå til å se mønstre.";
    return;
  }
  const sorted = [...pairs].sort((a, b) => a.stress - b.stress);
  const lowHalf = sorted.slice(0, Math.floor(sorted.length / 2));
  const highHalf = sorted.slice(Math.ceil(sorted.length / 2));
  const avgSleepLow = lowHalf.reduce((s, p) => s + p.sleep, 0) / lowHalf.length;
  const avgSleepHigh = highHalf.reduce((s, p) => s + p.sleep, 0) / highHalf.length;
  const diff = avgSleepLow - avgSleepHigh;
  note.textContent = Math.abs(diff) >= 3
    ? `I ukene med høyest stress har søvnscoren i snitt vært ${Math.abs(diff).toFixed(0)} poeng ${diff > 0 ? "lavere" : "høyere"} enn i ukene med lavest stress.`
    : "Ingen tydelig sammenheng mellom stressnivå og søvnkvalitet i perioden ennå.";
}

// ---------------------------------------------------------------- fremgang: faste vs. variable utgifter
function renderExpenseTrends() {
  if (!document.getElementById("chart-expenses")) return;
  const emKeys = emKeysBack(12);
  const cfg = loadBudgetConfig();
  const fixedKeys = cfg.categories.filter(c => c.type === "fixed").map(c => c.key);
  const variableKeys = cfg.categories.filter(c => c.type === "variable" && !c.savings).map(c => c.key);
  const tx = loadTransactions();
  const totalFor = (keys, emKey) => {
    const start = emStart(emKey), end = emEnd(emKey);
    return tx.filter(t => keys.includes(t.category) && t.date >= start && t.date <= end).reduce((s, t) => s + t.amount, 0);
  };
  const fixedVals = emKeys.map(ek => totalFor(fixedKeys, ek));
  const variableVals = emKeys.map(ek => totalFor(variableKeys, ek));

  renderTrendChart("chart-expenses", "tt-expenses", emKeys, [
    { name: "Faste utgifter", color: "#7a1f3d", values: fixedVals, unit: "kr" },
    { name: "Variable utgifter", color: "#a46cc0", values: variableVals, unit: "kr" },
  ], { legendId: "legend-expenses", fmtLabel: emShortLabel });

  const list = document.getElementById("fixed-expense-totals");
  if (list) {
    const pairs = emKeys.map((ek, i) => ({ ek, val: fixedVals[i] })).slice(-6).reverse();
    const rows = pairs.map(p => `<div class="et-row"><span>${emShortLabel(p.ek)}</span><b>${Math.round(p.val).toLocaleString()} kr</b></div>`).join("");
    list.innerHTML = `<h4 style="margin:14px 0 2px;font-size:13px;">Faste utgifter per økonomimåned</h4><div class="expense-totals-list">${rows}</div>`;
  }
}

// ---------------------------------------------------------------- fremgang: sparemål
function renderSavingsGoals() {
  const el = document.getElementById("savings-goals");
  if (!el) return;
  const cats = loadBudgetConfig().categories.filter(c => c.savings);
  el.innerHTML = cats.map(c => {
    const balance = savingsBalance(c.key);
    const target = savingsTarget(c.key);
    const pct = target ? Math.min(100, Math.round(100 * balance / target)) : 0;
    const proj = projectSavingsMilestone(c.key);
    let etaText;
    if (target > 0 && balance >= target) etaText = "🎉 Målet er nådd!";
    else if (proj) etaText = `Ved nåværende sparetakt (~${Math.round(proj.rate).toLocaleString()} kr/mnd) når du målet rundt ${emShortLabel(proj.emKey)}.`;
    else etaText = "Spar litt i denne kategorien for å se en anslått dato.";
    const isDogFund = c.key === DATA.dogFund.category;
    return `
    <div class="savings-goal-card">
      <div class="sg-label">${c.icon ? c.icon + " " : ""}${c.label}</div>
      <div class="sg-amount">${Math.round(balance).toLocaleString()} kr</div>
      <div class="cat-bar"><div class="${pct >= 100 ? "good" : ""}" style="width:${pct}%"></div></div>
      ${isDogFund ? "" : `<div class="sg-goal-row">Saldo nå: <input type="number" step="100" class="sg-balance-input" data-cat="${c.key}" value="${Math.round(balance)}"> kr</div>`}
      <div class="sg-goal-row">Mål: <input type="number" step="500" class="sg-target-input" data-cat="${c.key}" value="${target}"> kr</div>
      <div class="sg-eta">${etaText}</div>
    </div>`;
  }).join("");

  el.querySelectorAll(".sg-target-input").forEach(inp => {
    inp.addEventListener("change", () => {
      setSavingsTarget(inp.dataset.cat, parseFloat(inp.value) || 0);
      renderSavingsGoals();
      renderFund();
    });
  });
  el.querySelectorAll(".sg-balance-input").forEach(inp => {
    inp.addEventListener("change", () => {
      setSavingsCurrentBalance(inp.dataset.cat, parseFloat(inp.value) || 0);
      renderSavingsGoals();
    });
  });
}

// ---------------------------------------------------------------- fremgang: fond-utvikling
function renderFundTrend() {
  if (!document.getElementById("chart-fund")) return;
  const log = loadInvestFundLog().sort((a, b) => a.date.localeCompare(b.date));
  const labels = log.map(e => e.date);
  const valueVals = log.map(e => e.value);
  const contributedVals = log.map(e => (e.contributed != null ? e.contributed : null));

  renderTrendChart("chart-fund", "tt-fund", labels, [
    { name: "Fondsverdi", color: "#7a1f3d", values: valueVals, unit: "kr" },
    { name: "Innskutt kapital", color: "#a46cc0", values: contributedVals, unit: "kr" },
  ], { legendId: "legend-fund" });

  const summary = document.getElementById("fund-summary");
  if (!summary) return;
  if (!log.length) { summary.innerHTML = ""; return; }
  const latest = log[log.length - 1];
  if (latest.contributed != null && latest.value != null) {
    const gain = latest.value - latest.contributed;
    const gainPct = latest.contributed ? (100 * gain / latest.contributed) : 0;
    summary.innerHTML = `
      <div class="fs-item">Innskutt<br><b>${Math.round(latest.contributed).toLocaleString()} kr</b></div>
      <div class="fs-item">Verdi i dag<br><b>${Math.round(latest.value).toLocaleString()} kr</b></div>
      <div class="fs-item">Avkastning<br><b class="${gain >= 0 ? "pos" : "neg"}">${gain >= 0 ? "+" : ""}${Math.round(gain).toLocaleString()} kr (${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(1)}%)</b></div>
    `;
  } else {
    summary.innerHTML = `
      <div class="fs-item">Verdi i dag<br><b>${Math.round(latest.value).toLocaleString()} kr</b></div>
      <div class="fs-item" style="color:var(--muted);font-size:12px;max-width:220px;">Logg innskutt kapital for å se avkastningen</div>
    `;
  }
}

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
  { key: "longestRide", label: "Lengste sykkeltur", fmt: r => `${r.value} ${r.unit}` },
  { key: "longestRun", label: "Lengste løpetur", fmt: r => `${r.value} km` },
  { key: "longestStrength", label: "Lengste styrkeøkt", fmt: r => `${r.value} min` },
  { key: "mostSteps", label: "Flest skritt på en dag", fmt: r => `${r.value.toLocaleString()}` },
  { key: "mostCalories", label: "Flest kalorier på en dag", fmt: r => `${r.value.toLocaleString()} kcal` },
  { key: "longestSleep", label: "Lengste søvn på en natt", fmt: r => `${r.value} t` },
  { key: "bestHRV", label: "Høyeste HRV-natt", fmt: r => `${r.value} ms` },
  { key: "highestTrainingLoad", label: "Høyeste treningsbelastning", fmt: r => `${r.value}` },
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

// ---- Sonar-style daily scores: a big Recovery ring + small Strain/Nutrition rings ----
function scoreColor(score) {
  if (score == null) return "var(--hj-muted)";
  if (score >= 67) return "#2f8a4e";
  if (score >= 34) return "#b8860b";
  return "#c0392b";
}
function ringGaugeSvg(score, size, strokeWidth) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100;
  const offset = circumference * (1 - pct);
  const center = size / 2;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="var(--hj-line)" stroke-width="${strokeWidth}"/>
    <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="${scoreColor(score)}" stroke-width="${strokeWidth}"
      stroke-dasharray="${circumference.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}"
      stroke-linecap="round" transform="rotate(-90 ${center} ${center})"/>
  </svg>`;
}
function scoreRingHtml(score, size, strokeWidth) {
  return `<div class="score-ring" style="width:${size}px;height:${size}px;">
    ${ringGaugeSvg(score, size, strokeWidth)}
    <div class="score-ring-num" style="color:${scoreColor(score)};font-size:${Math.round(size * 0.32)}px;">${score != null ? score : "–"}</div>
  </div>`;
}
// kcal: scores 100 at the goal, falling off the further eaten is from it in either direction.
// protein: scores by how close you are to your protein floor, capped at 100 once you hit it.
function nutritionScore() {
  const n = DATA.nutritionPlan;
  const totals = dayNutritionTotals(todayISO());
  const proteinPct = n.proteinMin ? Math.min(100, Math.round(100 * totals.protein / n.proteinMin)) : null;
  let kcalScore = null;
  if (n.dailyKcal) {
    const diffPct = Math.abs(totals.kcal - n.dailyKcal) / n.dailyKcal;
    kcalScore = Math.max(0, Math.round(100 - diffPct * 150));
  }
  const parts = [proteinPct, kcalScore].filter(v => v != null);
  return parts.length ? Math.round(parts.reduce((s, v) => s + v, 0) / parts.length) : null;
}

function recoveryVerdict(score) {
  if (score == null) return "Ikke nok data til å beregne recovery ennå.";
  if (score >= 67) return "God recovery - kroppen er klar for en skikkelig økt i dag.";
  if (score >= 34) return "Middels recovery - kjør økta, men hold litt igjen hvis du kjenner det.";
  return "Lav recovery - vurder en lettere variant eller prioriter hvile i dag.";
}
// Tells her whether to push harder or ease off tomorrow, based on today's recovery
// (how ready the body was) against today's strain (how hard it was actually used) -
// and defers to the plan if tomorrow is already a scheduled rest day.
function strainNote(strain, recovery, p) {
  if (strain == null || recovery == null) return "Ikke nok data ennå til å si noe om i morgen.";

  const tomorrowDate = isoAddDays(todayISO(), 1);
  const tomorrowDay = p.week.find(d => d.date === tomorrowDate);
  if (tomorrowDay) {
    const tomorrowResolved = resolvePlanDay(tomorrowDay, loadPlanOverrides());
    if (tomorrowResolved.type === "rest") {
      return "I morgen er det uansett hviledag ifølge planen - fin timing uansett dagens belastning.";
    }
  }

  const highRecovery = recovery >= 67, lowRecovery = recovery < 34;
  const highStrain = strain >= 67, lowStrain = strain < 34;

  if (highRecovery && lowStrain) return "God recovery og lite belastning så langt - du kan trygt trene litt hardere i morgen.";
  if (highRecovery && highStrain) return "Du har alt hatt en tung dag med god recovery i bunn - fortsett som normalt i morgen.";
  if (lowRecovery && highStrain) return "Høy belastning på en dag med lav recovery - ta det roligere i morgen.";
  if (lowRecovery && lowStrain) return "Lav recovery selv uten mye belastning - prioriter hvile eller en lett økt i morgen.";
  if (highRecovery) return "God recovery - du tåler en normal eller litt tyngre økt i morgen.";
  if (lowRecovery) return "Lav recovery - hold morgendagens økt lett til moderat.";
  return "Middels recovery og belastning - en vanlig økt i morgen bør gå fint.";
}
function nutritionNote(score, totals, n) {
  if (score == null) return "Ikke logget noe i dag ennå.";
  const proteinPct = n.proteinMin ? Math.round(100 * totals.protein / n.proteinMin) : null;
  if (proteinPct != null && proteinPct < 70) return `${Math.round(totals.protein)} / ${n.proteinMin} g protein så langt.`;
  if (score >= 67) return "Bra treff på kalorier og protein i dag.";
  if (score >= 34) return "Et stykke unna kalorie-/proteinmålet ennå.";
  return "Langt unna kalorie-/proteinmålet i dag.";
}

function renderHjemSession() {
  const p = DATA.program;
  const el = document.getElementById("hjem-session");
  if (!p || !el) return;
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

  let statusKey = "notstarted", statusLabel = "Ikke startet";
  if (resolved.type === "rest") {
    statusKey = "done"; statusLabel = "Hviledag";
  } else if (resolved.done) {
    statusKey = "done"; statusLabel = "Fullført";
  } else if (loadSetLog().some(s => s.date === todayISO() && s.exercise.startsWith(resolved.key + "::"))) {
    statusKey = "inprogress"; statusLabel = "Pågår";
  }

  const recovery = p.today.recoveryScore;
  const strain = p.today.strainScore;
  const nutritionTotals = dayNutritionTotals(todayISO());
  const nutrition = nutritionScore();
  const recoveryText = [recoveryVerdict(recovery), ...(p.today.reasons || [])].join(" ");

  el.innerHTML = `
    <div class="hs-top">
      <div class="hs-score-block">
        ${scoreRingHtml(recovery, 72, 7)}
        <div class="hs-score-label">Recovery</div>
      </div>
      <div class="hs-info">
        <div class="hs-label">${resolved.type === "rest" ? "Hviledag" : resolved.label}</div>
        <div class="hs-sub">Uke ${p.currentWeek}${p.weekIsDeload ? " · Deload" : " av 4"} · ${p.weekFocus}</div>
        <span class="hs-status ${statusKey}">${statusLabel}</span>
      </div>
    </div>
    <div class="hs-recovery-note">${recoveryText}</div>
    <div class="hs-secondary-scores">
      <div class="hs-mini-score">
        ${scoreRingHtml(strain, 40, 5)}
        <div class="hs-mini-label">Belastning<b>${strain != null ? strain : "–"}</b>
          <span class="hs-mini-note">${strainNote(strain, recovery, p)}</span>
        </div>
      </div>
      <div class="hs-mini-score">
        ${scoreRingHtml(nutrition, 40, 5)}
        <div class="hs-mini-label">Ernæring<b>${nutrition != null ? nutrition : "–"}</b>
          <span class="hs-mini-note">${nutritionNote(nutrition, nutritionTotals, DATA.nutritionPlan)}</span>
        </div>
      </div>
    </div>
    <button class="hs-link" id="hjem-session-link">${resolved.type === "rest" ? "Til plan →" : "Til økta →"}</button>
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
  if (!n || !el) return;
  const totals = dayNutritionTotals(todayISO());
  const over = totals.kcal > n.dailyKcal;

  const burned = reportMetric("calories").today;
  let balanceHtml = "";
  if (burned != null) {
    const diff = burned - totals.kcal;
    const diffLabel = diff >= 0 ? `${diff} kcal underskudd så langt` : `${Math.abs(diff)} kcal overskudd så langt`;
    balanceHtml = `
      <div class="hnq-balance">
        <span>Forbrent så langt i dag (Garmin): ${burned} kcal</span>
        <span class="hnq-balance-diff${diff >= 0 ? "" : " over"}">${diffLabel}</span>
      </div>`;
  }

  el.innerHTML = `
    <div>
      <div class="hnq-label">Spist / Budsjett</div>
      <div class="hnq-val${over ? " over" : ""}">${totals.kcal} / ${n.dailyKcal} kcal</div>
      <div class="hnq-macro">${totals.protein} / ${n.proteinMin} g protein</div>
      ${balanceHtml}
    </div>
    <button id="hjem-logg-maltid-btn">+ Logg måltid</button>
  `;
  document.getElementById("hjem-logg-maltid-btn").addEventListener("click", openMatDrawer);
}

function renderHjemTodayTx() {
  const el = document.getElementById("hjem-tx-today");
  if (!el) return;
  const cfg = loadBudgetConfig();
  const catLabel = key => (cfg.categories.find(c => c.key === key) || {}).label || key;
  const tx = loadTransactions().filter(t => t.date === todayISO());
  const total = tx.reduce((s, t) => s + t.amount, 0);
  el.innerHTML = `
    <div class="hjem-card-title">Dagens transaksjoner</div>
    <ul class="hjem-tx-list">
      ${tx.length
        ? tx.map(t => `<li><span class="tx-name">${t.name || catLabel(t.category)}</span><b>${t.amount.toLocaleString()} kr</b></li>`).join("")
        : `<li class="hjem-tx-empty">Ingen transaksjoner i dag</li>`}
    </ul>
    <div class="hjem-tx-total"><span>Totalt i dag</span><span>${total.toLocaleString()} kr</span></div>
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

function renderHjemBodyToday() {
  const el = document.getElementById("hjem-body-today");
  if (!el) return;
  const ts = DATA.topStats || {};
  const steps = ts.steps || {};
  const stepsGoal = steps.goal || 8000;
  const stepsPct = stepsGoal ? Math.min(100, Math.round(100 * (steps.value || 0) / stepsGoal)) : 0;

  const activeCal = reportMetric("activeCalories").today;
  const calGoal = DATA.activeCalGoalDefault || 400;
  const calPct = calGoal ? Math.min(100, Math.round(100 * (activeCal || 0) / calGoal)) : 0;

  const sleep = ts.sleep || {};
  const stress = reportMetric("stress").today;
  const stressColor = stress == null ? null : stress <= 50 ? "green" : stress <= 75 ? "yellow" : "red";
  const bodyBattery = reportMetric("bodyBatteryLatest").today;

  el.innerHTML = `
    <div class="hjem-body-grid">
      <div class="hjem-card hjem-bigstat">
        <div class="hbs-label">Skritt</div>
        <div class="hbs-num">${steps.value != null ? steps.value.toLocaleString() : "–"}</div>
        <div class="hbs-bar"><div class="${stepsPct >= 100 ? "goalmet" : ""}" style="width:${stepsPct}%"></div></div>
      </div>
      <div class="hjem-card hjem-bigstat">
        <div class="hbs-label">Aktive kalorier</div>
        <div class="hbs-num">${activeCal != null ? Math.round(activeCal) : "–"}</div>
        <div class="hbs-bar"><div class="${calPct >= 100 ? "goalmet" : ""}" style="width:${calPct}%"></div></div>
      </div>
      <div class="hjem-minirow">
        <div class="hjem-card hjem-minicard">
          <div class="label">Søvn</div>
          <div class="value">${sleep.score != null ? sleep.score : "–"}</div>
          <div class="sub">${sleep.hours != null ? sleep.hours + " t" : ""}</div>
        </div>
        <div class="hjem-card hjem-minicard">
          <div class="label">Stress</div>
          <div class="value">${stressColor ? `<span class="stress-dot ${stressColor}"></span>` : ""}${stress != null ? Math.round(stress) : "–"}</div>
          <div class="sub"></div>
        </div>
        <div class="hjem-card hjem-minicard">
          <div class="label">Body Battery</div>
          <div class="value">${bodyBattery != null ? Math.round(bodyBattery) : "–"}</div>
          <div class="sub"></div>
        </div>
      </div>
    </div>
  `;
}

function loadInvestFundLog() { return loadLS(INVEST_FUND_KEY, []); }
function saveInvestFundLog(l) { saveLS(INVEST_FUND_KEY, l); }
function setInvestFundValue(date, value) {
  // quick single-field update (e.g. the Hjem-tab prompt) - carries the last known
  // contributed-capital figure forward, since that only changes on an actual deposit.
  const prior = loadInvestFundLog().filter(e => e.date < date).sort((a, b) => a.date.localeCompare(b.date));
  const contributed = prior.length ? prior[prior.length - 1].contributed : null;
  setInvestFundEntry(date, value, contributed);
}
function setInvestFundEntry(date, value, contributed) {
  const log = loadInvestFundLog().filter(e => e.date !== date);
  log.push({ date, value, contributed: contributed != null ? contributed : null });
  log.sort((a, b) => a.date.localeCompare(b.date));
  saveInvestFundLog(log);
}
function investFundStatus() {
  const log = loadInvestFundLog();
  if (!log.length) return { value: null, date: null, changeKr: null, changePct: null };
  const latest = log[log.length - 1];
  const prev = log.length > 1 ? log[log.length - 2] : null;
  const changeKr = prev ? latest.value - prev.value : null;
  const changePct = prev && prev.value ? (100 * changeKr / prev.value) : null;
  return { value: latest.value, date: latest.date, changeKr, changePct };
}

function renderHjemFinance() {
  const el = document.getElementById("hjem-finance");
  if (!el) return;
  const cfg = loadBudgetConfig();
  const emKey = emKeyForDate(todayISO());
  const totalBudget = cfg.categories.reduce((s, c) => s + getCategoryCap(c, emKey), 0);
  const start = emStart(emKey), end = emEnd(emKey);
  const spent = loadTransactions()
    .filter(t => t.date >= start && t.date <= end)
    .reduce((s, t) => s + t.amount, 0);
  const pct = totalBudget ? Math.min(100, Math.round(100 * spent / totalBudget)) : 0;
  const over = spent > totalBudget;

  const inv = investFundStatus();
  const changeClass = inv.changeKr == null ? "" : inv.changeKr >= 0 ? "pos" : "neg";
  const changeSign = inv.changeKr == null ? "" : inv.changeKr >= 0 ? "+" : "";
  const changeHtml = inv.changeKr != null
    ? `<span class="hjem-invest-change ${changeClass}">${changeSign}${Math.round(inv.changeKr).toLocaleString()} kr / ${changeSign}${inv.changePct.toFixed(1)}%</span>`
    : "";

  el.innerHTML = `
    <div class="hjem-finance-row">
      <div class="hf-label"><span>Brukt denne måneden</span><span>${spent.toLocaleString()} / ${totalBudget.toLocaleString()} kr</span></div>
      <div class="hjem-finance-bar"><div class="${over ? "over" : ""}" style="width:${pct}%"></div></div>
    </div>
    <div class="hjem-finance-row" id="hjem-invest-row" style="cursor:pointer;">
      <div class="hf-label"><span>Fond</span><span>${inv.date ? "Oppdatert " + fmtShort(inv.date) : "Ikke satt"}</span></div>
      <div class="hf-val">${inv.value != null ? inv.value.toLocaleString() + " kr" : "– kr"} ${changeHtml}</div>
    </div>
  `;
  document.getElementById("hjem-invest-row").addEventListener("click", () => {
    const next = prompt("Fondsverdi i dag (kr):", inv.value != null ? inv.value : "");
    if (next === null) return;
    const val = parseFloat(next.replace(",", "."));
    if (Number.isNaN(val)) return;
    setInvestFundValue(todayISO(), val);
    renderHjemFinance();
    renderFundTrend();
  });
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
  renderHjemWhy();
  renderHjemReminder();
  renderHjemSession();
  renderHjemKcalRing();
  renderHjemTodayTx();
  renderHjemBodyToday();
  renderHjemFinance();
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
      closeQuicklogDrawer();
    });
  });
  document.getElementById("ql-mat-save").addEventListener("click", () => {
    const name = document.getElementById("ql-mat-name").value.trim();
    if (!name) return;
    const kcal = parseInt(document.getElementById("ql-mat-kcal").value, 10) || null;
    addExtra(name, kcal);
    closeQuicklogDrawer();
  });
}

document.querySelectorAll("#quicklog-bar button[data-ql]").forEach(btn => {
  btn.addEventListener("click", () => {
    if (btn.dataset.ql === "hjem") showTab("hjem");
  });
});

renderHjem();
renderNutritionCoach();

// ---- Hjem live refresh: re-fetch own published page for fresh Garmin data ----
async function refreshGarminData() {
  try {
    const res = await fetch(location.href, { cache: "no-store" });
    if (!res.ok) return false;
    const html = await res.text();
    const startTag = "const DATA = ";
    const marker = "// ---------------------------------------------------------------- settings";
    const startIdx = html.indexOf(startTag);
    const endIdx = html.indexOf(marker, startIdx);
    if (startIdx === -1 || endIdx === -1) return false;
    let jsonText = html.slice(startIdx + startTag.length, endIdx).trim();
    if (jsonText.endsWith(";")) jsonText = jsonText.slice(0, -1);
    const fresh = JSON.parse(jsonText);
    DATA.topStats = fresh.topStats;
    DATA.reportMetrics = fresh.reportMetrics;
    DATA.program = fresh.program;
    DATA.trainingHistory = fresh.trainingHistory;
    return true;
  } catch (e) {
    return false;
  }
}

function refreshHjemGarminSections() {
  renderHjemSession();
  renderHjemBodyToday();
  renderHjemReminder();
}

document.getElementById("hjem-refresh-btn").addEventListener("click", async (e) => {
  const btn = e.currentTarget;
  btn.classList.add("spinning");
  await refreshGarminData();
  renderHjem();
  setTimeout(() => btn.classList.remove("spinning"), 650);
});

setInterval(() => {
  refreshGarminData().then(ok => { if (ok) refreshHjemGarminSections(); });
}, 20 * 60 * 1000);

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
  const spentToday = txToday.filter(t => !isSavingsCategory(t.category)).reduce((s, t) => s + t.amount, 0);

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

function renderWeeklyReport(targetId) {
  const out = document.getElementById(targetId || "report-output");
  if (!out) return;
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
  tx.filter(t => t.date >= weekStart && !isSavingsCategory(t.category)).forEach(t => {
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

  // cross-module: stress vs. variable spending
  const variableKeysForReport = loadBudgetConfig().categories.filter(c => c.type === "variable" && !c.savings).map(c => c.key);
  const highStressDays = history.filter(d => d.stress != null && d.stress >= 40);
  const lowStressDays = history.filter(d => d.stress != null && d.stress < 40);
  if (highStressDays.length >= 2 && lowStressDays.length >= 2) {
    const spendOn = date => tx.filter(t => t.date === date && variableKeysForReport.includes(t.category)).reduce((s, t) => s + t.amount, 0);
    const avgHigh = highStressDays.reduce((s, d) => s + spendOn(d.date), 0) / highStressDays.length;
    const avgLow = lowStressDays.reduce((s, d) => s + spendOn(d.date), 0) / lowStressDays.length;
    if (avgLow > 0 && avgHigh > avgLow * 1.15) {
      const pctMore = Math.round(100 * (avgHigh - avgLow) / avgLow);
      patterns.push(`I dager med høyt stress brukte du i snitt ${Math.round(avgHigh)} kr på variable utgifter, mot ${Math.round(avgLow)} kr i roligere dager (${pctMore}% mer).`);
    }
  }

  // cross-module: steps vs. sleep the following night
  const stepSleepDays = history.filter(d => d.steps != null && d.sleepHours != null);
  if (stepSleepDays.length >= 4) {
    const sorted = [...stepSleepDays].sort((a, b) => a.steps - b.steps);
    const lowHalf = sorted.slice(0, Math.floor(sorted.length / 2));
    const highHalf = sorted.slice(Math.ceil(sorted.length / 2));
    const avgSleepLow = lowHalf.reduce((s, d) => s + d.sleepHours, 0) / lowHalf.length;
    const avgSleepHigh = highHalf.reduce((s, d) => s + d.sleepHours, 0) / highHalf.length;
    const sleepDiff = avgSleepHigh - avgSleepLow;
    if (Math.abs(sleepDiff) >= 0.4) {
      patterns.push(sleepDiff > 0
        ? `Du sover bedre i ukedager med mange skritt - i snitt ${sleepDiff.toFixed(1)} t mer søvn enn på de rolige dagene.`
        : `Dagene med flest skritt ga faktisk ${Math.abs(sleepDiff).toFixed(1)} t mindre søvn - følg med på at aktive dager ikke går på bekostning av søvnen.`);
    }
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

// ---------------------------------------------------------------- fremgang (long-term trends/goals)
document.querySelectorAll("#body-period-tabs .period-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#body-period-tabs .period-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    bodyChartPeriodMonths = parseInt(btn.dataset.period, 10);
    renderBodyGoalChart();
  });
});
document.querySelectorAll("#body-measure-tabs .measure-select-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#body-measure-tabs .measure-select-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    bodyChartMeasure = btn.dataset.measure;
    renderBodyGoalChart();
  });
});

document.getElementById("fund-log-date").value = todayISO();
document.getElementById("fund-log-add").addEventListener("click", () => {
  const date = document.getElementById("fund-log-date").value || todayISO();
  const contributedRaw = document.getElementById("fund-log-contributed").value;
  const value = parseFloat(document.getElementById("fund-log-value").value);
  if (Number.isNaN(value)) return;
  if (contributedRaw.trim() === "") {
    setInvestFundValue(date, value);
  } else {
    setInvestFundEntry(date, value, parseFloat(contributedRaw));
  }
  document.getElementById("fund-log-contributed").value = "";
  document.getElementById("fund-log-value").value = "";
  renderFundTrend();
  renderHjemFinance();
});

renderWeightGoalInput();
renderBodyGoalChart();
renderCalorieCalibration();
renderActivityTrends();
renderExpenseTrends();
renderSavingsGoals();
renderFundTrend();
renderWeeklyReport("fremgang-weekly-report");

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
  SETTINGS_KEY, WHY_KEY, VACATION_KEY, CUSTOM_MEALS_KEY, MEAL_LOG_KEY, INVEST_FUND_KEY,
  SAVINGS_GOALS_KEY, CUSTOM_INGREDIENTS_KEY, MEAL_ING_OVERRIDES_KEY, MISSED_DAY_ACK_KEY,
];
window.BACKUP_KEYS = BACKUP_KEYS;

document.getElementById("sync-now-btn").addEventListener("click", () => {
  if (!window.__cloudAuth) { setSyncStatus("Skylagring er ikke klar ennå - prøv igjen om et øyeblikk."); return; }
  setSyncStatus("Synkroniserer...");
  window.__cloudAuth.pullNow();
});
document.getElementById("sync-logout-btn").addEventListener("click", () => {
  if (!window.__cloudAuth) return;
  window.__cloudAuth.signOut();
});

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
</script>

<script type="module">
  // Firebase needs its own module scope for these imports, so this talks to the classic
  // script above through window.__cloudAuth (calls into here) and window.__onAuthStateChanged /
  // window.__cloudSyncStatus (calls back out) rather than sharing scope directly. This script
  // is deferred (all type="module" scripts are), so the classic script above has always
  // already finished setting up those callbacks by the time any of this runs.
  import { initializeApp } from "https://www.gstatic.com/firebasejs/13.3.0/firebase-app.js";
  import {
    getAuth, onAuthStateChanged, signInWithEmailAndPassword, signOut,
    setPersistence, browserLocalPersistence,
  } from "https://www.gstatic.com/firebasejs/13.3.0/firebase-auth.js";
  import {
    getFirestore, doc, getDoc, setDoc,
  } from "https://www.gstatic.com/firebasejs/13.3.0/firebase-firestore.js";

  const firebaseConfig = {
    apiKey: "AIzaSyBPzs9R-3fq0yJy9GMGXQS5myayKhJNhNo",
    authDomain: "katrine-2027-dashboard.firebaseapp.com",
    projectId: "katrine-2027-dashboard",
    storageBucket: "katrine-2027-dashboard.firebasestorage.app",
    messagingSenderId: "208857107478",
    appId: "1:208857107478:web:d6318f950a993f577a7937",
  };
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  let currentUser = null;
  let lastSyncedAt = 0;
  let pushTimer = null;

  // persisted across page loads (per uid) - without this, every fresh page load would see
  // remote.updatedAt > 0 and think the cloud always has something newer, reloading forever.
  function syncMarkerKey(uid) { return "garminDashboardCloudSyncedAt_" + uid; }
  function loadLastSyncedAt(uid) { return parseInt(localStorage.getItem(syncMarkerKey(uid)) || "0", 10); }
  function saveLastSyncedAt(uid, ts) { localStorage.setItem(syncMarkerKey(uid), String(ts)); }

  function fmtTime(ms) {
    return new Date(ms).toLocaleTimeString("no-NO", { hour: "2-digit", minute: "2-digit" });
  }
  function dumpBackupData() {
    const dump = {};
    (window.BACKUP_KEYS || []).forEach(k => {
      const v = localStorage.getItem(k);
      if (v === null) return;
      try { dump[k] = JSON.parse(v); } catch (e) { /* skip unparsable value */ }
    });
    return dump;
  }
  function applyBackupData(data) {
    (window.BACKUP_KEYS || []).forEach(k => {
      if (data[k] !== undefined) localStorage.setItem(k, JSON.stringify(data[k]));
    });
  }

  async function cloudPush() {
    if (!currentUser) return;
    const now = Date.now();
    try {
      await setDoc(doc(db, "users", currentUser.uid), { updatedAt: now, data: dumpBackupData() });
      lastSyncedAt = now;
      saveLastSyncedAt(currentUser.uid, now);
      window.__cloudSyncStatus(`Synkronisert kl ${fmtTime(now)}`);
    } catch (e) {
      window.__cloudSyncStatus("Kunne ikke synke til skyen - sjekk internettforbindelsen");
    }
  }
  function schedulePush() {
    if (!currentUser) return;
    clearTimeout(pushTimer);
    pushTimer = setTimeout(cloudPush, 3000);
  }
  async function pullIfNewer() {
    if (!currentUser) return;
    try {
      const snap = await getDoc(doc(db, "users", currentUser.uid));
      if (!snap.exists()) { await cloudPush(); return; }
      const remote = snap.data();
      if (remote.updatedAt > lastSyncedAt) {
        applyBackupData(remote.data || {});
        lastSyncedAt = remote.updatedAt;
        saveLastSyncedAt(currentUser.uid, remote.updatedAt);
        window.__cloudSyncStatus(`Hentet nyere data fra skyen kl ${fmtTime(remote.updatedAt)} - laster siden på nytt...`);
        setTimeout(() => location.reload(), 1200);
      } else {
        window.__cloudSyncStatus(`Oppdatert - sist synket kl ${fmtTime(lastSyncedAt)}`);
      }
    } catch (e) {
      window.__cloudSyncStatus("Kunne ikke hente fra skyen - sjekk internettforbindelsen");
    }
  }

  window.__cloudAuth = {
    signIn: (email, password) => signInWithEmailAndPassword(auth, email, password),
    signOut: () => signOut(auth),
    schedulePush,
    pullNow: pullIfNewer,
  };

  setPersistence(auth, browserLocalPersistence).catch(() => {});
  onAuthStateChanged(auth, user => {
    currentUser = user;
    lastSyncedAt = user ? loadLastSyncedAt(user.uid) : 0;
    window.__onAuthStateChanged(user);
  });
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
