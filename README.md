# geolysis 大地工程分析系統｜Web 版

本版本保留五個工程分析模組，專供 Streamlit Community Cloud／一般 Streamlit 網頁部署。

## 保留功能
- 模組一：Hoek–Brown 岩體參數分析與等效 Mohr–Coulomb 參數。
- 模組二：USCS／AASHTO 土壤分類。
- 模組三：SPT 修正與經驗估算。
- 模組四：容許承載力與沉陷控制估算。
- 模組五：極限承載力估算與參數帶入。

## 本版調整
岩心照片匯入、照片判釋、天然節理／機械破損分類、採取率影像初估及 RQD 影像估算已從網頁版移除，改由獨立 Windows 單機程式處理。網頁版不再載入 OpenCV、PyMuPDF、Pillow 或本機視覺模型，也不會顯示未執行的 AI 判釋結果。

## 本機／Cloud 啟動
```bash
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit Cloud 部署時，GitHub 專案根目錄選擇 `app.py`。本版本不需要岩心照片分析相依套件。

## 工程注意
本系統提供工程估算與分類輔助，輸入資料、適用條件及公式假設仍須由工程人員核對；計算結果不應脫離地層、試驗及設計規範單獨使用。


## 2026-11-05 hotfix
Restored the missing GSI matrix, rock mi/UCS, disturbance D, application-scale, unit weight and height input controls in Module 1. The previous web split accidentally removed these controls while leaving calculation statements, causing a NameError.
