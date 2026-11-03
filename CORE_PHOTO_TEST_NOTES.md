# geolysis 岩芯照片分析｜第三階段測試紀錄

## 本階段參考來源

使用者既有公開專案：
https://github.com/ax02tom2/Core-photo-depth-matching-alignment

已閱讀該專案 README v2.11、`core.py`、`app.py`、`requirements.txt` 與 `point_editor/index.html`。

可借鏡的設計：
- 以完整岩芯箱幾何作為定位目標，不以有岩芯的區域取代箱體範圍。
- 使用藍色箱體遮罩、Hough 橫線群組與幾何線索，而非只用灰階水平梯度。
- 自動結果應可人工覆核；偵測失敗不應使整個 Streamlit 頁面中斷。
- 原專案的角點、旋轉與裁切狀態按照片分開保存。

## 本階段實作

- 保留既有 `detect_tray_rows()` 灰階水平梯度候選。
- 新增 `detect_blue_tray_rows()`：藍色 HSV 遮罩、形態學閉運算、Canny、HoughLinesP、水平角度過濾、依 y/斜率分組。
- 新增雙方法覆核圖：紅線為灰階梯度候選，藍線為藍箱 Hough 候選。
- UI 顯示兩種方法的候選 y 座標與偵測警告。
- 新增 `opencv-python-headless` 依賴。

## 測試結果

`PYTHONPATH=. pytest -q`

預期測試涵蓋：
1. RQD 與採取率計算。
2. 段長文字解析與比例換算。
3. 合成非藍箱照片的水平梯度列界候選。
4. 合成藍色岩芯箱的 Hough 橫線候選。
5. 非藍色照片下，藍箱偵測器可安全回傳無候選，不使程式崩潰。

## 限制

- 測試使用程式產生的合成影像，尚未以真實公開照片完成定量驗證。
- 藍色 Hough 候選是箱格隔板／箱體線條，不是岩芯天然節理或段長界線。
- 尚未實作完整四角點透視校正、岩芯本體分割、段長自動量測、天然／機械斷裂分類。
- 不會將影像候選直接換算為正式 RQD。
