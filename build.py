# -*- coding: utf-8 -*-
# Tự sinh index.html cho bản đồ bưu cục GHN (chạy bởi GitHub Action mỗi ngày).
# Nguồn DUY NHẤT: API data-gateway GHN (token qua env GHN_DATA_TOKEN) — đã bỏ Google My Maps (bị 403).
#   - Toạ độ + địa chỉ CŨ (tỉnh/huyện/phường): lấy thẳng từ gateway.
#   - Địa chỉ MỚI 2026: bảng tra warehouse_id -> địa chỉ mới (diachi-moi-map.json).
#   - Tô màu 6 VÙNG: gán _rg theo tỉnh CŨ (tinh-vung.json); ranh giới vùng từ vung-6.geojson.
# Template tách riêng ở template.html.
import os, sys, json, urllib.request

TOKEN=os.environ.get("GHN_DATA_TOKEN","").strip()
OUT=os.environ.get("OUT","index.html")
DIACHI_MAP=os.environ.get("DIACHI_MAP","diachi-moi-map.json")
TINH_VUNG=os.environ.get("TINH_VUNG","tinh-vung.json")
VUNG_GEOJSON=os.environ.get("VUNG_GEOJSON","vung-6.geojson")
TEMPLATE=os.environ.get("TEMPLATE","template.html")
GATEWAY="https://app.ghn.studio/api/data-gateway/query"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
if not TOKEN:
    print("ERROR: thiếu GHN_DATA_TOKEN", file=sys.stderr); sys.exit(1)

def post(payload):
    h={"Content-Type":"application/json","User-Agent":UA,"Accept":"application/json","Authorization":"Bearer "+TOKEN}
    req=urllib.request.Request(GATEWAY, data=json.dumps(payload).encode(), headers=h, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=120).read())

rows=(post({"endpoint":"buu-cuc-ghn","limit":6000}).get("data") or [])
print("Gateway trả:", len(rows), "bản ghi")

def valid_coord(r):
    try: la=float(r["latitude"]); lo=float(r["longitude"])
    except (TypeError,ValueError): return None
    if 8.0<=la<=24.0 and 102.0<=lo<=115.0:   # trong khung đất liền + đảo VN
        return [lo,la]
    return None

def is_kho(r):
    # GHN gắn cả kho hàng nặng/B2B/sorting là type BC -> loại bằng section_name + tên
    sec=(r.get("section_name") or "")
    nm=(r.get("warehouse_name") or "")
    if any(x in sec for x in ("B2B","Freight","Sorting")): return True
    if nm.startswith("Kho") or nm.startswith("(KHO)") or nm.startswith("(Kho"): return True
    return False

# Bảng tỉnh CŨ -> vùng (bắt buộc). Bảng tra địa chỉ mới (không bắt buộc).
try: t2r=json.load(open(TINH_VUNG, encoding="utf-8"))
except Exception as e: print("ERROR: không đọc được %s (%s)"%(TINH_VUNG,e), file=sys.stderr); sys.exit(1)
try: dmap=json.load(open(DIACHI_MAP, encoding="utf-8"))
except Exception as e: print("WARN: không đọc được %s (%s) -> địa chỉ mới rỗng"%(DIACHI_MAP,e), file=sys.stderr); dmap={}

feats=[]; unmapped=set()
for r in rows:
    if r.get("warehouse_type")!="BC" or r.get("is_virtual"): continue
    if not (r.get("is_enabled") and r.get("status_hrw")==1): continue
    co=valid_coord(r)
    if not co: continue
    if is_kho(r): continue
    tinh=(r.get("province_name") or "").strip()
    huyen=(r.get("district_name") or "").strip()
    phuong=(r.get("ward_name") or "").strip()
    ten=(r.get("warehouse_name") or "").strip()
    diachi=", ".join(x for x in (phuong,huyen,tinh) if x)   # địa chỉ cũ 3 cấp (warehouse_address bị che ***)
    rg=t2r.get(tinh,"")
    if tinh and not rg: unmapped.add(tinh)
    m=dmap.get(str(r.get("warehouse_id")))
    feats.append({"type":"Feature","geometry":{"type":"Point","coordinates":co},
        "properties":{"ma":str(r.get("warehouse_id")),"ten":ten,"tinh":tinh,"huyen":huyen,"phuong":phuong,
            "tinh_moi":(m["tinh"] if m else ""),"phuong_moi":(m["phuong"] if m else ""),
            "diachi":diachi,"_rg":rg}})

if len(feats)<500:
    print("ERROR: chỉ %d BC, nghi nguồn lỗi -> hủy build"%len(feats), file=sys.stderr); sys.exit(1)
if unmapped:
    print("WARN: tỉnh chưa map vùng (bị tô xám): %s"%", ".join(sorted(unmapped)), file=sys.stderr)

fc={"type":"FeatureCollection","features":feats}
geojson_min=json.dumps(fc, ensure_ascii=False, separators=(",",":"))
prov_min=open(VUNG_GEOJSON, encoding="utf-8").read().strip()
total=len(feats)
new_cnt=sum(1 for f in feats if f["properties"]["tinh_moi"])
with_rg=sum(1 for f in feats if f["properties"]["_rg"])
print("BC hiển thị: %d | có địa chỉ mới: %d | có vùng: %d"%(total,new_cnt,with_rg))

tpl=open(TEMPLATE, encoding="utf-8").read()
html=(tpl.replace("__GEOJSON__", geojson_min)
         .replace("__PROV__", prov_min)
         .replace("__TOTAL__", "{:,}".format(total).replace(",", ".")))
open(OUT,"w",encoding="utf-8").write(html)
print("Wrote %s (%d bytes)"%(OUT,len(html)))
