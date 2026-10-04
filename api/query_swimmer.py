# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import urllib.parse
import json
import gzip
import hashlib
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 兼容地端、專案根目錄與 Vercel Serverless 打包路徑
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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        name = params.get("name", [""])[0].strip()
        birth = params.get("birth", [""])[0].strip()
        sex = params.get("sex", [""])[0].strip()
        
        clean_name = name.replace(" ", "").replace("　", "")
        
        if not clean_name:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing name parameter"}, ensure_ascii=False).encode('utf-8'))
            return
            
        bucket_idx = get_bucket_index(clean_name)
        bucket_file = os.path.join(BUCKETS_DIR, f"bucket_{bucket_idx:02x}.json.gz")
        
        if not os.path.exists(bucket_file):
            self.send_response(404)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Bucket not found"}, ensure_ascii=False).encode('utf-8'))
            return
            
        try:
            with gzip.open(bucket_file, "rb") as gf:
                bucket_data = json.loads(gf.read().decode('utf-8'))
                
            swimmer_entry = bucket_data.get(clean_name, {})
            if isinstance(swimmer_entry, dict) and "records" in swimmer_entry:
                records = swimmer_entry.get("records", [])
                stats = swimmer_entry.get("stats", {})
            else:
                records = swimmer_entry if isinstance(swimmer_entry, list) else []
                stats = {}
            
            # 過濾出生年或性別（若有指定）
            if birth:
                records = [r for r in records if str(r.get("出生年", "")).strip() == str(birth).strip()]
            if sex:
                records = [r for r in records if str(r.get("性別", "")).strip() == str(sex).strip()]
                
            # 統計所有可選出生年
            all_records_for_name = swimmer_entry.get("records", []) if isinstance(swimmer_entry, dict) else (swimmer_entry if isinstance(swimmer_entry, list) else [])
            all_birth_years = sorted(list(set(str(r.get("出生年", "")).strip() for r in all_records_for_name if r.get("出生年"))))
            
            response_data = {
                "name": clean_name,
                "total": len(records),
                "birth_years": all_birth_years,
                "stats": stats,
                "scores": records
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
