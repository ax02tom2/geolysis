# geolysis 大地工程分析系統｜Web 版

本專案為 Streamlit 網頁版，包含五個大地工程分析模組，以及模組一的整孔岩心柱狀圖 DOCX／PDF 解析與逐列 RQD 影像初估。影像分析採本機 OpenCV 演算法，不依賴付費 AI 服務；所有 RQD 候選仍須由使用者覆核。

## 五個分析模組

1. **岩體參數與岩心分析**：Hoek–Brown 的 GSI、mi、完整岩石 UCS、擾動係數 D 與應用尺度；另支援整孔 DOCX／PDF 岩心柱狀圖匯入、每列 1 m 採取率與 RQD 影像初估、疑似斷裂標示及人工覆核。Hoek–Brown 輸出受圍壓範圍與適用模式限制。
2. **土壤分類**：USCS 與 AASHTO 分類、級配與塑性指標檢核。
3. **SPT 全修正**：能量、鑽孔、取樣器、桿長、上覆壓力與逐深度剖面修正。
4. **沉陷與容許壓力**：Burland–Burbidge 沉陷估算、單層／多層主固結、時間率、立即沉陷、次壓縮、差異沉陷與開挖回彈。
5. **極限承載力與基礎穩定**：Terzaghi、Meyerhof、Hansen、Vesic；另含下列擴充分析。

## 模組五擴充分析（已納入程式及 UI）

- **斜坡地表與傾斜基底**：依 USACE EM 1110-1-1905（2025）Table 5-2 至 5-4 與 Eq. 5-19，先以有效尺寸 B′、L′重建排水形狀／深度係數，並以 2025 地下水修正式計算排水 Nγ 項，再套用 Meyerhof-based 地表與基底傾斜係數；鄰接坡體必須先完成獨立整體穩定檢核且 FS > 1.3，否則系統停止地表坡角修正。
- **多層承載力穿刺**：可輸入多層水平土層強度與厚度，依 USACE 2025 Eqs. 5-17／5-18 對影響深度內的較弱下層採 2V:1H 擴散，取控制承載力。
- **地震承載力**：提供 kh／kv 偽靜力基礎作用包絡；另依 USACE 2025 Eqs. 9-3／9-4，計算殘餘超額孔隙水壓比 ru 對砂狀土 Nγ 項的折減。此功能不代表可將可液化或顯著強度損失地盤視為可接受淺基礎地盤。
- **基底滑動**：依 USACE 2025 Eqs. 5-28／5-30 計算界面摩擦、黏著與揚壓力；可手動輸入主動／已折減被動土壓，或依 Eqs. 5-31 至 5-35 自動估算 Rankine developed earth pressure。荷載組合明確區分常時／靜力 FS ≥ 2.0 與含地震荷載 FS ≥ 1.1；選擇地震組合只切換最低 FS，地震慣性力仍須由使用者納入 H、V 與土壓輸入。
- **整體穩定**：Bishop 簡化法手動切片計算，以及均質土強度、水平地下水位、圓弧滑動面的網格搜尋；自動搜尋的切片重量在地下水位以上採濕單位重 γ_moist，以下採飽和單位重 γ_sat，孔隙水壓另依水位計算。
- 原有靜力承載力與上述新增檢核彼此獨立；不得把單一承載力 FS 當成滑動或整體穩定 FS。

## 已知適用限制

- 斜坡／基底傾斜修正目前採 USACE Meyerhof-based 係數組；鄰接坡體 FS > 1.3 是地表坡角係數的適用前提；不等同 AASHTO/FHWA 全套設計方法。
- 多層承載力目前實作強上層覆蓋弱下層的 2V:1H 穿刺簡化法；不等同任意多層、任意破壞面之數值分析。
- 地震功能包括偽靜力作用包絡及 ru 對 Nγ 項折減；尚未整合完整地震時程、土體慣性極限分析、液化後殘餘強度剖面、側向擴展與震陷。
- Bishop 自動搜尋限均質 c′／φ′ 強度、圓弧滑面及水平地下水位；切片重量可區分 γ_moist 與 γ_sat，但不含分層強度、非圓弧滑面、地表附加荷載、地震及三維效應。正式設計應加密搜尋並以 Spencer／Morgenstern–Price 等方法交叉驗證。
- 基底滑動的主動／被動土壓力需由使用者以 developed strength 另行計算後輸入；常時與地震荷載組合分別採不同最低 FS，不能把地震例外值套用到常時分析。

## 本機啟動

已驗證的 CI 執行環境為 Python 3.11。

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit Community Cloud 部署時，GitHub 專案根目錄選擇 `app.py`。依賴套件包含 Streamlit、Pandas、Plotly，以及岩心影像與文件解析所需的 OpenCV headless、PyMuPDF、python-docx；工程計算由專案內的 `geolysis_engine/` 套件執行。

## 審查修正與公式追溯

本專案將計算公式與其採用的文獻版本分開標示；不同文獻若採用不同係數，不會混合成單一「通用公式」。

- **Meyerhof SPT 容許承載力（歷史比較法）**：輸入為 N60 時，換算至指定能量比 n 的 N 值採 Nn = N60 × 60/n；55% 與 70% 能量分別使用 USACE EM 1110-1-1905（1992）§4-4 的係數組。這是舊版經驗法，2025 版手冊已不再作為本專案的主要預設方法。
- **Bishop 簡化法**：孔隙水壓項使用切片底面水平寬度 b，即 (W − u·b)tanφ；滑弧方向採一致正向慣例，避免鏡像坡面因角度符號而被拒絕。
- **Meyerhof 小摩擦角係數**：0°<φ≤10° 依 USACE EM 1110-1-1905（1992）Table 4-3 在 0° 與 10° 之間線性插值；大於 10° 才使用相應完整式。
- **承載力深度係數**：一般經典 Meyerhof drained 分支依 USACE EM 1110-1-1905（1992）Table 4-3 使用 D/B，且 0°<φ≤10°形狀與深度係數線性插值；Hansen、Vesic 依 Tables 4-5／4-6 使用 D/B。模組五斜坡／傾斜基底修正則另依 USACE 2025 Table 5-2，以有效尺寸 B′、L′重建 drained 深度係數 Df/B′，並依 Eq. 5-19 重算 Nγ 項地下水折減，不可將舊版 D/B 與舊地下水剪力區插值直接沿用到 2025 修正。Meyerhof undrained 分支依 2025 Table 5-4 使用 Df/B′。
- **Rankine developed earth pressure**：依 USACE EM 1110-1-1905（2025）Eqs. 5-31 至 5-35。手冊式 5-34／5-35 明確採 ±2c′d 項；本專案依該手冊原式，不替換成其他教材可能使用的 2c′d√K 表達式。
- **Burland–Burbidge**：依 USACE EM 1110-1-1905（2025）§7-13，q 使用 gross 或 gross-equivalent bearing pressure；ZI=1.43B^0.7（英制單位）、Ic=0.35/N̄60^1.4（tsf⁻¹）。這些常數與 gross 壓力處理已與原文核對。
- **多層地盤**：依 USACE 2025 §5-5a(1)–(2)，近基礎剪力區弱層與強上層覆蓋弱下層的 punch-through 分開處理；2V:1H 穿刺式僅在手冊指定深度範圍內使用，超出範圍會提示未檢核層位。
- **SPT 覆土修正 CN**：Liao & Whitman 與 Seed & Idriss 使用相同基本平方根式；Seed & Idriss 液化評估慣例另採 CN≤1.7。Hoek–Brown 變形模數採 Hoek（2002）公式版本，與 Hoek–Diederichs（2006）不同，請勿混稱。

## 自動化驗證

CI 使用 Python 3.11，並固定 Streamlit 1.67.0、Pandas 3.1.1、Plotly 7.1.0，以避免 AppTest 與 widget 行為因依賴版本漂移。

GitHub Actions 使用 Python 3.11，包含指定回歸測試與完整測試目錄自動探索（`python -m pytest -q tests`），並執行編譯、USACE 2025 獨立基準案例、元件 key 檢查、Web 範圍檢查及 Streamlit AppTest。2026-11-12 本版完整測試為 573 passed、1 skipped；最新測試數與提交 SHA 請以 [GitHub Actions](https://github.com/ax02tom2/geolysis/actions) 為準。CI 通過不等同於 Streamlit Cloud 線上驗收或工址設計認證。

## 工程使用限制

本系統提供工程計算與分類輔助，不取代現地調查、試驗資料、地層模型、規範選用與工程師審查。使用者應確認輸入參數、單位、排水條件、載重組合、地下水位及公式適用範圍。所有結果都應保留輸入資料、公式方法與適用限制供專業人員審查。


## 程式結構（重構第一階段）

計算引擎已拆分為領域模組，並保留原有匯入介面：

- `geolysis_engine.classification`：USCS／AASHTO 土壤分類
- `geolysis_engine.spt`：SPT 修正與深度剖面
- `geolysis_engine.bearing`：承載力與斜坡、分層、地震修正
- `geolysis_engine.settlement`：固結、即時、次壓縮與差異沉陷
- `geolysis_engine.rock`：Hoek–Brown 岩體參數
- `geolysis_engine.stability`：基礎滑動與 Bishop 整體穩定
- `geolysis_engine._common`：共用數值驗證

既有程式仍可使用 `from geolysis_engine import bearing_capacity` 等匯入方式，不必一次修改全部呼叫端。計算引擎套件化已完成，對外函式名稱維持相容。


### Streamlit 介面結構

- `app.py`：頁面設定、系統標題、側邊欄與五個模組的協調入口。
- `geolysis_ui/module1.py` 至 `module5.py`：各工程模組的輸入欄位、互動與結果呈現。
- `geolysis_ui/core_log.py`：整孔 DOCX／PDF 岩心柱狀圖、原始頁面疊圖、逐列 RQD 初估及人工覆核。
- `core_log_parser.py`：PDF／DOCX 內嵌岩心影像擷取與列深度解析。
- `core_photo_analysis.py`：岩心本體分段、空隙／不確定區與斷裂候選分析。
- `geolysis_ui/__init__.py`：集中匯出各模組的 render 函式。

目前保留原本的單頁呈現、側邊欄模組選擇與 expander 收合方式；此階段只分離程式責任，不改成 Streamlit 多頁導覽，以免改變既有操作習慣。


### 共用 UI 狀態管理

`geolysis_ui/state.py` 集中處理計算結果快取與輸入簽章：重新計算前清除舊結果、儲存結果及其輸入簽章，並在顯示前確認目前輸入仍與結果相符。這可避免不同模組各自實作時出現舊結果未更新的差異。
