# -*- coding: utf-8 -*-
# Tự sinh index.html cho bản đồ bưu cục GHN (chạy bởi GitHub Action mỗi ngày).
#  - Toạ độ + địa chỉ cũ: KML Google My Maps (công khai)
#  - Trạng thái hoạt động: data-gateway nội bộ (token qua env GHN_DATA_TOKEN)
#  - Địa chỉ MỚI 2026: bảng tra ma->địa chỉ mới (diachi-moi-map.json, đã point-in-polygon sẵn)
#  - Tô màu theo 6 VÙNG kinh tế-xã hội: gán _rg cho mỗi bưu cục theo tỉnh CŨ (tinh-vung.json),
#    ranh giới vùng vẽ từ polygon tĩnh (vung-6.geojson). Template tách riêng ở template.html.
import os, sys, json, re
import html as _html
import urllib.request
import xml.etree.ElementTree as ET

MID="1p0y8EJ18YIuYJumMUTc1yArTaGm2Fcc"
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

def http_get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":UA}), timeout=120).read()
def http_post_json(url, payload, headers):
    h={"Content-Type":"application/json","User-Agent":UA,"Accept":"application/json"}; h.update(headers)
    req=urllib.request.Request(url, data=json.dumps(payload).encode(), headers=h, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=120).read())

LABELS=["Mã vận hành:","Tỉnh/thành phố:","Quận/huyện:","Phường/xã:","Số nhà, đường:","Vị trí:","Vĩ độ:","Kinh độ:"]
def clean(s):
    s=_html.unescape(s or ""); s=re.sub(r"<[^>]*>"," ",s); return re.sub(r"\s+"," ",s).strip()
def field(desc,label):
    i=desc.find(label)
    if i==-1: return ""
    st=i+len(label); en=len(desc)
    for L in LABELS:
        if L!=label:
            k=desc.find(L,st)
            if k!=-1 and k<en: en=k
    return desc[st:en].strip()

ns="{http://www.opengis.net/kml/2.2}"
kml=http_get("https://www.google.com/maps/d/kml?mid=%s&forcekml=1" % MID).decode("utf-8")
kml_by_ma={}
for pm in ET.fromstring(kml).iter(ns+"Placemark"):
    name=(pm.findtext(ns+"name") or "").strip()
    desc=clean(pm.findtext(ns+"description") or "")
    c=pm.find(".//"+ns+"coordinates")
    co=(c.text.strip() if (c is not None and c.text) else "")
    parts=co.split(",")
    if len(parts)<2: continue
    ma=field(desc,"Mã vận hành:")
    if not ma: continue
    kml_by_ma[ma]={"ten":name,"tinh":field(desc,"Tỉnh/thành phố:"),"huyen":field(desc,"Quận/huyện:"),
        "phuong":field(desc,"Phường/xã:"),"diachi":field(desc,"Số nhà, đường:") or field(desc,"Vị trí:"),
        "lng":parts[0],"lat":parts[1]}

res=http_post_json(GATEWAY, {"endpoint":"buu-cuc-ghn","limit":6000}, {"Authorization":"Bearer "+TOKEN})
api=res.get("data") or []
active={str(r["warehouse_id"]) for r in api if r.get("is_enabled") and r.get("status_hrw")==1}

try: dmap=json.load(open(DIACHI_MAP, encoding="utf-8"))
except Exception as e: print("WARN: không đọc được %s (%s) -> địa chỉ mới rỗng" % (DIACHI_MAP,e), file=sys.stderr); dmap={}

# Bảng tỉnh CŨ -> vùng (6 vùng). Bắt buộc phải có: nếu thiếu, bưu cục sẽ bị tô xám.
try: t2r=json.load(open(TINH_VUNG, encoding="utf-8"))
except Exception as e: print("ERROR: không đọc được %s (%s)" % (TINH_VUNG,e), file=sys.stderr); sys.exit(1)

feats=[]
unmapped=set()
for ma,k in kml_by_ma.items():
    if ma not in active: continue
    try: lng=float(k["lng"]); lat=float(k["lat"])
    except: continue
    m=dmap.get(ma)
    rg=t2r.get(k["tinh"],"")
    if k["tinh"] and not rg: unmapped.add(k["tinh"])
    feats.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lng,lat]},
        "properties":{"ma":ma,"ten":k["ten"],"tinh":k["tinh"],"huyen":k["huyen"],"phuong":k["phuong"],
            "tinh_moi":(m["tinh"] if m else ""),"phuong_moi":(m["phuong"] if m else ""),
            "diachi":k["diachi"],"_rg":rg}})

if len(feats)<500:
    print("ERROR: chỉ %d BC, nghi nguồn lỗi -> hủy build" % len(feats), file=sys.stderr); sys.exit(1)
if unmapped:
    print("WARN: %d tỉnh chưa có trong %s (bưu cục bị tô xám): %s"
          % (len(unmapped), TINH_VUNG, ", ".join(sorted(unmapped))), file=sys.stderr)

fc={"type":"FeatureCollection","features":feats}
geojson_min=json.dumps(fc, ensure_ascii=False, separators=(",",":"))
prov_min=open(VUNG_GEOJSON, encoding="utf-8").read().strip()
total=len(feats)
new_cnt=sum(1 for f in feats if f["properties"]["tinh_moi"])
with_rg=sum(1 for f in feats if f["properties"]["_rg"])
print("BC active: %d | có địa chỉ mới: %d | có vùng: %d" % (total,new_cnt,with_rg))

tpl=open(TEMPLATE, encoding="utf-8").read()
html = (tpl.replace("__GEOJSON__", geojson_min)
           .replace("__PROV__", prov_min)
           .replace("__TOTAL__", "{:,}".format(total).replace(",", ".")))
open(OUT,"w",encoding="utf-8").write(html)
print("Wrote %s (%d bytes)" % (OUT, len(html)))
