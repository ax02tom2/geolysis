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
    rqd_piece_lengths_mm: Iterable[float] | None = None,
) -> dict:
    """Calculate core recovery and RQD from separately confirmed measurements.

    Core recovery uses all physically recovered core length, including pieces
    broken mechanically. RQD uses only lengths bounded by natural
    discontinuities after mechanical breaks have been fitted together.
    """
    if drilled_interval_m <= 0:
        raise ValueError("鑽進深度區間必須大於 0。")
    recovered_lengths = [float(x) for x in recovered_lengths_mm]
    if any(x <= 0 for x in recovered_lengths):
        raise ValueError("回收岩心長度必須全部大於 0。")
    rqd_lengths = ([float(x) for x in rqd_piece_lengths_mm]
                   if rqd_piece_lengths_mm is not None else list(recovered_lengths))
    if any(x <= 0 for x in rqd_lengths):
        raise ValueError("RQD 岩心段長度必須全部大於 0。")

    drilled_mm = drilled_interval_m * 1000.0
    recovered_mm = sum(recovered_lengths)
    rqd_mm = sum(x for x in rqd_lengths if x >= rqd_threshold_mm)

    return {
        "drilled_length_mm": drilled_mm,
        "recovered_length_mm": recovered_mm,
        "recovery_percent": recovered_mm / drilled_mm * 100.0,
        "rqd_length_mm": rqd_mm,
        "rqd_percent": rqd_mm / drilled_mm * 100.0,
        "piece_count": len(rqd_lengths),
        "qualifying_piece_count": sum(x >= rqd_threshold_mm for x in rqd_lengths),
        "over_recovery": recovered_mm > drilled_mm,
        "rqd_exceeds_recovered": rqd_mm > recovered_mm,
        "rqd_exceeds_drilled": rqd_mm > drilled_mm,
        "lengths_mm": recovered_lengths,
        "rqd_lengths_mm": rqd_lengths,
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



def rotate_image(image: Image.Image, clockwise_degrees: int = 0) -> Image.Image:
    """以 90 度為單位旋轉影像；回傳新影像，不修改原圖。"""
    angle = int(clockwise_degrees) % 360
    if angle not in (0, 90, 180, 270):
        raise ValueError("旋轉角度只接受 0、90、180 或 270 度。")
    image = image.convert("RGB")
    if angle == 0:
        return image.copy()
    # PIL transpose uses counter-clockwise names; ROTATE_270 is clockwise 90°.
    transpose = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}[angle]
    return image.transpose(transpose)


def validate_tray_quadrilateral(corners, image_width: int, image_height: int) -> list[list[float]]:
    """驗證四角點順序、範圍、面積與凸性，回傳 TL/TR/BR/BL 座標。"""
    import numpy as np
    if image_width < 1 or image_height < 1:
        raise ValueError("影像尺寸無效。")
    pts = np.asarray(corners, dtype=np.float32)
    if pts.shape != (4, 2) or not np.isfinite(pts).all():
        raise ValueError("必須提供四個有效的 (x, y) 角點。")
    if (pts[:, 0] < 0).any() or (pts[:, 0] > image_width - 1).any() or (pts[:, 1] < 0).any() or (pts[:, 1] > image_height - 1).any():
        raise ValueError("角點超出照片範圍，請重新調整。")
    ordered = _order_quad_points(pts)
    contour = ordered.reshape((-1, 1, 2)).astype(np.float32)
    area = abs(float(cv2_contour_area(contour)))
    if area < image_width * image_height * 0.01:
        raise ValueError("四角形成的有效區域過小（小於照片面積 1%）。")
    # Reject crossed/concave geometry and near-zero edges.
    edges = np.roll(ordered, -1, axis=0) - ordered
    if min(float(np.linalg.norm(e)) for e in edges) < 20:
        raise ValueError("四角距離過近，請重新調整。")
    cross = []
    for i in range(4):
        a = ordered[(i + 1) % 4] - ordered[i]
        b = ordered[(i + 2) % 4] - ordered[(i + 1) % 4]
        cross.append(float(a[0] * b[1] - a[1] * b[0]))
    if not (all(v > 0 for v in cross) or all(v < 0 for v in cross)):
        raise ValueError("四角點形成交叉或凹陷多邊形，無法校正。")
    return [[round(float(x), 2), round(float(y), 2)] for x, y in ordered]

def cv2_contour_area(contour):
    import cv2
    return cv2.contourArea(contour)


def crop_tray_insets(image: Image.Image, left_pct: float = 2.0, right_pct: float = 2.0,
                     top_pct: float = 2.0, bottom_pct: float = 2.0) -> tuple[Image.Image, dict]:
    """依百分比裁除透視校正後的外框邊緣；每張照片可獨立設定。"""
    values = [float(left_pct), float(right_pct), float(top_pct), float(bottom_pct)]
    if any(v < 0 or v > 20 for v in values):
        raise ValueError("裁切留邊百分比必須介於 0 至 20%。")
    w, h = image.size
    x0, x1 = int(round(w * values[0] / 100)), int(round(w * (1-values[1]/100)))
    y0, y1 = int(round(h * values[2] / 100)), int(round(h * (1-values[3]/100)))
    if x1 - x0 < 80 or y1 - y0 < 80:
        raise ValueError("裁切後範圍過小；請減少裁切比例。")
    cropped = image.crop((x0, y0, x1, y1))
    return cropped, {"box_px": [x0, y0, x1, y1], "width_px": cropped.width, "height_px": cropped.height,
                     "insets_percent": {"left": values[0], "right": values[1], "top": values[2], "bottom": values[3]},
                     "warning": "裁切只排除箱框邊緣；請確認四列完整且沒有切掉岩芯端部。"}

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
    pts = np.asarray(validate_tray_quadrilateral(detection["corners"], image.width, image.height), dtype=np.float32)
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


def calculate_fixed_tray_row_layout(
    rectified_image: Image.Image,
    row_count: int = 4,
    row_length_mm: float = 1000.0,
    row_boundaries_pct: Iterable[float] | None = None,
) -> dict:
    """依固定岩芯箱規格建立逐列量測區，可覆核調整列界。

    假設透視校正後：每列沿影像寬度方向排列，列沿影像高度方向堆疊。
    預設 4 列、每列 1,000 mm；row_boundaries_pct 是內部分界百分比，
    例如 [24, 51, 76]。未提供時維持等分。這只建立幾何比例尺，
    不會辨識岩芯邊界或天然／機械斷裂。
    """
    if row_count < 1 or row_count > 12:
        raise ValueError("列數必須介於 1 至 12。")
    if row_length_mm <= 0:
        raise ValueError("每列實際長度必須大於 0 mm。")
    width, height = rectified_image.size
    if width < 80 or height < row_count * 20:
        raise ValueError("校正後影像尺寸不足，無法可靠分列。")

    if row_boundaries_pct is None:
        boundaries = [100.0 * i / row_count for i in range(1, row_count)]
    else:
        boundaries = [float(v) for v in row_boundaries_pct]
        if len(boundaries) != row_count - 1:
            raise ValueError(f"{row_count} 列必須提供 {row_count - 1} 個內部分界百分比。")
        if any(not (0.0 < v < 100.0) for v in boundaries):
            raise ValueError("列界百分比必須介於 0 至 100%。")
        if any(b <= a for a, b in zip(boundaries, boundaries[1:])):
            raise ValueError("列界必須由上至下遞增，不能重疊或倒置。")

    y_bounds = [0] + [int(round(height * v / 100.0)) for v in boundaries] + [height]
    if any((b - a) < 20 for a, b in zip(y_bounds, y_bounds[1:])):
        raise ValueError("部分列高不足 20 px，請調整列界或提高影像解析度。")

    mm_per_px = float(row_length_mm) / float(width)
    rows = []
    for index, (y0, y1) in enumerate(zip(y_bounds, y_bounds[1:])):
        rows.append({
            "row": index + 1,
            "box_px": [0, y0, width, y1],
            "width_px": width,
            "height_px": y1 - y0,
            "known_length_mm": float(row_length_mm),
            "mm_per_px": mm_per_px,
        })
    return {
        "row_count": row_count,
        "row_length_mm": float(row_length_mm),
        "rectified_width_px": width,
        "rectified_height_px": height,
        "row_boundaries_pct": boundaries,
        "mm_per_px": mm_per_px,
        "rows": rows,
        "assumption": "透視校正後每列沿影像寬度方向；列界可採等分初始值或人工調整，仍須確認四列完整。",
        "warning": "1 m/列可提供沿列方向的名義比例尺；若外框角點不準、箱體彎曲、鏡頭畸變或列長並非實際 1 m，比例尺會有誤差。列高不代表實際岩芯長度；本功能不辨識岩芯段界。",
    }


def draw_fixed_tray_row_layout(image: Image.Image, layout: dict) -> Image.Image:
    """在校正影像標示四列及每列 1 m 的量測基準。"""
    from PIL import ImageDraw

    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    line_width = max(2, out.width // 700)
    for row in layout.get("rows", []):
        x0, y0, x1, y1 = row["box_px"]
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 190, 0), width=line_width)
        label = f"ROW {row['row']} | 1000 mm | {row['mm_per_px']:.3f} mm/px"
        draw.rectangle((x0 + 4, y0 + 4, min(x1 - 1, x0 + 330), min(y1 - 1, y0 + 30)), fill=(20, 20, 20))
        draw.text((x0 + 9, y0 + 8), label, fill=(255, 255, 255))
    return out


def crop_fixed_tray_rows(image: Image.Image, layout: dict) -> list[Image.Image]:
    """依 layout 逐列裁切；不縮放、不改寫原校正影像。"""
    return [image.crop(tuple(row["box_px"])) for row in layout.get("rows", [])]



def detect_core_discontinuity_candidates(
    row_image: Image.Image,
    mm_per_px: float,
    min_separation_mm: float = 25.0,
    sensitivity: float = 2.5,
) -> dict:
    """Find candidate transverse discontinuities along one core-tray row.

    The detector combines column-wise grayscale gradient and dark-pixel occupancy
    within the central 20-80% of the row. It reports image candidates only; it
    cannot distinguish natural joints from drilling/handling breaks.
    """
    import numpy as np

    if mm_per_px <= 0:
        raise ValueError("mm_per_px 必須大於 0。")
    if min_separation_mm <= 0:
        raise ValueError("最小候選間距必須大於 0 mm。")
    if not 1.0 <= sensitivity <= 8.0:
        raise ValueError("sensitivity 必須介於 1 至 8。")
    rgb = np.asarray(row_image.convert("RGB"), dtype=np.uint8)
    h, w = rgb.shape[:2]
    if w < 80 or h < 20:
        return {"success": False, "candidates": [], "warning": "列影像尺寸不足，無法分析。"}

    gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.float32)
    y0, y1 = int(h * 0.20), max(int(h * 0.80), int(h * 0.20) + 1)
    band = gray[y0:y1, :]
    # Robustly aggregate vertical edge energy and the proportion of very dark pixels.
    grad = np.abs(np.diff(band, axis=1)).mean(axis=0)
    dark = (band[:, :-1] < np.percentile(band, 18)).mean(axis=0)
    # Smooth over a small fraction of image width to reduce isolated texture noise.
    win = max(3, int(round(w * 0.004)) | 1)
    kernel = np.ones(win, dtype=np.float32) / win
    grad_s = np.convolve(grad, kernel, mode="same")
    dark_s = np.convolve(dark, kernel, mode="same")
    grad_med = float(np.median(grad_s))
    grad_mad = float(np.median(np.abs(grad_s - grad_med))) + 1e-6
    dark_med = float(np.median(dark_s))
    dark_mad = float(np.median(np.abs(dark_s - dark_med))) + 1e-6
    score = (grad_s - grad_med) / max(1.4826 * grad_mad, 1.0) + 0.65 * (dark_s - dark_med) / max(1.4826 * dark_mad, 0.02)
    threshold = max(float(np.percentile(score, 92)), sensitivity)
    margin = max(4, int(w * 0.015))
    min_px = max(3, int(round(min_separation_mm / mm_per_px)))
    peaks = []
    for x in range(margin, w - margin):
        if score[x] >= threshold and score[x] >= score[x - 1] and score[x] >= score[x + 1]:
            peaks.append((float(score[x]), x))
    selected = []
    for strength, x in sorted(peaks, reverse=True):
        if all(abs(x - old_x) >= min_px for _, old_x in selected):
            selected.append((strength, x))
    selected.sort(key=lambda item: item[1])
    candidates = [{
        "x_px": int(x),
        "distance_mm": round(float(x * mm_per_px), 1),
        "signal_score": round(float(strength), 2),
        "candidate_type": "possible_transverse_discontinuity",
        "interpretation": "需人工確認；不可直接判定為天然節理",
    } for strength, x in selected]
    return {
        "success": True,
        "image_width_px": w,
        "row_length_mm": round(w * mm_per_px, 1),
        "mm_per_px": float(mm_per_px),
        "candidates": candidates,
        "threshold": round(threshold, 3),
        "method": "column_gradient_darkness_candidate_v1",
        "warning": "這些是影像不連續候選，可能來自天然節理、機械斷裂、岩性紋理、陰影、托盤背景或反光；必須人工結合岩心外觀與鑽探紀錄判別；不可直接判定為天然節理，也不得直接用於正式 RQD。",
    }


def draw_core_discontinuity_candidates(row_image: Image.Image, detection: dict) -> Image.Image:
    """Overlay possible transverse discontinuities on one row image."""
    from PIL import ImageDraw
    out = row_image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for i, item in enumerate(detection.get("candidates", []), start=1):
        x = int(item["x_px"])
        draw.line((x, 0, x, out.height - 1), fill=(255, 40, 40), width=max(2, out.width // 500))
        draw.text((min(x + 3, out.width - 90), 4), f"C{i} {item['distance_mm']:.0f}mm", fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    return out


def segment_lengths_from_confirmed_cuts(
    row_width_px: int,
    mm_per_px: float,
    confirmed_cut_positions_px: Iterable[float],
) -> list[float]:
    """Convert user-confirmed x cut positions into image-span lengths (mm).

    Returned lengths span the entire row image. The user must exclude tray margins
    and non-core gaps before using these values as measured core-piece lengths.
    """
    if row_width_px <= 0 or mm_per_px <= 0:
        raise ValueError("影像寬度與比例尺必須大於 0。")
    cuts = sorted(float(x) for x in confirmed_cut_positions_px)
    if any(x <= 0 or x >= row_width_px for x in cuts):
        raise ValueError("斷點位置必須位於影像內部（大於 0 且小於影像寬度）。")
    if any(b - a < 1 for a, b in zip(cuts, cuts[1:])):
        raise ValueError("斷點位置不可重複。")
    bounds = [0.0] + cuts + [float(row_width_px)]
    return [round((b - a) * mm_per_px, 1) for a, b in zip(bounds, bounds[1:])]



def calibrate_row_measurement_span(
    row_image: Image.Image,
    x_start_px: int,
    x_end_px: int,
    known_length_mm: float = 1000.0,
) -> tuple[Image.Image, dict]:
    """Crop the user-confirmed 1 m measurement span from one tray row."""
    width, height = row_image.size
    x0, x1 = int(x_start_px), int(x_end_px)
    if known_length_mm <= 0:
        raise ValueError("已知列長必須大於 0 mm。")
    if x0 < 0 or x1 > width or x1 - x0 < 40:
        raise ValueError("量測起訖像素必須在列影像範圍內，且至少相距 40 px。")
    cropped = row_image.crop((x0, 0, x1, height))
    mm_per_px = float(known_length_mm) / float(x1 - x0)
    return cropped, {
        "x_start_px": x0,
        "x_end_px": x1,
        "span_px": x1 - x0,
        "known_length_mm": float(known_length_mm),
        "mm_per_px": mm_per_px,
        "warning": "比例尺僅在使用者將起點與終點對準該列實際 1 m 端點時成立；請排除托盤邊框與端部空隙。",
    }


def segment_core_occupancy(
    row_image: Image.Image,
    mm_per_px: float,
    blue_hue_range: tuple[int, int] = (78, 132),
    min_core_occupancy: float = 0.18,
    min_gap_mm: float = 12.0,
) -> dict:
    """Estimate longitudinal core-present intervals in a blue tray row.

    This is a conservative colour/occupancy heuristic, not semantic rock
    segmentation. It is enabled only when a measurable blue-tray background is
    present. Intervals are image occupancy spans, not recovered core lengths.
    """
    import cv2
    import numpy as np

    if mm_per_px <= 0 or min_gap_mm <= 0:
        raise ValueError("比例尺與最小缺口長度必須大於 0。")
    if not 0.05 <= min_core_occupancy <= 0.8:
        raise ValueError("min_core_occupancy 必須介於 0.05 至 0.8。")
    rgb = np.asarray(row_image.convert("RGB"), dtype=np.uint8)
    h, w = rgb.shape[:2]
    if w < 80 or h < 24:
        return {"success": False, "intervals": [], "gaps": [], "warning": "列影像尺寸不足。"}
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lo, hi = blue_hue_range
    blue = cv2.inRange(hsv, (int(lo), 35, 25), (int(hi), 255, 255)) > 0
    y0, y1 = int(h * 0.22), max(int(h * 0.78), int(h * 0.22) + 1)
    band_blue = blue[y0:y1]
    blue_ratio = float(band_blue.mean())
    if blue_ratio < 0.025:
        return {"success": False, "intervals": [], "gaps": [], "blue_background_ratio": round(blue_ratio, 4),
                "warning": "未辨識到足夠藍色托盤背景；為避免把岩石顏色誤當背景，已停用自動分割。"}
    # A column is occupied when enough of its central height is non-blue.
    occupancy = 1.0 - band_blue.mean(axis=0)
    win = max(3, int(round(w * 0.006)) | 1)
    kernel = np.ones(win, dtype=np.float32) / win
    smooth = np.convolve(occupancy.astype(np.float32), kernel, mode="same")
    present = smooth >= min_core_occupancy
    # Bridge only tiny interruptions; do not bridge gaps longer than min_gap_mm.
    max_gap_px = max(1, int(round(min_gap_mm / mm_per_px)))
    # Fill bounded false runs no longer than max_gap_px.
    i = 0
    while i < w:
        if present[i]:
            i += 1
            continue
        j = i
        while j < w and not present[j]:
            j += 1
        if i > 0 and j < w and (j - i) <= max_gap_px:
            present[i:j] = True
        i = j
    runs = []
    i = 0
    while i < w:
        if not present[i]:
            i += 1
            continue
        j = i + 1
        while j < w and present[j]:
            j += 1
        if (j - i) * mm_per_px >= min_gap_mm:
            runs.append((i, j))
        i = j
    intervals = [{"x_start_px": a, "x_end_px": b, "length_mm": round((b-a)*mm_per_px, 1)} for a,b in runs]
    gaps = []
    cursor = 0
    for a,b in runs:
        if a > cursor and (a-cursor)*mm_per_px >= min_gap_mm:
            gaps.append({"x_start_px": cursor, "x_end_px": a, "length_mm": round((a-cursor)*mm_per_px, 1)})
        cursor = max(cursor, b)
    if cursor < w and (w-cursor)*mm_per_px >= min_gap_mm:
        gaps.append({"x_start_px": cursor, "x_end_px": w, "length_mm": round((w-cursor)*mm_per_px, 1)})
    return {"success": True, "image_width_px": w, "mm_per_px": float(mm_per_px),
            "blue_background_ratio": round(blue_ratio, 4), "intervals": intervals, "gaps": gaps,
            "method": "blue_tray_nonblue_column_occupancy_v1",
            "warning": "分割結果只表示中央影像高度的非藍色占據區間；可能把托盤污漬、標籤、陰影或非藍色背景當成岩芯。區間長度不是實際回收岩芯長度，不可直接用於 RQD。請逐段人工確認。"}


def draw_core_occupancy_segments(row_image: Image.Image, result: dict) -> Image.Image:
    """Overlay estimated core occupancy intervals and uncertain gaps."""
    from PIL import ImageDraw
    out = row_image.convert("RGB").copy()
    draw = ImageDraw.Draw(out, "RGBA")
    for item in result.get("intervals", []):
        draw.rectangle((item["x_start_px"], 0, item["x_end_px"], out.height-1), fill=(30, 180, 70, 55), outline=(20, 150, 50, 220), width=2)
    for item in result.get("gaps", []):
        draw.rectangle((item["x_start_px"], 0, item["x_end_px"], out.height-1), fill=(230, 50, 40, 55), outline=(210, 40, 30, 220), width=2)
    return out


def analyze_core_row_v8(
    row_image: Image.Image,
    mm_per_px: float,
    blue_hue_range: tuple[int, int] = (78, 132),
    min_segment_mm: float = 25.0,
    min_gap_mm: float = 8.0,
) -> dict:
    """Multi-band, blue-tray-aware core/gap segmentation for one 1 m row.

    The method combines non-blue occupancy in three vertical bands, robust
    smoothing and conservative three-state classification. It identifies
    image-supported core-presence intervals and full-width gap candidates;
    it does NOT infer natural joints, mechanical breaks, or RQD eligibility.
    """
    import cv2
    import numpy as np

    if not np.isfinite(mm_per_px) or mm_per_px <= 0:
        raise ValueError("比例尺必須是有限且大於 0 的數值。")
    if min_segment_mm <= 0 or min_gap_mm <= 0:
        raise ValueError("最小岩芯區段與空隙長度必須大於 0。")
    rgb = np.asarray(row_image.convert("RGB"), dtype=np.uint8)
    h, w = rgb.shape[:2]
    if w < 100 or h < 36:
        return {"success": False, "segments": [], "gaps": [], "uncertain": [], "warning": "列影像尺寸不足，無法進行多區帶判識。"}

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lo, hi = map(int, blue_hue_range)
    if not (0 <= lo <= hi <= 179):
        raise ValueError("藍色 Hue 範圍必須介於 0 至 179。")
    blue = cv2.inRange(hsv, (lo, 38, 28), (hi, 255, 255)) > 0
    # Exclude tray rims and possible labels near the row edges. Three bands
    # provide evidence that a non-blue object is present through the core body.
    y0, y1 = int(h * 0.18), int(h * 0.82)
    if y1 - y0 < 18:
        return {"success": False, "segments": [], "gaps": [], "uncertain": [], "warning": "有效中央影像高度不足。"}
    band_edges = np.linspace(y0, y1, 4).astype(int)
    band_occ = []
    for bi in range(3):
        band = blue[band_edges[bi]:band_edges[bi + 1], :]
        band_occ.append(1.0 - band.mean(axis=0))
    band_occ = np.asarray(band_occ, dtype=np.float32)
    blue_ratio = float(blue[y0:y1, :].mean())
    if blue_ratio < 0.035:
        return {"success": False, "segments": [], "gaps": [], "uncertain": [],
                "blue_background_ratio": round(blue_ratio, 4),
                "warning": "中央區域缺乏足夠藍色托盤背景，無法安全區分岩芯與背景；已停止自動判識。"}

    # Median filtering suppresses isolated stains/reflections. Physical kernel
    # is capped to avoid erasing short features in low-resolution photos.
    k = max(3, min(21, int(round(5.0 / mm_per_px)) | 1))
    if k % 2 == 0:
        k += 1
    filtered = np.vstack([cv2.medianBlur(row.reshape(1, -1), k).reshape(-1) for row in band_occ])
    mean_occ = filtered.mean(axis=0)
    strong_bands = (filtered >= 0.28).sum(axis=0)
    weak_bands = (filtered >= 0.10).sum(axis=0)
    # 2/3 bands occupied => core-present. All 3 bands nearly empty => gap.
    state = np.full(w, 1, dtype=np.uint8)  # 1 = uncertain
    state[(strong_bands >= 2) & (mean_occ >= 0.24)] = 2  # core
    state[(weak_bands == 0) & (mean_occ <= 0.08)] = 0  # clear gap

    # Merge tiny uncertain runs only when both neighbours agree; preserve real
    # gaps and avoid converting surface texture into a cut.
    def runs_of(values):
        out = []
        start = 0
        for idx in range(1, len(values) + 1):
            if idx == len(values) or values[idx] != values[start]:
                out.append((start, idx, int(values[start]))); start = idx
        return out

    runs = runs_of(state)
    for ri in range(1, len(runs) - 1):
        a, b, s = runs[ri]
        left, right = runs[ri - 1], runs[ri + 1]
        if s == 1 and left[2] == right[2] and (b - a) * mm_per_px <= 4.0:
            state[a:b] = left[2]
    runs = runs_of(state)
    segments, gaps, uncertain = [], [], []
    for a, b, s in runs:
        length = (b - a) * mm_per_px
        if s == 2 and length >= min_segment_mm:
            coverage = float((strong_bands[a:b] >= 2).mean())
            occ = float(mean_occ[a:b].mean())
            confidence = "較高" if coverage >= 0.85 and occ >= 0.45 else "中" if coverage >= 0.60 else "低"
            segments.append({"x_start_px": a, "x_end_px": b, "length_mm": round(length, 1),
                             "band_coverage": round(coverage, 3), "mean_occupancy": round(occ, 3),
                             "confidence": confidence, "status": "岩芯本體候選"})
        elif s == 0 and length >= min_gap_mm:
            gaps.append({"x_start_px": a, "x_end_px": b, "length_mm": round(length, 1),
                         "mean_occupancy": round(float(mean_occ[a:b].mean()), 3),
                         "status": "全高度低占據空隙候選"})
        elif s == 1 and length >= 4.0:
            uncertain.append({"x_start_px": a, "x_end_px": b, "length_mm": round(length, 1),
                              "mean_occupancy": round(float(mean_occ[a:b].mean()), 3),
                              "status": "不確定／需人工檢查"})

    return {
        "success": True, "image_width_px": w, "mm_per_px": float(mm_per_px),
        "blue_background_ratio": round(blue_ratio, 4), "segments": segments,
        "gaps": gaps, "uncertain": uncertain,
        "method": "blue_tray_multiband_core_segmentation_v2",
        "warning": "本結果是藍色托盤背景下的多區帶影像判識，不是已驗證的岩心語意模型。綠色區段仍可能包含污漬、標籤或非岩芯物；空隙也可能是遮擋。必須人工確認岩芯起訖、端部缺失及天然／機械斷裂，未確認前不得計入回收率或 RQD。照片不能直接量得 UCS。",
    }


def draw_core_row_analysis_v8(row_image: Image.Image, result: dict) -> Image.Image:
    """Draw V8 segmentation: green core candidates, red gaps, amber uncertain."""
    from PIL import ImageDraw
    out = row_image.convert("RGB").copy()
    draw = ImageDraw.Draw(out, "RGBA")
    for key, fill, outline in (
        ("segments", (25, 190, 75, 55), (15, 140, 55, 230)),
        ("gaps", (235, 55, 45, 65), (205, 35, 25, 230)),
        ("uncertain", (245, 175, 25, 65), (210, 135, 10, 230)),
    ):
        for item in result.get(key, []):
            a, b = item["x_start_px"], item["x_end_px"]
            draw.rectangle((a, 0, max(a, b - 1), out.height - 1), fill=fill, outline=outline, width=2)
    return out
