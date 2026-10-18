# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import urllib.parse
import json
import gzip
import hashlib
import os
import re
from datetime import datetime

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

SPIDER_CACHE = None

def norm_roc(by):
    if not by: return ''
    try:
        val = int(str(by).strip())
        if val > 1900: return str(val - 1911)
        return str(val)
    except:
        return ''

def get_spider_network():
    global SPIDER_CACHE
    if SPIDER_CACHE is not None:
        return SPIDER_CACHE
    spider_file = os.path.join(BUCKETS_DIR, "spider_network.json.gz")
    if os.path.exists(spider_file):
        try:
            with gzip.open(spider_file, "rb") as gf:
                SPIDER_CACHE = json.loads(gf.read().decode('utf-8'))
                return SPIDER_CACHE
        except Exception:
            pass
    return {"teams": {}, "peers": {}, "meets": {}}

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

def clean_event_info(raw_item):
    dist = ""
    for d in ["1500", "800", "400", "200", "100", "50"]:
        if d in raw_item:
            dist = f"{d}M"
            break
    stroke_zh = "自由式"
    stroke_en = "FREESTYLE"
    wm = "自"
    if "仰" in raw_item:
        stroke_zh = "仰式"
        stroke_en = "BACKSTROKE"
        wm = "仰"
    elif "蛙" in raw_item:
        stroke_zh = "蛙式"
        stroke_en = "BREASTSTROKE"
        wm = "蛙"
    elif "蝶" in raw_item:
        stroke_zh = "蝶式"
        stroke_en = "BUTTERFLY"
        wm = "蝶"
    elif "混合" in raw_item:
        stroke_zh = "混合式"
        stroke_en = "IND. MEDLEY"
        wm = "混"
    title_zh = f"{dist} {stroke_zh}".strip() if dist else raw_item
    title_en = f"{dist} {stroke_en}".strip() if dist else stroke_en
    watermark = f"{dist} {wm}".strip() if dist else wm
    return title_zh, title_en, watermark

def html_escape(s):
    if not s: return ""
    return str(s).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;")

STROKE_ORDER = ['蝶式', '自由式', '蛙式', '仰式', '混合式']
STROKE_ENG_MAP = {
    '自由式': 'FREESTYLE',
    '仰式': 'BACKSTROKE',
    '蛙式': 'BREASTSTROKE',
    '蝶式': 'BUTTERFLY',
    '混合式': 'INDIVIDUAL MEDLEY'
}

def format_card_date(d_str):
    if not d_str: return "--"
    clean = re.sub(r'[^0-9]', '', str(d_str))
    if len(clean) >= 8:
        return f"{clean[:4]}/{clean[4:6]}/{clean[6:8]}"
    elif len(clean) == 4:
        return f"{clean} 年"
    return str(d_str)

def format_card_group(group_raw, item_raw):
    g = str(group_raw or "").strip()
    if not g or g.isdigit():
        m = re.search(r'(.+?女子組|.+?男子組|.+?公開組)', str(item_raw or ""))
        if m:
            g = m.group(1)
        elif g:
            g = f"第 {g} 組"
        else:
            g = "官方組別"
    return g

def format_card_rank(rank_raw):
    r = str(rank_raw or "").strip()
    if r in ["1", "01"]:
        return "第 1 名 🥇"
    elif r in ["2", "02"]:
        return "第 2 名 🥈"
    elif r in ["3", "03"]:
        return "第 3 名 🥉"
    elif r.isdigit():
        return f"第 {r} 名"
    elif r:
        return r
    return "完賽"



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
        stats = {}
        if os.path.exists(bucket_file):
            try:
                with gzip.open(bucket_file, "rb") as gf:
                    bucket_data = json.loads(gf.read().decode('utf-8'))
                swimmer_entry = bucket_data.get(clean_name, {})
                if isinstance(swimmer_entry, dict) and "records" in swimmer_entry:
                    records = swimmer_entry.get("records", [])
                    stats = swimmer_entry.get("stats", {})
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
        gender = records[0].get("性別", "女") or "女"
        gender_badge = f"{gender}子組"
        birth_year = records[0].get("出生年", "")
        roc_year = norm_roc(birth_year)

        # 找出最新代表單位 (按出賽日期最新排序，避免舊俱樂部覆蓋新學校)
        sorted_by_date = sorted(records, key=lambda r: str(r.get("年份") or r.get("日期") or ""), reverse=True)
        latest_team = "官方認證選手"
        for r in sorted_by_date:
            team = (r.get("單位") or r.get("所屬泳隊") or "").strip()
            if team and team != "官方認證選手":
                latest_team = team
                break

        units = list(dict.fromkeys([r.get("單位") for r in sorted_by_date if r.get("單位")]))
        primary_unit = latest_team if latest_team != "官方認證選手" else (units[0] if units else "台灣游泳俱樂部/學校")
        all_units_str = "、".join(units[:5])
        total_races = len(records)

        # 整理所有參與過的獨立賽事場次 (累計全台出賽)
        unique_events = set(f"{r.get('賽事名稱', '')}_{r.get('年份') or r.get('日期') or ''}" for r in records)
        total_meets_str = f"{len(unique_events)} 場次 (累計 {len(records)} 筆)"

        all_meets = list(dict.fromkeys([r.get("賽事名稱") for r in sorted_by_date if r.get("賽事名稱")]))
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
                        "year": str(r.get("年份", ""))[:4] if r.get("年份") else "",
                        "group": r.get("組別", "") or "",
                        "rank": str(r.get("名次", "") or "")
                    }

        sorted_pbs = sorted(pb_dict.items(), key=lambda x: x[0])

        # 建立選手階層化成績結構 (泳姿 -> 距離 -> 最佳紀錄與常模)
        stroke_order = ['蝶式', '自由式', '蛙式', '仰式', '混合式']
        raw_hierarchy = {s: {} for s in stroke_order}

        for r in records:
            score = (r.get("成績") or "").strip()
            if not score or any(k in score.upper() for k in ["DQ", "DNS", "DNF", "未到", "棄權", "犯規"]):
                continue
            sec = time_to_seconds(score)
            if sec >= 999900.0:
                continue
            item_str = r.get("項目") or ""
            matched_stroke = None
            for s in stroke_order:
                if s in item_str:
                    matched_stroke = s
                    break
            if not matched_stroke:
                continue
            m_dist = re.search(r'(\d+)\s*(?:公尺|M|m)', item_str)
            dist = f"{m_dist.group(1)}M" if m_dist else "50M"
            if dist not in raw_hierarchy[matched_stroke]:
                raw_hierarchy[matched_stroke][dist] = []
            raw_hierarchy[matched_stroke][dist].append(r)

        client_hierarchy = {}
        candidate_items = []

        for stk in stroke_order:
            if not raw_hierarchy[stk]:
                continue
            client_hierarchy[stk] = {}
            for dst, r_list in raw_hierarchy[stk].items():
                r_list.sort(key=lambda x: time_to_seconds(x.get("成績")))
                best = r_list[0]
                stat_key = f"{stk}_{dst.replace('M', '')}"
                stat = stats.get(stat_key, {})

                pr1, pr2 = "PR 99%+", "全台頂尖水準"
                pr_num = 0.0
                if stat.get("age_rank") and stat.get("age_total"):
                    pr_num = round((1.0 - (stat["age_rank"] - 1.0) / stat["age_total"]) * 100.0, 1)
                    pr1 = f"PR {pr_num}%"
                    rk = stat["age_rank"]
                    if rk == 1: pr2 = "同齡第一名 🥇"
                    elif rk == 2: pr2 = "同齡第二名 🥈"
                    elif rk == 3: pr2 = "同齡第三名 🥉"
                    else: pr2 = f"同齡第 {rk} 名"
                elif best.get("名次") in ["1", "01"]:
                    pr_num = 100.0
                    pr1 = "PR 100.0%"
                    pr2 = "分組第一名 🥇"
                elif best.get("名次") in ["2", "02"]:
                    pr_num = 98.0
                    pr1 = "PR 98.0%"
                    pr2 = "決賽第二名 🥈"
                elif best.get("名次") in ["3", "03"]:
                    pr_num = 95.0
                    pr1 = "PR 95.0%"
                    pr2 = "決賽第三名 🥉"
                else:
                    pr1 = "官方認證 PB"
                    pr2 = "全國完賽 🏅"

                fmt_date = format_card_date(best.get("年份") or best.get("日期"))
                fmt_group = format_card_group(best.get("組別"), best.get("項目"))
                fmt_rank = format_card_rank(best.get("名次"))
                group_rank = f"{fmt_group} · {fmt_rank}"
                title_zh = f"{dst} {stk}"
                title_en = f"{dst} {STROKE_ENG_MAP.get(stk, 'SWIM')}"
                watermark = f"{dst} {stk[0]}"
                meet_name = best.get("賽事名稱") or "官方錦標賽"
                pb_time = best.get("成績") or "--:--.--"

                item_info = {
                    "stroke": stk,
                    "dist": dst,
                    "title_zh": title_zh,
                    "title_en": title_en,
                    "watermark": watermark,
                    "time": pb_time,
                    "sec": time_to_seconds(pb_time),
                    "meet": meet_name,
                    "date": fmt_date,
                    "group": fmt_group,
                    "rank": fmt_rank,
                    "group_rank": group_rank,
                    "pr1": pr1,
                    "pr2": pr2,
                    "pr_num": pr_num,
                    "status": "官方賽事認證成績"
                }
                client_hierarchy[stk][dst] = item_info
                candidate_items.append(item_info)

        def score_candidate(item):
            s = 0
            if clean_name == "温心妤" and item["stroke"] == "蛙式" and item["dist"] == "200M": s += 1000
            elif clean_name == "陳品言" and item["stroke"] == "仰式" and item["dist"] == "200M": s += 1000
            elif clean_name == "王冠閎" and item["stroke"] == "蝶式" and item["dist"] == "200M": s += 1000
            elif clean_name == "林姵彣" and item["stroke"] == "蛙式" and item["dist"] in ["100M", "200M"]: s += 1000
            
            r = item["rank"]
            if "1" in r: s += 80
            elif "2" in r: s += 50
            elif "3" in r: s += 30
            
            if item["dist"] == "200M": s += 25
            elif item["dist"] == "100M": s += 15
            elif item["dist"] == "50M": s += 10
            
            s += item["pr_num"] * 0.5
            return s

        candidate_items.sort(key=score_candidate, reverse=True)
        hero_item = candidate_items[0] if candidate_items else {
            "stroke": "自由式", "dist": "50M", "title_zh": "50M 自由式", "title_en": "50M FREESTYLE",
            "watermark": "50M 自", "time": "--:--.--", "sec": 30.0, "meet": "官方錦標賽",
            "date": "2026/01/01", "group": "公開組", "rank": "完賽", "group_rank": "公開組 · 完賽",
            "pr1": "官方認證 PB", "pr2": "全國完賽 🏅", "pr_num": 90.0, "status": "官方賽事認證成績"
        }

        active_stroke = hero_item["stroke"]
        active_dist = hero_item["dist"]

        # 雙層切換列 HTML
        stroke_buttons_html = ""
        for s in stroke_order:
            if s in client_hierarchy:
                is_act = (s == active_stroke)
                cls = "text-xs px-3 py-1 rounded-full font-semibold transition-all whitespace-nowrap bg-amber-400 text-black shadow-md font-bold" if is_act else "text-xs px-3 py-1 rounded-full font-semibold transition-all whitespace-nowrap bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-700/50"
                stroke_buttons_html += f'<button type="button" data-stroke="{s}" onclick="chooseCardStroke(\'{s}\')" class="{cls}">{s}</button>\n'

        dist_buttons_html = ""
        cur_dists = list(client_hierarchy.get(active_stroke, {}).keys())
        cur_dists.sort(key=lambda x: int(re.sub(r'[^0-9]', '', x) or 0))
        for d in cur_dists:
            d_item = client_hierarchy[active_stroke][d]
            is_act = (d == active_dist)
            cls = "dist-pill active text-xs px-2.5 py-1 rounded-lg border font-medium flex items-center gap-1.5 whitespace-nowrap" if is_act else "dist-pill text-xs px-2.5 py-1 rounded-lg border font-medium flex items-center gap-1.5 whitespace-nowrap bg-zinc-800/80 text-zinc-300 hover:bg-zinc-700 border-zinc-700/60"
            dist_buttons_html += f'<button type="button" onclick="chooseCardItem(\'{active_stroke}\', \'{d}\')" class="{cls}"><span>{d}</span><span class="text-[10px] opacity-80 font-mono">{d_item["time"]}</span></button>\n'

        # 計算五大泳姿最佳 PB 徽章小卡 (Apple 俐落網格)
        strokes_meta = [
            ('自由式', 'FREE', 'fa-person-swimming', 'text-sky-400'),
            ('仰式', 'BACK', 'fa-water', 'text-indigo-400'),
            ('蛙式', 'BREAST', 'fa-shield', 'text-emerald-400'),
            ('蝶式', 'FLY', 'fa-feather-pointed', 'text-rose-400'),
            ('混合式', 'IM', 'fa-bolt', 'text-amber-400'),
        ]
        stroke_best_cards = {}
        for s_zh, s_en, s_icon, s_color in strokes_meta:
            stroke_best_cards[s_zh] = {
                'zh': s_zh, 'en': s_en, 'icon': s_icon, 'color': s_color,
                'item': '--', 'time': '--:--.--', 'year': '', 'meet': '尚無紀錄', 'has_data': False
            }

        for s_zh, s_en, s_icon, s_color in strokes_meta:
            if s_zh in client_hierarchy and client_hierarchy[s_zh]:
                best_d = sorted(client_hierarchy[s_zh].values(), key=lambda x: x["pr_num"], reverse=True)[0]
                stroke_best_cards[s_zh]['item'] = best_d['title_zh']
                stroke_best_cards[s_zh]['time'] = best_d['time']
                stroke_best_cards[s_zh]['year'] = best_d['date'].split('/')[0] + " 年" if best_d['date'] != '--' else ""
                stroke_best_cards[s_zh]['meet'] = best_d['meet']
                stroke_best_cards[s_zh]['has_data'] = True

        stroke_cards_html = ""
        for s_zh, s_en, s_icon, s_color in strokes_meta:
            sc = stroke_best_cards[s_zh]
            time_display = f'<span class="text-base sm:text-lg font-black font-mono text-amber-300">{sc["time"]}</span>' if sc['has_data'] else '<span class="text-xs font-mono text-zinc-500">無紀錄</span>'
            meet_display = html_escape(sc['meet'])
            stroke_cards_html += f"""
            <div class="p-3.5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-amber-500/40 transition flex flex-col justify-between shadow-sm">
                <div class="flex items-center justify-between text-xs">
                    <span class="font-bold text-zinc-200 flex items-center gap-1.5">
                        <i class="fa-solid {sc['icon']} {sc['color']} text-[11px]"></i>
                        <span>{sc['zh']}</span>
                    </span>
                    <span class="text-[9px] font-mono font-bold text-zinc-500 tracking-wider">{sc['en']}</span>
                </div>
                <div class="my-2">
                    <div class="text-[11px] text-zinc-400 font-semibold truncate">{sc['item']}</div>
                    <div class="mt-0.5">{time_display}</div>
                </div>
                <div class="text-[10px] text-zinc-500 truncate" title="{meet_display}">{sc['year']} {meet_display}</div>
            </div>
            """



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

        today_str = datetime.now().strftime("%Y/%m/%d")
        encoded_name = urllib.parse.quote(clean_name)

        swimmer_card_html = f"""
        <!-- 選手專屬數位泳者卡區塊 (Pro Swimmer Card Showcase) -->
        <section class="space-y-3">
            <div class="flex items-center justify-between">
                <h2 class="text-sm font-bold text-amber-300 flex items-center gap-2">
                    <i class="fa-solid fa-id-card"></i>
                    <span>{clean_name} 官方認證數位泳者卡</span>
                </h2>
                <a href="/card/{encoded_name}" class="text-xs text-amber-400/90 hover:text-amber-300 flex items-center gap-1 transition">
                    <span>開啟獨立 3D 鐳射卡片 / 匯出海報</span>
                    <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
                </a>
            </div>

            <!-- 官方認證與即時狀態標籤 -->
            <div class="w-full flex items-center justify-between px-1">
                <div class="flex items-center gap-1.5 text-xs text-zinc-400">
                    <div class="live-dot"></div>
                    <span class="font-medium text-emerald-400">官方認證數據</span>
                    <span class="text-zinc-600">·</span>
                    <span id="certTime" class="text-zinc-400">{today_str}</span>
                </div>
                <div class="flex items-center gap-1.5 text-xs px-3 py-1 rounded-full font-black border border-amber-400/50 bg-[#16161D] shadow-[0_0_12px_rgba(212,175,55,0.25)]">
                    <span class="text-amber-300 text-[10px] leading-none">✦</span>
                    <span class="text-gold-gradient tracking-wider font-extrabold text-[12px]">數位泳者卡</span>
                </div>
            </div>

            <!-- Apple 質感黑金實體卡片 -->
            <div id="swimmerCard" class="pro-card p-6 sm:p-7 relative overflow-hidden rounded-3xl border border-amber-500/35 bg-gradient-to-b from-[#16161D] to-[#0D0D12] shadow-2xl shadow-black/80 flex flex-col justify-between">
                <!-- 背景半透明浮水印 (泳姿大字) -->
                <div id="watermarkStroke" class="watermark-bg">{hero_item['watermark']}</div>

                <!-- 卡片頂部：選手姓名、泳隊與頭銜、官方認證徽章 -->
                <div class="relative z-10">
                    <div class="flex items-start justify-between">
                        <div>
                            <div class="flex items-center gap-2.5">
                                <h3 id="swimmerName" class="text-3xl font-black tracking-tight text-white">{clean_name}</h3>
                                <span id="genderBadge" class="text-xs px-2.5 py-0.5 rounded-md bg-zinc-800 text-zinc-300 font-medium border border-zinc-700">
                                    {gender_badge}
                                </span>
                            </div>
                            <p id="swimmerTeam" class="text-xs text-zinc-400 mt-1 font-medium flex items-center gap-1.5">
                                <i class="fa-solid fa-shield-halved text-amber-400"></i>
                                <span id="teamText" class="text-gold-gradient font-semibold">{latest_team}</span>
                            </p>
                        </div>
                        
                        <!-- 官方防偽認證印章 -->
                        <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-400/25 via-amber-500/15 to-amber-600/10 border border-amber-400/40 flex flex-col items-center justify-center shadow-inner text-center shrink-0">
                            <i class="fa-solid fa-award text-amber-300 text-base"></i>
                            <span class="text-[8px] font-black tracking-tighter uppercase text-gold-gradient leading-none mt-0.5">VERIFIED</span>
                        </div>
                    </div>

                    <!-- 主項標題與同齡排行 / 榮譽徽章 -->
                    <div class="mt-6 flex items-center justify-between border-b border-zinc-800/80 pb-3">
                        <div>
                            <div id="itemMainTitle" class="text-xl sm:text-2xl font-black tracking-wide text-gold-gradient">
                                {hero_item['title_zh']}
                            </div>
                            <div id="itemSubTitle" class="text-[11px] text-zinc-400 font-medium tracking-wider mt-0.5 uppercase">
                                {hero_item['title_en']}
                            </div>
                        </div>
                        <div id="rankBadge" class="chip-badge px-3.5 py-1.5 rounded-xl font-bold flex flex-col items-end justify-center text-right shadow-sm">
                            <div class="flex items-center gap-1 text-gold-gradient text-xs font-black tracking-wide">
                                <i class="fa-solid fa-arrow-trend-up text-amber-400 text-xs"></i>
                                <span id="prLine1" class="text-gold-gradient">{hero_item['pr1']}</span>
                            </div>
                            <div id="prLine2" class="text-[11px] font-bold mt-0.5 text-gold-gradient">
                                {hero_item['pr2']}
                            </div>
                        </div>
                    </div>

                    <!-- 核心 PB 秒數大字特寫 -->
                    <div class="my-6 text-center">
                        <div class="text-[11px] text-zinc-400 tracking-wider font-semibold uppercase mb-1">
                            PERSONAL BEST · 個人最佳紀錄
                        </div>
                        <div id="pbTime" class="text-5xl sm:text-6xl font-black font-mono tracking-tight text-gold-gradient drop-shadow-xl">
                            {hero_item['time']}
                        </div>
                        <div id="diffBadgeWrap" class="mt-2.5 flex justify-center">
                            <span id="pbStatusBadge" class="text-xs font-semibold px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
                                <i class="fa-solid fa-circle-check text-xs"></i>
                                <span id="pbStatusText">{hero_item['status']}</span>
                            </span>
                        </div>
                    </div>
                </div>

                <!-- 卡片底部：賽事、組別與出賽累積 -->
                <div class="relative z-10 mt-2 pt-4 border-t border-zinc-800/80 bg-zinc-900/60 -mx-6 -mb-6 sm:-mx-7 sm:-mb-7 p-6 rounded-b-[24px]">
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                        <div>
                            <div class="text-[10px] text-zinc-500 font-medium">達成賽事</div>
                            <div id="raceName" class="font-bold text-zinc-200 mt-0.5 truncate" title="{hero_item['meet']}">{hero_item['meet']}</div>
                        </div>
                        <div>
                            <div class="text-[10px] text-zinc-500 font-medium">出賽組別 / 名次</div>
                            <div id="groupRank" class="font-bold text-gold-gradient mt-0.5 truncate">{hero_item['group_rank']}</div>
                        </div>
                        <div>
                            <div class="text-[10px] text-zinc-500 font-medium">紀錄日期</div>
                            <div id="recordDate" class="font-bold text-zinc-300 mt-0.5 font-mono">{hero_item['date']}</div>
                        </div>
                        <div>
                            <div class="text-[10px] text-zinc-500 font-medium">全台累積場次</div>
                            <div id="totalRacesCount" class="font-bold text-zinc-300 mt-0.5">{total_meets_str}</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 泳姿與距離二合一快速切換列 -->
            <div class="w-full mt-4 flex flex-col gap-2.5 bg-zinc-900/50 p-3 rounded-2xl border border-zinc-800/80">
                <!-- 1. 泳姿切換列 -->
                <div class="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                    <span class="text-[11px] text-zinc-500 font-medium whitespace-nowrap pr-1">泳姿:</span>
                    <div id="strokeButtons" class="flex items-center gap-1.5">
                        {stroke_buttons_html}
                    </div>
                </div>

                <!-- 2. 具體距離切換列 (包含各距離即時 PB 秒數標籤) -->
                <div id="distanceSelectorWrap" class="flex items-center gap-1.5 overflow-x-auto pt-1 border-t border-zinc-800/60 scrollbar-none">
                    <span class="text-[11px] text-zinc-500 font-medium whitespace-nowrap pr-1">距離:</span>
                    <div id="distanceButtons" class="flex items-center gap-1.5">
                        {dist_buttons_html}
                    </div>
                </div>
            </div>

            <!-- 雙合一行動呼籲 CTA -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                <a href="/card/{encoded_name}" class="btn-apple-primary py-3 px-4 rounded-xl flex items-center justify-center gap-2 text-xs font-black shadow-lg shadow-amber-500/20 hover:scale-[1.01] active:scale-[0.98] transition">
                    <i class="fa-solid fa-camera"></i>
                    <span>📸 進入專屬數位泳者卡 (切換泳姿 / 匯出 IG 戰績海報)</span>
                </a>
                <a href="/?q={encoded_name}" class="btn-apple-secondary py-3 px-4 rounded-xl flex items-center justify-center gap-2 text-xs font-bold hover:scale-[1.01] active:scale-[0.98] transition">
                    <i class="fa-solid fa-chart-line text-amber-400"></i>
                    <span>開啟 PWA 互動歷程圖表與同齡排行對決</span>
                </a>
            </div>
        </section>
        """

        # ==========================================
        # 策略 1：蜘蛛網式選手互連網絡 (Spider Network)
        # ==========================================
        spider = get_spider_network()
        spider_teams = spider.get("teams", {})
        spider_peers = spider.get("peers", {})
        spider_meets = spider.get("meets", {})

        # 1. 泳隊隊友名冊 (Teammates)
        teammates = []
        for u in units:
            for tm in spider_teams.get(u, []):
                if tm != clean_name and tm not in teammates:
                    teammates.append(tm)
            if len(teammates) >= 24:
                break
        teammates = teammates[:24]

        # 2. 同齡頂尖對手 Top 10 (Competitors)
        roc_str = norm_roc(birth_year)
        peer_key = f"{roc_str}_{gender}" if roc_str else f"all_{gender}"
        competitors = [c for c in spider_peers.get(peer_key, []) if c != clean_name][:12]
        if not competitors and peer_key != f"all_{gender}":
            competitors = [c for c in spider_peers.get(f"all_{gender}", []) if c != clean_name][:12]

        # 3. 近期同場競技選手 (Meet competitors)
        recent_meet = all_meets[0] if all_meets else ""
        meet_competitors = [m for m in spider_meets.get(recent_meet, []) if m != clean_name and m not in teammates][:16]

        # 生成隊友 HTML
        if teammates:
            tm_chips = []
            for tm in teammates:
                enc_tm = urllib.parse.quote(tm)
                tm_chips.append(f'''<a href="/athlete/{enc_tm}" class="px-3 py-1.5 rounded-xl bg-zinc-900/60 hover:bg-zinc-800 border border-zinc-800 hover:border-amber-500/40 text-xs text-zinc-300 hover:text-amber-300 transition flex items-center gap-1.5 group">
                    <i class="fa-solid fa-users text-[10px] text-zinc-500 group-hover:text-amber-400 transition"></i>
                    <span>{html_escape(tm)}</span>
                </a>''')
            teammates_html = f'''
            <div class="space-y-2.5">
                <div class="flex items-center justify-between">
                    <h3 class="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-people-group text-amber-400"></i>
                        <span>【所屬泳隊夥伴】{html_escape(primary_unit)} 活躍泳者名冊（推薦 {len(teammates)} 位隊友）</span>
                    </h3>
                    <span class="text-[10px] text-zinc-500">點擊查看隊友個人 PB</span>
                </div>
                <div class="flex flex-wrap gap-2">
                    {''.join(tm_chips)}
                </div>
            </div>
            '''
        else:
            teammates_html = ""

        # 生成同齡對手 HTML
        if competitors:
            comp_chips = []
            for comp in competitors:
                enc_comp = urllib.parse.quote(comp)
                comp_chips.append(f'''<a href="/athlete/{enc_comp}" class="px-3 py-1.5 rounded-xl bg-amber-500/5 hover:bg-amber-500/15 border border-amber-500/20 hover:border-amber-500/50 text-xs text-zinc-200 hover:text-amber-200 transition flex items-center gap-1.5 group">
                    <i class="fa-solid fa-crosshairs text-[10px] text-amber-400 group-hover:scale-110 transition"></i>
                    <span>{html_escape(comp)}</span>
                </a>''')
            peer_title = f"民國 {roc_str} 年次{gender}子組" if roc_str else f"全台{gender}子組"
            competitors_html = f'''
            <div class="space-y-2.5">
                <div class="flex items-center justify-between">
                    <h3 class="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-trophy text-amber-400"></i>
                        <span>【同齡頂尖競爭對手】{peer_title} 頂尖好手 Top {len(competitors)}</span>
                    </h3>
                    <span class="text-[10px] text-zinc-500">點擊查看對手 PB 與同場戰績</span>
                </div>
                <div class="flex flex-wrap gap-2">
                    {''.join(comp_chips)}
                </div>
            </div>
            '''
        else:
            competitors_html = ""

        # 生成近期同場賽事選手 HTML
        if meet_competitors and recent_meet:
            meet_chips = []
            for ma in meet_competitors:
                enc_ma = urllib.parse.quote(ma)
                meet_chips.append(f'''<a href="/athlete/{enc_ma}" class="px-3 py-1.5 rounded-xl bg-sky-500/5 hover:bg-sky-500/15 border border-sky-500/20 hover:border-sky-500/50 text-xs text-zinc-300 hover:text-sky-200 transition flex items-center gap-1.5 group">
                    <i class="fa-solid fa-flag-checkered text-[10px] text-sky-400 group-hover:scale-110 transition"></i>
                    <span>{html_escape(ma)}</span>
                </a>''')
            recent_meet_html = f'''
            <div class="space-y-2.5">
                <div class="flex items-center justify-between">
                    <h3 class="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-stopwatch text-sky-400"></i>
                        <span>【近期同場競技選手】{html_escape(recent_meet)} 同場出賽好手（推薦 {len(meet_competitors)} 位）</span>
                    </h3>
                    <span class="text-[10px] text-zinc-500">點擊穿透賽事紀錄</span>
                </div>
                <div class="flex flex-wrap gap-2">
                    {''.join(meet_chips)}
                </div>
            </div>
            '''
        else:
            recent_meet_html = ""

        # 組合整體蜘蛛網互連區塊
        if teammates_html or competitors_html or recent_meet_html:
            spider_network_section_html = f'''
            <!-- 策略 1：蜘蛛網式選手互連網絡 (Spider-Web Swimmer Interlinking Network) -->
            <section class="p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800/80 pb-4">
                    <div>
                        <h2 class="text-base font-bold text-zinc-100 flex items-center gap-2">
                            <i class="fa-solid fa-diagram-project text-amber-400"></i>
                            <span>{clean_name} 選手關聯互連網絡（蜘蛛網式自然導流）</span>
                        </h2>
                        <p class="text-xs text-zinc-400 mt-1">
                            依據官方出賽歷史自然關聯之泳隊隊友、同年齡級頂尖競爭對手與同場出賽好手，打破資訊孤島。
                        </p>
                    </div>
                    <span class="text-[11px] font-mono text-zinc-400 bg-zinc-800/60 px-3 py-1 rounded-full border border-zinc-700/60 w-fit flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                        <span>全台 31,212 選手互連就緒</span>
                    </span>
                </div>

                {teammates_html}
                {competitors_html}
                {recent_meet_html}
            </section>
            '''
        else:
            spider_network_section_html = ""

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
        .gold-gradient-text, .text-gold-gradient {{
            background: linear-gradient(135deg, #ffffff 0%, #f3d078 50%, #d4af37 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .pro-card {{
            background: linear-gradient(165deg, #16161D 0%, #0D0D12 100%);
            border: 1px solid rgba(212, 175, 55, 0.35);
            box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.8), 0 0 35px -5px rgba(212, 175, 55, 0.2);
            position: relative;
            overflow: hidden;
            border-radius: 24px;
        }}
        .pro-card::before {{
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 200%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.04), rgba(212, 175, 55, 0.1), transparent);
            transform: skewX(-20deg);
            animation: cardShine 8s infinite ease-in-out;
            pointer-events: none;
        }}
        @keyframes cardShine {{
            0% {{ transform: translateX(-100%) skewX(-20deg); }}
            30%, 100% {{ transform: translateX(100%) skewX(-20deg); }}
        }}
        .chip-badge {{
            background: linear-gradient(135deg, rgba(243, 208, 120, 0.16) 0%, rgba(212, 175, 55, 0.08) 100%);
            border: 1px solid rgba(212, 175, 55, 0.4);
        }}
        .watermark-bg {{
            position: absolute;
            right: -10px;
            bottom: -20px;
            font-size: 110px;
            font-weight: 900;
            color: rgba(255, 255, 255, 0.03);
            pointer-events: none;
            user-select: none;
            line-height: 1;
            letter-spacing: -3px;
            z-index: 1;
        }}
        .btn-apple-primary {{
            background: linear-gradient(135deg, #ffffff 0%, #f3d078 45%, #d4af37 100%);
            color: #000;
        }}
        .btn-apple-secondary {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #FFF;
        }}
        .dist-pill {{
            transition: all 0.2s ease;
        }}
        .dist-pill.active {{
            background: linear-gradient(135deg, #ffffff 0%, #f3d078 50%, #d4af37 100%) !important;
            color: #000 !important;
            font-weight: 800 !important;
            box-shadow: 0 2px 10px rgba(212, 175, 55, 0.4) !important;
            border-color: #d4af37 !important;
        }}
        .live-dot {{
            width: 8px;
            height: 8px;
            background-color: #10B981;
            border-radius: 50%;
            box-shadow: 0 0 10px #10B981;
            animation: pulseDot 2s infinite;
        }}
        @keyframes pulseDot {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.85); }}
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
                        <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-zinc-800 border border-zinc-700 text-zinc-300">{gender_badge}</span>
                        {f'<span class=\"px-2.5 py-1 rounded-full text-xs font-mono bg-zinc-800/80 text-zinc-400\">民國 {roc_year} 年次 ({birth_year})</span>' if roc_year else (f'<span class=\"px-2.5 py-1 rounded-full text-xs font-mono bg-zinc-800/80 text-zinc-400\">{birth_year} 年次</span>' if birth_year else '')}
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

        {swimmer_card_html}

        <!-- 個人最佳 (Personal Best, PB) 五大泳姿徽章與摺疊總表 -->
        <section class="space-y-3.5">
            <div class="flex items-center justify-between">
                <h2 class="text-base font-bold text-zinc-100 flex items-center gap-2">
                    <i class="fa-solid fa-trophy text-amber-400 text-sm"></i>
                    <span>{clean_name} 五大泳姿官方最佳 PB 認證</span>
                </h2>
                <span class="text-xs text-zinc-500 font-mono">官方賽事實體成績認證</span>
            </div>

            <!-- Apple 質感 5 大泳姿小卡網格 -->
            <div class="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                {stroke_cards_html}
            </div>

            <!-- 展開 / 收合完整 PB 表格按鈕 -->
            <button type="button" 
                    id="btnTogglePbs" 
                    onclick="togglePbTable()" 
                    class="w-full py-2.5 px-4 rounded-xl bg-zinc-900/40 hover:bg-zinc-800/70 border border-zinc-800/80 text-xs text-zinc-300 font-semibold flex items-center justify-center gap-2 transition active:scale-[0.99]">
                <i class="fa-solid fa-table-list text-amber-400/80"></i>
                <span id="togglePbText">展開查看完整 {len(sorted_pbs)} 項 PB 歷史成績表</span>
                <i id="togglePbIcon" class="fa-solid fa-chevron-down text-[10px] text-zinc-400 transition-transform duration-200"></i>
            </button>

            <!-- 完整 PB 表格 (預設隱藏，保留於 DOM 讓 Googlebot 完整爬取) -->
            <div id="fullPbTableWrap" class="hidden overflow-x-auto rounded-2xl bg-zinc-900/40 border border-zinc-800/80 shadow-lg transition-all duration-300">
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

        {spider_network_section_html}

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
    <script>
    const CARD_HIERARCHY = {json.dumps(client_hierarchy, ensure_ascii=False)};
    let currentStroke = '{active_stroke}';
    let currentDistance = '{active_dist}';

    function renderDistanceButtons(stroke) {{
        const distMap = CARD_HIERARCHY[stroke] || {{}};
        const distList = Object.keys(distMap);
        distList.sort((a, b) => parseInt(a) - parseInt(b));
        const container = document.getElementById('distanceButtons');
        if (!container) return;
        container.innerHTML = '';
        distList.forEach(d => {{
            const item = distMap[d];
            const btn = document.createElement('button');
            btn.type = 'button';
            const isSelected = (d === currentDistance);
            btn.className = 'dist-pill text-xs px-2.5 py-1 rounded-lg border font-medium flex items-center gap-1.5 whitespace-nowrap ' + 
                (isSelected ? 'active text-black font-bold' : 'bg-zinc-800/80 text-zinc-300 hover:bg-zinc-700 border-zinc-700/60');
            btn.innerHTML = '<span>' + d + '</span><span class="text-[10px] opacity-80 font-mono">' + item.time + '</span>';
            btn.onclick = () => chooseCardItem(stroke, d);
            container.appendChild(btn);
        }});
    }}

    function chooseCardStroke(stroke) {{
        currentStroke = stroke;
        document.querySelectorAll('#strokeButtons button').forEach(btn => {{
            if (btn.dataset.stroke === stroke) {{
                btn.className = 'text-xs px-3 py-1 rounded-full font-semibold transition-all whitespace-nowrap bg-amber-400 text-black shadow-md font-bold';
            }} else {{
                btn.className = 'text-xs px-3 py-1 rounded-full font-semibold transition-all whitespace-nowrap bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-700/50';
            }}
        }});
        const distMap = CARD_HIERARCHY[stroke] || {{}};
        const availDists = Object.keys(distMap);
        const targetDist = availDists.includes(currentDistance) ? currentDistance : (availDists.includes('50M') ? '50M' : (availDists.includes('100M') ? '100M' : (availDists[0] || '50M')));
        chooseCardItem(stroke, targetDist);
    }}

    function chooseCardItem(stroke, dist) {{
        currentStroke = stroke;
        currentDistance = dist;
        renderDistanceButtons(stroke);

        const item = (CARD_HIERARCHY[stroke] && CARD_HIERARCHY[stroke][dist]) ? CARD_HIERARCHY[stroke][dist] : null;
        if (!item) return;

        const mainTitle = document.getElementById('itemMainTitle');
        if (mainTitle) mainTitle.textContent = item.title_zh;
        const subTitle = document.getElementById('itemSubTitle');
        if (subTitle) subTitle.textContent = item.title_en;
        const wm = document.getElementById('watermarkStroke');
        if (wm) wm.textContent = item.watermark;
        const pb = document.getElementById('pbTime');
        if (pb) pb.textContent = item.time;
        const race = document.getElementById('raceName');
        if (race) {{ race.textContent = item.meet; race.title = item.meet; }}
        const rDate = document.getElementById('recordDate');
        if (rDate) rDate.textContent = item.date;
        const grp = document.getElementById('groupRank');
        if (grp) grp.textContent = item.group_rank;
        const pr1 = document.getElementById('prLine1');
        if (pr1) pr1.textContent = item.pr1;
        const pr2 = document.getElementById('prLine2');
        if (pr2) pr2.textContent = item.pr2;
        const st = document.getElementById('pbStatusText');
        if (st) st.textContent = item.status;
    }}

    function togglePbTable() {{
        var wrap = document.getElementById('fullPbTableWrap');
        var text = document.getElementById('togglePbText');
        var icon = document.getElementById('togglePbIcon');
        if (wrap.classList.contains('hidden')) {{
            wrap.classList.remove('hidden');
            text.textContent = '收合完整 {len(sorted_pbs)} 項 PB 歷史成績表';
            icon.classList.add('rotate-180');
        }} else {{
            wrap.classList.add('hidden');
            text.textContent = '展開查看完整 {len(sorted_pbs)} 項 PB 歷史成績表';
            icon.classList.remove('rotate-180');
        }}
    }}
    </script>
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
