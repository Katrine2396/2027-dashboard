"""
Sends Web Push notifications based on data already pulled into data/daily_summaries.json.
Runs after pull.py in the GitHub Actions workflow, every ~30 min. Needs:
  - the `pywebpush` package (installed by the workflow, not required for local dev)
  - two repo secrets: VAPID_PRIVATE_KEY (PEM) and PUSH_SUBSCRIPTION (JSON, copied from
    the dashboard's Innstillinger tab after enabling varsler on the phone)
If those secrets aren't set yet, this script does nothing (no error).
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

OSLO = ZoneInfo("Europe/Oslo")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STATE_PATH = os.path.join(DATA_DIR, "notification_state.json")
DAILY_SUMMARIES_PATH = os.path.join(DATA_DIR, "daily_summaries.json")

# Required by the Web Push protocol to identify the sender to push services
# (Apple/Google/Mozilla) - not shown to the user, doesn't need to be a real inbox.
VAPID_CLAIMS = {"sub": "mailto:dashboard-push@example.com"}


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(state, now):
    pruned = {
        k: v for k, v in state.items()
        if (now - datetime.strptime(k, "%Y-%m-%d").replace(tzinfo=OSLO)).days <= 2
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(pruned, f)


def send(title, body):
    from pywebpush import webpush, WebPushException

    subscription = json.loads(os.environ["PUSH_SUBSCRIPTION"])
    private_key = os.environ["VAPID_PRIVATE_KEY"]
    payload = json.dumps({"title": title, "body": body, "url": "./dashboard.html"})
    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=private_key,
            vapid_claims=dict(VAPID_CLAIMS),
        )
        print(f"Sent: {title}")
    except WebPushException as e:
        print(f"Push failed ({title}): {e}")


def steps_today():
    if not os.path.exists(DAILY_SUMMARIES_PATH):
        return None
    with open(DAILY_SUMMARIES_PATH) as f:
        data = json.load(f)
    today_key = datetime.now(OSLO).strftime("%Y-%m-%d")
    day = data.get(today_key)
    if not day:
        return None
    steps = day.get("movement", {}).get("steps", {})
    value = steps.get("value")
    goal = steps.get("goal") or 8000
    if value is None:
        return None
    return value, goal


def main():
    if "PUSH_SUBSCRIPTION" not in os.environ or "VAPID_PRIVATE_KEY" not in os.environ:
        print("Push notifications not set up yet (secrets missing) - skipping.")
        return

    if os.environ.get("TEST_NOTIFICATION") == "true":
        send("Testvarsel", "Varsler fungerer! \U0001F389")
        return

    now = datetime.now(OSLO)
    today_key = now.strftime("%Y-%m-%d")
    state = load_state()
    sent_today = state.get(today_key, [])

    def already_sent(kind):
        return kind in sent_today

    def mark_sent(kind):
        sent_today.append(kind)
        state[today_key] = sent_today

    # Steps pace - once a day, early-mid afternoon, only if clearly behind the
    # expected pace for a 07:00-22:00 waking window.
    if now.hour in (13, 14) and not already_sent("steps_pace"):
        result = steps_today()
        if result:
            value, goal = result
            elapsed_frac = min(1.0, max(0.0, (now.hour + now.minute / 60 - 7) / 15))
            expected = goal * elapsed_frac
            if value < expected - 1500:
                gap = int(expected - value)
                send(
                    "Skritt-tempo",
                    f"Du ligger ca. {gap} skritt bak tempoet for å nå {goal} i dag. Fortsatt tid igjen!",
                )
            mark_sent("steps_pace")

    # Lifesum reminder.
    if now.hour == 20 and not already_sent("lifesum_reminder"):
        send(
            "Husk å føre inn Lifesum-tallene",
            "Legg inn dagens kalorier, protein, fett og karbohydrater i Kosthold.",
        )
        mark_sent("lifesum_reminder")

    # Evening report ready, a bit later.
    if now.hour == 21 and not already_sent("evening_report"):
        send("Kveldsrapporten er klar", "Se hvordan dagen gikk og hva som venter i morgen.")
        mark_sent("evening_report")

    # Sunday planning, Sundays only.
    if now.weekday() == 6 and now.hour == 16 and not already_sent("sunday_planning"):
        send("Søndagsplanlegging", "Tid for å planlegge neste ukes måltider og mealprep.")
        mark_sent("sunday_planning")

    save_state(state, now)


if __name__ == "__main__":
    main()
