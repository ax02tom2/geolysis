# -*- coding: utf-8 -*-
"""
由幾何參數自動推算數量，以及「其他必要工項」評估 (不依賴 Streamlit，方便單獨測試)。

資料依據：「單價依據與合理性評估.xlsx」之 12 份已發包預算書案例明細。
標示【案例】者：單價與數量規則皆有案例支持；標示【估算】者：僅為工程經驗概估，請自行核對。
"""
import math
import re

def cq(x):
    """工程數量一律無條件進位 (先 round 6 位避免浮點誤差，例如 3*0.1*10 → 3.0000000000000004 被誤進成 4)。"""
    try:
        return int(math.ceil(round(float(x), 6)))
    except (TypeError, ValueError):
        return 0


# 坡面洩水管：每 2m × 2m 設 1 支 (擋土抗滑結構、噴凝土護坡共用同一算法)
DRAIN_SPACING = 2.0
DRAIN_AREA = DRAIN_SPACING * DRAIN_SPACING   # 4 m²/支

# ---------------- 主工項名稱 ----------------
M1 = "1.地表排水"
M2 = "2.地下排水(橫向集水管)"
M3 = "3.集水井(Φ4.5m)"
M4 = "4.預力地錨"
M5 = "5.坡面保護"
M6 = "6.擋土與抗滑結構"
M7 = "7.落石防護"
M8 = "8.調查與監測"
M9 = "9.土方及假設工程"
MAJOR_ORDER = [M1, M2, M3, M4, M5, M6, M7, M8, M9]
# 各主工項固定顏色 (圖表用)
MAJOR_COLORS = ["#2E86C1", "#17A589", "#8E44AD", "#E67E22", "#27AE60", "#C0392B", "#7F8C8D", "#F1C40F", "#795548"]

# ---------------- 細項名稱 (須與 app.py 的 DEFAULT_DB 完全一致) ----------------
N_DITCH = "噴凝土截水溝/排水溝 (含橫向截水溝)"
N_STEEP = "縱向噴漿溝/陡槽溝"
N_CONF = "匯流井/跌水池"
N_M2_PIPE = "橫向集水管 (HDPE有孔管，含鑽孔)"
N_WELL_EXC = "井內土石方開挖及運棄"
N_WELL_LINER32 = "鋼襯鈑及施工 (t=3.2mm，井深0~10m)"
N_WELL_LINER45 = "鋼襯鈑及施工 (t=4.5mm，井深10~15m)"
N_WELL_LINER53 = "鋼襯鈑及施工 (t=5.3mm，井深15m以上)"
N_WELL_RING = "加強環製作及施工 (H150)"
N_WELL_BACKFILL = "背填灌漿 (175kgf/cm²)"
N_WELL_PLAT = "中間平台"
N_WELL_COVER = "井蓋製作及施工"
N_WELL_PUMP = "施工中抽排水及通風"
N_WELL_PUMPWELL = "抽水井安裝及運作 (φ20cm，隨開挖)"
N_WELL_SAFE = "施工中防災措施 (局限空間通風、氣體偵測、警報)"
N_WELL_COLL = "集水管 (井內輻射，含鑽孔)"
N_WELL_DRAIN = "排水管 (井內長孔)"
N_ANCH = "預力地錨 (每m全長＝錨碇段+自由段，含鑽孔、鋼絞線、護管、灌漿)"
N_ANCH_HEAD = "錨頭組件"
N_ANCH_COVER = "保護蓋及錨頭防蝕處理"
N_ANCH_LOAD = "新設荷重計"
N_ANCH_TEST = "地錨確認試驗"
N_SHOT = "噴凝土/掛網噴凝土護坡 (t=10cm)"
N_SHOT20 = "噴凝土/掛網噴凝土護坡 (t=20cm)"
N_NAIL15 = "灌漿土釘/岩栓/錨筋 (1.5m×1.5m)"
N_NAIL20 = "灌漿土釘/岩栓/錨筋 (2m×2m)"
N_NAIL25 = "灌漿土釘/岩栓/錨筋 (2.5m×2.5m)"
N_GRID_RC = "RC格樑護坡"
N_GRID_SP = "噴凝土格樑護坡"
N_PLANT = "坡面掛網植生"
N_PILE12 = "抗滑樁/排樁 Φ1.2m (全套管，含鋼筋混凝土)"
N_PILE15 = "抗滑樁/排樁 Φ1.5m"
N_WALL = "RC擋土牆 (含鋼筋、模板、混凝土)"
N_WALL_DRAIN = "坡面洩水管 (30~50cm)"
N_DRILL = "地質鑽探 (含SPT、岩心、試驗)"
N_ROAD_MAN = "施工便道 (人工開挖，約1m寬)"
N_ROAD_MACH = "施工便道 (機械開挖，約2.5m寬)"
N_DEMOL_RC = "RC構造物打除"
N_DEMOL_ROCK = "浮石(危石)打除"

# 灌漿土釘/岩栓/錨筋：三種間距 (key 為 DRIVERS 的面積參數)
NAIL_TYPES = [
    ("area_nail15", N_NAIL15, 1.5),
    ("area_nail20", N_NAIL20, 2.0),
    ("area_nail25", N_NAIL25, 2.5),
]

# ---------------- 地質鑽探分區 ----------------
# 鑽探單價依區域差異大 (運搬、便道、機具進場)，M8 先選分區，單價即帶入。
# (分區名稱, 單價 元/m, 備註, 是否使用者提供)  ※ 分區與單價可在此或「單價資料庫」分頁修改
DRILL_ZONE_SEP = "｜"
ZONE_NONE = "(請選擇)"
DRILL_ZONES = [
    ("A區 平地、都會近郊", 4500, "平地、機具可直接進場 (沿用原預設 4,500)", False),
    ("B區 一般山區 (道路可達)", 5500, "中低海拔、道路可達；暫估，請依實際報價修正", False),
    ("C區 中部山區 (埔里、信義等)", 6000, "使用者提供：埔里、信義基本 6,000 以上才做得起來", True),
    ("D區 偏遠高山 (需便道或人力運搬)", 8000, "暫估，請依實際報價修正", False),
]


def drill_zone_row(zone):
    """分區名稱 → 資料庫中的細項名稱"""
    return f"{N_DRILL}{DRILL_ZONE_SEP}{zone}"

# 鋼襯鈑依板厚分段 (案例：井深 0~10m t=3.2mm、10~15m t=4.5mm、15m 以上 t=5.3mm)，每口井各段長度分別計
LINER_BANDS = [(0, 10), (10, 15), (15, 10**6)]
WELL_ID = 4.5            # 鋼襯內徑 (m)，背填灌漿 = π/4 × (開挖直徑² − 內徑²) × 井深

# 剩餘土石方運棄：依運距分區 (名稱, 單價 元/m3, 來源, 備註)
# PCCES/工程會公開資料沒有「運距分區」現成價目 (單價分析以傾卸車時數×時價+棄土場費用組成)，
# 故以案例運棄中位數 600 為 0~10km，其後每多 10km 加 130 (傾卸車 15t：1,575 元/時、約 30km/h、每車約 8 m3 估得 ≈126)。
HAUL_ZONE_SEP = " "
HAUL_ZONES = [
    ("0~10 km", 600, "案例", "12 案運棄 450~800，中位 600 (含處理/棄土證明)"),
    ("10~20 km", 730, "估算", "0~10km 價 + 約 130/10km (傾卸車 15t 1,575 元/時、30km/h、8 m3/車 推算)"),
    ("20~30 km", 860, "估算", "同上；台北市 112 年參考單價 餘方自行處理 15t 傾卸車 721 (隱含運距約 30km)"),
    ("30~40 km", 990, "估算", "同上；國土署 115 年全國均價約 1,041"),
    ("40~50 km", 1120, "估算", "同上"),
]


def haul_name(zone):
    return f"剩餘土石方運棄{HAUL_ZONE_SEP}(運距 {zone})"


# 集水井開挖單價 (元/m3，含開挖+運棄)，依深度分段；來源：案例開挖 1,255~1,675 + 運棄 450~800
WELL_EXC_BANDS = [(0, 20, 2100), (20, 40, 2300), (40, 10**6, 2300)]  # >40m 僅1案(約6,300)，暫以 2,300 外推並警示

# ---------------- 使用者先填的「幾何參數」 ----------------
# key / label / default / (text|int|float) / help
DRIVERS = {
    M2: [
        dict(key="n_drain", label="集水管 孔數", default=None, int=True, help="孔數 × 單孔長度 ＝ 集水管總長"),
        dict(key="len_drain", label="單孔長度 (m)", default=None),
    ],
    M3: [
        dict(key="depths", label="各井井深 (m)", default="", text=True,
             help="1 口 40 m 請填 40；多口井用逗號分隔，例如 40,30,30 (表示 3 口井)"),
        dict(key="dexc", label="開挖直徑 (m)", default=4.9,
             help="案例開挖量反推約 18.9 m²/m (≈ 開挖直徑 4.9 m，含鋼襯與背填厚度)。內徑 Φ4.5m"),
        dict(key="ring_sp", label="加強環間距 (m)", default=1.5,
             help="每口井 加強環數 = ⌈井深 ÷ 間距⌉。案例約 1.1~1.6 m 一環，預設 1.5"),
        dict(key="plat_sp", label="中間平台間距 (m)", default=6.0,
             help="每口井 中間平台數 = ⌈井深 ÷ 間距⌉。案例約每 5~6 m 一座，預設 6"),
        dict(key="n_coll", label="輻射集水管 支數/井", default=None, int=True),
        dict(key="len_coll", label="集水管 單支長 (m)", default=None),
        dict(key="n_drn", label="長孔排水管 支數/井", default=None, int=True),
        dict(key="len_drn", label="排水管 單孔長 (m)", default=None, help="孔長>100 m 時案例單價約 8,000 元/m (僅 1 案)"),
    ],
    M4: [
        dict(key="n_anch", label="地錨 支數", default=None, int=True),
        dict(key="len_free", label="自由段長度 (m)", default=None),
        dict(key="len_bond", label="錨碇段長度 (m)", default=None),
    ],
    M5: [
        dict(key="area_shot", label="噴凝土/掛網噴凝土 t=10cm 面積 (m²)", default=None,
             help="填面積後，護坡數量與搭配的坡面洩水管 (每 2m×2m 1 支) 自動帶出"),
        dict(key="area_shot20", label="噴凝土/掛網噴凝土 t=20cm 面積 (m²)", default=None,
             help="填面積後，護坡數量與搭配的坡面洩水管 (每 2m×2m 1 支) 自動帶出；洩水管支數以 t=10cm 與 t=20cm 面積合計計算"),
        dict(key="area_nail15", label="土釘/岩栓/錨筋 1.5m×1.5m 面積 (m²)", default=None,
             help="支數 = 面積 ÷ (1.5×1.5)，無條件進位"),
        dict(key="area_nail20", label="土釘/岩栓/錨筋 2m×2m 面積 (m²)", default=None,
             help="支數 = 面積 ÷ (2×2)，無條件進位"),
        dict(key="area_nail25", label="土釘/岩栓/錨筋 2.5m×2.5m 面積 (m²)", default=None,
             help="支數 = 面積 ÷ (2.5×2.5)，無條件進位"),
    ],
    M8: [
        dict(key="zone", label="鑽探分區", options=[ZONE_NONE] + [z[0] for z in DRILL_ZONES], default=ZONE_NONE,
             help="鑽探單價依區域不同 (埔里、信義約 6,000 以上)；選分區後單價自動帶入，仍可手動改。"),
    ],
    M6: [
        dict(key="n_pile12", label="Φ1.2m 樁 支數", default=None, int=True),
        dict(key="n_pile15", label="Φ1.5m 樁 支數", default=None, int=True),
        dict(key="len_pile", label="樁長 (m/支)", default=None),
        dict(key="wall_len", label="RC擋土牆 長度 (m)", default=None),
        dict(key="wall_area", label="擋土牆 平均斷面積 (m²)", default=None, help="= 每 m 長之混凝土量 (m³/m)，依標準斷面計"),
        dict(key="drain_area", label="坡面洩水管 配置面積 (m²)", default=None,
             help="擋土牆面/坡面需設洩水管之面積；每 2m×2m 設 1 支，支數 = 面積 ÷ 4，無條件進位"),
    ],
}


def parse_depths(text):
    """'40, 30,30' → ([40.0, 30.0, 30.0], [無法判讀的片段])"""
    vals, bad = [], []
    for tok in re.split(r"[,，、;；\s]+", str(text or "").strip()):
        if not tok:
            continue
        try:
            v = float(tok)
            (vals if v > 0 else bad).append(v if v > 0 else tok)
        except ValueError:
            bad.append(tok)
    return vals, bad


def well_exc_unit_price(depths, bands=None):
    """各井依深度分段加權後的平均單價；各深度段斷面積相同，故以深度加權。bands 預設為開挖單價分段。"""
    bands = bands or WELL_EXC_BANDS
    tot = sum(depths)
    if tot <= 0:
        return None
    cost = 0.0
    for d in depths:
        for lo, hi, p in bands:
            seg = max(0.0, min(d, hi) - lo)
            cost += seg * p
    return cost / tot


def _f(d, k, default=0.0):
    try:
        return float(d.get(k, default) or 0)
    except (TypeError, ValueError):
        return default


def auto_quantities(major, d):
    """依幾何參數推算數量 (一律無條件進位)。回傳 {細項名稱: (數量, 計算說明)}；沒有參數或參數為 0 時回傳空 dict。"""
    out = {}
    if major == M2:
        n, L = _f(d, "n_drain"), _f(d, "len_drain")
        if n > 0 and L > 0:
            out[N_M2_PIPE] = (cq(n * L), f"{n:g} 孔 × {L:g} m")
    elif major == M3:
        depths, _ = parse_depths(d.get("depths", ""))
        n, tot = len(depths), sum(depths)
        if n:
            dexc = _f(d, "dexc", 4.9)
            area = math.pi / 4 * dexc ** 2
            out[N_WELL_EXC] = (cq(area * tot), f"π/4 × {dexc:g}² × Σ井深 {tot:g} m ＝ {area:.2f} m²/m × {tot:g} m (進位)")
            for (lo, hi), nm in zip(LINER_BANDS, (N_WELL_LINER32, N_WELL_LINER45, N_WELL_LINER53)):
                seg = sum(max(0.0, min(x, hi) - lo) for x in depths)
                if seg > 0:
                    out[nm] = (cq(seg), f"各井 {lo}~{hi if hi < 10**6 else '底'} m 段長度合計 {seg:g} m (進位)")
            rs, ps = _f(d, "ring_sp", 1.5) or 1.5, _f(d, "plat_sp", 6.0) or 6.0
            nring = sum(cq(x / rs) for x in depths)
            nplat = sum(cq(x / ps) for x in depths)
            out[N_WELL_RING] = (nring, f"各井 ⌈井深÷{rs:g}m⌉ 合計 ({', '.join(str(cq(x / rs)) for x in depths)})")
            ann = max(0.0, math.pi / 4 * (dexc ** 2 - WELL_ID ** 2))
            if ann > 0:
                out[N_WELL_BACKFILL] = (cq(ann * tot), f"π/4 × ({dexc:g}² − {WELL_ID:g}²) × Σ井深 {tot:g} m ＝ {ann:.2f} m²/m (進位)")
            out[N_WELL_PLAT] = (nplat, f"各井 ⌈井深÷{ps:g}m⌉ 合計 ({', '.join(str(cq(x / ps)) for x in depths)})")
            out[N_WELL_COVER] = (n, f"{n} 口井各 1 座")
            out[N_WELL_PUMPWELL] = (cq(tot), f"長度同井深：Σ井深 {tot:g} m (進位)")
            out[N_WELL_PUMP] = (n, f"{n} 口井")
            out[N_WELL_SAFE] = (n, f"{n} 口井")
            nc, lc = _f(d, "n_coll"), _f(d, "len_coll")
            if nc > 0 and lc > 0:
                out[N_WELL_COLL] = (cq(n * nc * lc), f"{n} 井 × {nc:g} 支 × {lc:g} m")
            nd, ld = _f(d, "n_drn"), _f(d, "len_drn")
            if nd > 0 and ld > 0:
                out[N_WELL_DRAIN] = (cq(n * nd * ld), f"{n} 井 × {nd:g} 支 × {ld:g} m")
    elif major == M4:
        n, lf, lb = _f(d, "n_anch"), _f(d, "len_free"), _f(d, "len_bond")
        if n > 0:
            out[N_ANCH] = (cq(n * (lf + lb)), f"{n:g} 支 × (自由段 {lf:g} + 錨碇段 {lb:g}) m")
            out[N_ANCH_HEAD] = (cq(n), f"{n:g} 支")
            out[N_ANCH_TEST] = (1, "1 式 (可改)")
    elif major == M5:
        a10, a20 = _f(d, "area_shot"), _f(d, "area_shot20")
        if a10 > 0:
            out[N_SHOT] = (cq(a10), f"t=10cm 面積 {a10:g} m² (進位)")
        if a20 > 0:
            out[N_SHOT20] = (cq(a20), f"t=20cm 面積 {a20:g} m² (進位)")
        if a10 + a20 > 0:
            at = a10 + a20
            out[N_WALL_DRAIN] = (cq(at / DRAIN_AREA), f"噴凝土面積合計 {at:g} m² ÷ (2m×2m) ＝ {at / DRAIN_AREA:.2f} → 進位")
        for key, name, sp in NAIL_TYPES:
            an = _f(d, key)
            if an > 0:
                out[name] = (cq(an / (sp * sp)), f"{an:g} m² ÷ ({sp:g}m×{sp:g}m) ＝ {an / (sp * sp):.2f} → 進位")
    elif major == M6:
        L = _f(d, "len_pile")
        for key, name, dia in (("n_pile12", N_PILE12, "1.2"), ("n_pile15", N_PILE15, "1.5")):
            n = _f(d, key)
            if n > 0 and L > 0:
                out[name] = (cq(n * L), f"{n:g} 支 × {L:g} m")
        wl, wa = _f(d, "wall_len"), _f(d, "wall_area")
        if wl > 0 and wa > 0:
            out[N_WALL] = (cq(wl * wa), f"{wl:g} m × {wa:g} m²")
        da = _f(d, "drain_area")
        if da > 0:
            out[N_WALL_DRAIN] = (cq(da / DRAIN_AREA), f"面積 {da:g} m² ÷ (2m×2m) ＝ {da / DRAIN_AREA:.2f} → 進位")
    return out


def auto_prices(major, d):
    """依參數推算的單價。回傳 {細項名稱: (單價, 說明)}"""
    out = {}
    if major == M3:
        depths, _ = parse_depths(d.get("depths", ""))
        p = well_exc_unit_price(depths)
        if p:
            out[N_WELL_EXC] = (int(round(p)), "依各井深度分段加權 (0~20m 2,100；20m 以上 2,300)")
    return out


def geometry_warnings(major, d):
    """回傳提醒訊息；開頭 ℹ️ 為提示，⚠️ 為警示。"""
    w = []
    if major == M3:
        depths, bad = parse_depths(d.get("depths", ""))
        if bad:
            w.append(f"⚠️ 井深欄位有無法判讀的內容：{'、'.join(map(str, bad))}")
        if not depths:
            w.append("ℹ️ 請先在上方填「各井井深」，井內開挖、鋼襯、井蓋等數量會自動計算。")
        if depths and max(depths) > 40:
            w.append("⚠️ 井深超過 40 m：案例僅 1 案 (>40m 開挖約 6,300 元/m³)，本估算以 2,300 外推，可能低估，請以報價核對。")
        if depths and _f(d, "dexc", 4.9) < 4.5:
            w.append("⚠️ 開挖直徑小於井內徑 4.5 m，請確認。")
        if depths and _f(d, "len_drn") > 100 and _f(d, "n_drn") > 0:
            w.append("⚠️ 排水管孔長 >100 m：案例 100~200 m 單價約 8,000 元/m (僅 1 案)，請把下方排水管單價改高。")
    elif major == M4:
        if _f(d, "n_anch") > 0 and (_f(d, "len_free") <= 0 or _f(d, "len_bond") <= 0):
            w.append("⚠️ 地錨自由段或錨碇段長度為 0，請確認。")
    elif major == M2:
        if _f(d, "n_drain") > 0 and _f(d, "len_drain") <= 0:
            w.append("⚠️ 集水管單孔長度為 0。")
    elif major == M5:
        a = _f(d, "area_shot") + _f(d, "area_shot20")
        if a > 0:
            w.append(f"ℹ️ 噴凝土護坡合計 {a:g} m²：已自動搭配坡面洩水管 {cq(a / DRAIN_AREA)} 支 (每 2m×2m 1 支)。")
    elif major == M8:
        z = d.get("zone", "")
        if not z or z == ZONE_NONE:
            w.append("ℹ️ 請先選「鑽探分區」，地質鑽探單價才會依區域帶入 (未選時暫用 4,500 元/m)。")
    elif major == M6:
        if (_f(d, "n_pile12") > 0 or _f(d, "n_pile15") > 0) and _f(d, "len_pile") <= 0:
            w.append("⚠️ 已填樁支數但樁長為 0。")
    return w


# ---------------- 其他必要工項評估 ----------------
# tag：「案例」＝單價與數量規則皆有案例支持；「估算」＝工程經驗概估 (請核對)
def _c(name, unit, qty, price, basis, tag):
    return dict(名稱=name, 單位=unit, 數量=qty, 單價=price, 依據=basis, 可信度=tag)


def _pct(name, pct, direct, basis):
    amt = direct * pct / 100.0
    return _c(name, "式", 1, amt, f"已列直接費 × {pct:g}%；{basis}", "估算")


def evaluate_others(major, d, qmap, direct):
    """
    評估「沒有逐項列出、但實務上必要」的工項。
    qmap：本主工項各細項已填數量 {名稱: 數量}；direct：本主工項已列細項之直接費合計。
    回傳 list of dict(名稱, 單位, 數量, 單價, 依據, 可信度)。
    注意：施工便道另列於「9.土方及假設工程」；臨時沉砂、臨時排水溝、鋼軌樁擋土等臨時設施含在雜項工程費率內，此處不重複計。
    """
    comps = []
    if major == M1:
        ditch = qmap.get(N_DITCH, 0) + qmap.get(N_STEEP, 0)
        if ditch > 0:
            need = cq(ditch / 60)
            have = qmap.get(N_CONF, 0)
            extra = max(0, need - cq(have))
            if extra:
                comps.append(_c("跌水池 (扣除已填匯流井/跌水池座數)", "處", extra, 12000,
                                f"案例 11,185~17,160 元/處；案例約每 40~110 m 溝長 1 處，本評估取每 60 m 1 處 (溝長 {ditch:g} m → {need} 處，已填 {have:g})", "案例"))
        if direct > 0:
            comps.append(_pct("轉角、接頭、伸縮縫及端點處理", 3, direct, "無案例單項"))
    elif major == M2:
        if direct > 0:
            comps.append(_pct("集水管出水口、連接及端點保護", 3, direct, "無案例單項"))
    elif major == M3:
        depths, _ = parse_depths(d.get("depths", ""))
        tot = sum(depths)
        if tot > 0:
            comps.append(_c("集水井開挖地質記錄 (含報告)", "人月", cq(tot / 10), 100000,
                            "案例 80,000~120,000 元/人月；數量約每 10 m 井深 1 人月 (案例 6~10 人月/2~6 口井)", "案例"))
            comps.append(_c("施工中安全監測及研判 (含報告)", "月", cq(tot / 8), 130000,
                            "案例 65,000~200,000 元/月 (取中值)；月數約每 8 m 井深 1 個月 (案例 10~18 個月/2~6 口井)", "案例"))
    elif major == M4:
        if direct > 0:
            comps.append(_pct("張拉鎖定、泥漿排水及施工紀錄等附屬作業", 3, direct, "無案例單項"))
    elif major == M5:
        if direct > 0:
            comps.append(_pct("坡頂坡趾收邊、排水孔、伸縮縫及零星修整", 5, direct, "無案例單項"))
    elif major == M6:
        if direct > 0:
            comps.append(_pct("出渣泥漿處理、止水及零星工項 (坡面洩水管已另列)", 6, direct, "無案例單項 (阿里山排樁案已含繫梁)"))
    elif major == M7:
        if direct > 0:
            comps.append(_pct("基礎、錨碇及五金配件", 10, direct, "案例無此類工項"))
    elif major == M8:
        if direct > 0:
            comps.append(_pct("資料整理及成果報告", 10, direct, "無案例單項"))
    return comps


# ---------------- 細項改名容錯 ----------------
# 使用者在「單價資料庫」把細項改名 (例如「中間平台」→「中間平台(含爬梯)」) 後，自動算量/其他必要工項評估
# 仍要找得到對應項目：先精確比對，其次以名稱包含關係或「括號前主名稱」相同且唯一者比對。
def _norm_name(x):
    x = str(x).replace("（", "(").replace("）", ")").replace("，", ",")
    return re.sub(r"\s+", "", x)


def _stem(x):
    return _norm_name(x).split("(")[0]


def canonical_map(major, names):
    """回傳 {資料庫列名稱: 內建細項名稱}。只含對得上的列；對不上者視為使用者自訂項目 (不自動算量)。"""
    canon = [v for k, v in globals().items() if k.startswith("N_") and isinstance(v, str)]
    names = list(names)
    out, used = {}, set()
    for nm in names:                       # 1. 精確
        if nm in canon:
            out[nm] = nm
            used.add(nm)
    left = [nm for nm in names if nm not in out]
    for c in canon:
        if c in used:
            continue
        nc = _norm_name(c)
        nco = nc.rstrip(")")               # 括號內多加說明 (如「…井深10~15m，含加勁)」) 仍視為同一項
        hits = []
        for nm in left:
            if nm in out:
                continue
            nn = _norm_name(nm)
            short = min(len(nc), len(nn))
            if short >= 3 and (nco in nn or nn in nc):
                hits.append(nm)
        if len(hits) != 1:                 # 2. 括號前主名稱相同，且該主名稱在內建項目中唯一
            sc = _stem(c)
            if len(sc) >= 3 and sum(1 for x in canon if _stem(x) == sc) == 1:
                hits = [nm for nm in left if nm not in out and _stem(nm) == sc]
        if len(hits) == 1:
            out[hits[0]] = c
            used.add(c)
    return out
