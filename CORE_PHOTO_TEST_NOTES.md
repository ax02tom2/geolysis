# 岩芯照片分析測試紀錄（第二階段）

## 本階段新增

- 新增水平列界候選偵測 `detect_tray_rows()`。
- 新增候選列界標註圖 `draw_row_candidates()`。
- Streamlit 照片檢視區新增「分析水平列界候選」勾選項。
- 新增 `tests/test_core_photo_analysis.py`，測試 RQD/採取率、段長解析、比例換算與合成岩芯箱列界定位。

## 公開範例來源

- Roboflow Universe：Geotechnical borehole cores dataset（頁面標示 CC BY 4.0，75 張影像）
  https://universe.roboflow.com/automated-bore-logging/geotechnical-borehole-cores-jmfad
- Xu et al. (2023), *Intelligent recognition of drill cores and automatic RQD analytics based on deep learning*, Acta Geotechnica.
  https://doi.org/10.1007/s11440-023-02011-2
- Australian Minerals：Australian guidelines for the submission of digital exploration data（2026），岩芯照片拍攝建議。
  https://www.australiaminerals.gov.au/__data/assets/pdf_file/0005/189392/Australian-guidelines-for-the-submission-of-digital-exploration-data-V5.0-Mar-2026.pdf

## 測試限制與結果

- 已檢視公開岩芯箱照片範例的版面型態；但目前執行環境無法連線下載公開圖片原始檔（DNS/network access unavailable），因此**沒有把公開照片像素輸入演算法，也不宣稱已通過真實照片準確度測試**。
- 列界演算法目前以全寬水平灰階梯度找尋隔板候選，對合成的五列岩芯箱測試圖可找出四條內部分隔線，形成五個列區段。
- 自動列界只用來定位箱列；不代表岩芯本體遮罩、岩芯段界、天然節理、機械斷裂或實際長度。
- 測試命令：`python -m pytest -q`
- 結果：`3 passed`。

## 下一步工程限制

要進入可靠的岩芯段長度與 RQD 自動化，仍需有可合法使用、含尺度與標註的真實岩芯箱影像資料，並建立岩芯本體、段界、箱列、尺度標記及天然/機械斷裂標籤。未完成這些驗證前，影像結果只能作為人工覆核候選。
