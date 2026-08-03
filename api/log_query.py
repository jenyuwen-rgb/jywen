# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import json
import os
import ssl
from datetime import datetime, timezone, timedelta

# Telegram 設定
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8939873453:AAH5EXWOMoJ6D3I3i1FoQihMLa_lmumCt5A")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID", "8270092740")

# JSONBlob 雲端橋樑設定 (無需 Token，公開讀寫，永遠不會被撤銷)
JSONBLOB_ID = os.environ.get("JSONBLOB_ID", "019fc7cd-0365-74bf-b991-b922e8f1a40c")
JSONBLOB_API = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"

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

        ssl_ctx = ssl._create_unverified_context()

        # ① 發送 Telegram 機器人即時推播
        if swimmer:
            msg_text = (
                f"🔔 <b>[Vercel 雲端連線通知]</b>\n\n"
                f"📍 <b>來源地區</b>：{location_str} (IP: <code>{ip_masked}</code>)\n"
                f"🔍 <b>查詢/造訪</b>：<b>【{swimmer}】</b>\n"
                f"📄 <b>頁面</b>：<code>{page}</code>\n"
                f"⏰ <b>時間</b>：{now_str}"
            )
            try:
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
                        'User-Agent': 'Mozilla/5.0'
                    }
                )
                with urllib.request.urlopen(req, timeout=5, context=ssl_ctx) as resp:
                    pass
            except Exception as tg_err:
                print(f"[Vercel Telemetry] Telegram 推播異常: {tg_err}")

        # ② 同步連線紀錄至 JSONBlob 雲端橋樑（無需 Token，永久穩定）
        try:
            new_entry = {
                "time": now_str,
                "ip": ip_masked,
                "location": location_str,
                "swimmer": swimmer,
                "page": page
            }

            # 讀取現有日誌
            existing_logs = []
            try:
                req_get = urllib.request.Request(
                    JSONBLOB_API,
                    headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req_get, timeout=4, context=ssl_ctx) as resp:
                    existing_logs = json.loads(resp.read().decode('utf-8'))
                    if not isinstance(existing_logs, list):
                        existing_logs = []
            except Exception:
                existing_logs = []

            # 防重複：同一時間+同一選手+同一IP 不重複寫入
            is_dup = any(
                e.get("time") == new_entry["time"] and
                e.get("swimmer") == new_entry["swimmer"] and
                e.get("ip") == new_entry["ip"]
                for e in existing_logs
            )
            if not is_dup:
                existing_logs.append(new_entry)
                existing_logs = existing_logs[-200:]  # 保留最新 200 筆

                req_put = urllib.request.Request(
                    JSONBLOB_API,
                    data=json.dumps(existing_logs, ensure_ascii=False).encode('utf-8'),
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'User-Agent': 'Mozilla/5.0'
                    },
                    method='PUT'
                )
                with urllib.request.urlopen(req_put, timeout=5, context=ssl_ctx) as resp:
                    pass
        except Exception as jb_err:
            print(f"[Vercel Telemetry] JSONBlob 同步異常: {jb_err}")

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
