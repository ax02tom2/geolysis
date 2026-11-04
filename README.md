# 大地工程分析系統（Geolysis）

本專案為 Streamlit 網頁應用程式，整合五大大地工程分析模組，並擴充整孔岩心柱狀圖文件匯入、逐列影像分析及斷裂候選人工覆核。

## 功能內容

- 模組一：Hoek-Brown (2002)、GSI／mi／UCS／D、等效 Mohr-Coulomb 參數與破壞包絡線。
- 岩心柱狀圖：DOCX／PDF 匯入、照片列擷取、頁面深度與列號索引、整頁原圖與判釋疊圖。PDF parser 已修正首箱漏列及末頁部分箱照二次裁切。
- 岩心影像：托盤四角校正、固定四列 × 每列 1 m、影像岩心／空隙候選及疑似斷裂候選。
- RQD：候選位置需人工覆核；天然節理、機械破損與待確認不可混為一談。影像初估不等於正式 RQD。
- 模組二：USCS／AASHTO 土壤分類。
- 模組三：SPT 修正與經驗估算。
- 模組四：淺基礎容許承載力估算。
- 模組五：極限承載力理論估算。

## 專案結構

```text
app.py
core_log_parser.py
core_photo_analysis.py
requirements.txt
README.md
point_editor/index.html
tests/test_core_fracture_analysis.py
```

## 本機啟動

建議 Python 3.11 或更新版本：

```bash
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
# Windows CMD
.venv\\Scripts\\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## 測試

```bash
pip install pytest
python -m py_compile app.py core_log_parser.py core_photo_analysis.py
pytest -q
```

## 部署注意

- Streamlit Cloud 的主程式檔案需指定為 `app.py`，專案根目錄必須同時包含 `core_log_parser.py`、`core_photo_analysis.py`、`requirements.txt` 與 `point_editor/index.html`。
- 本 ZIP 不包含 `storage.py`，因本版 `app.py` 不匯入 `storage`，也不包含工程估價系統的 Google Sheets 儲存功能。請勿與另一個引用 `from storage import ...` 的工程估價版 `app.py` 混用。
- 若 Cloud 仍顯示 `from storage import ...`，代表 Cloud 實際部署的 `app.py` 不是本 ZIP 這份版本，需確認部署分支、主程式檔路徑及 commit。
- `geolysis` 為原專案保留的相依套件；本版 Hoek-Brown 等主要公式直接在 `app.py` 計算。

## 工程判釋限制

影像分析目前提供候選區域與候選斷裂位置，不可僅憑顏色或暗線自動判定天然節理、機械破損。RQD 仍須依實際岩心、天然節理界定段長及人工覆核；照片推估不能取代現場紀錄或實驗室試驗。

## V3 快取失效與執行診斷

- `core_photo_analysis.py` 的 SHA256 會成為逐列分析快取鍵的一部分；修改核心影像演算法後不會沿用舊的失敗快取。
- 啟動／重跑時會比對模組來源指紋，必要時 reload 核心分析模組。
- 頁面顯示分析引擎 Build ID；「分析引擎診斷」可檢視來源路徑、指紋與完整 traceback。
- 若頁面沒有顯示 `v3-` Build ID，代表目前部署仍不是此版本。

## V3.1 PDF parser 修正與驗證

- 不再以頁高 16% 作為岩心箱照起始門檻，避免漏掉頁面第一箱。
- 依同頁箱照高度判斷末頁圖片是否已裁成剩餘列數，避免重複裁切。
- 可用 `H25_CORE_PDF` 環境變數執行實際 PDF 回歸測試；測試會檢查 3 頁、20/20/10 列、列號 1–50、深度及末兩列影像。
- 本次 H25-1B 測試為 19 passed。分析核心仍未達到自動判定天然節理／機械破損的驗證程度，詳見 `VALIDATION_REPORT.txt`。


## V3.2 Cloud startup hotfix

V3.2 removes forced module reload during Streamlit reruns and replaces dataclass-based records with ordinary Python classes to avoid module-registration edge cases. This is a targeted mitigation for `AttributeError: NoneType ... __dict__`; confirm against the full Streamlit Cloud traceback after deployment.
