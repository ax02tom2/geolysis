"""岩芯照片分析第一階段：影像檢查、比例校正與 RQD 基礎計算。

注意：本模組不宣稱能僅憑未校正照片自動辨識天然斷裂。
RQD 必須使用可追溯的實際岩芯段長度，且需排除機械斷裂。
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

from PIL import Image, ImageOps


@dataclass
class ImageInfo:
    width_px: int
    height_px: int
    format: str
    mode: str
    file_size_bytes: int


def inspect_image(data: bytes) -> tuple[Image.Image, ImageInfo]:
    """安全地解碼圖片並回傳 EXIF 校正後影像與基本資訊。"""
    with Image.open(BytesIO(data)) as raw:
        raw.verify()
    with Image.open(BytesIO(data)) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        info = ImageInfo(
            width_px=image.width,
            height_px=image.height,
            format=(raw.format or "unknown").upper(),
            mode=raw.mode,
            file_size_bytes=len(data),
        )
    return image, info


def pixel_scale_mm_per_px(reference_length_mm: float, reference_length_px: float) -> float:
    if reference_length_mm <= 0 or reference_length_px <= 0:
        raise ValueError("比例尺的實際長度與像素長度都必須大於 0。")
    return reference_length_mm / reference_length_px


def parse_piece_lengths(raw: str) -> list[float]:
    """解析以逗號、空白、分號或換行分隔的岩芯段長度（mm）。"""
    tokens = [x for x in __import__("re").split(r"[,，;；\s]+", raw.strip()) if x]
    values = []
    for token in tokens:
        try:
            value = float(token)
        except ValueError as exc:
            raise ValueError(f"無法辨識岩芯段長度：{token}") from exc
        if value <= 0:
            raise ValueError("岩芯段長度必須全部大於 0。")
        values.append(value)
    return values


def calculate_core_indices(
    drilled_interval_m: float,
    recovered_lengths_mm: Iterable[float],
    rqd_threshold_mm: float = 100.0,
) -> dict:
    """依輸入的實際岩芯段長度計算回收率與 RQD。

    回收率 = 回收岩芯總長 / 鑽進長度
    RQD = 長度 >= 100 mm 的完整岩芯段總長 / 鑽進長度
    """
    if drilled_interval_m <= 0:
        raise ValueError("鑽進深度區間必須大於 0。")
    lengths = [float(x) for x in recovered_lengths_mm]
    if any(x <= 0 for x in lengths):
        raise ValueError("岩芯段長度必須全部大於 0。")

    drilled_mm = drilled_interval_m * 1000.0
    recovered_mm = sum(lengths)
    rqd_mm = sum(x for x in lengths if x >= rqd_threshold_mm)

    return {
        "drilled_length_mm": drilled_mm,
        "recovered_length_mm": recovered_mm,
        "recovery_percent": recovered_mm / drilled_mm * 100.0,
        "rqd_length_mm": rqd_mm,
        "rqd_percent": rqd_mm / drilled_mm * 100.0,
        "piece_count": len(lengths),
        "qualifying_piece_count": sum(x >= rqd_threshold_mm for x in lengths),
        "over_recovery": recovered_mm > drilled_mm,
        "lengths_mm": lengths,
    }


def detect_tray_rows(image: Image.Image, max_rows: int = 12) -> dict:
    """以水平邊界梯度找出岩芯箱列界候選；只做定位輔助，不辨識岩芯段或斷裂。

    回傳 row_bounds（像素座標）及 row_bands。演算法使用全寬垂直灰階差，
    對清楚的橫向隔板較敏感；文字、陰影、反光也可能形成假候選。
    """
    import numpy as np

    if max_rows < 2 or max_rows > 30:
        raise ValueError("max_rows 必須介於 2 至 30。")
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    h, w = gray.shape
    if h < 80 or w < 80:
        return {"row_bounds": [0, h], "row_bands": [(0, h)], "candidates": [], "method": "image_too_small"}

    # 降低文字與局部岩芯紋理的影響：以全寬平均垂直差作為橫向隔板分數。
    diff = np.abs(np.diff(gray, axis=0))
    score = diff.mean(axis=1)
    smooth_n = max(3, int(round(h * 0.004)) | 1)
    kernel = np.ones(smooth_n, dtype=np.float32) / smooth_n
    smooth = np.convolve(score, kernel, mode="same")

    med = float(np.median(smooth))
    mad = float(np.median(np.abs(smooth - med)))
    threshold = max(float(np.percentile(smooth, 82)), med + 2.0 * mad)
    min_distance = max(12, int(h / (max_rows + 1)))
    peaks = []
    edge_margin = max(8, int(h * 0.07))  # 排除照片最外緣的箱體外框
    for y in range(edge_margin, h - edge_margin):
        if smooth[y] >= threshold and smooth[y] >= smooth[y - 1] and smooth[y] >= smooth[y + 1]:
            peaks.append((float(smooth[y]), int(y)))
    # 強峰優先，並限制相鄰候選過近；最後依 y 排序。
    selected = []
    for strength, y in sorted(peaks, reverse=True):
        if all(abs(y - old_y) >= min_distance for _, old_y in selected):
            selected.append((strength, y))
        if len(selected) >= max_rows - 1:
            break
    selected.sort(key=lambda item: item[1])
    bounds = [0] + [y for _, y in selected] + [h]
    bands = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i + 1] - bounds[i] >= 12]
    candidates = [
        {"y_px": y, "strength": round(strength, 3)}
        for strength, y in selected
    ]
    return {
        "row_bounds": bounds,
        "row_bands": bands,
        "candidates": candidates,
        "threshold": round(threshold, 3),
        "method": "horizontal_gradient_candidate_v1",
        "warning": "列界候選可能包含文字、陰影或反光；需人工確認，不能直接視為岩芯段界。",
    }


def draw_row_candidates(image: Image.Image, detection: dict) -> Image.Image:
    """繪製水平列界候選，供使用者目視覆核。"""
    from PIL import ImageDraw

    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for i, y in enumerate(detection.get("row_bounds", [])[1:-1], start=1):
        draw.line((0, y, out.width, y), fill=(255, 40, 40), width=max(2, out.width // 1200))
        draw.text((8, min(y + 3, out.height - 18)), f"candidate {i}: y={y}px", fill=(255, 40, 40), stroke_width=1, stroke_fill=(255, 255, 255))
    return out


def detect_blue_tray_rows(image: Image.Image, max_rows: int = 12) -> dict:
    """參考使用者 Core-photo-depth-matching-alignment 的箱體幾何思路。

    以藍色箱體遮罩 + HoughLinesP 找長水平隔板，再依 y 位置與斜率分組。
    這是「箱體列界候選」而非岩芯斷裂偵測；對非藍色箱、遮蔽、反光或嚴重透視
    仍可能失效。保留原圖座標，不做透視校正或自動 RQD。
    """
    import cv2
    import numpy as np

    if max_rows < 2 or max_rows > 30:
        raise ValueError("max_rows 必須介於 2 至 30。")
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    if min(h, w) < 80:
        return {"candidates": [], "row_bounds": [0, h], "method": "image_too_small", "warning": "影像尺寸太小。"}

    # 降採樣以控制處理時間，並使用比原校正工具更寬的藍色範圍。
    scale = min(1.0, 1400.0 / max(h, w))
    sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
    small = cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_AREA) if scale < 1 else rgb
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, (78, 45, 35), (132, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    edges = cv2.Canny(mask, 40, 120)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=max(18, int(0.045 * sw)),
        minLineLength=max(35, int(0.16 * sw)),
        maxLineGap=max(8, int(0.035 * sw)),
    )
    if lines is None:
        return {"candidates": [], "row_bounds": [0, h], "method": "blue_hough_v1", "warning": "未找到足夠長的藍色水平箱體線段；可能不是藍色箱體或箱體被遮蔽。"}

    raw = []
    for line in np.asarray(lines).reshape(-1, 4):
        x1, y1, x2, y2 = map(float, line)
        dx, dy = x2 - x1, y2 - y1
        length = float(np.hypot(dx, dy))
        angle = abs(float(np.degrees(np.arctan2(dy, dx))))
        angle = min(angle, abs(180.0 - angle))
        if length < 0.16 * sw or angle > 22.0:
            continue
        slope = dy / (dx + 1e-8)
        y_center = (y1 + y2) / 2 + slope * (sw / 2 - (x1 + x2) / 2)
        raw.append((y_center, slope, length))

    if not raw:
        return {"candidates": [], "row_bounds": [0, h], "method": "blue_hough_v1", "warning": "有藍色像素，但沒有足夠長且近水平的箱體線段。"}

    raw.sort(key=lambda x: x[0])
    groups = []
    for y, slope, length in raw:
        match = None
        for group in groups:
            angle_delta = abs(np.degrees(np.arctan(slope)) - np.degrees(np.arctan(group["slope"])))
            if abs(y - group["y"]) <= max(6.0, 0.018 * sh) and angle_delta <= 8:
                match = group
                break
        if match is None:
            groups.append({"y": y, "slope": slope, "length": length, "n": 1})
        else:
            match["y"] = (match["y"] * match["n"] + y) / (match["n"] + 1)
            match["slope"] = (match["slope"] * match["n"] + slope) / (match["n"] + 1)
            match["length"] += length
            match["n"] += 1

    groups.sort(key=lambda g: g["y"])
    # 合併同一隔板因兩側邊緣而產生的重複群組。
    merged = []
    for g in groups:
        if merged and abs(g["y"] - merged[-1]["y"]) <= max(8.0, 0.022 * sh):
            old = merged[-1]
            old["y"] = (old["y"] * old["n"] + g["y"] * g["n"]) / (old["n"] + g["n"])
            old["length"] += g["length"]
            old["n"] += g["n"]
        else:
            merged.append(dict(g))

    # 排除最外緣框線，保留內部隔板候選；用線長作為排序依據但不宣稱機率信心。
    margin = max(5, int(0.045 * sh))
    inner = [g for g in merged if margin < g["y"] < sh - margin]
    inner.sort(key=lambda g: g["length"], reverse=True)
    selected = inner[: max_rows - 1]
    selected.sort(key=lambda g: g["y"])
    ys = [int(round(g["y"] / scale)) for g in selected]
    candidates = [
        {"y_px": y, "line_length_px": round(g["length"] / scale, 1), "segments": int(g["n"])}
        for y, g in zip(ys, selected)
    ]
    bounds = [0] + ys + [h]
    return {
        "row_bounds": bounds,
        "candidates": candidates,
        "method": "blue_tray_hough_v1",
        "warning": "藍色箱體橫線候選只用於定位箱格列界，不代表岩芯段界；請人工確認。非藍色箱體或透視嚴重時可能漏檢。",
        "detected_line_groups": len(merged),
    }


def draw_combined_row_candidates(image: Image.Image, detections: list[dict]) -> Image.Image:
    """同圖顯示不同演算法候選：紅色=灰階梯度、藍色=藍箱 Hough。"""
    from PIL import ImageDraw

    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    colors = {"horizontal_gradient_candidate_v1": (240, 45, 45), "blue_tray_hough_v1": (30, 110, 255)}
    y_seen = set()
    for detection in detections:
        method = detection.get("method", "")
        color = colors.get(method, (255, 180, 0))
        for item in detection.get("candidates", []):
            y = int(item["y_px"])
            if (method, y) in y_seen:
                continue
            y_seen.add((method, y))
            draw.line((0, y, out.width, y), fill=color, width=max(2, out.width // 1400))
            draw.text((8, min(y + 3, out.height - 18)), f"{method.split('_')[0]} y={y}", fill=color, stroke_width=1, stroke_fill=(255, 255, 255))
    return out


def _order_quad_points(points):
    """Order four points as top-left, top-right, bottom-right, bottom-left."""
    import numpy as np
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def detect_blue_tray_quadrilateral(image: Image.Image) -> dict:
    """偵測藍色岩芯箱外框四邊形；回傳原圖座標與幾何品質，不自動假定一定成功。"""
    import cv2
    import numpy as np

    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, 1800.0 / max(h, w))
    sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
    small = cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_AREA) if scale < 1 else rgb
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, (78, 40, 30), (135, 255, 255))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, sw // 180), max(3, sh // 180)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    image_area = float(sw * sh)
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < image_area * 0.08:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.025 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = _order_quad_points(approx.reshape(4, 2))
        else:
            rect = cv2.minAreaRect(contour)
            quad = _order_quad_points(cv2.boxPoints(rect))
        sides = [float(np.linalg.norm(quad[(i + 1) % 4] - quad[i])) for i in range(4)]
        top, right, bottom, left = sides
        width_est = (top + bottom) / 2
        height_est = (left + right) / 2
        if min(width_est, height_est) < 1:
            continue
        aspect = max(width_est, height_est) / min(width_est, height_est)
        if aspect > 12:
            continue
        rectangularity = min(area / max(cv2.contourArea(approx) if len(approx) == 4 else area, 1), 1.0)
        score = area * min(aspect, 5) * rectangularity
        candidates.append((score, quad, area, aspect, len(approx)))
    if not candidates:
        return {"success": False, "method": "blue_mask_quad_v1", "warning": "未找到面積足夠且形狀合理的藍色箱體外框；請使用原圖或人工校正。"}
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, quad, area, aspect, vertices = candidates[0]
    quad_original = (quad / scale).tolist()
    # Basic checks: corners must span enough of image and have no degenerate sides.
    sides = [float(np.linalg.norm(quad[(i + 1) % 4] - quad[i])) for i in range(4)]
    min_side = min(sides)
    valid = area / image_area >= 0.08 and min_side >= min(sw, sh) * 0.08
    return {
        "success": bool(valid), "method": "blue_mask_quad_v1",
        "corners": [[round(float(x), 1), round(float(y), 1)] for x, y in quad_original],
        "area_ratio": round(area / image_area, 4), "aspect_ratio": round(aspect, 3),
        "approx_vertices": int(vertices), "candidate_count": len(candidates),
        "warning": "四角為藍色遮罩幾何候選，可能抓到局部箱體或背景物件；透視校正前請確認四角都落在同一岩芯箱外框。" if valid else "候選外框幾何品質不足，未建議校正。",
    }


def rectify_tray_perspective(image: Image.Image, detection: dict, max_dimension: int = 2400) -> tuple[Image.Image, dict]:
    """依已確認四角進行透視校正；不修改輸入原圖。"""
    import cv2
    import numpy as np
    if not detection.get("success") or len(detection.get("corners", [])) != 4:
        raise ValueError("沒有可用的四角候選，無法進行透視校正。")
    pts = np.asarray(detection["corners"], dtype=np.float32)
    tl, tr, br, bl = pts
    width = int(round(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl))))
    height = int(round(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl))))
    if width < 80 or height < 80:
        raise ValueError("外框尺寸過小，校正結果不可靠。")
    factor = min(1.0, max_dimension / max(width, height))
    out_w, out_h = max(80, int(width * factor)), max(80, int(height * factor))
    dst = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(pts, dst)
    arr = np.asarray(image.convert("RGB"))
    warped = cv2.warpPerspective(arr, matrix, (out_w, out_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(245, 245, 245))
    return Image.fromarray(warped), {"output_width_px": out_w, "output_height_px": out_h, "scale_factor": round(factor, 4), "warning": "透視校正僅改變影像幾何外觀；若原圖無尺度基準，不能因此取得真實 mm/px。"}


def draw_tray_quadrilateral(image: Image.Image, detection: dict) -> Image.Image:
    from PIL import ImageDraw
    out = image.convert("RGB").copy()
    if detection.get("success") and len(detection.get("corners", [])) == 4:
        pts = [(int(round(x)), int(round(y))) for x, y in detection["corners"]]
        draw = ImageDraw.Draw(out)
        draw.line(pts + [pts[0]], fill=(255, 40, 30), width=max(3, out.width // 600))
        for i, (x, y) in enumerate(pts, 1):
            r = max(7, out.width // 100)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(255, 230, 0), outline=(0, 0, 0), width=2)
            draw.text((x+r, y+r), str(i), fill=(0, 0, 0), stroke_width=2, stroke_fill=(255, 255, 255))
    return out
