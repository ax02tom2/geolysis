# -*- coding: utf-8 -*-
"""
PCCES 版 Excel 匯出 (比照「預算書」的 預算總表 / 預算詳細表 格式)。
不依賴 Streamlit，可單獨測試。

結構：
  壹 發包工作費
      一 排水工程 / 二 地錨工程 / 三 邊坡工程 ... (直接工程，依 SECTION_MAP 分章)
      N+1 雜項工程            (直接工程費 × 雜項%)
      N+2 職業安全衛生及環境保護 (直接工程費 × 職安%)
      N+3 保險、廠商管理及利潤  ((直接工程 + 雜項 + 職安) × 利潤%)
      N+4 營業稅              (前述各項合計 × 稅%)
  貳 其他費用 (物價調整費、工程預備費、設計監造費，費率為 0 者不列)
  總價(總計)
"""
import io
import math
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.worksheet.properties import PageSetupProperties

from cost_logic import M1, M2, M3, M4, M5, M6, M7, M8, M9

# PCCES 章節對照：(章節名稱, [對應的主工項...])。要調整分章方式改這裡即可。
SECTION_MAP = [
    ("排水工程", [M1, M2]),
    ("集水井工程", [M3]),
    ("地錨工程", [M4]),
    ("邊坡工程", [M5]),
    ("擋土及抗滑工程", [M6]),
    ("落石防護工程", [M7]),
    ("調查及監測工程", [M8]),
    ("土方及假設工程", [M9]),
]

FONT = "新細明體"
_CN = "零一二三四五六七八九"
thin = Side(style="thin", color="000000")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
MONEY = "#,##0"
QTY = "#,##0"


def cn_num(n):
    """1→一, 10→十, 11→十一, 21→二十一"""
    if n < 10:
        return _CN[n]
    if n < 20:
        return "十" + (_CN[n - 10] if n > 10 else "")
    tens, ones = divmod(n, 10)
    return _CN[tens] + "十" + (_CN[ones] if ones else "")


def _r(x):
    """四捨五入到整數 (一般進位，非銀行家捨入)"""
    return int(math.floor(x + 0.5))


def _pct(x):
    return f"{x:g}%"


def _section_name(major):
    return re.sub(r"[\(（].*$", "", re.sub(r"^\d+[\.、]\s*", "", major)).strip() + "工程"


def group_sections(lines):
    """把明細依 SECTION_MAP 分章；回傳 [(章節名稱, [line,...]), ...]，只含有資料的章節"""
    used, out = set(), []
    for name, majors in SECTION_MAP:
        items = [l for m in majors for l in lines if l["主工項"] == m]
        used.update(majors)
        if items:
            out.append((name, items))
    # 資料庫中使用者自行新增、不在對照表內的主工項：各自成章
    for m in dict.fromkeys(l["主工項"] for l in lines):
        if m not in used:
            out.append((_section_name(m), [l for l in lines if l["主工項"] == m]))
    return out


def compute_pcces(lines, p):
    """依 PCCES 逐項四捨五入計算。回傳 dict，含各章小計與各費用項。"""
    sections = []
    for name, items in group_sections(lines):
        rows = []
        for l in items:
            amt = _r(l["數量"] * l["單價"])
            rows.append(dict(name=l["細項名稱"], unit=l["單位"], qty=l["數量"],
                             price=l["單價"], amt=amt, note=l.get("備註", "") or ""))
        sections.append(dict(name=name, rows=rows, total=sum(r["amt"] for r in rows)))
    direct = sum(s["total"] for s in sections)
    misc = _r(direct * p["misc"] / 100)
    safety = _r(direct * p["safety"] / 100)
    profit = _r((direct + misc + safety) * p["profit"] / 100)
    tax = _r((direct + misc + safety + profit) * p["tax"] / 100)
    contract = direct + misc + safety + profit + tax
    others = []
    for key, label in (("escalation", "物價調整費"), ("contingency", "工程預備費"), ("design", "設計監造費")):
        pc = p.get(key, 0) or 0
        if pc:
            others.append((f"{label}(壹項*{_pct(pc)})", _r(contract * pc / 100)))
    return dict(sections=sections, direct=direct, misc=misc, safety=safety, profit=profit,
                tax=tax, contract=contract, others=others,
                total=contract + sum(a for _, a in others))


def _font(size=10, bold=False):
    return Font(name=FONT, size=size, bold=bold)


def _header(ws, agency, title, project_name, location, ncols_last="G"):
    ws.merge_cells(f"A1:{ncols_last}1")
    ws.merge_cells(f"A2:{ncols_last}2")
    ws["A1"] = agency or ""
    ws["A2"] = title
    for c in ("A1", "A2"):
        ws[c].font = _font(16, True)
        ws[c].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 24
    ws.row_dimensions[2].height = 24
    ws.merge_cells("B6:D6")
    ws.merge_cells("B7:D7")
    ws.merge_cells("F6:G6")
    ws.merge_cells("F7:G7")
    ws["A6"], ws["B6"] = "工程名稱", project_name or "(未命名專案)"
    ws["E6"], ws["F6"] = "會計科目", ""
    ws["A7"], ws["B7"] = "施工地點", location or ""
    ws["E7"], ws["F7"] = "工程編號", ""
    for r in (6, 7):
        ws.row_dimensions[r].height = 24
        for col in "ABCDEFG":
            cell = ws[f"{col}{r}"]
            cell.border = BORDER
            cell.font = _font()
            cell.alignment = Alignment(horizontal="center" if col in "AE" else "left", vertical="center")


def _fee_rows(res, p, n_sec):
    """四項費用的 (項次, 名稱, 金額) 與其公式說明，項次接續在直接工程章節之後"""
    last_direct = cn_num(n_sec)
    rng_profit = f"一~{cn_num(n_sec + 2)}"
    rng_tax = f"一~{cn_num(n_sec + 3)}"
    return [
        (cn_num(n_sec + 1), f"雜項工程 (一~{last_direct}項直接工程費*{_pct(p['misc'])})", res["misc"]),
        (cn_num(n_sec + 2), f"職業安全衛生及環境保護 (一~{last_direct}項直接工程費*{_pct(p['safety'])})", res["safety"]),
        (cn_num(n_sec + 3), f"保險、廠商管理及利潤({rng_profit})項*{_pct(p['profit'])}", res["profit"]),
        (cn_num(n_sec + 4), f"營業稅({rng_tax})項*{_pct(p['tax'])}", res["tax"]),
    ]


def build_pcces_excel(lines, p, project_name="", agency="", location=""):
    """產出 PCCES 版 Excel (預算總表 + 預算詳細表)，回傳 bytes。
    p 需含 misc, safety, profit, tax；選填 escalation, contingency, design。"""
    res = compute_pcces(lines, p)
    secs = res["sections"]
    n_sec = len(secs)
    fees = _fee_rows(res, p, n_sec)

    wb = Workbook()
    # ================= 預算總表 =================
    ws = wb.active
    ws.title = "預算總表"
    _header(ws, agency, "總表[預算]", project_name, location)
    heads = {"A8": "項 次", "B8": "工  作  項  目", "F8": "金額(元)", "G8": "備註"}
    ws.merge_cells("B8:E8")
    for col in "ABCDEFG":
        c = ws[f"{col}8"]
        if f"{col}8" in heads:
            c.value = heads[f"{col}8"]
        c.border, c.font = BORDER, _font()
        c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[8].height = 24

    r = 9

    def srow(no, name, amt, bold=False, indent=0):
        nonlocal r
        ws.merge_cells(f"B{r}:E{r}")
        ws[f"A{r}"], ws[f"B{r}"], ws[f"F{r}"] = no, name, amt
        for col in "ABCDEFG":
            c = ws[f"{col}{r}"]
            c.border, c.font = BORDER, _font(10, bold)
        ws[f"A{r}"].alignment = Alignment(horizontal="center", vertical="center")
        ws[f"B{r}"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=indent)
        ws[f"F{r}"].number_format = MONEY
        ws.row_dimensions[r].height = 21
        r += 1

    srow("壹", "發包工作費", res["contract"], bold=True)
    for i, s in enumerate(secs, 1):
        srow(cn_num(i), s["name"], s["total"])
    for no, name, amt in fees:
        srow(no, name, amt)
    if res["others"]:
        srow("貳", "其他費用", sum(a for _, a in res["others"]), bold=True)
        for i, (name, amt) in enumerate(res["others"], 1):
            srow(cn_num(i), name, amt)
    srow("", "總價(總計)", res["total"], bold=True)
    for col, w in zip("ABCDEFG", (12.7, 27.3, 6.3, 12.1, 9.7, 16, 17.3)):
        ws.column_dimensions[col].width = w

    # ================= 預算詳細表 =================
    wd = wb.create_sheet("預算詳細表")
    _header(wd, agency, "詳細價目表[預算]", project_name, location)
    for col, t in zip("ABCDEFG", ("項 次", "項  目  及  說  明", "單 位", "數 量", "單 價", "複 價", "編碼(備註)")):
        c = wd[f"{col}8"]
        c.value, c.border, c.font = t, BORDER, _font()
        c.alignment = Alignment(horizontal="center", vertical="center")
    wd.row_dimensions[8].height = 24

    r = 9

    def drow(no="", name="", unit=None, qty=None, price=None, amt=None, note="", bold=False, section=False):
        nonlocal r
        vals = [no, name, unit, qty, price, amt, note]
        for col, v in zip("ABCDEFG", vals):
            c = wd[f"{col}{r}"]
            c.value = v if v != "" else None
            c.border, c.font = BORDER, _font(10, bold)
        wd[f"A{r}"].alignment = Alignment(horizontal="center", vertical="top")
        wd[f"B{r}"].alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        wd[f"C{r}"].alignment = Alignment(horizontal="center", vertical="top")
        wd[f"D{r}"].number_format = QTY
        wd[f"E{r}"].number_format = MONEY
        wd[f"F{r}"].number_format = MONEY
        for col in "DEF":
            wd[f"{col}{r}"].alignment = Alignment(horizontal="right", vertical="top")
        wd[f"G{r}"].alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        r += 1

    drow("壹", "發包工作費", bold=True)
    for i, s in enumerate(secs, 1):
        drow(cn_num(i), s["name"], bold=True)
        for j, it in enumerate(s["rows"], 1):
            drow(j, it["name"], it["unit"], it["qty"], it["price"], it["amt"], it["note"])
    for no, name, amt in fees:
        drow(no, name, None, 1, amt, amt)
    if res["others"]:
        drow("貳", "其他費用", bold=True)
        for i, (name, amt) in enumerate(res["others"], 1):
            drow(cn_num(i), name, "式", 1, amt, amt)
    drow("", "總價(總計)", None, None, None, res["total"], bold=True)
    for col, w in zip("ABCDEFG", (11.7, 40, 6.7, 10.7, 10.3, 12.7, 28)):
        wd.column_dimensions[col].width = w
    wd.freeze_panes = "A9"

    # ================= 列印設定 (A4 直式、寬度縮放為 1 頁、每頁重複表頭) =================
    for sh in (ws, wd):
        sh.page_setup.orientation = "portrait"
        sh.page_setup.paperSize = 9
        sh.page_setup.fitToWidth = 1
        sh.page_setup.fitToHeight = 0
        sh.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
        sh.print_title_rows = "1:8"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
