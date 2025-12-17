import json
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from timezonefinder import TimezoneFinder
import swisseph as swe


SIGNS_BG = [
    "Овен", "Телец", "Близнаци", "Рак", "Лъв", "Дева",
    "Везни", "Скорпион", "Стрелец", "Козирог", "Водолей", "Риби"
]


def _cors(handler: BaseHTTPRequestHandler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _normalize_deg(x: float) -> float:
    return (x % 360.0 + 360.0) % 360.0


def _lon_to_sign_bg(lon_deg: float):
    lon = _normalize_deg(lon_deg)
    sign_index = int(lon // 30) % 12
    deg_in_sign = lon - sign_index * 30
    return SIGNS_BG[sign_index], deg_in_sign


def _geocode(place_text: str):
    # OpenStreetMap Nominatim
    url = "https://nominatim.openstreetmap.org/search"
    params = {"format": "jsonv2", "limit": 1, "q": place_text}
    headers = {"User-Agent": "AscendantCalculator/1.0"}
    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError("Не намерих мястото. Пробвай по-точно: 'Sofia, Bulgaria'.")
    return float(data[0]["lat"]), float(data[0]["lon"])


def _timezone_for(lat: float, lon: float) -> str:
    tf = TimezoneFinder()
    tz = tf.timezone_at(lat=lat, lng=lon)
    return tz or "UTC"


def _parse_local_datetime(date_str: str, time_str: str, unknown_time: bool, tz_name: str):
    # date_str: YYYY-MM-DD, time_str: HH:MM
    if unknown_time or not time_str:
        time_str = "12:00"
    local_naive = datetime.fromisoformat(f"{date_str}T{time_str}:00")
    return local_naive.replace(tzinfo=ZoneInfo(tz_name))


def _calc_ascendant(local_dt, lat: float, lon: float):
    utc_dt = local_dt.astimezone(timezone.utc)

    h = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, h, swe.GREG_CAL)

    # Placidus houses ("P") -> ascmc[0] = Ascendant longitude
    # Note: swe.houses expects 'hsys' as a single char. In pyswisseph use b'P' or 'P'
    cusps, ascmc = swe.houses(jd_ut, lat, lon, b'P')
    asc_lon = float(ascmc[0])

    sign_bg, deg_in_sign = _lon_to_sign_bg(asc_lon)
    return utc_dt, asc_lon, sign_bg, deg_in_sign


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        _cors(self)
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(raw or "{}")

            date_str = data.get("date")
            time_str = data.get("time")
            place_text = data.get("placeText")
            unknown_time = bool(data.get("unknownTime", False))

            if not date_str or not place_text:
                self.send_response(400)
                _cors(self)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Липсва date (YYYY-MM-DD) или placeText."
                }, ensure_ascii=False).encode("utf-8"))
                return

            lat, lon = _geocode(place_text)
            tz_name = _timezone_for(lat, lon)

            local_dt = _parse_local_datetime(date_str, time_str, unknown_time, tz_name)
            utc_dt, asc_lon, sign_bg, deg_in_sign = _calc_ascendant(local_dt, lat, lon)

            response = {
                "ok": True,
                "place": place_text,
                "lat": lat,
                "lon": lon,
                "timezone": tz_name,
                "unknownTime": unknown_time,
                "utcTime": utc_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),

                # резултатът
                "ascSignBg": sign_bg,
                "ascDegree": round(_normalize_deg(asc_lon), 4),
                "ascDegreeInSign": round(deg_in_sign, 4),
                "ascDegreeFormatted": f"{sign_bg} {deg_in_sign:.2f}°",
            }

            self.send_response(200)
            _cors(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            _cors(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))
