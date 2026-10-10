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
JSONBLOB_ID = os.environ.get("JSONBLOB_ID", "019fd1ff-27cd-7921-a1ce-c0a46b9741b0")
JSONBLOB_API = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"

def mask_ip(ip_str):
    if not ip_str:
        return "未知 IP"
    ip = ip_str.split(',')[0].strip()
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.{parts[3]}"
    return ip

def clean_param(s, max_len=120):
    if not s:
        return ""
    return str(s).replace("<", "").replace(">", "").strip()[:max_len]

def infer_mode(swimmer_str):
    s = (swimmer_str or "").strip().upper()
    if ';' in s or '；' in s:
        return "PK"
    elif '/SIM' in s or '得獎模擬' in s:
        return "SIM"
    elif '/STD' in s or '達標' in s:
        return "STD"
    elif '/RANK' in s or '排行' in s:
        return "RANK"
    return "PB"

def infer_device_channel(user_agent, custom_device="", custom_channel=""):
    ua = user_agent or ""
    
    # 設備推導
    device = custom_device
    if not device:
        if "iPhone" in ua:
            device = "iPhone (iOS)"
        elif "iPad" in ua:
            device = "iPad (iPadOS)"
        elif "Android" in ua:
            device = "Android"
        elif "Macintosh" in ua or "Mac OS" in ua:
            device = "Mac (macOS)"
        elif "Windows" in ua:
            device = "Windows PC"
        else:
            device = "其他設備"

    # 管道推導
    channel = custom_channel
    if not channel:
        if "Line/" in ua or "Line" in ua:
            channel = "LINE 內開"
        elif "FBAN" in ua or "FBAV" in ua or "Instagram" in ua:
            channel = "社群內開"
        else:
            channel = "一般瀏覽器"
            
    return device, channel

GLOBAL_LOG_QUEUE = []
import time
_IP_RATE_STORE = {}

def check_rate_limit(client_ip: str, max_requests: int = 120, window_seconds: int = 60) -> bool:
    if not client_ip or client_ip in ("127.0.0.1", "localhost", "testclient"):
        return True
    now = time.time()
    history = _IP_RATE_STORE.get(client_ip, [])
    history = [t for t in history if now - t < window_seconds]
    if len(history) >= max_requests:
        _IP_RATE_STORE[client_ip] = history
        return False
    history.append(now)
    _IP_RATE_STORE[client_ip] = history
    if len(_IP_RATE_STORE) > 2000:
        for k in list(_IP_RATE_STORE.keys())[:500]:
            _IP_RATE_STORE.pop(k, None)
    return True

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
        client_ip = (self.headers.get('x-forwarded-for') or self.headers.get('x-real-ip') or (self.client_address[0] if hasattr(self, 'client_address') and self.client_address else "")).split(',')[0].strip()
        if not check_rate_limit(client_ip, max_requests=120, window_seconds=60):
            self.send_response(429)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._send_cors_headers()
            self.send_header('Retry-After', '60')
            self.end_headers()
            self.wfile.write(b'{"error": "Too Many Requests. Please slow down."}')
            return

        full_path = self.headers.get('x-matched-path', '') or self.path
        parsed_path = urllib.parse.urlparse(full_path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        raw_query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        
        action = query_params.get('action', [''])[0].strip() or raw_query.get('action', [''])[0].strip()
        swimmer = clean_param(query_params.get('swimmer', [''])[0].strip() or raw_query.get('swimmer', [''])[0].strip()) or "[頁面造訪]"
        location = clean_param(query_params.get('location', [''])[0].strip() or raw_query.get('location', [''])[0].strip())
        page = clean_param(query_params.get('page', ['/'])[0].strip() or raw_query.get('page', ['/'])[0].strip(), 200) or "/"
        device = clean_param(query_params.get('device', [''])[0].strip() or raw_query.get('device', [''])[0].strip())
        channel = clean_param(query_params.get('channel', [''])[0].strip() or raw_query.get('channel', [''])[0].strip())
        
        if action == 'pull':
            logs = []
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                json_path = os.path.join(base_dir, "static", "visitor_query_logs.json")
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        logs = data.get("logs", [])
            except Exception:
                logs = []

            if GLOBAL_LOG_QUEUE:
                for item in reversed(GLOBAL_LOG_QUEUE):
                    if not any(e.get("time") == item.get("time") and e.get("swimmer") == item.get("swimmer") for e in logs):
                        logs.insert(0, item)

            swimmer_counts = {}
            for entry in logs:
                s = entry.get("swimmer", "").strip()
                if s and s != "[頁面造訪]":
                    names = [n.strip() for n in s.replace('；', ';').split(';') if n.strip()]
                    for n in names:
                        clean_name = n.split('/')[0].strip()
                        if clean_name:
                            swimmer_counts[clean_name] = swimmer_counts.get(clean_name, 0) + 1

            sorted_hot = sorted(swimmer_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            hot_swimmers = [{"name": name, "count": count} for name, count in sorted_hot]

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "total_logs": len(logs),
                "hot_swimmers": hot_swimmers,
                "logs": logs[:200]
            }, ensure_ascii=False).encode('utf-8'))
            return

        self.process_log(swimmer=swimmer, page=page, custom_loc=location, custom_device=device, custom_channel=channel)

    def do_POST(self):
        client_ip = (self.headers.get('x-forwarded-for') or self.headers.get('x-real-ip') or (self.client_address[0] if hasattr(self, 'client_address') and self.client_address else "")).split(',')[0].strip()
        if not check_rate_limit(client_ip, max_requests=120, window_seconds=60):
            self.send_response(429)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._send_cors_headers()
            self.send_header('Retry-After', '60')
            self.end_headers()
            self.wfile.write(b'{"error": "Too Many Requests. Please slow down."}')
            return

        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
            payload = json.loads(post_data) if post_data else {}
        except Exception:
            payload = {}

        swimmer = clean_param(payload.get("swimmer", "").strip() or query_params.get("swimmer", [""])[0].strip()) or "[頁面造訪]"
        page = clean_param(payload.get("page", "").strip() or query_params.get("page", ["query.html"])[0].strip(), 200) or "query.html"
        location = clean_param(payload.get("location", "").strip() or query_params.get("location", [""])[0].strip())
        device = clean_param(payload.get("device", "").strip() or query_params.get("device", [""])[0].strip())
        channel = clean_param(payload.get("channel", "").strip() or query_params.get("channel", [""])[0].strip())

        self.process_log(swimmer=swimmer, page=page, custom_loc=location, custom_device=device, custom_channel=channel)

    def process_log(self, swimmer, page="query.html", custom_loc="", custom_device="", custom_channel=""):
        utc_now = datetime.now(timezone.utc)
        taipei_now = utc_now + timedelta(hours=8)
        now_str = taipei_now.strftime("%Y/%m/%d %H:%M:%S")

        raw_ip = self.headers.get('x-forwarded-for') or self.headers.get('x-real-ip') or (self.client_address[0] if self.client_address else "127.0.0.1")
        ip_masked = mask_ip(raw_ip)

        city = urllib.parse.unquote(self.headers.get('x-vercel-ip-city', '')).strip()
        country = self.headers.get('x-vercel-ip-country', '').strip()
        country_name = "台灣" if country == "TW" else ("美國" if country == "US" else (country if country else "未知國家"))
        loc_parts = []
        if country_name:
            loc_parts.append(country_name)
        if city:
            loc_parts.append(city)
        location_str = custom_loc or (" ".join(loc_parts) if loc_parts else "台灣")
        
        user_agent = self.headers.get('User-Agent', '')
        device_str, channel_str = infer_device_channel(user_agent, custom_device, custom_channel)
        mode_str = infer_mode(swimmer)
        
        clean_swimmer = swimmer.replace('[頁面造訪]', '').strip()
        if clean_swimmer.startswith('/'):
            clean_swimmer = clean_swimmer[1:]

        ssl_ctx = ssl._create_unverified_context()

        # 1. 寫入記憶體隊列
        if clean_swimmer:
            entry = {
                "time": now_str,
                "ip": ip_masked,
                "location": location_str,
                "swimmer": clean_swimmer,
                "page": page,
                "mode": mode_str,
                "device": device_str,
                "channel": channel_str
            }
            GLOBAL_LOG_QUEUE.append(entry)
            if len(GLOBAL_LOG_QUEUE) > 200:
                GLOBAL_LOG_QUEUE.pop(0)

        # 2. 同步寫入 Google Sheets
        if clean_swimmer:
            try:
                qs = f"?time={urllib.parse.quote(now_str)}&ip={urllib.parse.quote(ip_masked)}&location={urllib.parse.quote(location_str)}&swimmer={urllib.parse.quote(clean_swimmer)}&page={urllib.parse.quote(page)}&device={urllib.parse.quote(device_str)}&channel={urllib.parse.quote(channel_str)}&mode={urllib.parse.quote(mode_str)}"
                sheet_api_url = "https://script.google.com/macros/s/AKfycbzXrhiFSCgzOu02sSY28broCKRLs-zryveAT-682VnDhy7vHzwMmuDhs_GzeKlXlrUUqQ/exec" + qs
                sheet_data = json.dumps({
                    "time": now_str,
                    "ip": ip_masked,
                    "location": location_str,
                    "swimmer": clean_swimmer,
                    "page": page,
                    "device": device_str,
                    "channel": channel_str,
                    "mode": mode_str
                }).encode('utf-8')
                sheet_req = urllib.request.Request(
                    sheet_api_url,
                    data=sheet_data,
                    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(sheet_req, timeout=5, context=ssl_ctx) as s_resp:
                    pass
            except Exception as sheet_err:
                print(f"[Vercel Telemetry] Google Sheet 記錄異常: {sheet_err}")

        # 3. Telegram 機器人即時推播
        if clean_swimmer:
            msg_text = (
                f"🔔 <b>[Vercel 訪客查詢動態]</b>\n\n"
                f"🔍 <b>查詢選手</b>：<b>【{clean_swimmer}】</b> ({mode_str})\n"
                f"📱 <b>設備管道</b>：<code>{device_str} · {channel_str}</code>\n"
                f"📍 <b>來源地區</b>：{location_str} (IP: <code>{ip_masked}</code>)\n"
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
                    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=3, context=ssl_ctx) as resp:
                    pass
            except Exception as tg_err:
                pass

        response_body = {
            "status": "ok",
            "time": now_str,
            "ip": ip_masked,
            "location": location_str,
            "swimmer": clean_swimmer,
            "mode": mode_str,
            "device": device_str,
            "channel": channel_str
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(response_body, ensure_ascii=False).encode('utf-8'))
