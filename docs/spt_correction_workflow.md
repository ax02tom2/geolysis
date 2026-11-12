# SPT 修正與逐深度剖面操作說明

版本日期：2026-11-12

## 1. 單點 SPT 修正

輸入包括實測 N 值、能量比 ER、鑽孔直徑修正係數 CB、取樣器修正係數 CS、鑽桿長度，以及土層行為與 CN 方法。

依 USACE EM 1110-1-1905（2025）：

- 能量修正：CE = ER / 60。
- 鑽桿長度修正 CR 依 Table 4-6 分段；長度 10–30 m 使用 1.00。
- 黏土等凝聚性土層不套用 CN；CB 固定為 1.00。
- 非凝聚性土層若啟用 CN，必須輸入該深度有效覆土應力。
- USACE 表列的 CB 範圍為 1.00–1.15，CS 範圍為 1.00–1.30；超出範圍會拒絕計算。
- ER 超出常見設備範圍（約 50–130%）會提示核對量測；不會自動改寫使用者輸入。
- 鑽桿長度超過 30 m 時仍以 CR=1.00 計算，但會明確警告該長度超出 Table 4-6 列示範圍。

## 2. CN 覆土修正

- Liao & Whitman：CN = √(Pa / σ′v)，並依 USACE 2025 上限控制，預設最高 2.0。
- Seed & Idriss：使用相同型式的覆土修正，但本系統將液化用途上限限制為 1.7。
- Skempton：採用對應公式作為可選方法。
- 不修正：CN=1。
- 凝聚性土層：CN=1，不要求輸入有效覆土應力。
- 非凝聚性土層若使用上述 CN 方法，Effective_Stress_KPa 必須大於 0。

有效覆土應力應為試驗深度處的有效垂直應力，不可直接以總覆土應力取代。

## 3. 膨脹修正（Dilatancy）

膨脹修正不是所有砂土都適用。僅在地下水位以下、飽和細砂／粉土且已完成 CN 修正、(N1)60 > 15 時才考慮。

- 單點分析的核取方塊代表使用者確認上述地質與地下水條件。
- 逐深度剖面若啟用膨脹修正，所有非凝聚性且非拒錘列都必須明確填寫 Apply_Dilatancy true／false。
- 不可把單點試驗的條件直接套用到整孔所有非凝聚性土層。
- 拒錘／部分貫入列不套用一般 N 值修正，也不計算一般 N60。

## 4. 逐深度 CSV 欄位

必要欄位：

- Depth_m
- N

依條件需要：

- Effective_Stress_KPa：僅非凝聚性、非拒錘且啟用 CN 的列必填。
- Soil_Behavior：cohesionless 或 cohesive；未提供時沿用上方設定。
- Refusal：true／false，也接受常見拒錘／部分貫入文字。
- Apply_Dilatancy：逐列膨脹修正旗標。
- Energy_Ratio_pct、Borehole_Factor、Sampler_Factor、Rod_Length_m：選填，可逐列覆寫上方設備設定。
- Burland_Material：可供模組四沉陷分析沿用的材料分類欄位。

黏土、拒錘列或選擇不修正 CN 的列，可以留空 Effective_Stress_KPa。若同一剖面包含砂土與黏土，建議明確提供 Soil_Behavior，避免把 CN 套用到黏土。

## 5. 限制與工程覆核

- CN 使用的有效覆土應力仍需由工址土層單位重、地下水位及上覆荷重計算或由可靠資料取得；本模組不會從 N 值反推有效應力。
- Apply_Dilatancy 是使用者對細砂／粉土、地下水位及飽和條件的逐列確認；系統不能僅憑 cohesionless 自動判定細料級配或地下水位置。
- 拒錘與部分貫入應保留原始現場紀錄，不可把拒錘值當成一般 N 值外插。
- SPT 修正結果應與能量校正紀錄、鑽孔直徑、取樣器型式、鑽桿長度及現場紀錄一併覆核。

## 6. 參考依據

- USACE EM 1110-1-1905, Geotechnical Design of Shallow Foundations on Soils (2025), SPT correction discussion and Tables 4-5 / 4-6.
- ASTM D1586/D1586M, Standard Test Method for Standard Penetration Test (SPT) and Split-Barrel Sampling of Soils.
- ASTM D4633, Standard Test Method for Energy Measurement for Dynamic Penetrometers.
