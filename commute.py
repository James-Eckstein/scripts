#!/usr/bin/env python3
import sys
import os
import json
import datetime
import urllib.parse
import urllib.request

NTFY_TOPIC = "bournemouth_salisbury_commute"

LOCATIONS = {
    "home": {
        "name": "2 The Mews, Upper Norwich Road, Bournemouth, BH2 5RA",
        "query": "Upper Norwich Road, Bournemouth, BH2 5RA",
        "lat": 50.7208,
        "lon": -1.8795
    },
    "work": {
        "name": "Naim Audio (Salisbury)",
        "query": "Naim Audio Ltd, Southampton Road, Salisbury, SP1 2LN",
        "lat": 51.0667,
        "lon": -1.7820
    }
}

def fetch_osrm_duration(origin, dest):
    try:
        key = open(os.path.expanduser("~/.tomtom_key")).read().strip()
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin['lat']},{origin['lon']}:{dest['lat']},{dest['lon']}/json?key={key}&traffic=true&travelMode=car&departAt=now"
        req = urllib.request.Request(url, headers={'User-Agent': 'commute-script'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            summ = json.loads(resp.read().decode())["routes"][0]["summary"]
            return int(summ["travelTimeInSeconds"] / 60), round(summ["lengthInMeters"] * 0.000621371, 1)
    except Exception as e:
        print(f"[TOMTOM] {e} - falling back to OSRM")
    url = f"https://router.project-osrm.org/route/v1/driving/{origin['lon']},{origin['lat']};{dest['lon']},{dest['lat']}?overview=false"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("code") == "Ok":
                mins = int(data["routes"][0]["duration"] / 60)
                dist = round(data["routes"][0]["distance"] * 0.000621371, 1)
                return mins, dist
    except Exception:
        pass
    return None, None

def send_commute_notification(direction="auto"):
    now = datetime.datetime.now()
    current_time_str = now.strftime('%H:%M')
    stamp = now.strftime('%Y-%m-%d %H:%M')

    if direction == "auto":
        direction = "work" if now.hour < 12 else "home"

    if direction == "work":
        origin, dest = LOCATIONS["home"], LOCATIONS["work"]
        target_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        base_mins, dist = fetch_osrm_duration(origin, dest)
        if base_mins is None:
            print(f"{stamp} [ERROR] Could not fetch route duration.")
            return
        total_duration = base_mins + 10
        leave_time = target_time - datetime.timedelta(minutes=total_duration + 5)
        leave_arrival = leave_time + datetime.timedelta(minutes=total_duration)
        est_arrival = now + datetime.timedelta(minutes=total_duration)

        title = f"Morning Commute: ~{total_duration}m to Naim"
        body = (
            f"Sent at {current_time_str} | Drive: ~{total_duration}m ({dist} mi)\n"
            f"Leave by {leave_time.strftime('%H:%M')} -> arrive {leave_arrival.strftime('%H:%M')} (Target: 09:15)\n"
            f"If you leave now -> arrive {est_arrival.strftime('%H:%M')}\n"
            f"To: {dest['name']}"
        )
        tags = ["car", "traffic_light"]
    else:
        origin, dest = LOCATIONS["work"], LOCATIONS["home"]
        base_mins, dist = fetch_osrm_duration(origin, dest)
        if base_mins is None:
            print(f"{stamp} [ERROR] Could not fetch route duration.")
            return
        total_duration = base_mins + 12
        est_arrival = now + datetime.timedelta(minutes=total_duration)

        title = f"Homeward Commute: ~{total_duration}m to Bournemouth"
        body = (
            f"Sent at {current_time_str} | Drive: ~{total_duration}m ({dist} mi)\n"
            f"ETA: {est_arrival.strftime('%H:%M')} (Depart: {current_time_str})\n"
            f"To: {dest['name']}"
        )
        tags = ["house", "car"]

    origin_param = f"{origin['lat']},{origin['lon']}"
    dest_param = urllib.parse.quote(dest["query"])
    maps_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_param}&destination={dest_param}&travelmode=driving"

    payload = {
        "topic": NTFY_TOPIC,
        "title": title,
        "message": body,
        "priority": 4,
        "tags": tags,
        "click": maps_url,
        "actions": [
            {
                "action": "view",
                "label": "Navigate",
                "url": maps_url,
                "clear": True
            }
        ]
    }

    try:
        req = urllib.request.Request(
            "https://ntfy.sh",
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                print(f"{stamp} [{direction.upper()}] Push delivered ({origin['name'].split(',')[0]} -> {dest['name'].split(',')[0]})")
            else:
                print(f"{stamp} [NTFY] Status code: {resp.status}")
    except Exception as e:
        print(f"{stamp} [NTFY] Error: {e}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    send_commute_notification(mode)
