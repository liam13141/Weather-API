from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import requests, datetime

API_KEY = "3dea6ae1817cf94ce90732907a006e3f"
AUTH_CODE = "10292051924712"  # ✅ Required authorization value

app = FastAPI(title="WeatherStyle Pro API 🌦️", description="Protected JSON weather API")

# Allow all origins (so your HTML dashboard can access it)
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

def clothing_recommendation(temp_c, condition):
    cond = condition.lower()
    if "rain" in cond or "drizzle" in cond:
        return "🌧️ It's wet out — wear a waterproof jacket and boots!"
    elif temp_c >= 33:
        return "🔥 Extremely hot! Light clothes and stay hydrated."
    elif 25 <= temp_c < 33:
        return "☀️ Warm day — T-shirt, shorts, and sunglasses are perfect."
    elif 18 <= temp_c < 25:
        return "🌤️ Mild and comfy — light layers or a tee with jeans."
    elif 10 <= temp_c < 18:
        return "🧥 A bit chilly — wear a light jacket or hoodie."
    elif 0 <= temp_c < 10:
        return "🧤 Cold — grab a coat and warm layers."
    else:
        return "❄️ Freezing! Heavy coat, gloves, hat, and scarf!"


@app.get("/weather")
def get_weather(city: str, authorization: str = None):
    """Return weather data as JSON if authorized."""
    # 🔒 Authorization check
    if authorization != AUTH_CODE:
        raise HTTPException(status_code=403, detail="Unauthorized: invalid authorization code")

    # --- Fetch from OpenWeatherMap ---
    current = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric")
    forecast = requests.get(f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric")

    if current.status_code != 200:
        raise HTTPException(status_code=404, detail="City not found")

    data = current.json()
    forecast_data = forecast.json()

    main = data["weather"][0]["main"]
    desc = data["weather"][0]["description"].title()
    temp_c = data["main"]["temp"]
    temp_f = round(temp_c * 9/5 + 32, 1)
    feels = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    wind = round(data["wind"]["speed"] * 3.6, 1)
    pressure = data["main"]["pressure"]
    sunrise = datetime.datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%I:%M %p")
    sunset = datetime.datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%I:%M %p")
    emoji = ICON_MAP.get(main, "🌍")

    # 5-day forecast
    days = {}
    for item in forecast_data["list"]:
        dt = datetime.datetime.fromtimestamp(item["dt"])
        day = dt.strftime("%a")
        if day not in days:
            days[day] = {
                "min": item["main"]["temp_min"],
                "max": item["main"]["temp_max"],
                "main": item["weather"][0]["main"],
                "desc": item["weather"][0]["description"].title(),
            }
        else:
            days[day]["min"] = min(days[day]["min"], item["main"]["temp_min"])
            days[day]["max"] = max(days[day]["max"], item["main"]["temp_max"])

    return {
        "city": data["name"],
        "emoji": emoji,
        "desc": desc,
        "temp_c": temp_c,
        "temp_f": temp_f,
        "feels_like": feels,
        "humidity": humidity,
        "wind_kmh": wind,
        "pressure_hpa": pressure,
        "sunrise": sunrise,
        "sunset": sunset,
        "clothing_tip": clothing_recommendation(temp_c, desc),
        "forecast": days
    }
