#!/usr/bin/env python3

import os
print("Current working dir:",os.getcwd())
print("LIsting fonts dir:",os.listdir("/home/jacks/rpi-rgb-led-matrix/fonts"))

#!/usr/bin/env python3
import requests
import math
import time
from datetime import datetime
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

# Your location (Denver area example)
MY_LAT = 39.755689061134724
MY_LON = -104.99042412407124

# API URL for bounding box (around your area)
URL = "https://data-cloud.flightradar24.com/zones/fcgi/feed.js?bounds=39.87,39.69,-105.11,-104.8"

# Setup matrix options
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'adafruit-hat'  # adjust if you have different hardware

matrix = RGBMatrix(options=options)
canvas = matrix.CreateFrameCanvas()

# Load font — update path if needed
font = graphics.Font()
font.LoadFont("/usr/local/share/fonts/rgbmatrix/7x13.bdf")
textColor = graphics.Color(0, 255, 0)  # green text

# Helper functions
def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.cos(lat2) * math.sin(dlon)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360

def direction_arrow(bearing):
    arrows = ["↑N", "↗NE", "→E", "↘SE", "↓S", "↙SW", "←W", "↖NW"]
    return arrows[round(bearing / 45) % 8]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * 0.621371 * c  # miles

def infer_airline(callsign):
    callsign_map = {
        "SWA": "Southwest",
        "UA": "United",
        "AAL": "American",
        "DAL": "Delta",
        "FFT": "Frontier",
        "NKS": "Spirit",
        "JBU": "JetBlue",
        "ACA": "Air Canada",
        "AC": "Air Canada",
        "SKW": "SkyWest",
        "UAL": "United"
    }
    if not isinstance(callsign, str):
        return "Unknown"
    return next((name for prefix, name in callsign_map.items() if callsign.startswith(prefix)), "Unknown")

def fetch_and_parse_aircraft():
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching data...")
        res = requests.get(URL, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://www.flightradar24.com/",
            "Origin": "https://www.flightradar24.com"
        })
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"Fetch error: {e}")
        return []

    aircraft_list = []
    for key, val in data.items():
        if key in ["full_count", "version"]:
            continue
        try:
            lat, lon = float(val[1]), float(val[2])
            # Filter by bounding box (adjust to your area)
            if not (39.69 <= lat <= 39.96 and -105.11 <= lon <= -104.58):
                continue
            # Only include aircraft with known destination
            destination = val[13] if len(val) > 13 else None
            if not destination or destination == "Unknown":
                continue
            aircraft = {
                "hex": val[0],
                "lat": lat,
                "lon": lon,
                "alt": val[4],
                "speed": val[5],
                "track": val[3] if len(val) > 3 else None,
                "aircraft_type": val[8] if len(val) > 8 else "Unknown",
                "registration": val[9] if len(val) > 9 else "Unknown",
                "origin": val[11] if len(val) > 11 else "Unknown",
                "destination": val[12] if len(val) > 12 else "Unknown",
                "flight_number": val[13] if len(val) > 13 else "Unknown",
            }
            aircraft_list.append(aircraft)
        except (IndexError, ValueError):
            continue
    return aircraft_list

def main():
    global canvas
    while True:
        aircraft_list = fetch_and_parse_aircraft()
        canvas.Clear()

        if not aircraft_list:
            graphics.DrawText(canvas, font, 1, 10, textColor, "No aircraft nearby")
        else:
            # Just show the first aircraft only
            aircraft = aircraft_list[0]

            dist = haversine(MY_LAT, MY_LON, aircraft["lat"], aircraft["lon"])
            bearing = calculate_bearing(MY_LAT, MY_LON, aircraft["lat"], aircraft["lon"])
            airline = infer_airline(aircraft["flight_number"])

            y = 10  # start y position

            # Display lines of info for the plane
            graphics.DrawText(canvas, font, 1, y, textColor, f"{airline} {aircraft['flight_number']}")
            y += 15
            graphics.DrawText(canvas, font, 1, y, textColor, f"From: {aircraft['origin']}")
            y += 15
            graphics.DrawText(canvas, font, 1, y, textColor, f"To: {aircraft['destination']}")
            y += 15
            graphics.DrawText(canvas, font, 1, y, textColor, f"Dist: {int(dist)} mi {direction_arrow(bearing)}")
            y += 15
            graphics.DrawText(canvas, font, 1, y, textColor, f"Alt: {aircraft['alt']} ft  Speed: {aircraft['speed']} knots")

        # Swap canvas for display refresh
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(30)  # update every 10 seconds

if __name__ == "__main__":
    main()

