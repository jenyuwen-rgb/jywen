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


def fetch_site_tpesa_races():
    """台北體總 (TPESA) - 官方歷屆 PDF 成績清單"""
    return [
        {"text": "115年青年盃成績", "value": "http://www.tpesa.org.tw/result/115年青年盃成績.pdf"},
        {"text": "114年中正盃成績", "value": "http://www.tpesa.org.tw/result/114年中正盃成績.pdf"},
        {"text": "114年青年盃成績", "value": "http://www.tpesa.org.tw/result/114年青年盃成績.pdf"},
        {"text": "113年中正盃成績", "value": "http://www.tpesa.org.tw/result/113年中正盃成績.pdf"},
        {"text": "113年青年盃成績", "value": "http://www.tpesa.org.tw/result/113年青年盃成績.pdf"},
        {"text": "112年中正盃成績", "value": "http://www.tpesa.org.tw/result/112年中正盃成績.pdf"},
        {"text": "112年青年盃成績", "value": "http://www.tpesa.org.tw/result/112年青年盃成績.pdf"},
        {"text": "111年中正盃成績", "value": "http://www.tpesa.org.tw/result/111年中正盃成績.pdf"},
        {"text": "111年青年盃成績", "value": "http://www.tpesa.org.tw/result/111年青年盃成績.pdf"},
        {"text": "110年中正盃成績", "value": "http://www.tpesa.org.tw/result/110年中正盃成績.pdf"},
        {"text": "110年青年盃成績", "value": "http://www.tpesa.org.tw/result/110年青年盃成績.pdf"},
        {"text": "109年中正盃成績", "value": "http://www.tpesa.org.tw/result/109年中正盃成績.pdf"},
        {"text": "109年青年盃成績", "value": "http://www.tpesa.org.tw/result/109年青年盃成績.pdf"},
        {"text": "108年中正盃成績", "value": "http://www.tpesa.org.tw/result/108年中正盃成績.pdf"},
        {"text": "108年青年盃成績", "value": "http://www.tpesa.org.tw/result/108年青年盃成績.pdf"},
        {"text": "107年中正盃成績", "value": "http://www.tpesa.org.tw/result/107年中正盃成績.pdf"},
        {"text": "107年青年盃成績", "value": "http://www.tpesa.org.tw/result/107年青年盃成績.pdf"}
    ]


def fetch_site_ntpc_races():
    """新北市體育總會游泳委員會 (NTPC)"""
    return [
        {"text": "新北市115年小學運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/stutea115/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市115年中等學校運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/cenm115/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市115年度基層運動選手訓練站游泳區域性對抗賽 (SPNET)", "value": "https://www.spnet.tw/cmswim115/showplan.php"},
        {"text": "新北市115學年度小學游泳對抗賽 (SPNET)", "value": "https://www.spnet.tw/ceswim115/showplan.php"},
        {"text": "新北市114年小學運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/stutea114/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市114年中等學校運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/cenm114/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市114年度基層運動選手訓練站游泳區域性對抗賽 (SPNET)", "value": "https://www.spnet.tw/cmswim114/showplan.php"},
        {"text": "新北市114學年度小學游泳對抗賽 (SPNET)", "value": "https://www.spnet.tw/ceswim114/showplan.php"},
        {"text": "新北市113年小學運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/stutea113/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市113年中等學校運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/cenm113/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市113年度基層運動選手訓練站游泳區域性對抗賽 (SPNET)", "value": "https://www.spnet.tw/cmswim113/showplan.php"},
        {"text": "新北市113學年度小學游泳對抗賽 (SPNET)", "value": "https://www.spnet.tw/ceswim113/showplan.php"},
        {"text": "新北市112年小學運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/stutea112/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市112年中等學校運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/cenm112/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市111年小學運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/stutea111/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市111年中等學校運動會【游泳】(SPNET)", "value": "https://sports.spnet.tw/cenm111/qryprocess.php?mCat=%E6%B8%B8%E6%B3%B3"},
        {"text": "新北市中等學校運動會游泳大會紀錄", "value": "https://nas.spnet.tw/twps/3s.pdf"},
        {"text": "新北市小學運動會游泳大會紀錄", "value": "https://nas.spnet.tw/twps/6s.pdf"},
        {"text": "新北市115學年度中等學校運動會游泳賽", "value": "https://ntpc-sports.com/twps/%e6%96%b0%e5%8c%97%e5%b8%82115%e5%ad%b8%e5%b9%b4%e5%ba%a6%e4%b8%ad%e7%ad%89%e5%ad%b8%e6%a0%a1%e9%81%8b%e5%8b%95%e6%9c%83%e3%80%90%e6%b8%b8%e6%b3%b3%e3%80%91%e7%ab%b6%e8%b3%bd%e8%b3%87%e8%a8%8a/"},
        {"text": "新北市114學年度中等學校游泳對抗賽", "value": "https://nas.spnet.tw/twps/20260306/新北市114學年度中等學校游泳對抗賽秩序冊.pdf"},
        {"text": "新北市114年市長盃分齡游泳錦標賽", "value": "https://nas.spnet.tw/twps/114mayor_cup.pdf"},
        {"text": "新北市113年市長盃分齡游泳錦標賽", "value": "https://nas.spnet.tw/twps/113mayor_cup.pdf"}
    ]


def fetch_site_hcc_races():
    """新竹市體育會游泳委員會 (HCC)"""
    return [
        {"text": "115年新竹市風城盃分級游泳錦標賽", "value": "https://hcc-swim.org/115wind_city"},
        {"text": "115年新竹市市長盃游泳錦標賽", "value": "https://hcc-swim.org/115mayor_cup"},
        {"text": "114年新竹市風城盃分級游泳錦標賽", "value": "https://hcc-swim.org/114wind_city"},
        {"text": "114年新竹市市長盃游泳錦標賽", "value": "https://hcc-swim.org/114mayor_cup"},
        {"text": "114年新竹市中小學聯合運動會游泳賽", "value": "https://hcc-swim.org/114school_games"},
        {"text": "113年新竹市風城盃分級游泳錦標賽", "value": "https://hcc-swim.org/113wind_city"},
        {"text": "113年新竹市市長盃游泳錦標賽", "value": "https://hcc-swim.org/113mayor_cup"}
    ]


def fetch_site_tyc_races():
    """桃園市體育總會游泳委員會 (TYC)"""
    return [
        {"text": "115年桃園市市長盃游泳錦標賽", "value": "https://sports.taoyuansport.org.tw/115mayor_cup"},
        {"text": "115年桃園市中小學校聯合運動會游泳賽", "value": "https://sports.taoyuansport.org.tw/115school_games"},
        {"text": "114年桃園市市長盃游泳錦標賽", "value": "https://sports.taoyuansport.org.tw/114mayor_cup"},
        {"text": "114年桃園市議長盃游泳錦標賽", "value": "https://sports.taoyuansport.org.tw/114speaker_cup"},
        {"text": "114年桃園市中小學校聯合運動會游泳賽", "value": "https://sports.taoyuansport.org.tw/114school_games"},
        {"text": "113年桃園市市長盃游泳錦標賽", "value": "https://sports.taoyuansport.org.tw/113mayor_cup"},
        {"text": "113年桃園市議長盃游泳錦標賽", "value": "https://sports.taoyuansport.org.tw/113speaker_cup"}
    ]


import time

_IP_RATE_STORE = {}
_RACES_CACHE = {}

def check_rate_limit(client_ip: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
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

def get_cached_races(cache_key: str, fetch_fn, ttl: int = 300):
    now = time.time()
    if cache_key in _RACES_CACHE:
        cached_data, timestamp = _RACES_CACHE[cache_key]
        if now - timestamp < ttl:
            return cached_data
    data = fetch_fn()
    _RACES_CACHE[cache_key] = (data, now)
    return data

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        client_ip = (self.headers.get('x-forwarded-for') or self.headers.get('x-real-ip') or (self.client_address[0] if hasattr(self, 'client_address') and self.client_address else "")).split(',')[0].strip()
        if not check_rate_limit(client_ip, max_requests=60, window_seconds=60):
            self.send_response(429)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Retry-After', '60')
            self.end_headers()
            self.wfile.write(b'{"error": "Too Many Requests. Please slow down."}')
            return

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
            'site_tpesa': fetch_site_tpesa_races,
            'site_ntpc': fetch_site_ntpc_races,
            'site_hcc': fetch_site_hcc_races,
            'site_tyc': fetch_site_tyc_races,
        }

        cache_key = f"races_{site or 'all'}"
        def load_races():
            if site and site in fetch_map:
                return [{"id": site, "races": fetch_map[site]()}]
            else:
                return [
                    {"name": "台中市游泳委員會", "id": "site_a", "races": fetch_site_a_races()},
                    {"name": "台南市游泳委員會", "id": "site_b", "races": fetch_site_b_races()},
                    {"name": "高雄市游泳委員會", "id": "site_c", "races": fetch_site_c_races()},
                    {"name": "中華泳協 CTSA",   "id": "site_d", "races": fetch_site_d_races()},
                    {"name": "高雄水上",         "id": "site_e", "races": fetch_site_e_races()},
                    {"name": "台北體總 TPESA",   "id": "site_tpesa", "races": fetch_site_tpesa_races()},
                    {"name": "新北市游泳委員會", "id": "site_ntpc", "races": fetch_site_ntpc_races()},
                    {"name": "新竹市游泳委員會", "id": "site_hcc", "races": fetch_site_hcc_races()},
                    {"name": "桃園市游泳委員會", "id": "site_tyc", "races": fetch_site_tyc_races()},
                ]

        data = get_cached_races(cache_key, load_races, ttl=300)

        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=300')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # 靜默日誌
