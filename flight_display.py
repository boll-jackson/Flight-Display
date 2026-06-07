#!/usr/bin/env python3
import os
import urllib.request, json
print("Current working dir:",os.getcwd())
print("LIsting fonts dir:",os.listdir("/home/jacks/rpi-rgb-led-matrix/fonts"))

#!/usr/bin/env python3
import requests
import math
import time
from datetime import datetime
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from PIL import Image

# Your location (Denver area example)
MY_LAT = 39.755689061134724
MY_LON = -104.99042412407124

# API URL for bounding box (around your area)
URL = "https://data-cloud.flightradar24.com/zones/fcgi/feed.js?bounds=39.87,39.69,-105.11,-104.8"
LOGO_DIR = "/home/jacks/rpi-rgb-led-matrix/bindings/python/samples/flight-display/airline_logos_tool/airline_logos"
print(f"[{datetime.now():%H:%M:%S}] LOGO_DIR = {LOGO_DIR}")

CYCLE_INTERVAL = 5    # seconds per plane when multiple are present
FETCH_INTERVAL = 30   # seconds before re-fetching from the API


# Setup matrix options
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 2
options.multiplexing=0
options.parallel = 1
options.hardware_mapping = 'adafruit-hat'  # adjust if you have different hardware
options.row_address_type = 0
options.pwm_bits = 11
options.pwm_lsb_nanoseconds = 130
options.pixel_mapper_config = ""
options.show_refresh_rate = 0
options.disable_hardware_pulsing = True

matrix = RGBMatrix(options=options)
canvas = matrix.CreateFrameCanvas()

# Load font — update path if needed
font = graphics.Font()
font.LoadFont("/usr/local/share/fonts/rgbmatrix/7x13.bdf")
textColor = graphics.Color(255, 255, 255)  # green text

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
        "DL": "Delta",
        "FFT": "Frontier",
        "NKS": "Spirit",
        "JBU": "JetBlue",
        "ACA": "Air Canada",
        "AC": "Air Canada",
        "SKW": "SkyWest",
        "UAL": "United",
        "WN": "Southwest",
        "AA": "American",
        "F9": "Frontier",
        "BA": "British",
        "B6": "Jetblue"
    }
    if not isinstance(callsign, str):
        return "Unknown"
    return next((name for prefix, name in callsign_map.items() if callsign.startswith(prefix)), "Unknown")


def load_logo(iata_code):
    """
    Return a 32×32 PIL Image for the given IATA code.
    If missing → solid black square fallback.
    """
    path = os.path.join(LOGO_DIR, f"{iata_code.upper()}.bmp")
    if os.path.isfile(path):
        try:
            img = Image.open(path).convert("RGB")
            return img.resize((32, 32), Image.LANCZOS)
        except Exception as ed:
            print(f"Warning: Could not load {path}: {ed}")
    fallback = Image.new("RGB", (32, 32), (0, 0, 0))
    return fallback


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
            if not (39.69 <= lat <= 39.96 and -105.11 <= lon <= -104.58):
                continue
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

def fetch_weather():
    try:
        url = "https://wttr.in/Denver?format=j1"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        current = data["current_condition"][0]
        temp_f = current["temp_F"]
        desc = current["weatherDesc"][0]["value"]
        humidity = current["humidity"]
        feels = current["FeelsLikeF"]
        return temp_f, desc, humidity, feels
    except Exception as e:
        print(f"Weather fetch error: {e}")
        return None, None, None, None

def draw_aircraft(offscreen_canvas, aircraft, index, total):
    """Draw a single aircraft's info onto the canvas."""
    altitude = aircraft["alt"]
    speed = aircraft["speed"]
    dist = haversine(MY_LAT, MY_LON, aircraft["lat"], aircraft["lon"])
    bearing = calculate_bearing(MY_LAT, MY_LON, aircraft["lat"], aircraft["lon"])
    airline = infer_airline(aircraft["flight_number"])

    flight_num = aircraft["flight_number"]
    iata = "".join([c for c in flight_num if c.isalpha()])[:2].upper()
    if len(iata) != 2:
        iata = "XX"

    logo_img = load_logo(iata)

    # Draw logo (top-right panel)
    for y in range(32):
        for x in range(32):
            r, g, b = logo_img.getpixel((x, y))
            offscreen_canvas.SetPixel(96 + x, y, r, g, b)

    origin = aircraft["origin"]
    destination = aircraft["destination"]
    plane_type = aircraft["aircraft_type"]

    # Counter badge e.g. "1/3" shown before flight number
    counter = f"{index + 1}/{total}"

    graphics.DrawText(offscreen_canvas, font, 1, 10, textColor, f"{counter} {flight_num}")
    graphics.DrawText(offscreen_canvas, font, 1, 20, textColor, f"{origin}-{destination}")
    graphics.DrawText(offscreen_canvas, font, 1, 30, textColor, f"To:")
    graphics.DrawText(offscreen_canvas, font, 1, 40, textColor, f"{airline} {plane_type}")
    graphics.DrawText(offscreen_canvas, font, 1, 50, textColor, f"{dist:.1f} mi {direction_arrow(bearing)}")
    graphics.DrawText(offscreen_canvas, font, 1, 60, textColor, f"Alt:{altitude} Spd:{speed}")

def main():
    offscreen_canvas = matrix.CreateFrameCanvas()

    aircraft_list = []
    last_fetch = 0       # force immediate fetch on first iteration
    plane_index = 0      # which plane we're currently showing

    while True:
        try:
            now = time.time()

            # Re-fetch from API on first run and every FETCH_INTERVAL seconds
            if now - last_fetch >= FETCH_INTERVAL:
                aircraft_list = fetch_and_parse_aircraft()
                last_fetch = time.time()
                plane_index = 0  # reset to first plane after a fresh fetch

            offscreen_canvas.Clear()

            if not aircraft_list:
                temp_f, desc, humidity, feels = fetch_weather()
                if temp_f:
                    graphics.DrawText(offscreen_canvas, font, 1, 10, textColor, "Denver, CO")
                    graphics.DrawText(offscreen_canvas, font, 1, 20, textColor, f"{temp_f}F  {desc}")
                    graphics.DrawText(offscreen_canvas, font, 1, 30, textColor, f"Feels: {feels}F")
                    graphics.DrawText(offscreen_canvas, font, 1, 40, textColor, f"Humidity: {humidity}%")
                    graphics.DrawText(offscreen_canvas, font, 1, 50, textColor, "No planes nearby")
                else:
                    graphics.DrawText(offscreen_canvas, font, 1, 10, textColor, "No planes")
                    graphics.DrawText(offscreen_canvas, font, 1, 20, textColor, "No weather")
                    graphics.DrawText(offscreen_canvas, font, 1, 30, textColor, "¯\_(ツ)_/¯")

                offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)
                time.sleep(CYCLE_INTERVAL)

            else:
                total = len(aircraft_list)
                # Clamp index in case list shrank after a re-fetch
                plane_index = plane_index % total

                draw_aircraft(offscreen_canvas, aircraft_list[plane_index], plane_index, total)
                offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)

                # Advance to next plane
                plane_index = (plane_index + 1) % total
                time.sleep(CYCLE_INTERVAL)

        except Exception as ef:
            print(f"ERROR: {ef} – restarting in 10 sec...")
            time.sleep(10)
            continue

if __name__ == "__main__":
    main()

