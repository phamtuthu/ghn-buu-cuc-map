# -*- coding: utf-8 -*-
# Chỉ để DÒ schema API gateway (chạy tay qua workflow_dispatch). Không ghi index.html.
import os, sys, json, urllib.request
from collections import Counter

TOKEN=os.environ.get("GHN_DATA_TOKEN","").strip()
GATEWAY="https://app.ghn.studio/api/data-gateway/query"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
if not TOKEN: print("ERROR: thiếu GHN_DATA_TOKEN", file=sys.stderr); sys.exit(1)

def post(payload):
    h={"Content-Type":"application/json","User-Agent":UA,"Accept":"application/json","Authorization":"Bearer "+TOKEN}
    req=urllib.request.Request(GATEWAY, data=json.dumps(payload).encode(), headers=h, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=120).read())

res=post({"endpoint":"buu-cuc-ghn","limit":6000})
rows=res.get("data") or []
print("TỔNG bản ghi:", len(rows))
if not rows: print("res keys:", list(res.keys())); sys.exit(1)

r0=rows[0]
print("\n=== KEYS bản ghi đầu ===")
print(sorted(r0.keys()))
print("\n=== MẪU 2 bản ghi (rút gọn) ===")
for r in rows[:2]:
    print(json.dumps({k:r[k] for k in r}, ensure_ascii=False)[:1500])

def dist(field, n=80):
    c=Counter(str(r.get(field)) for r in rows)
    print("\n=== %s: %d giá trị khác nhau ===" % (field, len(c)))
    for v,cnt in c.most_common(n): print("  %5d  %s" % (cnt, v))

for f in ["warehouse_type","is_virtual","is_enabled","status_hrw"]:
    if f in r0: dist(f, 20)

# toạ độ
latk = next((k for k in ["latitude","lat","lat_","warehouse_latitude"] if k in r0), None)
lngk = next((k for k in ["longitude","lng","lon","warehouse_longitude"] if k in r0), None)
print("\nField toạ độ đoán: lat=%s lng=%s" % (latk,lngk))

# địa chỉ / tỉnh / huyện / phường
addr_like=[k for k in r0 if any(x in k.lower() for x in ["province","district","ward","address","region","tinh","huyen","phuong","name"])]
print("Field liên quan địa chỉ/vùng:", addr_like)

if "province_name" in r0: dist("province_name", 80)
if "region_shortname" in r0: dist("region_shortname", 30)

# đối chiếu province_name với tinh-vung.json
try:
    t2r=json.load(open("tinh-vung.json",encoding="utf-8"))
    provs={str(r.get("province_name")) for r in rows if r.get("province_name")}
    inmap=[p for p in provs if p in t2r]
    notin=[p for p in provs if p not in t2r]
    print("\n=== ĐỐI CHIẾU province_name vs tinh-vung.json (63 tỉnh cũ) ===")
    print("Khớp: %d / %d tỉnh" % (len(inmap), len(provs)))
    print("KHÔNG khớp (%d):" % len(notin), sorted(notin))
except Exception as e:
    print("skip đối chiếu:", e)
