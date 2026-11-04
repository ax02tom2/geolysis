import hashlib
import inspect
import io
import json
import math
import os
import shutil

import altair as alt
import pandas as pd
import streamlit as st

from cost_logic import (
    M1, M2, M3, M4, M5, M6, M7, M8, M9, MAJOR_ORDER, MAJOR_COLORS, DRIVERS,
    auto_quantities, auto_prices, geometry_warnings, evaluate_others,
    N_DRILL, DRILL_ZONES, DRILL_ZONE_SEP, ZONE_NONE, drill_zone_row,
    N_ANCH_COVER, N_ANCH_LOAD, N_ANCH_TEST, N_SHOT, N_SHOT20, N_WELL_PUMPWELL, canonical_map, N_NAIL15, N_NAIL20, N_NAIL25,
    N_GRID_RC, N_GRID_SP, N_PLANT, N_WALL_DRAIN, cq,
    N_WELL_LINER32, N_WELL_LINER45, N_WELL_LINER53, N_WELL_RING, N_WELL_BACKFILL, N_WELL_PLAT, N_WELL_COVER,
    N_WELL_EXC, N_ROAD_MAN, N_ROAD_MACH, N_DEMOL_RC, N_DEMOL_ROCK, HAUL_ZONES, haul_name,
)
from db_upgrade import (
    SRC_CASE, SRC_DERIVED, SRC_EST, SRC_USER, SRC_EDIT, DEFAULT_SOURCES, mark_edits, upgrade_db,
)
from pcces_export import build_pcces_excel
from storage import (
    LocalStore, build_gsheet_store, diff_db, merge_db, diff_to_log_rows, now_str,
)

st.set_page_config(
    page_title="大地工程規劃階段經費初估",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# 版本
# ==========================================
CURRENT_VERSION = "v17_shotcrete_pumpwell"  # 只有「預設資料庫內容」改動時才需要更改

REQUIRED_COLS = ["主工項", "細項名稱", "單位", "單價(元)"]
ALL_COLS = ["主工項", "細項名稱", "單位", "單價(元)", "備註", "資料來源"]


# 新版 Streamlit 以 width="stretch" 取代 use_container_width=True (舊參數已被移除)；這裡自動相容新舊版本
def _compat(name):
    fn = getattr(st, name)
    new_api = "width" in inspect.signature(fn).parameters

    def inner(*args, **kwargs):
        if "use_container_width" in kwargs:
            flag = kwargs.pop("use_container_width")
            if new_api:
                kwargs["width"] = "stretch" if flag else "content"
            else:
                kwargs["use_container_width"] = flag
        return fn(*args, **kwargs)
    return inner


for _n in ("dataframe", "data_editor", "altair_chart", "button", "download_button"):
    setattr(st, _n, _compat(_n))

# ==========================================
# 預設單價資料庫 (規劃階段簡化版)
# 單價依據：12 份已發包預算書 (地錨 / 排樁 / 集水井) 之詳細價目表整理
# ==========================================
# 資料來源：已發包案例 (取自預算書單價)／案例推算 (組合推算)／估算待核 (案例無此項，請以報價核對)／
# 使用者新增／使用者修改 (改過預設單價，改版時照舊保留) — 常數定義在 db_upgrade.py


# (主工項, 細項名稱, 單位, 單價, 資料來源, 備註/案例依據)
DEFAULT_DB = [
    (M1, "噴凝土截水溝/排水溝 (含橫向截水溝)", "m", 5000, SRC_CASE, "案例 5,025~6,298 (3筆)"),
    (M1, "縱向噴漿溝/陡槽溝", "m", 4200, SRC_CASE, "案例 3,939~4,342 (3筆)"),
    (M1, "匯流井/跌水池", "座", 35000, SRC_CASE, "匯流井 27,143~51,484；跌水池 11,185~17,160"),

    (M2, "橫向集水管 (HDPE有孔管，含鑽孔)", "m", 2400, SRC_CASE, "案例 1,180~2,620；近年 2,230~2,620"),

    (M3, "井內土石方開挖及運棄", "m3", 2200, SRC_DERIVED, "0~20m 約2,100；20~40m 約2,300；>40m 深井可達6,300 (1案)"),
    (M3, N_WELL_LINER32, "m", 37000, SRC_DERIVED, "案例 t=3.2mm 31,680~40,476 (中位約 37,000)；每口井 0~10m 段，數量＝各井該段長度合計"),
    (M3, N_WELL_LINER45, "m", 47700, SRC_DERIVED, "案例 t=4.5mm 40,520~51,360 (中位 47,700)；每口井 10~15m 段"),
    (M3, N_WELL_LINER53, "m", 50000, SRC_DERIVED, "案例 t=5.3mm 43,028~61,068，取 50,000 (不低於 t=4.5mm)；五彎仔 91,180~95,580 (含吊運復舊)、石碇鍍鋅 80,192 不納入；每口井 15m 以上段"),
    (M3, N_WELL_RING, "環", 25800, SRC_DERIVED, "案例 19,390~40,917 (H125~H200)，中位約 25,800；每井 ⌈井深÷間距⌉ 環，案例約 1.1~1.6 m 一環"),
    (M3, N_WELL_BACKFILL, "m3", 3200, SRC_CASE, "案例 3,111~3,330；數量＝環形空間 π/4×(開挖直徑²−4.5²)×井深 (約 2.95 m³/m，案例 2.9~3.2)"),
    (M3, N_WELL_PLAT, "座", 67300, SRC_CASE, "案例 62,580~69,400 (中位 67,300；五彎仔 118,221 不納入)；每井約每 6 m 1 座，含爬梯 (案例無獨立爬梯項)"),
    (M3, N_WELL_COVER, "座", 71250, SRC_CASE, "案例 71,250 (4 案相同)、92,482；每口井 1 座"),
    (M3, N_WELL_PUMPWELL, "m", 4000, SRC_CASE, "案例 3,000~5,132 元/m (取 4,000)；長度同井深，填各井井深後數量自動帶入"),
    (M3, "施工中抽排水及通風", "座", 200000, SRC_CASE, "案例抽排水照明 120,000~245,200"),
    (M3, "施工中防災措施 (局限空間通風、氣體偵測、警報)", "座", 450000, SRC_DERIVED, "案例組價約 280,000~850,000/座"),
    (M3, "集水管 (井內輻射，含鑽孔)", "m", 2400, SRC_CASE, "案例 1,180~2,620"),
    (M3, "排水管 (井內長孔)", "m", 6000, SRC_EST, "L≤100m 約 2,230~4,000；L=100~200m 僅1案 8,000，請依孔長改單價"),

    (M4, "預力地錨 (每m全長＝錨碇段+自由段，含鑽孔、鋼絞線、護管、灌漿)", "m", 3200, SRC_CASE,
     "數量＝支數×(錨碇段+自由段) 全長；案例 1,600~3,701 元/m，近年(110~113年) 2,700~3,701"),
    (M4, "錨頭組件", "支", 8000, SRC_CASE, "案例 4,000~16,017"),
    (M4, N_ANCH_COVER, "支", 10000, SRC_USER, "使用者提供 10,000/支 (原「既有地錨檢修更新」)；數量自行填"),
    (M4, N_ANCH_LOAD, "組", 60000, SRC_USER, "使用者提供 60,000/組；須配合施工辦理；數量自行填"),
    (M4, N_ANCH_TEST, "式", 300000, SRC_USER, "使用者提供 300,000/式 (案例確認試驗 115,080~165,000/支)"),

    (M5, N_SHOT, "m2", 1200, SRC_USER, "使用者提供 1,200/m² (t=10cm；原案例 3,300~3,564)；需搭配坡面洩水管 (每 2m×2m 1 支)"),
    (M5, N_SHOT20, "m2", 1800, SRC_USER, "使用者提供 1,800/m² (t=20cm)；需搭配坡面洩水管 (每 2m×2m 1 支)"),
    (M5, N_WALL_DRAIN, "支", 350, SRC_USER, "搭配噴凝土/掛網噴凝土護坡，每 2m×2m 設 1 支 (面積÷4，進位)；與擋土抗滑結構同一單價"),
    (M5, N_NAIL15, "支", 1500, SRC_USER, "使用者提供 1,500/支；支數＝面積÷(1.5×1.5)，進位"),
    (M5, N_NAIL20, "支", 3000, SRC_USER, "使用者提供 3,000/支；支數＝面積÷(2×2)，進位"),
    (M5, N_NAIL25, "支", 4500, SRC_USER, "使用者提供 4,500/支；支數＝面積÷(2.5×2.5)，進位"),
    (M5, N_GRID_RC, "m2", 5000, SRC_USER, "使用者提供 5,000"),
    (M5, N_GRID_SP, "m2", 3000, SRC_USER, "使用者提供 3,000"),
    (M5, N_PLANT, "m2", 800, SRC_USER, "使用者提供 800 (原坡面植生案例 435)"),

    (M6, "抗滑樁/排樁 Φ1.2m (全套管，含鋼筋混凝土)", "m", 22000, SRC_CASE, "案例(111年排樁含繫梁) 21,800/m"),
    (M6, "抗滑樁/排樁 Φ1.5m", "m", 31000, SRC_EST, "依Φ1.2m案例按斷面放大推估"),
    (M6, "RC擋土牆 (含鋼筋、模板、混凝土)", "m3", 7500, SRC_DERIVED, "案例單價組價約 4,900~9,300"),
    (M6, "坡面洩水管 (30~50cm)", "支", 350, SRC_USER, "每 2m×2m 設 1 支 (面積÷4，進位)；使用者提供 350 (原「坡面洩水孔」案例 1,000~1,300 為較長孔，已移除)"),

    (M7, "被動式防落石網", "m", 35000, SRC_EST, "案例無此項，請以廠商報價核對 (500kJ 約此價；1000kJ 約55,000)"),
    (M7, "主動式邊坡防護網", "m2", 3800, SRC_EST, "案例無此項，沿用舊庫"),

    (M8, N_DRILL, "m", 4500, SRC_EST, "單價依上方「鑽探分區」帶入 (未選分區時用此價)；案例無單項；五彎仔補充地質探查整案 970,000"),
    (M8, "傾斜管/水位觀測井 (含鑽孔)", "m", 5500, SRC_CASE, "傾斜管含鑽孔 5,500 (1案)；僅安裝 2,020~3,300"),
    (M8, "施工期間監測及其他調查", "式", 500000, SRC_EST, "案例施工中監測 65,000~200,000/月；依期程自行估"),

    (M9, "挖土方", "m3", 125, SRC_USER, "使用者提供區間 100~150，預設取中間值"),
    (M9, "挖軟岩", "m3", 625, SRC_USER, "使用者提供區間 500~750，預設取中間值"),
    (M9, "挖硬岩", "m3", 1100, SRC_USER, "使用者提供區間 1,000~1,200，預設取中間值"),
    *[(M9, haul_name(z), "m3", price, SRC_DERIVED if tag == "案例" else SRC_EST, note)
      for (z, price, tag, note) in HAUL_ZONES],
    (M9, N_ROAD_MAN, "m", 1200, SRC_EST, "案例及公開資料查無人工便道單價；以約 0.5 工/m × 2,000 元/工 + 材料機具 20% 概估，請依地形與報價修正"),
    (M9, N_ROAD_MACH, "m", 4000, SRC_USER, "使用者提供 4,000/m (案例機械便道 2,062~5,615/m²，約 1,600/m² 同量級)"),
    (M9, N_DEMOL_RC, "m3", 900, SRC_USER, "使用者提供 900/m³"),
    (M9, N_DEMOL_ROCK, "m2", 150, SRC_USER, "使用者提供 150/m²"),
    (M9, "山區索道/吊運設備", "式", 900000, SRC_EST, "案例僅1筆 900,000 (台8線116k)"),
]

# 地質鑽探分區單價 (在「單價資料庫」可修改；主畫面不逐列顯示，改由「鑽探分區」下拉帶入)
DEFAULT_DB += [
    (M8, drill_zone_row(z), "m", price, SRC_USER if user_given else SRC_EST, note)
    for (z, price, note, user_given) in DRILL_ZONES
]


def _build_default_df():
    rows = [
        {"主工項": m, "細項名稱": n, "單位": u, "單價(元)": p, "備註": note, "資料來源": src}
        for (m, n, u, p, src, note) in DEFAULT_DB
    ]
    return pd.DataFrame(rows)


# ==========================================
# 資料處理函式
# ==========================================
def normalize_db(df):
    """驗證並整理資料庫；格式有誤時丟出 ValueError，不會讓整個 App 當掉"""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError("缺少必要欄位：" + "、".join(missing))
    if "備註" not in df.columns:
        df["備註"] = ""
    if "資料來源" not in df.columns:
        df["資料來源"] = SRC_USER
    df = df[ALL_COLS].copy()
    for c in ["主工項", "細項名稱", "單位", "備註", "資料來源"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    df.loc[df["資料來源"] == "", "資料來源"] = SRC_USER
    price = pd.to_numeric(
        df["單價(元)"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    bad = df[price.isna() | (df["主工項"] == "") | (df["細項名稱"] == "")]
    if len(bad) > 0:
        raise ValueError(
            f"有 {len(bad)} 列的主工項、細項名稱或單價無效 (第一筆在表格第 {bad.index[0] + 1} 列)"
        )
    df["單價(元)"] = price.round().astype(int)
    df = df.drop_duplicates(subset=["主工項", "細項名稱"], keep="last").reset_index(drop=True)
    return df


DEFAULT_DF = normalize_db(_build_default_df())

# 防呆：cost_logic 引用的細項名稱必須存在於預設資料庫 (改名時會立刻提醒)
import cost_logic as _cl
_missing = [v for k, v in vars(_cl).items() if k.startswith('N_') and v not in set(DEFAULT_DF['細項名稱'])]
assert not _missing, f'cost_logic 細項名稱與資料庫不一致：{_missing}'


# ==========================================
# 儲存後端：secrets 有設定 Google 試算表就用它 (永久保存)，否則退回本機檔案
# ==========================================
@st.cache_resource(ttl=600, show_spinner=False)
def _get_store():
    try:
        cfg = st.secrets["gsheet"]
        info = st.secrets["gcp_service_account"]
    except Exception:
        return LocalStore(), None
    try:
        return build_gsheet_store(info, cfg["spreadsheet_id"]), None
    except Exception as e:
        return LocalStore(), f"Google 試算表連線失敗，暫時改用本機檔案：{e}"


store, store_err = _get_store()


def initialize_database():
    """版本不同時才重建資料庫；重建前先備份。保留「使用者新增」「使用者修改」項目；
    舊版 (v14/v15) 尚無修改標記時，以舊預設快照比對，找出使用者改過的單價一併保留。"""
    cur = store.read_db()
    if cur is not None and store.get_version() == CURRENT_VERSION:
        return
    new_df, notes = DEFAULT_DF.copy(), []
    if cur is not None:
        store.backup_db("before_upgrade")
        try:
            if "資料來源" in cur.columns:
                new_df, notes = upgrade_db(normalize_db(cur), DEFAULT_DF, store.get_version())
        except Exception as e:
            notes = [f"保留使用者修改失敗，已改用預設值 (舊檔已備份)：{e}"]
            new_df = DEFAULT_DF.copy()
    store.write_db(new_df)
    store.set_version(CURRENT_VERSION)
    rows = [[now_str(), "(系統)", "資料庫版本升級", "", "", "", "", CURRENT_VERSION,
             "重建預設單價，保留「使用者新增」「使用者修改」項目"]]
    rows += [[now_str(), "(系統)", "升級保留", "", "", "", "", "", n] for n in notes]
    store.append_log(rows)


@st.cache_data(ttl=30, show_spinner=False)
def _cached_db(_store):
    return _store.read_db()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_hist(_store):
    return _store.read_history()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_log(_store):
    return _store.read_log()


def load_db():
    try:
        return normalize_db(_cached_db(store))
    except Exception as e:
        st.error(f"共用資料庫讀取失敗，暫時使用內建預設值：{e}")
        return DEFAULT_DF.copy()


def load_history():
    return _cached_hist(store)


def commit_db(new_df, cur_df, user, action, note, backup_tag):
    """寫入資料庫並記錄「誰、何時、改了什麼」。回傳變更筆數 (0＝沒有變更，不寫入)。"""
    new_df = mark_edits(cur_df, new_df, DEFAULT_DF)   # 預設項目改了單價/單位 → 標「使用者修改」，改版時保留
    changes = diff_db(cur_df, new_df)
    if not changes:
        return 0
    store.backup_db(backup_tag)
    store.write_db(new_df)
    store.append_log(diff_to_log_rows(changes, user, action, note))
    st.cache_data.clear()
    return len(changes)


# ==========================================
# 單價資料庫編輯權限：secrets 的 [editors] 有設定帳號密碼 → 需登入才能改；沒設定 → 不限制
# ==========================================
def _load_editors():
    try:
        editors = dict(st.secrets["editors"])
        if not editors:
            return {}
        return {
            str(k): str(v)
            for k, v in editors.items()
        }
    except Exception:
        return {}


EDITORS = _load_editors()


def can_edit():
    return bool(EDITORS) and bool(
        st.session_state.get("editor_ok")
    )


def acting_user():
    """記錄用的使用者：已登入 → 登入帳號 (已驗證)；否則 → 側邊欄填的名字 (未驗證)"""
    if st.session_state.get("editor_ok"):
        return st.session_state.get("editor_user", "")
    return (st.session_state.get("user_name") or "").strip()


def _login(account, password):
    import hmac
    real = EDITORS.get(account.strip())
    if real is not None and hmac.compare_digest(real.encode("utf-8"), password.encode("utf-8")):
        st.session_state["editor_ok"] = True
        st.session_state["editor_user"] = account.strip()
        return True
    return False


# 上傳檔欄名別名 (相容「單價依據與合理性評估.xlsx」第 1 分頁的欄名)
COL_ALIAS = {"規劃單價(元)": "單價(元)", "規劃單價": "單價(元)", "單價": "單價(元)",
             "案例依據/說明": "備註", "案例依據": "備註", "說明": "備註"}


def _canon_columns(df):
    df = df.dropna(how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]
    ren = {c: COL_ALIAS[c] for c in df.columns if c in COL_ALIAS and COL_ALIAS[c] not in df.columns}
    return df.rename(columns=ren)


def read_uploaded_csv(uploaded):
    data = uploaded.getvalue()
    last_err = None
    for enc in ("utf-8-sig", "cp950"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
    raise ValueError(f"無法判讀檔案編碼 (請存成 UTF-8 CSV)：{last_err}")


def read_uploaded_table(uploaded):
    """CSV 或 Excel(.xlsx)。Excel 會找第一個同時含必要欄位的分頁。"""
    if uploaded.name.lower().endswith(".xlsx"):
        xl = pd.ExcelFile(io.BytesIO(uploaded.getvalue()))
        for sh in xl.sheet_names:
            df = _canon_columns(xl.parse(sh))
            if all(c in df.columns for c in REQUIRED_COLS):
                return df
        raise ValueError("Excel 中找不到同時含「主工項、細項名稱、單位、單價」欄位的分頁")
    return _canon_columns(read_uploaded_csv(uploaded))


def rec_get(rec, *keys, default=0):
    for k in keys:
        if k in rec and rec[k] is not None:
            return rec[k]
    return default


def _clear_history():
    user = acting_user()
    store.clear_history()
    store.append_log([[now_str(), user, "清空歷史紀錄", "", "", "", "", "", ""]])
    st.cache_data.clear()
    st.session_state["confirm_clear"] = False
    st.session_state["flash"] = "已清空團隊紀錄 (已記入更新紀錄)。"


def md(t):
    """Streamlit markdown 會把成對的 ~ 當刪除線；顯示文字一律跳脫"""
    return str(t).replace("~", "\\~")


def money(x):
    return f"{int(round(x)):,}"


# ---- 數量/單價輸入框：顯示千位數逗號 (st.number_input 不支援，改用文字框＋自動格式化) ----
def _fmt_num(v, integer):
    if v is None or v == "":
        return ""
    if integer or float(v) == int(float(v)):
        return f"{int(round(float(v))):,}"
    return f"{float(v):,.4f}".rstrip("0").rstrip(".")


def _parse_num(txt):
    t = str(txt or "").replace(",", "").replace("，", "").replace(" ", "").strip()
    if t == "":
        return None
    try:
        return float(t)
    except ValueError:
        return "bad"


def _comma_cb(key, integer):
    v = _parse_num(st.session_state.get(key, ""))
    if v == "bad" or (v is not None and v < 0):      # 無法判讀或負數 → 還原上一個有效值
        st.session_state[key] = st.session_state.get(key + "__ok", "")
        return
    st.session_state[key] = st.session_state[key + "__ok"] = _fmt_num(v, integer)


def comma_input(container, label, key, default=None, integer=True, help=None, collapsed=True):
    """文字框版數字輸入：輸入後自動加千位數逗號。預設值改變 (如資料庫單價更新、參數變動) 時重新帶入，行為同 number_input。
    回傳 int (integer=True) 或 float；空白回傳 0。"""
    dtxt = _fmt_num(default, integer)
    if key not in st.session_state or st.session_state.get(key + "__def") != dtxt:
        st.session_state[key] = st.session_state[key + "__ok"] = st.session_state[key + "__def"] = dtxt
    container.text_input(label, key=key, on_change=_comma_cb, args=(key, integer), help=help,
                         label_visibility="collapsed" if collapsed else "visible")
    v = _parse_num(st.session_state.get(key, ""))
    if v is None or v == "bad":
        return 0
    return int(round(v)) if integer else float(v)


# ==========================================
# 計算與 Excel 匯出
# ==========================================
def calc_costs(direct_by_major, p):
    """費用結構：雜項工程 (% 直接費)、職業安全衛生及環境保護 (% 直接費)
    → 保險、廠商管理及利潤 (% 直接+雜項+職安) → 營業稅 (% 前四項和)。
    其他費用(選填)以含稅發包工程費為基數計算。"""
    rows = []
    for m, d in direct_by_major.items():
        misc = d * p["misc"] / 100
        safety = d * p["safety"] / 100
        prof = (d + misc + safety) * p["profit"] / 100
        tax = (d + misc + safety + prof) * p["tax"] / 100
        rows.append({"主工項": m, "直接工程費": d, "雜項工程": misc, "職安及環保": safety,
                     "保險、廠商管理及利潤": prof, "營業稅": tax, "合計": d + misc + safety + prof + tax})
    df = pd.DataFrame(rows)
    contract = df["合計"].sum() if len(df) else 0
    others = {
        "物價調整費": contract * p["escalation"] / 100,
        "工程預備費": contract * p["contingency"] / 100,
        "設計監造費": contract * p["design"] / 100,
    }
    return df, contract, others


def build_excel(lines, p, project_name):
    """產出 Excel：總表 + 每個主工項一張分頁"""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="DDEBF7")
    sub_fill = PatternFill("solid", fgColor="F2F2F2")
    bold = Font(bold=True)
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "總表"

    def style_row(ws, r, ncol=7, fill=None, b=False):
        for c in range(1, ncol + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = border
            if fill:
                cell.fill = fill
            if b:
                cell.font = bold
            if c in (4, 5, 6):
                cell.number_format = "#,##0.##" if c == 4 else "#,##0"
            if c in (1, 3):
                cell.alignment = Alignment(horizontal="center")

    def set_widths(ws):
        for col, w in zip("ABCDEFG", (8, 52, 8, 12, 14, 16, 46)):
            ws.column_dimensions[col].width = w

    majors = [m for m in MAJOR_ORDER if any(l["主工項"] == m for l in lines)]
    majors += [m for m in dict.fromkeys(l["主工項"] for l in lines) if m not in majors]
    direct_by_major = {m: sum(l["複價"] for l in lines if l["主工項"] == m) for m in majors}
    cost_df, contract, others = calc_costs(direct_by_major, p)

    # --- 各主工項分頁 ---
    for m in majors:
        name = "".join(ch for ch in m if ch not in '[]:*?/\\')[:31]
        ws = wb.create_sheet(name)
        set_widths(ws)
        ws.append(["項次", "工程名稱", "單位", "數量", "單價", "複價", "備註"])
        style_row(ws, 1, fill=head_fill, b=True)
        ws.append(["一", m])
        style_row(ws, 2, b=True)
        r = 3
        for i, l in enumerate([x for x in lines if x["主工項"] == m], 1):
            ws.append([i, l["細項名稱"], l["單位"], l["數量"], l["單價"], l["複價"], l["備註"]])
            style_row(ws, r)
            ws.cell(row=r, column=2).alignment = Alignment(wrap_text=True)
            r += 1
        d = direct_by_major[m]
        misc = d * p["misc"] / 100
        safety = d * p["safety"] / 100
        prof = (d + misc + safety) * p["profit"] / 100
        tax = (d + misc + safety + prof) * p["tax"] / 100
        ws.append(["", "小計", "", "", "", d, ""]); style_row(ws, r, fill=sub_fill, b=True); r += 1
        ws.append(["二", "雜項工程", "%", p["misc"], d, misc, "一項和之 %g%%" % p["misc"]]); style_row(ws, r); r += 1
        ws.append(["三", "職業安全衛生及環境保護", "%", p["safety"], d, safety, "一項和之 %g%%" % p["safety"]]); style_row(ws, r); r += 1
        ws.append(["四", "保險、廠商管理及利潤", "%", p["profit"], d + misc + safety, prof, "一~三項和之 %g%%" % p["profit"]]); style_row(ws, r); r += 1
        ws.append(["五", "營業稅", "%", p["tax"], d + misc + safety + prof, tax, "一~四項和之 %g%%" % p["tax"]]); style_row(ws, r); r += 1
        ws.append(["", "總計", "", "", "", d + misc + safety + prof + tax, ""]); style_row(ws, r, fill=sub_fill, b=True)
        ws.freeze_panes = "A2"

    # --- 總表 (9 欄：項次 / 主工項 / 直接工程費 / 雜項 / 職安及環保 / 保險管理利潤 / 營業稅 / 合計) ---
    for col, w in zip("ABCDEFGHI", (8, 34, 2, 14, 14, 14, 16, 14, 16)):
        ws0.column_dimensions[col].width = w
    ws0.append([project_name or "(未命名專案)"])
    ws0["A1"].font = Font(bold=True, size=14)
    heads = ["項次", "主工項", "", "直接工程費", "雜項工程", "職安及環保", "保險、廠商管理及利潤", "營業稅", "合計"]
    ws0.append(heads)
    style_row(ws0, 2, ncol=9, fill=head_fill, b=True)
    for c in range(1, 10):
        ws0.cell(row=2, column=c).alignment = Alignment(horizontal="center", wrap_text=True)
    r = 3
    for i, row in enumerate(cost_df.itertuples(index=False), 1):
        ws0.append([i, row[0], "", row[1], row[2], row[3], row[4], row[5], row[6]])
        style_row(ws0, r, ncol=9)
        for c in range(4, 10):
            ws0.cell(row=r, column=c).number_format = "#,##0"
        r += 1
    tot = cost_df[["直接工程費", "雜項工程", "職安及環保", "保險、廠商管理及利潤", "營業稅", "合計"]].sum()
    ws0.append(["", "含稅發包工程費 (各項合計)", ""] + [tot[c] for c in tot.index])
    style_row(ws0, r, ncol=9, fill=sub_fill, b=True)
    for c in range(4, 10):
        ws0.cell(row=r, column=c).number_format = "#,##0"
    r += 1
    for k, v in others.items():
        if v:
            ws0.append(["", k, "", "", "", "", "", "", v]); style_row(ws0, r, ncol=9)
            ws0.cell(row=r, column=9).number_format = "#,##0"; r += 1
    ws0.append(["", "總計", "", "", "", "", "", "", contract + sum(others.values())])
    style_row(ws0, r, ncol=9, fill=sub_fill, b=True); ws0.cell(row=r, column=9).number_format = "#,##0"
    ws0.cell(row=r + 2, column=2, value="註：初估單價為規劃階段概估，請依實際地質、施工條件及報價調整。")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ==========================================
# 初始化
# ==========================================
if "db_ready" not in st.session_state:
    try:
        initialize_database()
    except Exception as e:
        st.error(f"資料庫初始化失敗：{e}")
    st.session_state["db_ready"] = True
db = load_db()
UNITS_INT = {"式", "座", "組", "孔", "處", "支", "次", "月", "人月", "套"}   # (數量一律整數，保留供參考)
ROW_NOTE_DEFAULT = {N_ANCH_LOAD: "須配合施工辦理"}

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

st.markdown(
    """
    <style>
    .metric-card {background:#f0f6ff;border-left:6px solid #1f77b4;padding:14px 18px;border-radius:8px;margin-bottom:8px;}
    .metric-card h2 {margin:0;color:#1f3b57;}
    .metric-card p {margin:0;color:#555;}
    [class*="st-key-qty2_"] input, [class*="st-key-prc_"] input, [class*="st-key-drvn_"] input {text-align:right;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧮 大地工程規劃階段經費初估")
st.caption("規劃用精簡版：先填各主工項上方的設計參數 (井深、地錨支數等)，數量自動帶出；沒列到的必要工項由系統依案例評估並列出內容。")

# ==========================================
# 側邊欄：費率設定
# ==========================================
with st.sidebar:
    if st.session_state.get("editor_ok"):
        st.caption(f"👤 已登入：{st.session_state.get('editor_user', '')}")
    else:
        st.text_input("👤 你的名字", key="user_name",
                      help=("發布歷史紀錄時記錄發布者。" if EDITORS else
                            "修改單價、上傳更新、發布紀錄時會記入「更新紀錄」(誰、何時、改了什麼)。"))
    if store.kind == "gsheet":
        st.caption("☁️ 資料存於 Google 試算表 (永久保存)")
    else:
        st.caption("⚠️ 目前為本機檔案模式：網頁重啟或重新部署後，單價修改與歷史紀錄可能消失。")
    if store_err:
        st.warning(store_err)
    st.header("⚙️ 費用比例")
    misc = st.number_input("雜項工程 (% 直接工程費)", 0.0, 50.0, 20.0, 0.5, key="rate_misc",
                           help=md("含品管、交維、臨時設施等 (職安及環保另列)。以直接工程費為基數。"))
    safety = st.number_input("職業安全衛生及環境保護 (% 直接工程費)", 0.0, 20.0, 3.5, 0.5, key="rate_safety",
                             help="以直接工程費為基數。")
    profit = st.number_input("保險、廠商管理及利潤 (% )", 0.0, 30.0, 10.5, 0.5, key="rate_profit",
                             help=md("基數＝直接工程費＋雜項工程＋職安及環保 (比照預算書「包商利潤、保險及管理費 (一~九)項*10.5%」)。"))
    tax = st.number_input("營業稅 (%)", 0.0, 20.0, 5.0, 0.5, key="rate_tax", help="基數＝直接工程費＋雜項＋職安及環保＋保險、廠商管理及利潤。")
    st.markdown("**其他費用 (選填，0 = 不計)**")
    escalation = st.number_input("物價調整費 (% 含稅發包費)", 0.0, 20.0, 0.0, 0.5, key="rate_esc")
    contingency = st.number_input("工程預備費 (% 含稅發包費)", 0.0, 30.0, 0.0, 0.5, key="rate_cont")
    design = st.number_input("設計監造費 (% 含稅發包費)", 0.0, 20.0, 0.0, 0.5, key="rate_design")
    st.caption(md("已發包案例的「總價/主體工程」約 1.29~1.45 倍 (含機關工程管理費約 2~4%、空污費 0.3%、物調等)。上列預設值只算到含稅發包工程費，規劃階段建議視需要加列其他費用。"))

params = {"misc": misc, "safety": safety, "profit": profit, "tax": tax, "escalation": escalation,
          "contingency": contingency, "design": design}

page_options = ["📊 專案經費初估", "📚 單價資料庫", "📁 團隊歷史紀錄"]
selected_page = st.radio(
    "功能頁面", page_options, horizontal=True, key="active_page",
    label_visibility="collapsed",
)

# ==========================================
# TAB 1
# ==========================================
if selected_page == "📊 專案經費初估":
    pc1, pc2, pc3 = st.columns([2, 1.2, 1])
    project_name = pc1.text_input("專案名稱", key="project_name")
    agency_name = pc2.text_input("機關名稱 (PCCES 版 Excel 表頭，可空白)", key="agency_name")
    site_name = pc3.text_input("施工地點 (可空白)", key="site_name")
    present = [m for m in MAJOR_ORDER if m in set(db["主工項"])]
    extras = [m for m in dict.fromkeys(db["主工項"]) if m not in present]
    major_options = present + extras
    selected_raw = st.multiselect("本案涵蓋的主工項", major_options, key="majors",
                              help="只勾選本案會用到的工項，未填數量的細項不會計入。")
    selected = [m for m in major_options if m in selected_raw]   # 依編號排序，不依點選順序

    show_ref = st.toggle("顯示單價依據 (案例區間)", value=False, key="show_ref",
                         help="預設隱藏以保持畫面簡潔；也可把滑鼠移到單價欄的 ⓘ 查看。")

    lines = []
    est_notes = []   # 以經驗概估(非案例)的評估項目，最後統一提醒
    W = [4, 0.8, 1.2, 1.3, 1.4, 2.3]
    for m in selected:
        sub = db[db["主工項"] == m]
        # 鑽探分區列只在資料庫存放單價，不逐列顯示 (由「鑽探分區」下拉帶入)
        sub = sub[~sub["細項名稱"].str.startswith(N_DRILL + DRILL_ZONE_SEP)].reset_index(drop=True)
        # 使用者在資料庫改過細項名稱 (如「中間平台」→「中間平台(含爬梯)」) 時，仍對應到內建項目，自動算量不中斷
        cmap = canonical_map(m, sub["細項名稱"])
        inv_cmap = {v: k for k, v in cmap.items()}
        with st.expander(m, expanded=True):
            # ---- ① 幾何參數 (防呆：先填這裡，下方數量自動帶出，仍可手動修改) ----
            drv = {}
            spec = DRIVERS.get(m, [])
            if spec:
                st.markdown("**① 先填設計參數 → 下方數量自動計算 (之後仍可手動改)**")
                for i0 in range(0, len(spec), 4):
                    chunk = spec[i0:i0 + 4]
                    for col, sp in zip(st.columns(len(chunk)), chunk):
                        kk = f"drv_{m}|{sp['key']}"
                        if sp.get("text"):
                            drv[sp["key"]] = col.text_input(sp["label"], value=sp["default"], key=kk, help=sp.get("help"))
                        elif sp.get("options"):
                            drv[sp["key"]] = col.selectbox(sp["label"], sp["options"], key=kk, help=sp.get("help"))
                        else:
                            dflt = sp["default"]   # None = 留白，由使用者依設計填寫
                            drv[sp["key"]] = comma_input(col, sp["label"], f"drvn_{m}|{sp['key']}", dflt,
                                                         integer=bool(sp.get("int")), help=sp.get("help"), collapsed=False)
                for msg in geometry_warnings(m, drv):
                    (st.info if msg.startswith("ℹ️") else st.warning)(md(msg))
            auto_q = auto_quantities(m, drv)
            auto_p = auto_prices(m, drv)
            if m == M8 and drv.get("zone") and drv["zone"] != ZONE_NONE:
                zr = db[(db["主工項"] == M8) & (db["細項名稱"] == drill_zone_row(drv["zone"]))]
                if len(zr):
                    auto_p[N_DRILL] = (int(zr.iloc[0]["單價(元)"]), f"依分區「{drv['zone']}」(可於單價資料庫修改分區單價)")
            # 資料庫單價已被使用者改過 (與預設不同) → 以資料庫單價為準，不再用程式內建的分段加權價
            for _n in list(auto_p):
                _d = DEFAULT_DF[(DEFAULT_DF["主工項"] == m) & (DEFAULT_DF["細項名稱"] == _n)]
                _c = db[(db["主工項"] == m) & (db["細項名稱"] == inv_cmap.get(_n, _n))]
                if _n == N_WELL_EXC and len(_d) and len(_c) and int(_d.iloc[0]["單價(元)"]) != int(_c.iloc[0]["單價(元)"]):
                    auto_p.pop(_n)
            # 參數改變 → 自動數量 widget 換新 key，重新帶入新計算值
            sig = hashlib.md5(json.dumps(drv, sort_keys=True, default=str).encode()).hexdigest()[:6]

            if m == M9:
                st.caption("剩餘土石方運棄依「運距分區」分列：同一案分送不同土資場時，各分區各填數量；施工便道人工/機械分列，臨時沉砂、臨排、擋土等含在雜項工程費率。")
            st.markdown("**② 工項數量**" if spec else "**工項數量**")
            h = st.columns(W)
            for c, t in zip(h, ["工程名稱", "單位", "數量", "單價 (可改)", "複價", "備註 (如 L=50m@3m)"]):
                c.markdown(f"**{t}**")
            qmap, direct_listed = {}, 0.0
            for _, row in sub.iterrows():
                name = row["細項名稱"]
                cname = cmap.get(name, name)     # 內建項目名稱 (自動算量、評估邏輯用)
                k = f"{m}|{name}"
                c = st.columns(W)
                tag = "" if row["資料來源"] in (SRC_CASE, SRC_USER) else f" `{row['資料來源']}`"
                c[0].markdown(f"{name}{tag}")
                is_auto = cname in auto_q
                if is_auto:
                    c[0].caption(md(f"🔗 自動：{auto_q[cname][1]}"))
                if cname in auto_p:
                    c[0].caption(md(f"🔗 單價自動：{auto_p[cname][1]}"))
                if show_ref and row["備註"]:
                    c[0].caption(md(f"📖 {row['備註']}"))
                c[1].write(row["單位"])
                dq = auto_q[cname][0] if is_auto else 0
                qkey = f"qty2_{k}_{sig}" if is_auto else f"qty2_{k}"
                # 工程數量一律以整數 (無條件進位) 填列；數量、單價皆顯示千位數逗號
                qty = comma_input(c[2], "數量", qkey, cq(dq))
                dp = auto_p[cname][0] if cname in auto_p else int(row["單價(元)"])
                pkey = f"prc_{k}_{sig}" if cname in auto_p else f"prc_{k}"
                price = comma_input(c[3], "單價", pkey, dp, help=md(row["備註"]) if row["備註"] else None)
                note = c[5].text_input("備註", value=ROW_NOTE_DEFAULT.get(cname, ""), key=f"note_{k}", label_visibility="collapsed")
                amt = qty * price
                c[4].write(money(amt) if qty else "-")
                qmap[cname] = float(qty)
                if qty:
                    direct_listed += amt
                    lines.append({"主工項": m, "細項名稱": name, "單位": row["單位"],
                                  "數量": float(qty), "單價": int(price), "複價": float(amt), "備註": note})
                # 防呆提醒：手動改掉自動數量 / 單價偏離資料庫過多
                if is_auto and abs(qty - dq) > max(0.5, abs(dq) * 0.01):
                    st.warning(md(f"⚠️ 「{name}」數量目前為 {qty:g}，依上方參數應為 {dq:,.1f}。"))
                base = int(row["單價(元)"])
                if qty and cname not in auto_p and base > 0 and abs(price - base) / base > 0.3:
                    st.warning(f"⚠️ 「{name}」單價 {price:,} 與資料庫 {base:,} 相差超過 30%，請確認。")

            if m == M5 and qmap.get(N_SHOT, 0) + qmap.get(N_SHOT20, 0) > 0 and qmap.get(N_WALL_DRAIN, 0) == 0:
                st.warning("⚠️ 已列噴凝土/掛網噴凝土護坡，需搭配坡面洩水管 (每 2m×2m 1 支)，目前數量為 0；請在上方填「噴凝土面積 (t=10cm / t=20cm)」自動帶入。")

            # ---- ③ 其他必要工項：系統依案例/參數評估，並列出內容 ----
            comps = evaluate_others(m, drv, qmap, direct_listed)
            if comps:
                st.markdown("**③ 其他必要工項 (系統評估，內容如下)**")
                oc1, oc2 = st.columns([2, 1])
                use_oth = oc1.checkbox("計入下列評估項目", value=True, key=f"useoth_{m}")
                factor = oc2.number_input("評估調整倍率", min_value=0.0, max_value=5.0, value=1.0, step=0.1,
                                          key=f"othf_{m}", help="整體放大/縮小評估金額，例如偏遠山區、工期長可調 1.2")
                cdf = pd.DataFrame([{
                    "項目": x["名稱"], "單位": x["單位"], "數量": x["數量"],
                    "單價": round(x["單價"] * factor), "複價": round(cq(x["數量"]) * x["單價"] * factor),
                    "可信度": x["可信度"], "評估依據": x["依據"],
                } for x in comps])
                st.dataframe(cdf.style.format({"數量": "{:,.1f}", "單價": "{:,.0f}", "複價": "{:,.0f}"}),
                             use_container_width=True, hide_index=True)
                st.caption(md(f"評估小計：{money(cdf['複價'].sum())} 元"
                           + ("" if use_oth else "　(未計入)")
                           + "｜施工便道另列於「9.土方及假設工程」；臨時沉砂、臨排、擋土等臨時設施已含在雜項工程費率內，此處不重複。"))
                if use_oth:
                    for x in comps:
                        lines.append({"主工項": m, "細項名稱": "【評估】" + x["名稱"], "單位": x["單位"],
                                      "數量": float(cq(x["數量"])), "單價": int(round(x["單價"] * factor)),
                                      "複價": float(cq(x["數量"]) * x["單價"] * factor), "備註": x["依據"]})
                        if x["可信度"] == "估算":
                            est_notes.append(f"{m}｜{x['名稱']}")

            # ---- 手動追加 (一般用不到) ----
            with st.popover("＋ 手動追加零星工項 (一式)"):
                k = f"{m}|__lump"
                lname = st.text_input("名稱", value="其他零星工項 (一式)", key=f"lname_{k}")
                lamt = comma_input(st, "金額 (元)", f"lamt_{k}", 0, collapsed=False)
                lnote = st.text_input("說明包含哪些內容", key=f"note_{k}")
            if lamt > 0:
                lines.append({"主工項": m, "細項名稱": (lname or "其他零星工項 (一式)").strip(), "單位": "式",
                              "數量": 1.0, "單價": int(lamt), "複價": float(lamt), "備註": lnote})

    st.markdown("---")
    if not lines:
        st.info("請先勾選主工項並填入數量，系統會即時試算。")
    else:
        majors_used = [m for m in dict.fromkeys(l["主工項"] for l in lines)]
        direct_by_major = {m: sum(l["複價"] for l in lines if l["主工項"] == m) for m in majors_used}
        cost_df, contract, others = calc_costs(direct_by_major, params)
        total = contract + sum(others.values())
        direct_total = cost_df["直接工程費"].sum()

        st.markdown(
            f"<div class='metric-card'><p>估算總經費 (NT$)</p><h2>{money(total)}</h2>"
            f"<p>含稅發包工程費 {money(contract)}　｜　直接工程費 {money(direct_total)}</p></div>",
            unsafe_allow_html=True,
        )

        st.markdown("##### 各主工項經費 (比照 Excel 分頁小計)")
        show = cost_df.copy()
        for c in show.columns[1:]:
            show[c] = show[c].map(money)
        st.dataframe(show, use_container_width=True, hide_index=True)

        chart_df = cost_df[["主工項", "合計"]]
        chart = alt.Chart(chart_df).mark_bar().encode(
            x=alt.X("合計:Q", title="含稅經費 (元)"),
            y=alt.Y("主工項:N", sort=MAJOR_ORDER, title=None),
            color=alt.Color("主工項:N", legend=None,
                            scale=alt.Scale(domain=MAJOR_ORDER, range=MAJOR_COLORS)),
            tooltip=["主工項", alt.Tooltip("合計:Q", format=",.0f")],
        ).properties(height=40 * len(chart_df) + 40)
        st.altair_chart(chart, use_container_width=True)

        with st.expander("📋 完整明細表"):
            detail = pd.DataFrame(lines)
            st.dataframe(detail.style.format({"數量": "{:,.1f}", "單價": "{:,.0f}", "複價": "{:,.0f}"}),
                         use_container_width=True, hide_index=True)

        s = pd.DataFrame([
            ["直接工程費", direct_total],
            [f"雜項工程 ({misc:g}%)", cost_df["雜項工程"].sum()],
            [f"職業安全衛生及環境保護 ({safety:g}%)", cost_df["職安及環保"].sum()],
            [f"保險、廠商管理及利潤 ({profit:g}%)", cost_df["保險、廠商管理及利潤"].sum()],
            [f"營業稅 ({tax:g}%)", cost_df["營業稅"].sum()],
            ["含稅發包工程費", contract],
            *[[k, v] for k, v in others.items() if v],
            ["總計", total],
        ], columns=["項目", "金額(元)"])
        s["金額(元)"] = s["金額(元)"].map(money)
        st.markdown("##### 經費結構")
        st.dataframe(s, use_container_width=True, hide_index=True)

        unpriced = [l["細項名稱"] for l in lines
                    if l["主工項"] in set(db["主工項"]) and
                    db[(db["主工項"] == l["主工項"]) & (db["細項名稱"] == l["細項名稱"])]["資料來源"].eq(SRC_EST).any()]
        if unpriced:
            st.warning("以下項目單價為「估算待核」(案例中無依據)，請以廠商報價或 PCCES 核對：\n\n- " + "\n- ".join(unpriced))

        if est_notes:
            st.info("以下「其他必要工項」為工程經驗概估 (非案例單價)，請依實際條件核對：\n\n- " + "\n- ".join(md(x) for x in est_notes))

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            st.download_button(
                "📥 下載 Excel (總表+各主工項分頁)",
                data=build_excel(lines, params, project_name),
                file_name=f"{project_name or '經費初估'}_經費估算.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with b2:
            st.download_button(
                "📥 下載 PCCES 版 Excel (預算總表+詳細表)",
                data=build_pcces_excel(lines, params, project_name, agency_name, site_name),
                file_name=f"{project_name or '經費初估'}_PCCES版.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                help="比照預算書格式：壹 發包工作費 → 排水/地錨/邊坡…各工程 → 雜項、職安、利潤、營業稅。",
            )
        with b3:
            st.download_button(
                "📥 下載明細 CSV",
                data=pd.DataFrame(lines).to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{project_name or '經費初估'}_明細.csv", mime="text/csv",
                use_container_width=True,
            )
        with b4:
            if st.button("📤 發布至團隊歷史紀錄", use_container_width=True):
                if not project_name.strip():
                    st.error("請先輸入專案名稱。")
                elif not acting_user():
                    st.error("請先在左側輸入你的名字。")
                else:
                    store.append_history({
                        "時間": now_str(),
                        "專案名稱": project_name.strip(),
                        "發布者": acting_user(),
                        "直接工程費": direct_total,
                        "附屬費用": cost_df["雜項工程"].sum(),
                        "職安環保費": cost_df["職安及環保"].sum(),
                        "管理費": cost_df["保險、廠商管理及利潤"].sum(),
                        "物價調整費": others["物價調整費"],
                        "預備費": others["工程預備費"],
                        "營業稅": cost_df["營業稅"].sum(),
                        "設計監造費": others["設計監造費"],
                        "總經費": total,
                        "細項明細": lines,
                    })
                    st.cache_data.clear()
                    st.session_state["flash"] = "已發布至團隊歷史紀錄。"
                    st.rerun()

# ==========================================
# TAB 2
# ==========================================
elif selected_page == "📚 單價資料庫":
    st.header("📚 單價資料庫")
    st.markdown(
        "資料來源欄：**已發包案例** (直接取自預算書)、**案例推算** (用案例單價組合)、"
        "**估算待核** (案例中無此項，請核對)、**使用者新增**、**使用者修改** (你改過的預設單價，系統改版時會保留，不用重打；"
        "把單價改回預設值即還原，之後會跟著新版預設更新)。備註欄記錄案例價格區間。"
    )
    if not EDITORS:
        st.warning("🔓 尚未讀到帳號密碼設定 (Secrets 的 [editors])，目前任何人都能編輯單價。")
    if EDITORS and not can_edit():
        st.info("🔒 目前為唯讀。要修改、新增或上傳單價，請先登入。")
        with st.form("login_form"):
            lc1, lc2 = st.columns(2)
            acc = lc1.text_input("帳號")
            pwd = lc2.text_input("密碼", type="password")
            if st.form_submit_button("登入"):
                if _login(acc, pwd):
                    st.rerun()
                else:
                    st.error("帳號或密碼錯誤。")
        q = st.text_input("🔍 關鍵字搜尋", key="db_search_ro")
        view = db if not q else db[db.apply(lambda r: q in " ".join(r.astype(str)), axis=1)]
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button("📥 下載目前資料庫 CSV", data=db.to_csv(index=False).encode("utf-8-sig"),
                           file_name="shared_cost_db.csv", mime="text/csv")
    else:
        if EDITORS:
            st.caption(f"✅ 已登入：{st.session_state.get('editor_user', '')}　(修改會以此帳號記入更新紀錄)")
            if st.button("登出"):
                st.session_state["editor_ok"] = False
                st.session_state["editor_user"] = ""
                st.rerun()
        q = st.text_input("🔍 關鍵字搜尋", key="db_search")
        view = db if not q else db[db.apply(lambda r: q in " ".join(r.astype(str)), axis=1)]
        edited = st.data_editor(
            view, num_rows="dynamic", use_container_width=True, key="db_editor", hide_index=True,
            column_config={"單價(元)": st.column_config.NumberColumn("單價(元)", min_value=0, format="localized")},
        )
        user = acting_user()
        note_txt = st.text_input("本次修改備註 (選填，會記入更新紀錄)", key="edit_note")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 儲存修改", use_container_width=True, disabled=bool(q),
                         help="搜尋中無法儲存，請先清除關鍵字。新增的列請在『資料來源』留空或填『使用者新增』。"):
                if not user:
                    st.error("請先在左側輸入你的名字。" if not EDITORS else "請先登入。")
                else:
                    try:
                        n = commit_db(normalize_db(edited), db, user, "表格編輯", note_txt, "before_edit")
                        st.session_state["flash"] = (f"已儲存 {n} 項變更並記入更新紀錄。" if n else "沒有任何變更。")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"儲存失敗：{e}")
        with c2:
            st.download_button("📥 下載目前資料庫 CSV", data=db.to_csv(index=False).encode("utf-8-sig"),
                               file_name="shared_cost_db.csv", mime="text/csv", use_container_width=True)

        st.markdown("##### 📤 上傳單價更新 (先預覽差異，確認後才寫入)")
        st.caption(md("支援 CSV 或 Excel(.xlsx)。必要欄位：主工項、細項名稱、單位、單價；選填：備註、資料來源。"
                      "欄名「規劃單價(元)」「案例依據/說明」也可 (同 單價依據與合理性評估.xlsx 第 1 分頁格式)。"
                      "以「主工項＋細項名稱」對應既有項目。"))
        up = st.file_uploader("選擇檔案", type=["csv", "xlsx"], key="db_upload")
        mode = st.radio("上傳方式", ["合併 (新增或更新，不刪除原有項目)", "整份覆蓋 (檔案中沒有的原有項目會被刪除)"],
                        key="up_mode")
        if up is not None:
            changes = None
            try:
                raw = read_uploaded_table(up)
                upd = normalize_db(raw)
                merged = merge_db(db, upd, "資料來源" in raw.columns) if mode.startswith("合併") else upd
                changes = diff_db(db, merged)
            except ValueError as e:
                st.error(f"檔案格式有誤：{e}")
            if changes is not None:
                if not changes:
                    st.info("與目前資料庫完全相同，沒有需要更新的項目。")
                else:
                    cdf = pd.DataFrame(changes)
                    n_add, n_mod, n_del = [int((cdf["類型"] == t).sum()) for t in ("新增", "修改", "刪除")]
                    st.markdown(f"**預覽：新增 {n_add} 項、修改 {n_mod} 欄、刪除 {n_del} 項**")
                    st.dataframe(cdf, use_container_width=True, hide_index=True)
                    big = [c for c in changes if c["漲跌"] and abs(float(c["漲跌"].rstrip("%"))) > 30]
                    if big:
                        st.warning(f"⚠️ 有 {len(big)} 項單價漲跌超過 30%，請確認檔案單位與數字無誤。")
                    if n_del:
                        st.warning("⚠️ 整份覆蓋會刪除上列項目；若只是要更新部分單價，請改選「合併」。")
                    if st.button("✅ 確認寫入資料庫", type="primary"):
                        if not user:
                            st.error("請先在左側輸入你的名字。" if not EDITORS else "請先登入。")
                        else:
                            act = "上傳合併" if mode.startswith("合併") else "上傳覆蓋"
                            tag = "before_upload"
                            note = (note_txt + "　" if note_txt else "") + f"檔案：{up.name}"
                            n = commit_db(merged, db, user, act, note, tag)
                            st.session_state["flash"] = f"已寫入 {n} 項變更並記入更新紀錄。"
                            st.rerun()


    with st.expander("🕘 更新紀錄 (誰、何時、改了什麼)"):
        lg = _cached_log(store)
        if len(lg):
            st.dataframe(lg.iloc[::-1].head(300), use_container_width=True, hide_index=True)
            st.download_button("📥 下載完整更新紀錄 CSV", data=lg.to_csv(index=False).encode("utf-8-sig"),
                               file_name="update_log.csv", mime="text/csv")
        else:
            st.info("尚無更新紀錄。")

# ==========================================
# TAB 3
# ==========================================
else:
    st.header("📁 團隊歷史估算紀錄")
    history_data = load_history()
    if history_data:
        all_export = []
        for record in reversed(history_data):
            who = f" ({record['發布者']})" if record.get("發布者") else ""
            title = f"📌 [{record.get('時間', '')}] {record.get('專案名稱', '(未命名)')}{who} ─ 總經費: NT$ {int(float(rec_get(record, '總經費'))):,}"
            with st.expander(title):
                m1 = st.columns(5)
                m1[0].metric("直接工程費", f"{int(rec_get(record, '直接工程費')):,}")
                m1[1].metric("雜項/附屬費用", f"{int(rec_get(record, '附屬費用', '安全品管等附屬', '雜項費')):,}")
                m1[2].metric("職安及環保", f"{int(rec_get(record, '職安環保費')):,}")
                m1[3].metric("管理及利潤", f"{int(rec_get(record, '管理費')):,}")
                m1[4].metric("營業稅", f"{int(rec_get(record, '營業稅')):,}")
                m2 = st.columns(4)
                m2[0].metric("物價調整費", f"{int(rec_get(record, '物價調整費')):,}")
                m2[1].metric("預備費", f"{int(rec_get(record, '預備費')):,}")
                m2[2].metric("設計監造費", f"{int(rec_get(record, '設計監造費')):,}")
                m2[3].metric("總經費", f"{int(rec_get(record, '總經費')):,}")
                if record.get("細項明細"):
                    d = pd.DataFrame(record["細項明細"])
                    fmt = {c: "{:,.0f}" for c in ("單價(元)", "單價", "複價") if c in d.columns}
                    if "數量" in d.columns:
                        fmt["數量"] = "{:,.1f}"
                    st.dataframe(d.style.format(fmt), use_container_width=True, hide_index=True)
                    for row in record["細項明細"]:
                        x = dict(row)
                        x["專案名稱"] = record.get("專案名稱", "")
                        x["估算時間"] = record.get("時間", "")
                        all_export.append(x)
                else:
                    st.warning("舊版紀錄未儲存明細。")
        st.markdown("---")
        b1, b2, b3 = st.columns(3)
        with b1:
            summ = pd.DataFrame(history_data).drop(columns=["細項明細"], errors="ignore")
            st.download_button("📥 下載總表 CSV", data=summ.to_csv(index=False).encode("utf-8-sig"),
                               file_name="history_summary.csv", mime="text/csv", use_container_width=True)
        with b2:
            if all_export:
                ex = pd.DataFrame(all_export)
                cols = ["專案名稱", "估算時間"] + [c for c in ex.columns if c not in ("專案名稱", "估算時間")]
                st.download_button("📥 下載含明細 CSV", data=ex[cols].to_csv(index=False).encode("utf-8-sig"),
                                   file_name="history_full_details.csv", mime="text/csv", use_container_width=True)
        with b3:
            st.checkbox("我了解將清空所有同仁的紀錄 (系統會先自動備份)", key="confirm_clear")
            st.button("🗑 清空所有團隊紀錄", use_container_width=True,
                      disabled=not (st.session_state.get("confirm_clear", False) and acting_user() and can_edit()),
                      on_click=_clear_history, help="需先勾選左側確認；並需已輸入名字 (有設定帳號密碼時，需先在「單價資料庫」分頁登入)。")
    else:
        st.info("目前尚無團隊估算紀錄。")

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:gray;font-size:13px;'>"
    "📌 預設單價整理自 12 份已發包預算書 (地錨、排樁、集水井)，各案年度不同、未做物價調整；"
    "標示「估算待核」者案例中無依據。本系統僅供規劃階段概估，正式經費應依地質調查、設計圖說及預算書為準。"
    "</div>",
    unsafe_allow_html=True,
)
