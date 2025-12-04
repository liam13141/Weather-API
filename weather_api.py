from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests, datetime, os, math

API_KEY = os.getenv("OPENWEATHER_API_KEY")
AUTH_CODE = os.getenv("AUTH_CODE")

app = FastAPI(
    title="WeatherStyle PRO GOD MODE API 🌎⚡",
    description="Ultra-expanded weather API with full compatibility for WeatherStyle Pro Ultra++ HTML"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ICON_MAP = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧️",
    "Drizzle": "🌦️",
    "Thunderstorm": "⛈️",
    "Snow": "❄️",
    "Mist": "🌫️",
    "Fog": "🌫️",
    "Haze": "🌫️",
}

# --------------------------
# Helper functions
# --------------------------
def uv_advice(uv):
    if uv < 3: return "Low risk"
    if uv < 6: return "Moderate — sunscreen advised"
    if uv < 8: return "High — reduce exposure"
    if uv < 11: return "Very high — seek shade"
    return "Extreme — avoid sun"

def frostbite_time(temp_c, wind_kmh):
    wind_ms = wind_kmh / 3.6
    chill = 13.12 + 0.6215 * temp_c - 11.37 * (wind_ms**0.16) + 0.3965 * temp_c * (wind_ms**0.16)
    if chill > -10: return "No frostbite risk"
    if chill > -20: return "Risk in 30+ minutes"
    if chill > -28: return "Risk in 10–30 minutes"
    return "Severe risk < 10 min"

def heatstroke_risk(temp, humidity):
    if temp >= 40: return "Extreme"
    if temp >= 34: return "Danger"
    if temp >= 30: return "High risk"
    return "Low"

def fire_danger(temp, humidity, wind):
    score = temp * 0.4 + wind * 0.3 - humidity * 0.2
    if score < 10: return "Low"
    if score < 20: return "Moderate"
    if score < 35: return "High"
    return "Extreme"

def radar_frames():
    info = requests.get("https://api.rainviewer.com/public/weather-maps.json").json()
    frames = []
    for f in info["radar"]["past"]:
        frames.append(f"https://tilecache.rainviewer.com/v2/radar/{f['path']}/256/6/33/21/2/1_1.png")
    return frames

def build_forecast(raw):
    days = {}
    for entry in raw["list"]:
        dt = datetime.datetime.fromtimestamp(entry["dt"])
        day = dt.strftime("%a")
        temp_min = entry["main"]["temp_min"]
        temp_max = entry["main"]["temp_max"]
        main = entry["weather"][0]["main"]

        if day not in days:
            days[day] = {"min": temp_min, "max": temp_max, "main": main}
        else:
            days[day]["min"] = min(days[day]["min"], temp_min)
            days[day]["max"] = max(days[day]["max"], temp_max)

    return days

def hurricanes_data():
    try:
        res = requests.get("https://www.nhc.noaa.gov/CurrentStorms.json").json()
        return {"activeStorms": res}
    except:
        return {"activeStorms": []}

# --------------------------
# MAIN
# --------------------------
@app.get("/weather")
def weather(city: str, authorization: str = None):

    if authorization != AUTH_CODE:
        raise HTTPException(403, "Unauthorized")

    # Core weather
    cur = requests.get(
        f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    )
    if cur.status_code != 200:
        raise HTTPException(404, "City not found")
    data = cur.json()

    lat, lon = data["coord"]["lat"], data["coord"]["lon"]

    # 5-day forecast
    fore_raw = requests.get(
        f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    ).json()

    # AQI
    aqi_raw = requests.get(
        f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    ).json()
    aqi = aqi_raw["list"][0]["main"]["aqi"]

    # UV
    uv_raw = requests.get(
        f"https://api.openweathermap.org/data/2.5/uvi?lat={lat}&lon={lon}&appid={API_KEY}"
    ).json()
    uv = uv_raw.get("value", 0)

    # Radar
    radar = radar_frames()

    # Hurricanes
    storms = hurricanes_data()

    # Build forecast
    forecast = build_forecast(fore_raw)

    return {
        "city": data["name"],
        "main": data["weather"][0]["main"],
        "description": data["weather"][0]["description"].title(),
        "temperature_c": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "wind_kmh": round(data["wind"]["speed"] * 3.6, 1),

        "aqi": aqi,
        "aqi_label": ["Good","Fair","Moderate","Poor","Very Poor"][aqi-1],

        "uv_index": uv,
        "uv_advice": uv_advice(uv),

        "frostbite_time": frostbite_time(data["main"]["temp"], round(data["wind"]["speed"] * 3.6, 1)),
        "heatstroke_risk": heatstroke_risk(data["main"]["temp"], data["main"]["humidity"]),
        "fire_danger": fire_danger(data["main"]["temp"], data["main"]["humidity"], round(data["wind"]["speed"] * 3.6, 1)),

        "music_vibes": ["Chill","Relax","Rainy Vibes","Phonk","Storm Mode"],
        "travel": "Safe" if data["weather"][0]["main"] == "Clear" else "Caution",

        "forecast": forecast,
        "radar_tiles": {"tiles": radar},

        "hurricanes": storms
    }
