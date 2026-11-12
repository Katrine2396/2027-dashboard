"""One-off script to confirm the Garmin Personal API connection works."""
from garmin_client import api_get

print("Requesting a token and fetching your 5 latest activities...\n")

result = api_get("/activitylist-service/activities/search/activities", {"start": 0, "limit": 5})

if not result:
    print("No activities found.")
else:
    print(f"{'Date':<12} {'Type':<16} {'Distance':>10}")
    print("-" * 40)
    for a in result:
        date = (a.get("startTimeLocal") or "")[:10]
        atype = (a.get("activityType") or {}).get("typeKey", "?")
        dist_m = a.get("distance") or 0
        dist_km = dist_m / 1000
        print(f"{date:<12} {atype:<16} {dist_km:>8.2f} km")

print("\nConnection works.")
