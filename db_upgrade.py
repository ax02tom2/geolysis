# -*- coding: utf-8 -*-
"""單價資料庫「改版不遺失使用者修改」邏輯 (不依賴 Streamlit，可單獨測試)。

做法：
 1. 使用者在「單價資料庫」改了預設項目的單價/單位 → 資料來源自動標成「使用者修改」(mark_edits)。
 2. 版本更新重建預設資料庫時，「使用者修改」與「使用者新增」的項目照舊保留 (upgrade_db)。
 3. 第一次升級 (舊資料庫還沒有「使用者修改」標記)：拿舊版預設快照 (legacy_defaults.py) 比對，
    與舊預設不同的單價視為使用者改過，一併保留。
 4. 使用者把單價改回預設值 → 自動還原為預設來源，之後新版調整預設價時會跟著更新。
"""
import pandas as pd

from legacy_defaults import LEGACY_DEFAULTS
from cost_logic import canonical_map

SRC_CASE = "已發包案例"
SRC_DERIVED = "案例推算"
SRC_EST = "估算待核"
SRC_USER = "使用者新增"
SRC_EDIT = "使用者修改"
DEFAULT_SOURCES = (SRC_CASE, SRC_DERIVED, SRC_EST)


def _key(r):
    return (r["主工項"], r["細項名稱"])


def mark_edits(cur, new, default_df):
    """儲存/上傳時：預設項目的單價或單位被改 → 標「使用者修改」；改回預設值 → 還原預設來源。"""
    cur_map = {_key(r): r for _, r in cur.iterrows()}
    dflt = {_key(r): r for _, r in default_df.iterrows()}
    new = new.copy()
    for i, r in new.iterrows():
        k = _key(r)
        if k not in dflt:
            continue                       # 使用者自行新增的項目：本來就會保留
        d = dflt[k]
        same_as_default = (int(r["單價(元)"]) == int(d["單價(元)"])) and (r["單位"] == d["單位"])
        if same_as_default:
            if r["資料來源"] == SRC_EDIT:
                new.at[i, "資料來源"] = d["資料來源"]
            continue
        old = cur_map.get(k)
        changed = old is None or int(old["單價(元)"]) != int(r["單價(元)"]) or old["單位"] != r["單位"]
        if changed or r["資料來源"] == SRC_EDIT:
            new.at[i, "資料來源"] = SRC_EDIT
    return new


def detect_legacy_edits(old, version):
    """舊資料庫尚無「使用者修改」標記時：與該版預設快照比對，找出被改過的列 (回傳 index 集合)。"""
    base = LEGACY_DEFAULTS.get(version)
    if not base:
        return set()
    hit = set()
    for i, r in old.iterrows():
        b = base.get(f"{r['主工項']}||{r['細項名稱']}")
        if b is None:
            continue
        if r["單位"] != b[0] or int(r["單價(元)"]) != int(b[1]):
            hit.add(i)
    return hit


def upgrade_db(old, new_default, old_version):
    """舊資料庫 + 新預設 → 升級後資料庫。回傳 (df, notes)；notes 為要寫入更新紀錄的文字清單。"""
    new_df = new_default.copy()
    notes = []
    old = old.copy()
    if not (old["資料來源"] == SRC_EDIT).any():
        for i in detect_legacy_edits(old, old_version):
            if old.at[i, "資料來源"] in DEFAULT_SOURCES + (SRC_USER,):
                old.at[i, "資料來源"] = SRC_EDIT
    keys = {_key(r): i for i, r in new_df.iterrows()}
    # 使用者把預設項目改了名稱 (如「中間平台」→「中間平台(含爬梯)」)：新版預設沿用使用者的名稱，程式的自動算量照常對應
    for major in old["主工項"].unique():
        orphan = old[(old["主工項"] == major) & old["資料來源"].isin(DEFAULT_SOURCES + (SRC_EDIT,))]
        orphan = [n for n in orphan["細項名稱"] if (major, n) not in keys]
        for oname, cname in canonical_map(major, orphan).items():
            if oname != cname and (major, cname) in keys:
                i = keys.pop((major, cname))
                new_df.at[i, "細項名稱"] = oname
                keys[(major, oname)] = i
                notes.append(f"保留改名：{cname} → {oname}")
    extra = []
    for _, r in old.iterrows():
        k = _key(r)
        if r["資料來源"] == SRC_EDIT:
            if k in keys:
                i = keys[k]
                dp = int(new_df.at[i, "單價(元)"])
                new_df.at[i, "單位"] = r["單位"]
                new_df.at[i, "單價(元)"] = int(r["單價(元)"])
                new_df.at[i, "資料來源"] = SRC_EDIT
                new_df.at[i, "備註"] = f"{new_df.at[i, '備註']}｜【你修改的單價；新版預設為 {dp:,}】"
                notes.append(f"保留修改：{k[1]} → {int(r['單價(元)']):,}/{r['單位']} (新版預設 {dp:,})")
            else:
                notes.append(f"淘汰(新版已無此項)：{k[1]}，你原修改的單價 {int(r['單價(元)']):,}")
        elif r["資料來源"] == SRC_USER and k not in keys:
            extra.append(r)
    if extra:
        new_df = pd.concat([new_df, pd.DataFrame(extra)], ignore_index=True)
    return new_df.reset_index(drop=True), notes
