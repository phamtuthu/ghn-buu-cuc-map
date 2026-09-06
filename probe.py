# -*- coding: utf-8 -*-
# Chỉ để DÒ + DUMP dữ liệu gateway (chạy tay qua workflow_dispatch). Không ghi index.html.
import os, sys, json, urllib.request

TOKEN=os.environ.get("GHN_DATA_TOKEN","").strip()
GATEWAY="https://app.ghn.studio/api/data-gateway/query"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
if not TOKEN: print("ERROR: thiếu GHN_DATA_TOKEN", file=sys.stderr); sys.exit(1)

def post(payload):
    h={"Content-Type":"application/json","User-Agent":UA,"Accept":"application/json","Authorization":"Bearer "+TOKEN}
    req=urllib.request.Request(GATEWAY, data=json.dumps(payload).encode(), headers=h, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=120).read())

rows=(post({"endpoint":"buu-cuc-ghn","limit":6000}).get("data") or [])
print("TỔNG bản ghi:", len(rows))

KEEP=["warehouse_id","warehouse_name","warehouse_address","warehouse_type","is_enabled","is_virtual",
      "status_hrw","latitude","longitude","province_name","district_name","ward_name","ward_code",
      "region_shortname","section_name"]
dump=[{k:r.get(k) for k in KEEP} for r in rows]
json.dump(dump, open("gateway-dump.json","w",encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
print("Đã ghi gateway-dump.json:", len(dump), "bản ghi")
