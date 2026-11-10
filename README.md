# geolysis 大地工程分析系統｜Web 版

本專案為 Streamlit 網頁版，保留五個大地工程分析模組。岩心照片判釋與 RQD 影像流程已獨立，不屬於本 Web 專案。

## 五個分析模組

1. **Hoek–Brown 岩體參數**：GSI、mi、完整岩石 UCS、擾動係數 D 與應用尺度；可估算等效 Mohr–Coulomb 參數。輸出受圍壓範圍與適用模式限制。
2. **土壤分類**：USCS 與 AASHTO 分類、級配與塑性指標檢核。
3. **SPT 全修正**：能量、鑽孔、取樣器、桿長、上覆壓力與逐深度剖面修正。
4. **沉陷與容許壓力**：Burland–Burbidge 沉陷估算、單層／多層主固結、時間率、立即沉陷、次壓縮、差異沉陷與開挖回彈；可用承載力上限控制沉陷設計壓力。
5. **極限承載力**：Terzaghi、Meyerhof、Hansen、Vesic；含地下水、偏心有效尺寸、載重傾斜及總／淨承載力輸出。各理論的公式體系與適用限制需分別確認，不應混用修正係數。

## 本機啟動

已驗證的 CI 執行環境為 Python 3.11。

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit Community Cloud 部署時，GitHub 專案根目錄選擇 `app.py`。依賴套件僅保留 Web 介面實際使用的 Streamlit、Pandas 與 Plotly；工程計算由專案內的 `geolysis_engine.py` 執行。

## 自動化驗證

GitHub Actions 會在推送至 main、Pull Request 及手動觸發時執行：
- Python 編譯檢查：`app.py`、`geolysis_engine.py`
- 工程計算回歸測試
- Streamlit 數字輸入元件 key 唯一性檢查
- Web 版功能範圍檢查

最近一次完整 CI：**141 passed**（2026-11-10，Python 3.11）。這代表自動化測試通過，不等同於已在 Streamlit Cloud 完成部署或瀏覽器端驗收。

## 工程使用限制

本系統提供工程計算與分類輔助，不取代現地調查、試驗資料、地層模型、規範選用與工程師審查。使用者應確認輸入參數、單位、排水條件、載重組合、地下水位及公式適用範圍。未實作的斜坡地表、傾斜基底、地震、多層承載力、基底滑動與整體穩定，不得視為已完成分析。
