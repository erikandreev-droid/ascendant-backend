import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

import swisseph as swe
from timezonefinder import TimezoneFinder


SIGNS_BG = [
    "Овен",
    "Телец",
    "Близнаци",
    "Рак",
    "Лъв",
    "Дева",
    "Везни",
    "Скорпион",
    "Стрелец",
    "Козирог",
    "Водолей",
    "Риби",
]


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            **cors_headers(),
            "Content-Type": "application/json; charset=utf-8",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def normalize_deg(x):
    return (x % 360 + 360) % 360


def lon_to_sign(lon):
    lon = normalize_deg(lon)
    sign_index = int(lon // 30)
    deg_in_sign = lon - sign_index * 30
    return SIGNS_BG[sign_index], deg_in_sign


def geocode(place_text):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "jsonv2",
        "limit": 1,
        "q": place_text,
    }
    headers = {
        # 🔴 СМЕНИ ИМЕЙЛА ТУК 🔴
        "User-Agent": "AscendantCalculator/1.0 (contact: your@email.com)"
    }

    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()

    if not data:
        raise Exception("Place not found")

    return float(data[0]["lat"]), float(data[0]["lon"])


def handler(request):
    method = (request.get("method") or request.get("httpMethod") or "").upper()

    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": cors_headers(),
            "body": "",
        }

    if method != "POST":
        return response(405, {"error": "Use POST"})

    try:
        body_raw = request.get("body") or ""

        if request.get("isBase64Encoded"):
            import base64
            body_raw = base64.b64decode(body_raw).decode("utf-8")

        data = json.loads(body_raw or "{}")

        date = data.get("date")          # YYYY-MM-DD
        time = data.get("time")          # HH:MM
        place = data.get("placeText")
        unknown_time = bool(data.get("unknownTime"))

        if not date or not place:
            return response(400, {"error": "Missing date or placeText"})

        if unknown_time or not time:
            time = "12:00"

        lat, lon = geocode(place)

        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lon) or "UTC"

        local_dt = datetime.fromisoformat(f"{date}T{time}:00").replace(
            tzinfo=ZoneInfo(tz_name)
        )
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

        hour = (
            utc_dt.hour
            + utc_dt.minute / 60
            + utc_dt.second / 3600
        )

        jd_ut = swe.julday(
            utc_dt.year,
            utc_dt.month,
            utc_dt.day,
            hour,
            swe.GREG_CAL,
        )

        flags = swe.FLG_SWIEPH
        cusps, ascmc = swe.houses_ex(jd_ut, flags, lat, lon, b"P")
        asc_lon = ascmc[0]

        sign_bg, deg_in_sign = lon_to_sign(asc_lon)

        return response(
            200,
            {
                "ascSignBg": sign_bg,
                "ascDegreeFormatted": f"{sign_bg} {deg_in_sign:.2f}°",
                "ascDegree": round(asc_lon, 6),
                "utcIso": utc_dt.isoformat().replace("+00:00", "Z"),
                "timezone": tz_name,
                "lat": lat,
                "lon": lon,
                "warning": (
                    "Часът е неизвестен — използван е 12:00"
                    if unknown_time
                    else None
                ),
            },
        )

    except Exception as e:
        return response(400, {"error": str(e)})
