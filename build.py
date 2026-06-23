# -*- coding: utf-8 -*-
# Tự sinh index.html cho bản đồ bưu cục GHN (chạy bởi GitHub Action mỗi ngày).
#  - Toạ độ + địa chỉ cũ: KML Google My Maps (công khai)
#  - Trạng thái hoạt động: data-gateway nội bộ (token qua env GHN_DATA_TOKEN)
#  - Địa chỉ MỚI 2025: bảng tra ma->địa chỉ mới (diachi-moi-map.json, đã point-in-polygon sẵn)
import os, sys, json, re
import html as _html
import urllib.request
import xml.etree.ElementTree as ET

MID="1p0y8EJ18YIuYJumMUTc1yArTaGm2Fcc"
TOKEN=os.environ.get("GHN_DATA_TOKEN","").strip()
OUT=os.environ.get("OUT","index.html")
DIACHI_MAP=os.environ.get("DIACHI_MAP","diachi-moi-map.json")
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

feats=[]
for ma,k in kml_by_ma.items():
    if ma not in active: continue
    try: lng=float(k["lng"]); lat=float(k["lat"])
    except: continue
    m=dmap.get(ma)
    feats.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lng,lat]},
        "properties":{"ma":ma,"ten":k["ten"],"tinh":k["tinh"],"huyen":k["huyen"],"phuong":k["phuong"],"diachi":k["diachi"],
            "tinh_moi":(m["tinh"] if m else ""),"phuong_moi":(m["phuong"] if m else "")}})

if len(feats)<500:
    print("ERROR: chỉ %d BC, nghi nguồn lỗi -> hủy build" % len(feats), file=sys.stderr); sys.exit(1)

fc={"type":"FeatureCollection","features":feats}
provs_old=sorted({f["properties"].get("tinh","") for f in feats if f["properties"].get("tinh")}, key=lambda s:s.lower())
provs_new=sorted({f["properties"].get("tinh_moi","") for f in feats if f["properties"].get("tinh_moi")}, key=lambda s:s.lower())
geojson_min=json.dumps(fc, ensure_ascii=False, separators=(",",":"))
provs_old_js=json.dumps(provs_old, ensure_ascii=False)
provs_new_js=json.dumps(provs_new, ensure_ascii=False)
total=len(feats)
new_cnt=sum(1 for f in feats if f["properties"]["tinh_moi"])
print("BC active: %d | có địa chỉ mới: %d | tỉnh cũ: %d | tỉnh mới: %d" % (total,new_cnt,len(provs_old),len(provs_new)))

TPL = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Bản đồ bưu cục GHN</title>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  :root{ --ghn:#f47920; --ghn-dark:#e8521e; --ink:#1f2430; --muted:#7a8190; --line:#eceef2; }
  *{ box-sizing:border-box; }
  html,body{ margin:0; height:100%; font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; color:var(--ink); }
  #app{ display:flex; height:100%; }
  #side{ width:380px; min-width:380px; height:100%; display:flex; flex-direction:column; background:#fff; border-right:1px solid var(--line); z-index:2; }
  .head{ padding:18px 20px 14px; border-bottom:1px solid var(--line); }
  .brand{ display:flex; align-items:center; gap:10px; }
  .logo{ width:34px; height:34px; border-radius:9px; background:var(--ghn); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:15px; letter-spacing:.5px; }
  .title{ font-size:17px; font-weight:700; }
  .subtitle{ font-size:12px; color:var(--muted); margin-top:2px; }
  .note{ font-size:11px; color:#b03a2e; margin-top:6px; font-weight:600; }
  .controls{ padding:14px 20px; display:flex; flex-direction:column; gap:10px; border-bottom:1px solid var(--line); }
  .controls select, .controls input{ width:100%; padding:10px 12px; border:1px solid #dfe3ea; border-radius:10px; font-size:14px; outline:none; background:#fff; color:var(--ink); }
  .controls select:focus, .controls input:focus{ border-color:var(--ghn); box-shadow:0 0 0 3px rgba(244,121,32,.15); }
  .row-btns{ display:flex; gap:8px; align-items:stretch; }
  .btn{ flex:1; padding:10px 10px; border:1px solid #dfe3ea; border-radius:10px; background:#fff; cursor:pointer; font-size:13px; font-weight:700; color:var(--ink); }
  .btn:hover{ border-color:var(--ghn); }
  .btn.primary{ background:var(--ghn); color:#fff; border-color:var(--ghn); }
  .btn.primary:hover{ background:var(--ghn-dark); }
  .seg{ display:flex; border:1px solid #dfe3ea; border-radius:10px; overflow:hidden; flex:0 0 auto; }
  .seg button{ padding:0 14px; border:0; background:#fff; cursor:pointer; font-size:13px; font-weight:600; color:var(--muted); }
  .seg button.on{ background:var(--ink); color:#fff; }
  .controls select:disabled{ background:#f4f5f7; color:#aab2c0; cursor:not-allowed; }
  .count{ font-size:13px; color:var(--muted); padding:10px 20px 6px; }
  .count b{ color:var(--ghn-dark); }
  #list{ flex:1; overflow:auto; padding:0 10px 10px; }
  .item{ padding:11px 12px; border-radius:10px; cursor:pointer; border:1px solid transparent; }
  .item:hover{ background:#fff7f1; border-color:#ffe2cc; }
  .item.active{ background:#fff2e8; border-color:var(--ghn); }
  .item .nm{ font-size:14px; font-weight:600; line-height:1.3; }
  .item .ad{ font-size:12.5px; color:var(--muted); margin-top:3px; line-height:1.35; }
  .item .mc{ font-size:11.5px; color:var(--ghn-dark); font-weight:600; margin-top:3px; }
  #map{ flex:1; height:100%; position:relative; }
  .maplibregl-popup-content{ padding:14px 16px; border-radius:12px; max-width:280px; box-shadow:0 6px 24px rgba(0,0,0,.16); line-height:1.5; }
  .pop-nm{ font-weight:700; margin:0 0 6px; font-size:14px; }
  .pop-ad{ margin:0; color:#444; font-size:13px; }
  .pop-dir{ display:inline-flex; align-items:center; gap:6px; margin-top:11px; font-size:13px; font-weight:700; color:var(--ghn-dark); text-decoration:none; }
  .pop-dir:hover{ text-decoration:underline; }
  @media (max-width:768px){
    #app{ flex-direction:column; }
    #side{ width:100%; min-width:0; height:48%; border-right:none; border-bottom:1px solid var(--line); }
    #map{ height:52%; }
  }
</style>
</head>
<body>
<div id="app">
  <aside id="side">
    <div class="head">
      <div class="brand">
        <div class="logo">GHN</div>
        <div>
          <div class="title">Hệ thống bưu cục GHN</div>
          <div class="subtitle">__TOTAL__ bưu cục trên toàn quốc</div>
        </div>
      </div>
      <div class="note">Quần đảo Hoàng Sa &amp; Trường Sa thuộc chủ quyền Việt Nam</div>
    </div>
    <div class="controls">
      <select id="prov"><option value="">Tất cả tỉnh / thành phố</option></select>
      <select id="ward" disabled><option value="">Tất cả phường / xã</option></select>
      <input id="q" type="search" placeholder="Tìm theo tên hoặc địa chỉ bưu cục…"/>
      <div class="row-btns">
        <button id="near" class="btn primary">📍 Bưu cục gần tôi</button>
        <div class="seg"><button id="bLight" class="on">Sáng</button><button id="bDark">Tối</button></div>
      </div>
      <div class="row-btns">
        <span style="font-size:13px;color:var(--muted);align-self:center;">Địa chỉ:</span>
        <div class="seg" style="flex:1;"><button id="aOld" class="on" style="flex:1;">Cũ</button><button id="aNew" style="flex:1;">Mới (2025)</button></div>
      </div>
    </div>
    <div class="count">Đang hiển thị <b id="cnt">0</b> bưu cục</div>
    <div id="list"></div>
  </aside>
  <div id="map"></div>
</div>

<script>
const DATA = __GEOJSON__;
const PROVINCES_OLD = __PROVINCES_OLD__;
const PROVINCES_NEW = __PROVINCES_NEW__;
const ALL = DATA.features;
let addrMode = "cu";   // "cu" = địa chỉ cũ (3 cấp), "moi" = địa chỉ mới 2025 (2 cấp)
function provOf(p){ return addrMode==="moi" ? (p.tinh_moi||"") : (p.tinh||""); }
function wardKeyOf(p){ return addrMode==="moi" ? (p.phuong_moi||"") : ((p.huyen||"")+"|||"+(p.phuong||"")); }
function wardLabelOf(p){ return addrMode==="moi" ? (p.phuong_moi||"") : ((p.phuong||"") + (p.huyen? " — "+p.huyen : "")); }

// ==== NỀN BẢN ĐỒ (MapTiler vector — Hoàng Sa/Trường Sa tiếng Việt) ====
const MAPTILER_KEY = "RsMVLUahBV8V4aHHyxoJ";
const STYLES = {
  light: `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_KEY}`,
  dark:  `https://api.maptiler.com/maps/streets-v2-dark/style.json?key=${MAPTILER_KEY}`
};

const ISLANDS = { type:"FeatureCollection", features:[
  { type:"Feature", geometry:{type:"Point",coordinates:[112.0,16.5]}, properties:{ten:"Quần đảo Hoàng Sa", thuoc:"TP. Đà Nẵng, Việt Nam"} },
  { type:"Feature", geometry:{type:"Point",coordinates:[112.7,9.6]},  properties:{ten:"Quần đảo Trường Sa", thuoc:"Tỉnh Khánh Hòa, Việt Nam"} }
]};

const GHN_ICON = "data:image/png;base64,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";
const VIEW_VN = { center:[109.6,14.6], zoom:4.55 };
const map = new maplibregl.Map({ container:"map", style:STYLES.light, center:VIEW_VN.center, zoom:VIEW_VN.zoom, attributionControl:true });
map.addControl(new maplibregl.NavigationControl({visualizePitch:false}), "top-right");
map.addControl(new maplibregl.FullscreenControl(), "top-right");
const geo = new maplibregl.GeolocateControl({ positionOptions:{enableHighAccuracy:true}, trackUserLocation:true });
map.addControl(geo, "top-right");

// Nạp logo GHN làm icon marker (giữ được khi đổi nền)
let _ghnImg=null;
function _ensureGhn(){ try{ if(_ghnImg && map.isStyleLoaded() && !map.hasImage("ghn")){ map.addImage("ghn", _ghnImg); map.triggerRepaint && map.triggerRepaint(); } }catch(e){} }
(function(){ const im=new Image(); im.onload=()=>{ _ghnImg=im; _ensureGhn(); }; im.src=GHN_ICON; })();
map.on("styleimagemissing", e=>{ if(e.id==="ghn") _ensureGhn(); });
map.on("load", _ensureGhn);
map.on("idle", _ensureGhn);

const popup = new maplibregl.Popup({ offset:14, closeButton:true, maxWidth:"300px" });
function popHTML(p, c){
  const dir = c ? `<a class="pop-dir" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${c[1]},${c[0]}">🧭 Chỉ đường</a>` : "";
  const oldLine = [p.phuong, p.huyen, p.tinh].filter(Boolean).join(", ");
  const newLine = [p.phuong_moi, p.tinh_moi].filter(Boolean).join(", ") || "(chưa có)";
  const primary = addrMode==="moi" ? newLine : oldLine;
  const secLab  = addrMode==="moi" ? "Địa chỉ cũ" : "Địa chỉ mới (2025)";
  const secVal  = addrMode==="moi" ? oldLine : newLine;
  return `<div>
    <p class="pop-nm">${p.ten||""}</p>
    <p class="pop-ad">${p.diachi||""}<br><b>${primary}</b></p>
    <p style="font-size:11.5px;color:#8a93a3;margin:6px 0 0;">${secLab}: ${secVal}</p>
    ${dir}</div>`;
}

// ==== Thêm các lớp dữ liệu (idempotent — gọi lại được sau khi đổi nền) ====
function addOverlays(){
  if(!map.getSource("islands")) map.addSource("islands", { type:"geojson", data:ISLANDS });
  if(!map.getLayer("island-dot")) map.addLayer({ id:"island-dot", type:"circle", source:"islands",
    paint:{ "circle-radius":5, "circle-color":"#c0392b", "circle-stroke-width":2, "circle-stroke-color":"#fff" }});
  if(!map.getLayer("island-label")) map.addLayer({ id:"island-label", type:"symbol", source:"islands",
    layout:{ "text-field":["concat",["get","ten"],"\n",["get","thuoc"]], "text-font":["Noto Sans Bold"],
             "text-size":12, "text-offset":[0,1.1], "text-anchor":"top", "text-allow-overlap":true },
    paint:{ "text-color":"#e74c3c", "text-halo-color":"#ffffff", "text-halo-width":1.8 }});

  if(!map.getSource("bc")) map.addSource("bc", { type:"geojson", data:{type:"FeatureCollection",features:current.length?current:ALL}, cluster:true, clusterMaxZoom:13, clusterRadius:55 });
  // nguồn điểm thô (không gom cụm) — riêng cho heatmap mật độ
  if(!map.getSource("bc-all")) map.addSource("bc-all", { type:"geojson", data:{type:"FeatureCollection",features:current.length?current:ALL} });
  // Heatmap mô phỏng mật độ — đậm ở mức zoom xa, mờ dần khi zoom gần (đặt dưới các marker)
  if(!map.getLayer("heat")) map.addLayer({ id:"heat", type:"heatmap", source:"bc-all", maxzoom:12,
    paint:{
      "heatmap-weight":["interpolate",["linear"],["zoom"], 4,0.7, 11,1],
      "heatmap-intensity":["interpolate",["linear"],["zoom"], 4,1.1, 8,1.8, 11,3],
      "heatmap-radius":["interpolate",["linear"],["zoom"], 4,16, 7,26, 9,34, 12,48],
      "heatmap-opacity":["interpolate",["linear"],["zoom"], 4,0.72, 9.5,0.62, 12,0],
      "heatmap-color":["interpolate",["linear"],["heatmap-density"],
        0,"rgba(59,82,139,0)", 0.15,"rgba(59,82,139,0.55)", 0.4,"rgb(33,145,140)",
        0.65,"rgb(94,201,98)", 0.85,"rgb(180,222,44)", 1,"rgb(253,231,37)"]
    }}, "island-dot");
  if(!map.getLayer("clusters")) map.addLayer({ id:"clusters", type:"circle", source:"bc", filter:["has","point_count"],
    paint:{ "circle-color":["step",["get","point_count"], "#FFC78A", 25, "#F89B3F", 120, "#EA5B22"],
            "circle-radius":["step",["get","point_count"], 15, 25, 21, 120, 29],
            "circle-stroke-width":4, "circle-stroke-color":"rgba(244,121,32,.28)" }});
  if(!map.getLayer("cluster-count")) map.addLayer({ id:"cluster-count", type:"symbol", source:"bc", filter:["has","point_count"],
    layout:{ "text-field":["get","point_count_abbreviated"], "text-font":["Noto Sans Bold"], "text-size":13 },
    paint:{ "text-color":"#fff" }});
  // zoom xa: chấm nhỏ
  if(!map.getLayer("point-dot")) map.addLayer({ id:"point-dot", type:"circle", source:"bc", filter:["!",["has","point_count"]], maxzoom:14,
    paint:{ "circle-color":"#f47920", "circle-radius":6, "circle-stroke-width":2, "circle-stroke-color":"#fff" }});
  // zoom gần (>=14): logo GHN
  if(!map.getLayer("point")) map.addLayer({ id:"point", type:"symbol", source:"bc", filter:["!",["has","point_count"]], minzoom:14,
    layout:{ "icon-image":"ghn", "icon-size":0.26, "icon-allow-overlap":true, "icon-ignore-placement":true, "icon-anchor":"center" }});
  _ensureGhn();
}

// ==== Tương tác (đăng ký 1 lần — vẫn chạy sau khi đổi nền vì gắn theo id layer) ====
map.on("click","clusters",(e)=>{
  const f=map.queryRenderedFeatures(e.point,{layers:["clusters"]})[0];
  map.getSource("bc").getClusterExpansionZoom(f.properties.cluster_id).then(z=>map.easeTo({ center:f.geometry.coordinates, zoom:z }));
});
const onPointClick=(e)=>{ const f=e.features[0]; popup.setLngLat(f.geometry.coordinates).setHTML(popHTML(f.properties, f.geometry.coordinates)).addTo(map); };
map.on("click","point",onPointClick);
map.on("click","point-dot",onPointClick);
["clusters","point","point-dot"].forEach(l=>{
  map.on("mouseenter",l,()=>map.getCanvas().style.cursor="pointer");
  map.on("mouseleave",l,()=>map.getCanvas().style.cursor="");
});

map.on("load", ()=>{ addOverlays(); buildProvinces(); apply(); autoLocate(); });

// ==== Đổi nền Sáng / Tối ====
const CUSTOM_SOURCE_IDS=["islands","bc","bc-all"];
const CUSTOM_LAYER_IDS=["heat","island-dot","island-label","clusters","cluster-count","point","point-dot"];
function setBase(which){
  document.getElementById("bLight").classList.toggle("on", which==="light");
  document.getElementById("bDark").classList.toggle("on", which==="dark");
  // transformStyle: giữ nguyên source/layer tùy biến khi đổi nền (chính thống, không phụ thuộc render)
  map.setStyle(STYLES[which], { transformStyle:(prev,next)=>{
    if(!prev) return next;
    const sources={...next.sources};
    CUSTOM_SOURCE_IDS.forEach(id=>{ if(prev.sources[id]) sources[id]=prev.sources[id]; });
    const keep=prev.layers.filter(l=>CUSTOM_LAYER_IDS.includes(l.id));
    return {...next, sources, layers:[...next.layers, ...keep]};
  }});
}

// ==== Lọc + danh sách ====
const selProv=document.getElementById("prov");
const inpQ=document.getElementById("q");
const elCnt=document.getElementById("cnt");
const elList=document.getElementById("list");
const elWard=document.getElementById("ward");
let current=[]; let firstApply=true; let userLoc=null; let nearestMode=false; let userMarker=null;

function buildProvinces(){
  const list = addrMode==="moi" ? PROVINCES_NEW : PROVINCES_OLD;
  selProv.innerHTML='<option value="">Tất cả tỉnh / thành phố</option>';
  list.forEach(p=>{ const o=document.createElement("option"); o.value=p; o.textContent=p; selProv.appendChild(o); });
}
function buildWards(prov){
  elWard.innerHTML='<option value="">Tất cả phường / xã</option>';
  if(!prov){ elWard.disabled=true; return; }
  const seen=new Set(), opts=[];
  for(const f of ALL){ const pr=f.properties; if(provOf(pr)!==prov) continue;
    const key=wardKeyOf(pr), lbl=wardLabelOf(pr);
    if(!lbl || key==="|||" || seen.has(key)) continue; seen.add(key);
    opts.push({key, label: lbl});
  }
  opts.sort((a,b)=>a.label.localeCompare(b.label,"vi"));
  for(const o of opts){ const e=document.createElement("option"); e.value=o.key; e.textContent=o.label; elWard.appendChild(e); }
  elWard.disabled=false;
}
function norm(s){ return (s||"").toLowerCase(); }
function km(a,b){ const R=6371,r=x=>x*Math.PI/180; const dLat=r(b[1]-a[1]),dLng=r(b[0]-a[0]);
  const s=Math.sin(dLat/2)**2+Math.cos(r(a[1]))*Math.cos(r(b[1]))*Math.sin(dLng/2)**2; return 2*R*Math.asin(Math.sqrt(s)); }
function fmtKm(d){ return d<1 ? Math.round(d*1000)+" m" : d.toFixed(1).replace(".",",")+" km"; }

function setBCData(feats){
  const fc={type:"FeatureCollection",features:feats};
  if(map.getSource("bc")) map.getSource("bc").setData(fc);
  if(map.getSource("bc-all")) map.getSource("bc-all").setData(fc);
}
function apply(){
  nearestMode=false;
  const p=selProv.value, w=elWard.value, q=norm(inpQ.value).trim();
  current = ALL.filter(f=>{
    const pr=f.properties;
    if(p && provOf(pr)!==p) return false;
    if(w && wardKeyOf(pr)!==w) return false;
    if(q && !(norm(pr.ten).includes(q)||norm(pr.diachi).includes(q)||norm(pr.huyen).includes(q)||norm(pr.phuong).includes(q)||norm(pr.tinh).includes(q)||norm(pr.phuong_moi).includes(q)||norm(pr.tinh_moi).includes(q))) return false;
    return true;
  });
  setBCData(current);
  elCnt.textContent = current.length.toLocaleString("vi-VN");
  renderList();
  if(!p && !q){ if(!firstApply) map.easeTo({ ...VIEW_VN, duration:600 }); }
  else fitTo(current);
  firstApply=false;
}
function fitTo(feats){
  if(!feats.length) return;
  if(feats.length===1){ map.easeTo({center:feats[0].geometry.coordinates, zoom:15}); return; }
  const b=new maplibregl.LngLatBounds();
  feats.forEach(f=>b.extend(f.geometry.coordinates));
  map.fitBounds(b,{ padding:60, maxZoom:14, duration:600 });
}
function renderList(){
  const frag=document.createDocumentFragment();
  current.slice(0,400).forEach(f=>{
    const p=f.properties;
    const meta = (nearestMode && userLoc) ? `${fmtKm(km(userLoc,f.geometry.coordinates))} · ${provOf(p)||""}` : (provOf(p)||"");
    const d=document.createElement("div"); d.className="item";
    d.innerHTML=`<div class="nm">${p.ten||""}</div><div class="ad">${p.diachi||""}</div><div class="mc">${meta}</div>`;
    d.onclick=()=>{
      document.querySelectorAll(".item.active").forEach(x=>x.classList.remove("active"));
      d.classList.add("active");
      map.easeTo({ center:f.geometry.coordinates, zoom:15 });
      popup.setLngLat(f.geometry.coordinates).setHTML(popHTML(p, f.geometry.coordinates)).addTo(map);
    };
    frag.appendChild(d);
  });
  elList.innerHTML="";
  if(current.length>400){
    const note=document.createElement("div"); note.className="count"; note.style.padding="8px 12px";
    note.innerHTML=`Hiển thị 400/${current.length.toLocaleString("vi-VN")} mục gần nhất — lọc tỉnh hoặc tìm kiếm để thu hẹp.`;
    elList.appendChild(note);
  }
  elList.appendChild(frag);
}

// ==== Bưu cục gần tôi ====
document.getElementById("near").addEventListener("click", ()=>{
  if(!navigator.geolocation){ alert("Trình duyệt không hỗ trợ định vị."); return; }
  navigator.geolocation.getCurrentPosition(pos=>{
    userLoc=[pos.coords.longitude, pos.coords.latitude];
    if(userMarker) userMarker.remove();
    userMarker=new maplibregl.Marker({color:"#2d7ef7"}).setLngLat(userLoc).addTo(map);
    selProv.value=""; inpQ.value=""; buildWards(""); elWard.value="";
    current=[...ALL].sort((a,b)=>km(userLoc,a.geometry.coordinates)-km(userLoc,b.geometry.coordinates));
    nearestMode=true;
    setBCData(current);
    elCnt.textContent=current.length.toLocaleString("vi-VN");
    renderList();
    map.easeTo({ center:userLoc, zoom:11, duration:700 });
  }, err=>{ alert("Không lấy được vị trí: "+err.message); }, {enableHighAccuracy:true, timeout:10000});
});

// ==== Tự định vị khi mở: gần bưu cục thì zoom lớn vào ====
function autoLocate(){
  if(!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(pos=>{
    userLoc=[pos.coords.longitude, pos.coords.latitude];
    let best=Infinity;
    for(const f of ALL){ const d=km(userLoc,f.geometry.coordinates); if(d<best) best=d; }
    if(best>30){ userLoc=null; return; }   // ở xa khu vực có bưu cục -> giữ view toàn quốc
    if(userMarker) userMarker.remove();
    userMarker=new maplibregl.Marker({color:"#2d7ef7"}).setLngLat(userLoc).addTo(map);
    selProv.value=""; inpQ.value=""; buildWards(""); elWard.value="";
    current=[...ALL].sort((a,b)=>km(userLoc,a.geometry.coordinates)-km(userLoc,b.geometry.coordinates));
    nearestMode=true;
    setBCData(current);
    elCnt.textContent=current.length.toLocaleString("vi-VN");
    renderList();
    map.easeTo({ center:userLoc, zoom: best<3?15:13, duration:900 });
  }, ()=>{}, {enableHighAccuracy:true, timeout:8000});
}

selProv.addEventListener("change", ()=>{ buildWards(selProv.value); apply(); });
elWard.addEventListener("change", apply);
let t; inpQ.addEventListener("input", ()=>{ clearTimeout(t); t=setTimeout(apply,250); });
document.getElementById("bLight").addEventListener("click", ()=>setBase("light"));
document.getElementById("bDark").addEventListener("click", ()=>setBase("dark"));

// ==== Chuyển địa chỉ Cũ / Mới ====
function setAddrMode(m){
  if(addrMode===m) return;
  addrMode=m;
  document.getElementById("aOld").classList.toggle("on", m==="cu");
  document.getElementById("aNew").classList.toggle("on", m==="moi");
  selProv.value=""; inpQ.value=""; buildWards(""); elWard.value="";
  buildProvinces();
  apply();
}
document.getElementById("aOld").addEventListener("click", ()=>setAddrMode("cu"));
document.getElementById("aNew").addEventListener("click", ()=>setAddrMode("moi"));
</script>
</body>
</html>
"""
html = (TPL.replace("__GEOJSON__", geojson_min)
           .replace("__PROVINCES_OLD__", provs_old_js)
           .replace("__PROVINCES_NEW__", provs_new_js)
           .replace("__TOTAL__", "{:,}".format(total).replace(",", ".")))
open(OUT,"w",encoding="utf-8").write(html)
print("Wrote %s (%d bytes)" % (OUT, len(html)))
