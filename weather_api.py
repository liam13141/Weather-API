from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests, datetime, os, math

API_KEY = os.getenv("OPENWEATHER_API_KEY")
AUTH_CODE = os.getenv("AUTH_CODE")

app = FastAPI(
    title="WeatherStyle PRO GOD MODE API 🌎⚡",
    description="Ultra-expanded weather API: AQI, UV, alerts, radar, NASA, NOAA, pollen, hurricanes, analytics."
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
# UTILITY HELPERS
# --------------------------
def uv_advice(uv):
    if uv < 3: return "🟢 Low risk — enjoy the outdoors."
    if uv < 6: return "🟡 Moderate — sunscreen advised."
    if uv < 8: return "🟠 High — reduce midday exposure."
    if uv < 11: return "🔴 Very high — seek shade."
    return "🟣 Extreme — avoid going outside."

def frostbite_time(temp_c, wind_kmh):
    # OSHA wind chill chart estimation
    wind_ms = wind_kmh / 3.6
    chill = 13.12 + 0.6215*temp_c - 11.37*(wind_ms**0.16) + 0.3965*temp_c*(wind_ms**0.16)
    if chill > -10: return "No frostbite risk."
    if chill > -20: return "Risk in 30+ minutes."
    if chill > -28: return "Risk in 10–30 minutes."
    return "Severe risk in <10 minutes."

def heatstroke_risk(temp_c, humidity):
    # simple heat index approximation
    if temp_c >= 40: return "🔥 Extremely high — stay indoors."
    if temp_c >= 34: return "🔥 Danger — heavy activity risky."
    if temp_c >= 30: return "🥵 High — stay hydrated."
    return "🟢 Normal risk."

def fire_danger(temp, humidity, wind):
    score = temp * 0.4 + wind * 0.3 - humidity * 0.2
    if score < 10: return "🟢 Low"
    if score < 20: return "🟡 Moderate"
    if score < 35: return "🟠 High"
    return "🔴 Extreme"

def mood_color(main):
    return {
        "Clear": "#FFD300",
        "Clouds": "#C7C7C7",
        "Rain": "#4A90E2",
        "Snow": "#E0F7FF",
        "Thunderstorm": "#5C2E91",
        "Mist": "#A8A8A8"
    }.get(main, "#FFFFFF")

def music_vibes(main):
    return {
        "Clear": ["Lofi beats", "Chill EDM", "Summer vibes"],
        "Rain": ["Dark phonk", "Sad lofi", "Ambient"],
        "Snow": ["Cozy piano", "Christmas jazz"],
        "Clouds": ["Soft pop", "Relaxed trapsoul"],
        "Thunderstorm": ["Phonk bass", "Trap metal"],
    }.get(main, ["Ambient"])
    
# --------------------------
# NOAA WEATHER ALERTS
# --------------------------
def get_noaa_alerts(lat, lon):
    try:
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        res = requests.get(url, headers={"User-Agent": "WeatherStylePro"})
        data = res.json()
        alerts = []
        for a in data.get("features", []):
            props = a["properties"]
            alerts.append({
                "event": props["event"],
                "severity": props["severity"],
                "headline": props["headline"],
                "description": props["description"]
            })
        return alerts
    except:
        return []

# --------------------------
# NASA POWER SOLAR API
# --------------------------
def nasa_solar(lat, lon):
    try:
        url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON"
        res = requests.get(url).json()
        d = list(res["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"].values())[-1]
        return round(d, 1)
    except:
        return None

# --------------------------
# HURRICANE TRACKER (NOAA NHC)
# --------------------------
def hurricane_data():
    try:
        res = requests.get("https://www.nhc.noaa.gov/CurrentStorms.json").json()
        return res
    except:
        return []

# --------------------------
# RADAR TILES (RAINVIEWER)
# --------------------------
def radar_tile():
    info = requests.get("https://api.rainviewer.com/public/weather-maps.json").json()
    files = info["radar"]["past"]
    return {
        "tiles": [
            f"https://tilecache.rainviewer.com/v2/radar/{f['path']}/256/{z}/{x}/{y}/2/1_1.png"
            for f in files for z in [6] for x in [33] for y in [21]
        ],
        "timestamps": [f["time"] for f in files]
    }

# --------------------------
# HISTORICAL WEATHER (Open-Meteo)
# --------------------------
def historical(lat, lon):
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date=2024-01-01&end_date=2024-01-07&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
    try:
        return requests.get(url).json()
    except:
        return {}

# --------------------------
# MAIN WEATHER ENDPOINT
# --------------------------
@app.get("/weather")
def weather(city: str, authorization: str = None):

    if authorization != AUTH_CODE:
        raise HTTPException(403, "Unauthorized")

    current = requests.get(
        f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    )

    if current.status_code != 200:
        raise HTTPException(404, "City not found")

    data = current.json()
    lat, lon = data["coord"]["lat"], data["coord"]["lon"]

    # OpenWeather extras
    forecast = requests.get(
        f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    ).json()

    main = data["weather"][0]["main"]
    desc = data["weather"][0]["description"].title()
    emoji = ICON_MAP.get(main, "🌍")

    temp = data["main"]["temp"]
    humidity = data["main"]["humidity"]
    wind = round(data["wind"]["speed"] * 3.6, 1)

    # Air Quality
    aqi_raw = requests.get(
        f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    ).json()
    aqi = aqi_raw["list"][0]["main"]["aqi"]

    # UV
    uv_raw = requests.get(
        f"https://api.openweathermap.org/data/2.5/uvi?lat={lat}&lon={lon}&appid={API_KEY}"
    ).json()
    uv = uv_raw.get("value", 0)

    # NOAA Alerts
    alerts = get_noaa_alerts(lat, lon)

    # NASA solar
    solar = nasa_solar(lat, lon)

    # Radar
    tiles = radar_tile()

    # Hurricanes
    storms = hurricane_data()

    # Historical data
    hist = historical(lat, lon)

    return {
        "city": city,
        "emoji": emoji,
        "main": main,
        "description": desc,
        "temperature_c": temp,
        "humidity": humidity,
        "wind_kmh": wind,
        "aqi": aqi,
        "uv_index": uv,
        "uv_advice": uv_advice(uv),
        "frostbite_time": frostbite_time(temp, wind),
        "heatstroke_risk": heatstroke_risk(temp, humidity),
        "fire_danger": fire_danger(temp, humidity, wind),
        "music_vibes": music_vibes(main),
        "theme_color": mood_color(main),
        "travel": "⚠️ Caution" if main in ["Rain", "Snow"] else "✅ Safe",
        "alerts": alerts,
        "solar_kw_m2": solar,
        "radar_tiles": tiles,
        "hurricanes": storms,
        "historical": hist
    }

# --------------------------
# MULTI CITY
# --------------------------
@app.get("/weather/multi")
def multi(cities: str, authorization: str = None):

    if authorization != AUTH_CODE:
        raise HTTPException(403, "Unauthorized")

    city_list = [c.strip() for c in cities.split(",")]

    return {c: weather(c, authorization) for c in city_list}
