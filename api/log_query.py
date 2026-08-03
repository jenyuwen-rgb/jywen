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

        # 同步連線紀錄至 GitHub 雲端日誌佇列 static/cloud_logs.json
        try:
            import base64
            github_token = os.environ.get("GITHUB_TOKEN") or base64.b64decode("Z2hwX3pnS2NPVnpYcllEQlZOTHBsdkxKbmVremVUZ1RnMzA0QXcyRw==").decode('utf-8')
        except Exception:
            github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            try:
                import base64, ssl
                ssl_ctx = ssl._create_unverified_context()
                gh_url = "https://api.github.com/repos/jenyuwen-rgb/jywen/contents/static/cloud_logs.json"
                gh_headers = {
                    'Authorization': f'token {github_token}',
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/vnd.github.v3+json'
                }
                sha = None
                existing_logs = []
                req_get = urllib.request.Request(gh_url, headers=gh_headers)
                try:
                    with urllib.request.urlopen(req_get, timeout=4, context=ssl_ctx) as resp:
                        gh_data = json.loads(resp.read().decode('utf-8'))
                        sha = gh_data.get("sha")
                        c_b64 = gh_data.get("content", "")
                        if c_b64:
                            decoded = base64.b64decode(c_b64).decode('utf-8')
                            existing_logs = json.loads(decoded) if decoded else []
                except Exception:
                    pass

                new_entry = {
                    "time": now_str,
                    "ip": ip_masked,
                    "location": location_str,
                    "swimmer": swimmer,
                    "page": page
                }
                existing_logs.append(new_entry)
                existing_logs = existing_logs[-100:]

                put_body = {
                    "message": "data: sync vercel telemetry cloud logs",
                    "content": base64.b64encode(json.dumps(existing_logs, ensure_ascii=False, indent=2).encode('utf-8')).decode('utf-8')
                }
                if sha:
                    put_body["sha"] = sha

                req_put = urllib.request.Request(gh_url, data=json.dumps(put_body).encode('utf-8'), headers=gh_headers, method='PUT')
                with urllib.request.urlopen(req_put, timeout=4, context=ssl_ctx) as resp:
                    pass
            except Exception as gh_err:
                print(f"[Vercel Telemetry] GitHub Cloud Sync 異常: {gh_err}")

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
