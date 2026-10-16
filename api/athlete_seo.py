# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import urllib.parse
import json
import gzip
import hashlib
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
possible_dirs = [
    os.path.join(CURRENT_DIR, "..", "data_buckets"),
    os.path.join(CURRENT_DIR, "data_buckets"),
    os.path.join(os.getcwd(), "data_buckets"),
    os.path.join(os.getcwd(), "01_整合平台_前端源碼", "data_buckets")
]
BUCKETS_DIR = os.path.join(CURRENT_DIR, "..", "data_buckets")
for d in possible_dirs:
    if os.path.exists(d):
        BUCKETS_DIR = d
        break

def get_bucket_index(name: str) -> int:
    clean_name = name.replace(" ", "").replace("　", "")
    h = hashlib.md5(clean_name.encode("utf-8")).hexdigest()
    return int(h[:4], 16) % 256

def time_to_seconds(t_str):
    if not t_str: return 999999.0
    s = str(t_str).strip()
    if any(k in s.upper() for k in ["DQ", "DNS", "DNF", "未到", "棄權", "犯規"]):
        return 999999.0
    try:
        if ":" in s:
            p = s.split(":")
            if len(p) == 2: return float(p[0]) * 60 + float(p[1])
            elif len(p) == 3: return float(p[0]) * 3600 + float(p[1]) * 60 + float(p[2])
        return float(s)
    except:
        return 999999.0

MEET_ALIASES = {
    '青年盃': ['全青', '青年盃', '全國青年盃'],
    '中等學校運動會': ['全中運', '中運會'],
    '大專校院運動會': ['全大運', '大運會'],
    '全國運動會': ['全運會'],
    '分齡': ['分齡賽', '分齡盃', '全國分齡'],
    '總統盃': ['總統盃', '全總'],
    '短水道': ['短道賽', '短水道', '冬短'],
    '春季': ['春季盃', '春季賽'],
    '秋季': ['秋季盃', '秋季賽'],
    '冬季': ['冬季盃', '冬季賽'],
    '中小學': ['中小學', '中小學游泳錦標賽', '中小學春季', '中小學秋季'],
    '水運會': ['水運會', '小學水運會'],
}

def get_meet_aliases(meet_names):
    aliases = set()
    cities = ['台北', '新北', '桃園', '台中', '台南', '高雄', '基隆', '新竹', '嘉義', '彰化', '屏東', '宜蘭', '花蓮', '台東']
    for m in meet_names:
        norm = m.replace('臺', '台')
        found_city = ''
        for c in cities:
            if c in norm:
                found_city = c
                break
        for k, alias_list in MEET_ALIASES.items():
            if k in norm:
                for a in alias_list:
                    aliases.add(a)
                    if found_city:
                        aliases.add(f"{found_city}{a}")
                        aliases.add(f"{found_city}市{a}")
    return sorted(list(aliases))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 解析路徑與參數
        full_path = self.headers.get('x-matched-path', '') or self.path
        parsed = urllib.parse.urlparse(full_path)
        params = urllib.parse.parse_qs(parsed.query)
        
        # 支援 /athlete/:name 與 ?name=:name
        name = params.get("name", [""])[0].strip()
        if not name:
            path_parts = [p for p in parsed.path.split('/') if p]
            if len(path_parts) >= 2 and path_parts[0] in ("athlete", "athletes"):
                name = urllib.parse.unquote(path_parts[1].replace('.html', '')).strip()

        clean_name = name.replace(" ", "").replace("　", "")

        if not clean_name:
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"<h1>404 Not Found - Missing Swimmer Name</h1>")
            return

        bucket_idx = get_bucket_index(clean_name)
        bucket_file = os.path.join(BUCKETS_DIR, f"bucket_{bucket_idx:02x}.json.gz")

        records = []
        if os.path.exists(bucket_file):
            try:
                with gzip.open(bucket_file, "rb") as gf:
                    bucket_data = json.loads(gf.read().decode('utf-8'))
                swimmer_entry = bucket_data.get(clean_name, {})
                if isinstance(swimmer_entry, dict) and "records" in swimmer_entry:
                    records = swimmer_entry.get("records", [])
                elif isinstance(swimmer_entry, list):
                    records = swimmer_entry
            except Exception as e:
                pass

        if not records:
            # 查無此選手
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            not_found_html = f"""<!DOCTYPE html>
<html lang="zh-TW" class="dark">
<head>
    <meta charset="UTF-8">
    <title>查無選手【{clean_name}】成績｜金水台灣游泳資料庫</title>
    <meta name="robots" content="noindex, follow">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen flex flex-col items-center justify-center p-4">
    <div class="max-w-md text-center space-y-4">
        <h1 class="text-2xl font-bold text-amber-300">查無選手【{clean_name}】</h1>
        <p class="text-zinc-400 text-sm">官方資料庫尚未收錄此選手之個人出賽紀錄，或姓名有誤。</p>
        <a href="/" class="inline-block px-4 py-2 bg-amber-500 text-zinc-950 font-bold rounded-lg">回首頁查詢其他選手</a>
    </div>
</body>
</html>"""
            self.wfile.write(not_found_html.encode('utf-8'))
            return

        # 整理選手資訊
        gender = records[0].get("性別", "男") or "男"
        birth_year = records[0].get("出生年", "")
        units = list(dict.fromkeys([r.get("單位") for r in records if r.get("單位")]))
        primary_unit = units[0] if units else "台灣游泳俱樂部/學校"
        all_units_str = "、".join(units[:5])
        total_races = len(records)

        # 整理所有參與過的獨立賽事名稱（去除重複）
        all_meets = list(dict.fromkeys([r.get("賽事名稱") for r in records if r.get("賽事名稱")]))
        meets_highlight = "、".join(all_meets[:6])

        # 計算 Personal Best (PB)
        pb_dict = {}
        for r in records:
            item = r.get("項目", "") or ""
            score_str = r.get("成績", "") or ""
            sec = time_to_seconds(score_str)
            if sec < 999900.0:
                if item not in pb_dict or sec < pb_dict[item]["sec"]:
                    pb_dict[item] = {
                        "sec": sec,
                        "time_str": score_str,
                        "meet": r.get("賽事名稱", "") or "",
                        "year": str(r.get("年份", ""))[:4] if r.get("年份") else ""
                    }

        sorted_pbs = sorted(pb_dict.items(), key=lambda x: x[0])

        # 提取賽事簡稱 (如: 台南市中小學, 全青, 全中運, 青年盃, 分齡賽, 總統盃等)
        meet_aliases = get_meet_aliases(all_meets)
        aliases_highlight = f"（含 {', '.join(meet_aliases[:4])} 等簡稱）" if meet_aliases else ""

        # 構建 SEO 關鍵字與標題 (精準鎖定: 選手名 某賽事 或 選手名 簡稱 或 選手名 游泳)
        page_title = f"{clean_name} 游泳歷年成績與參賽紀錄{aliases_highlight}｜金水台灣游泳資料庫"
        meta_desc = f"{clean_name}（{primary_unit}）游泳歷年官方賽事成績總表。累計出賽 {total_races} 場，參賽涵蓋 {meets_highlight} 等重大賽事（含搜尋常用簡稱：{', '.join(meet_aliases[:8])}）。完整收錄五大泳姿個人最佳紀錄 (PB)、名次與泳隊歷程。"

        alias_keywords = [f"{clean_name} {a}" for a in meet_aliases[:12]]
        meet_keywords = [f"{clean_name} {m}" for m in all_meets[:8]]
        meta_keywords = f"{clean_name}, {clean_name} 游泳, {clean_name} 成績, {clean_name} PB, " + ", ".join(alias_keywords + meet_keywords)

        # Schema.org JSON-LD
        schema_json = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": clean_name,
            "jobTitle": "台灣游泳運動員 (Competitive Swimmer)",
            "description": meta_desc,
            "gender": "Male" if "男" in gender else "Female",
            "affiliation": {
                "@type": "SportsTeam",
                "name": primary_unit
            },
            "url": f"https://swimming-pwa.vercel.app/athlete/{urllib.parse.quote(clean_name)}",
            "mainEntityOfPage": f"https://swimming-pwa.vercel.app/?q={urllib.parse.quote(clean_name)}",
            "knowsAbout": all_meets[:15] + meet_aliases[:15] + ["個人最佳紀錄 (PB)", "自由式", "仰式", "蛙式", "蝶式", "混合式"]
        }

        # 渲染 PB 表格列
        pb_rows_html = ""
        for item, pb in sorted_pbs[:15]:
            pb_rows_html += f"""
            <tr class="border-b border-zinc-800/60 hover:bg-zinc-800/30 transition">
                <td class="py-3 px-4 text-zinc-100 font-semibold">{item}</td>
                <td class="py-3 px-4 font-mono font-bold text-amber-300 text-base">{pb['time_str']}</td>
                <td class="py-3 px-4 text-zinc-400 text-xs">{pb['year']} 年</td>
                <td class="py-3 px-4 text-zinc-400 text-xs hidden sm:table-cell">{pb['meet']}</td>
            </tr>
            """

        # 渲染賽事口語簡稱區塊 (Google 搜尋高頻命中關鍵字)
        alias_block_html = ""
        if meet_aliases:
            alias_badges = "".join([f'<span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/10 border border-amber-500/25 text-amber-300">{a}</span>' for a in meet_aliases])
            alias_block_html = f"""
            <div class="p-3.5 rounded-xl bg-amber-500/5 border border-amber-500/15 space-y-1.5">
                <div class="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                    <i class="fa-solid fa-tags text-xs"></i>
                    <span>出賽賽事口語簡稱（Google 搜尋常見關鍵字）</span>
                </div>
                <div class="flex flex-wrap gap-1.5 pt-1">
                    {alias_badges}
                </div>
            </div>
            """

        # 渲染參賽賽事標籤 (Meets Badges)
        meets_badges_html = ""
        for m in all_meets:
            meets_badges_html += f"""
            <span class="inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800/80 border border-zinc-700/80 text-zinc-200">
                <i class="fa-solid fa-award text-amber-400/80 mr-1.5 text-xs"></i>
                {m}
            </span>
            """

        # 渲染近期出賽前 60 筆
        history_rows_html = ""
        for r in records[:60]:
            y_str = str(r.get("年份", ""))
            if len(y_str) >= 4: y_str = y_str[:4]
            rank_display = f"第 {r.get('名次')} 名" if r.get('名次') and str(r.get('名次')).isdigit() else (r.get('名次') or "-")
            history_rows_html += f"""
            <tr class="border-b border-zinc-800/40 text-xs hover:bg-zinc-800/20">
                <td class="py-2.5 px-3 text-zinc-400 font-mono">{y_str}</td>
                <td class="py-2.5 px-3 text-zinc-300 font-medium">{r.get('賽事名稱', '-')}</td>
                <td class="py-2.5 px-3 text-zinc-200">{r.get('項目', '-')}</td>
                <td class="py-2.5 px-3 font-mono font-bold text-emerald-400">{r.get('成績', '-')}</td>
                <td class="py-2.5 px-3 text-zinc-400">{rank_display}</td>
                <td class="py-2.5 px-3 text-zinc-500 hidden md:table-cell">{r.get('單位', '-')}</td>
            </tr>
            """

        encoded_name = urllib.parse.quote(clean_name)

        full_html = f"""<!DOCTYPE html>
<html lang="zh-TW" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>{page_title}</title>
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="{meta_keywords}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://swimming-pwa.vercel.app/athlete/{encoded_name}">
    
    <!-- Open Graph -->
    <meta property="og:type" content="profile">
    <meta property="og:title" content="{clean_name} 游泳成績與參賽紀錄總表｜金水游泳">
    <meta property="og:description" content="{clean_name} 累計出賽 {total_races} 場，涵蓋 {meets_highlight} 等重大賽事。點擊開啟完整交互分析。">
    <meta property="og:url" content="https://swimming-pwa.vercel.app/athlete/{encoded_name}">
    <meta property="og:site_name" content="金水游泳成績查詢">
    
    <!-- Schema.org 結構化資料 (Person / Athlete) -->
    <script type="application/ld+json">
    {json.dumps(schema_json, ensure_ascii=False, indent=4)}
    </script>
    
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body {{ background-color: #09090b; color: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
        .gold-gradient-text {{
            background: linear-gradient(135deg, #ffffff 0%, #f3d078 50%, #d4af37 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
    </style>
</head>
<body class="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-between selection:bg-amber-500/30 selection:text-amber-200">
    <header class="sticky top-0 z-50 bg-zinc-900/80 backdrop-blur-md border-b border-zinc-800/80 px-4 py-3">
        <div class="max-w-4xl mx-auto flex items-center justify-between">
            <a href="/" class="flex items-center gap-2 text-zinc-200 hover:text-white transition">
                <span class="text-xl font-black gold-gradient-text">金水</span>
                <span class="text-xs text-zinc-400 font-medium">● 台灣游泳成績資料庫</span>
            </a>
            <a href="/?q={encoded_name}" class="px-3 py-1.5 rounded-lg bg-amber-400/10 hover:bg-amber-400/20 text-amber-300 border border-amber-400/30 text-xs font-semibold flex items-center gap-1.5 transition">
                <i class="fa-solid fa-chart-line"></i>
                <span>開啟 PWA 互動圖表</span>
            </a>
        </div>
    </header>

    <main class="max-w-4xl mx-auto px-4 py-8 flex-grow w-full space-y-8">
        <nav class="text-xs text-zinc-500 flex items-center gap-2">
            <a href="/" class="hover:text-zinc-300 transition">首頁</a>
            <span>/</span>
            <span class="text-zinc-400">選手個人賽事檔案</span>
            <span>/</span>
            <span class="text-amber-300/90 font-semibold">{clean_name}</span>
        </nav>

        <section class="p-6 rounded-2xl bg-zinc-900/50 border border-zinc-800 shadow-xl space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <div class="flex items-center gap-3">
                        <h1 class="text-3xl font-black gold-gradient-text tracking-tight">{clean_name}</h1>
                        <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-zinc-800 border border-zinc-700 text-zinc-300">{gender}</span>
                        {f'<span class="px-2.5 py-1 rounded-full text-xs font-mono bg-zinc-800/80 text-zinc-400">民國 {birth_year} 年次</span>' if birth_year else ''}
                    </div>
                    <p class="text-sm text-zinc-400 mt-1">代表所屬泳隊／學校：<strong class="text-zinc-200">{primary_unit}</strong> {f'（曾代表：{all_units_str}）' if len(units) > 1 else ''}</p>
                </div>
                <div class="flex items-center gap-2">
                    <a href="/?q={encoded_name}" class="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-600 text-zinc-950 font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20 hover:scale-[1.02] active:scale-[0.98] transition">
                        <i class="fa-solid fa-magnifying-glass"></i>
                        <span>在 PWA 中進行跨組排行與得獎模擬</span>
                    </a>
                </div>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                <div class="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800/80">
                    <div class="text-xs text-zinc-500">累計官方出賽</div>
                    <div class="text-xl font-bold font-mono text-zinc-100 mt-1">{total_races} <span class="text-xs font-normal text-zinc-400">場次</span></div>
                </div>
                <div class="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800/80">
                    <div class="text-xs text-zinc-500">主項最佳紀錄數</div>
                    <div class="text-xl font-bold font-mono text-amber-400 mt-1">{len(sorted_pbs)} <span class="text-xs font-normal text-zinc-400">項</span></div>
                </div>
                <div class="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800/80">
                    <div class="text-xs text-zinc-500">出賽涵蓋賽事數</div>
                    <div class="text-xl font-bold font-mono text-emerald-400 mt-1">{len(all_meets)} <span class="text-xs font-normal text-zinc-400">場重大賽事</span></div>
                </div>
                <div class="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800/80">
                    <div class="text-xs text-zinc-500">主要代表單位</div>
                    <div class="text-xs font-medium text-zinc-300 mt-1.5 truncate" title="{primary_unit}">{primary_unit}</div>
                </div>
            </div>
        </section>

        <!-- 歷年參賽賽事索引 (Google 搜尋命中專區) -->
        <section class="p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-3">
            <div class="flex items-center justify-between">
                <h2 class="text-base font-bold text-zinc-100 flex items-center gap-2">
                    <i class="fa-solid fa-calendar-check text-sky-400"></i>
                    <span>{clean_name} 歷年出賽官方賽事清單（共 {len(all_meets)} 場賽事）</span>
                </h2>
                <span class="text-xs text-zinc-500">含 CTSA / 全國各縣市官方賽事</span>
            </div>
            <!-- 口語簡稱專區 (如：台南市中小學、全青、全中運、分齡賽、青年盃) -->
            {alias_block_html}

            <div class="flex flex-wrap gap-2 pt-1">
                {meets_badges_html}
            </div>
        </section>

        <!-- 個人最佳 (Personal Best, PB) 總表 -->
        <section class="space-y-4">
            <div class="flex items-center justify-between">
                <h2 class="text-lg font-bold text-zinc-100 flex items-center gap-2">
                    <i class="fa-solid fa-trophy text-amber-400 text-sm"></i>
                    <span>{clean_name} 個人最佳成績 (PB) 總表</span>
                </h2>
                <span class="text-xs text-zinc-500 font-mono">官方賽事實體成績認證</span>
            </div>
            
            <div class="overflow-x-auto rounded-2xl bg-zinc-900/40 border border-zinc-800/80 shadow-lg">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="border-b border-zinc-800 bg-zinc-900/80 text-xs font-semibold text-zinc-400">
                            <th class="py-3 px-4">競賽項目</th>
                            <th class="py-3 px-4">個人最佳 (PB)</th>
                            <th class="py-3 px-4">創紀錄年份</th>
                            <th class="py-3 px-4 hidden sm:table-cell">締造賽事</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-zinc-800/40">
                        {pb_rows_html if pb_rows_html else '<tr><td colspan="4" class="p-4 text-center text-zinc-500">暫無 PB 紀錄</td></tr>'}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- 歷年出賽紀錄摘要 -->
        <section class="space-y-4">
            <div class="flex items-center justify-between">
                <h2 class="text-lg font-bold text-zinc-100 flex items-center gap-2">
                    <i class="fa-solid fa-list-check text-emerald-400 text-sm"></i>
                    <span>{clean_name} 歷年出賽明細摘要（前 60 場）</span>
                </h2>
                <a href="/?q={encoded_name}" class="text-xs text-amber-400 hover:underline">在 PWA 查看全部 {total_races} 場出賽 &rarr;</a>
            </div>

            <div class="overflow-x-auto rounded-2xl bg-zinc-900/40 border border-zinc-800/80 shadow-lg">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="border-b border-zinc-800 bg-zinc-900/80 text-xs font-semibold text-zinc-400">
                            <th class="py-2.5 px-3">年份</th>
                            <th class="py-2.5 px-3">賽事名稱</th>
                            <th class="py-2.5 px-3">項目</th>
                            <th class="py-2.5 px-3">成績</th>
                            <th class="py-2.5 px-3">名次</th>
                            <th class="py-2.5 px-3 hidden md:table-cell">代表單位</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-zinc-800/30">
                        {history_rows_html}
                    </tbody>
                </table>
            </div>
        </section>

        <section class="p-6 rounded-2xl bg-gradient-to-br from-zinc-900 to-zinc-950 border border-amber-500/20 text-center space-y-3">
            <h3 class="text-base font-bold text-zinc-100">想深入分析 {clean_name} 的同齡全國排名與得獎模擬？</h3>
            <p class="text-xs text-zinc-400 max-w-lg mx-auto">
                金水游泳查詢平台提供全台 85 萬筆大數據即時比對，包含各年齡組常模分佈、16 大賽事得獎模擬 (/SIM)、以及全中運/全大運官方標準檢定 (/STD)。
            </p>
            <div class="pt-2">
                <a href="/?q={encoded_name}" class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-100 hover:bg-white text-zinc-950 font-bold text-xs shadow-md transition">
                    <span>立即在 PWA 中開啟 {clean_name} 的完整戰績與同齡對手分析</span>
                    <i class="fa-solid fa-arrow-right"></i>
                </a>
            </div>
        </section>
    </main>

    <footer class="border-t border-zinc-800/80 bg-zinc-950 px-4 py-6 text-center text-xs text-zinc-600">
        <p>金水游泳查詢——一位泳者父親的池畔筆記｜全台泳者永久免費查閱</p>
        <p class="mt-1">收錄中華泳協 (CTSA)、臺北市、新北市、臺中市、臺南市、高雄市等全台各級游泳賽事官方成績</p>
    </footer>
</body>
</html>"""

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'public, max-age=3600, s-maxage=86400')
        self.end_headers()
        self.wfile.write(full_html.encode('utf-8'))

if __name__ == '__main__':
    # 本地測試模式
    from http.server import HTTPServer
    server = HTTPServer(('127.0.0.1', 8999), handler)
    print("Testing server running on http://127.0.0.1:8999")
    server.serve_forever()
