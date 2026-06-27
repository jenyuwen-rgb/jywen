from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import json
import html

# ──────────────────────────────────────────────
# Vercel Serverless Function: GET /api/races
# 伺服器端爬取五大游泳協會賽事清單，解決 CORS 問題
# ──────────────────────────────────────────────

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
}

def fetch_url(url, encoding='utf-8', timeout=12):
    """伺服器端發 HTTP GET，不受 CORS 限制"""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        return raw.decode(encoding, errors='ignore')

def parse_options(html_text, select_name=None, select_id=None, link_pattern=None):
    """
    極簡 HTML 解析（不依賴 BeautifulSoup）
    回傳 [{"text": ..., "value": ...}, ...]
    """
    import re
    races = []
    seen = set()

    if link_pattern:
        # 台南模式：解析 <a href="...history_detail.asp...">文字</a>
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']*' + re.escape(link_pattern) + r'[^"\']*)["\'][^>]*>(.*?)</a>', html_text, re.IGNORECASE | re.DOTALL):
            href = m.group(1).strip()
            text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            text = html.unescape(text)
            if text and href not in seen:
                seen.add(href)
                races.append({"text": text, "value": href})
    else:
        # 找 <select name="..." ...> 或 <select id="...">
        if select_name:
            pat = r'<select[^>]+name=["\']' + re.escape(select_name) + r'["\'][^>]*>(.*?)</select>'
        else:
            pat = r'<select[^>]+id=["\']' + re.escape(select_id) + r'["\'][^>]*>(.*?)</select>'

        m = re.search(pat, html_text, re.IGNORECASE | re.DOTALL)
        if not m:
            return races
        select_html = m.group(1)

        for opt in re.finditer(r'<option[^>]+value=["\']([^"\']*)["\'][^>]*>(.*?)</option>', select_html, re.IGNORECASE | re.DOTALL):
            val = opt.group(1).strip()
            text = re.sub(r'<[^>]+>', '', opt.group(2)).strip()
            text = html.unescape(text)
            if val and val not in ('0', '') and text not in ('==請選擇==',) and val not in seen:
                seen.add(val)
                races.append({"text": text, "value": val})

    return races


def fetch_site_a_races():
    """台中市游泳委員會 (Swim8)"""
    try:
        h = fetch_url("https://swim8.kcsat.org/score_search")
        return parse_options(h, select_name="search_game_filter")
    except Exception as e:
        return [{"text": f"獲取失敗: {e}", "value": ""}]


def fetch_site_b_races():
    """台南市游泳委員會"""
    try:
        h = fetch_url("https://www.tainanswim.com.tw/history.asp", encoding='utf-8')
        return parse_options(h, link_pattern="history_detail.asp")
    except Exception as e:
        return [{"text": f"獲取失敗: {e}", "value": ""}]


def fetch_site_c_races():
    """高雄市游泳委員會"""
    try:
        h = fetch_url("http://kcc.nowforyou.com/register/gameeventqry.asp", encoding='utf-8')
        return parse_options(h, select_name="xgameno")
    except Exception as e:
        return [{"text": f"獲取失敗: {e}", "value": ""}]


def fetch_site_d_races():
    """中華泳協 CTSA"""
    try:
        h = fetch_url("https://ctsa.utk.com.tw/CTSA/public/race/game_data.aspx")
        return parse_options(h, select_id="ctl00_ContentPlaceHolder1_DD_Activity_ID")
    except Exception as e:
        return [{"text": f"獲取失敗: {e}", "value": ""}]


def fetch_site_e_races():
    """高雄水上"""
    try:
        h = fetch_url("https://swim.kcsat.org/score_search")
        return parse_options(h, select_name="search_game_filter")
    except Exception as e:
        return [{"text": f"獲取失敗: {e}", "value": ""}]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 解析 ?site= 參數，支援單站查詢以降低冷啟動時間
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        site = params.get('site', [None])[0]

        fetch_map = {
            'site_a': fetch_site_a_races,
            'site_b': fetch_site_b_races,
            'site_c': fetch_site_c_races,
            'site_d': fetch_site_d_races,
            'site_e': fetch_site_e_races,
        }

        if site and site in fetch_map:
            # 單站模式
            data = [{"id": site, "races": fetch_map[site]()}]
        else:
            # 全站模式（依序爬取，Vercel timeout 10s，並行版需 asyncio）
            data = [
                {"name": "台中市游泳委員會", "id": "site_a", "races": fetch_site_a_races()},
                {"name": "台南市游泳委員會", "id": "site_b", "races": fetch_site_b_races()},
                {"name": "高雄市游泳委員會", "id": "site_c", "races": fetch_site_c_races()},
                {"name": "中華泳協 CTSA",   "id": "site_d", "races": fetch_site_d_races()},
                {"name": "高雄水上",         "id": "site_e", "races": fetch_site_e_races()},
            ]

        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # 靜默日誌
