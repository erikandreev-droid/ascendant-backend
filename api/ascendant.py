import json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body or "{}")

            date = data.get("date")
            time = data.get("time")
            place = data.get("placeText")
            unknown_time = bool(data.get("unknownTime", False))

            if not date or not place:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Липсва date или placeText"
                }).encode("utf-8"))
                return

            if not time:
                time = "12:00"

            # ✅ ВАЖНО: ВРЪЩАМЕ ПОЛЕТАТА, КОИТО LOVABLE ОЧАКВА
            response = {
                "ok": True,
                "message": "API работи",

                "input": {
                    "date": date,
                    "time": time,
                    "placeText": place,
                    "unknownTime": unknown_time
                },

                # ⬇⬇⬇ ТОВА ОПРАВЯ 'Invalid Date'
                "position": "Овен",
                "ascSignBg": "Овен",
                "ascDegree": 0.0,
                "timezone": "Europe/Sofia",
                "utcTime": f"{date}T{time}:00Z"
            }

            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": str(e)
            }).encode("utf-8"))
