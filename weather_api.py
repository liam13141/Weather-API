from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests, datetime, math, os

API_KEY = os.getenv("OPENWEATHER_API_KEY")
AUTH_CODE = os.getenv("AUTH_CODE")

app = FastAPI(title="WeatherStyle PRO Ultra++ API (Auto-Radar)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------
# TILE MATH FOR RAINVIEWER RADAR
# -----------------------------------------
def latlon_to_tile(lat, lon, zoom=6):
    """Convert lat/lon to tile X/Y for radar."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

# -----------------------------------------
# SAFE REQUEST
# -----------------------------------------
def safe(url):
    try:
        return requests.get(url, timeout=4).json()
    except:
        return {}

# -----------------------------------------
# AQI LABELS
# -----------------------------------------
AQI_LABELS = {
    1: "Good",
    2: "Fair",
    3: "Moderate",
    4: "Poor",
    5: "Very Poor",
}

# -----------------------------------------
# UV ESTIMATION
# -----------------------------------------
def estimate_uv(temp_c, clouds_percent):
    """Rough UV estimation based on temperature + cloud cover."""
    uv = (temp_c / 7) * (1 - clouds_percent / 100)
    return max(0, round(uv, 1))

# -----------------------------------------
# FIRE DANGER
# -----------------------------------------
def fire_danger(temp, humidity, wind):
    score = temp * 0.4 + wind * 0.3 - humidity * 0.2
    if score < 10: return "Low"
    if score < 20: return "Moderate"
    if score < 35: return "High"
    return "Extreme"

# -----------------------------------------
# HEAT RISK
# -----------------------------------------
def heat_risk(temp):
    if temp >= 40: return "Extreme"
    if temp >= 35: return "Danger"
    if temp >= 30: return "High"
    return "Low"

# -----------------------------------------
# RAINVIEWER RADAR
# -----------------------------------------
def radar_for_location(lat, lon):
    rain = safe("https://api.rainviewer.com/public/weather-maps.json")

    if "radar" not in rain:
        return {"tiles": []}

    xtile, ytile = latlon_to_tile(lat, lon, zoom=6)

    frames = []
    for frame in rain["radar"]["past"]:
        ts = frame["path"]
        url = (
            f"https://tilecache.rainviewer.com/v2/radar/{ts}/256/6/{xtile}/{ytile}/2/1_1.png"
        )
        frames.append(url)

    return {"tiles": frames}

# -----------------------------------------
# FORECAST FORMATTER
# -----------------------------------------
def build_forecast(raw):
    days = {}
    for entry in raw.get("list", []):
        dt = datetime.datetime.fromtimestamp(entry["dt"])
        day = dt.strftime("%a")

        temp_min = entry["main"]["temp_min"]
        temp_max = entry["main"]["temp_max"]
        wmain = entry["weather"][0]["main"]

        if day not in days:
            days[day] = {"min": temp_min, "max": temp_max, "main": wmain}
        else:
            days[day]["min"] = min(days[day]["min"], temp_min)
            days[day]["max"] = max(days[day]["max"], temp_max)

    return days

# -----------------------------------------
# MAIN WEATHER ENDPOINT
# -----------------------------------------
@app.get("/weather")
def weather(city: str, authorization: str = None):

    if authorization != AUTH_CODE:
        raise HTTPException(403, "Unauthorized")

    # ------------------------ CURRENT WEATHER ------------------------
    cur = safe(
        f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    )

    if "weather" not in cur:
        raise HTTPException(404, f"City '{city}' not found")

    lat = cur["coord"]["lat"]
    lon = cur["coord"]["lon"]

    main = cur["weather"][0]["main"]
    desc = cur["weather"][0]["description"].title()
    temp = cur["main"]["temp"]
    humidity = cur["main"]["humidity"]
    wind_kmh = round(cur["wind"]["speed"] * 3.6, 1)
    clouds = cur["clouds"]["all"]

    # ------------------------ FORECAST ------------------------
    raw_fc = safe(
        f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    )
    forecast = build_forecast(raw_fc)

    # ------------------------ AQI ------------------------
    aqi_raw = safe(
        f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    )
    try:
        aqi = aqi_raw["list"][0]["main"]["aqi"]
    except:
        aqi = 1

    # ------------------------ UV ESTIMATED ------------------------
    uv = estimate_uv(temp, clouds)

    # ------------------------ RADAR ------------------------
    radar = radar_for_location(lat, lon)

    # ------------------------ HURRICANES ------------------------
    hurricanes = safe("https://www.nhc.noaa.gov/CurrentStorms.json")
    storms = hurricanes if isinstance(hurricanes, list) else []

    # ------------------------ RETURN ------------------------
    return {
        "city": cur["name"],
        "main": main,
        "description": desc,
        "temperature_c": temp,
        "humidity": humidity,
        "wind_kmh": wind_kmh,

        # Essentials
        "aqi": aqi,
        "aqi_label": AQI_LABELS.get(aqi, "Unknown"),
        "uv_index": uv,
        "uv_advice": "Apply sunscreen" if uv > 3 else "Low risk",

        # Safety
        "fire_danger": fire_danger(temp, humidity, wind_kmh),
        "heatstroke_risk": heat_risk(temp),
        "frostbite_time": "No risk" if temp > -10 else "Possible",

        # Extras
        "music_vibes": ["Chill", "Storm vibes", "Phonk", "Ambient"],
        "travel": "Safe" if main == "Clear" else "Caution",
        "activity_suggestions": ["Walk", "Gym", "Gaming", "Relax"],

        # Forecast
        "forecast": forecast,

        # Radar
        "radar_tiles": radar,

        # Hurricanes
        "hurricanes": {
            "activeStorms": storms
        }
    }
