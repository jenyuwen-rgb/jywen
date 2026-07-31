# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import json
import os
import re
from datetime import datetime, timezone, timedelta

# Telegram 設定
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8939873453:AAH5EXWOMoJ6D3I3i1FoQihMLa_lmumCt5A")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID", "8270092740")

def mask_ip(ip_str):
    if not ip_str:
        return "未知 IP"
    ip = ip_str.split(',')[0].strip()
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.{parts[3]}"
    return ip

class handler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"status": "active", "service": "Vercel Query Telemetry API"}).encode('utf-8'))

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            payload = json.loads(post_data) if post_data else {}
        except Exception:
            payload = {}

        swimmer = payload.get("swimmer", "").strip() or "[頁面造訪]"
        page = payload.get("page", "query.html")

        # 抓取 IP 與 Vercel Edge 地理位置 Header
        raw_ip = self.headers.get('x-forwarded-for') or self.headers.get('x-real-ip') or self.client_address[0]
        ip_masked = mask_ip(raw_ip)

        city = urllib.parse.unquote(self.headers.get('x-vercel-ip-city', '')).strip()
        country = self.headers.get('x-vercel-ip-country', '').strip()
        region = self.headers.get('x-vercel-ip-country-region', '').strip()

        # 格式化國家與城市名稱
        country_name = "台灣" if country == "TW" else ("美國" if country == "US" else (country if country else "未知國家"))
        loc_parts = []
        if country_name:
            loc_parts.append(country_name)
        if city:
            loc_parts.append(city)
        location_str = " ".join(loc_parts) if loc_parts else "未知區域"

        # 台北時間 GMT+8
        tz_taipei = timezone(timedelta(hours=8))
        now_str = datetime.now(tz_taipei).strftime("%Y-%m-%d %H:%M:%S")

        # 發送 Telegram 機器人即時推播 (只要有連線或搜尋即發送)
        if swimmer:
            msg_text = (
                f"🔔 <b>[Vercel 雲端連線通知]</b>\n\n"
                f"📍 <b>來源地區</b>：{location_str} (IP: <code>{ip_masked}</code>)\n"
                f"🔍 <b>查詢/造訪</b>：<b>【{swimmer}】</b>\n"
                f"📄 <b>頁面</b>：<code>{page}</code>\n"
                f"⏰ <b>時間</b>：{now_str}"
            )

            # 發送至 Telegram API
            try:
                import ssl
                ssl_ctx = ssl._create_unverified_context()
                tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                req_data = json.dumps({
                    "chat_id": TELEGRAM_USER_ID,
                    "text": msg_text,
                    "parse_mode": "HTML"
                }).encode('utf-8')
                req = urllib.request.Request(
                    tg_url, 
                    data=req_data, 
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
                    }
                )
                with urllib.request.urlopen(req, timeout=5, context=ssl_ctx) as resp:
                    pass
            except Exception as tg_err:
                print(f"[Vercel Telemetry] Telegram 推播異常: {tg_err}")

        response_body = {
            "status": "ok",
            "time": now_str,
            "ip": ip_masked,
            "location": location_str,
            "swimmer": swimmer
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(response_body, ensure_ascii=False).encode('utf-8'))
