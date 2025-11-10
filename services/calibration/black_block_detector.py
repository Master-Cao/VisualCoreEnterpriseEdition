#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
黑块检测器
从强度图中检测黑色标记块（用于标定）
移植自 VisionCore/tools/detect_black_block_to_xy.py
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class BlackBlock:
    """黑块检测结果"""
    center_u: int
    center_v: int
    area_px: float
    score: float


def _build_binaries(gray: np.ndarray) -> List[dict]:
    """生成多种二值化变体以提高检测鲁棒性"""
    variants = []
    h, w = gray.shape[:2]
    
    # 原始灰度图
    variants.append(("raw", gray))
    
    # CLAHE增强
    try:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        variants.append(("clahe", clahe.apply(gray)))
    except Exception:
        pass
    
    # 直方图均衡化
    try:
        variants.append(("equalize", cv2.equalizeHist(gray)))
    except Exception:
        pass
    
    # 光照归一化
    try:
        sigma = max(8.0, 0.08 * min(h, w))
        bg = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), sigmaX=sigma, sigmaY=sigma)
        corr = cv2.divide(gray.astype(np.float32) + 1.0, bg + 1.0, scale=128.0)
        corr = np.clip(corr, 0, 255).astype(np.uint8)
        variants.append(("illum", corr))
    except Exception:
        pass
    
    # 对每个变体应用多种阈值方法
    results = []
    k = max(3, int(round(min(h, w) * 0.01)))
    k = k + 1 if k % 2 == 0 else k
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, k), max(3, k)))
    
    # 多种块大小
    block_sizes = []
    for bs_ratio in (0.03, 0.05, 0.08):
        bs = int(round(bs_ratio * min(h, w)))
        bs = bs + 1 if bs % 2 == 0 else bs
        if bs >= 5:
            block_sizes.append(bs)
    if 25 not in block_sizes:
        block_sizes.append(25)
    
    Cs = (3, 7, 11)
    
    for vname, g in variants:
        g_blur = cv2.GaussianBlur(g, (5, 5), 0)
        
        # Otsu阈值
        _, b_otsu_inv = cv2.threshold(g_blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        m = cv2.morphologyEx(b_otsu_inv, cv2.MORPH_OPEN, kernel, iterations=1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel, iterations=1)
        results.append({"name": f"{vname}_otsu", "img": m})
        
        # 自适应阈值
        for bs in block_sizes:
            for C in Cs:
                try:
                    b_adapt_inv = cv2.adaptiveThreshold(
                        g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY_INV, bs, C
                    )
                    m2 = cv2.morphologyEx(b_adapt_inv, cv2.MORPH_OPEN, kernel, iterations=1)
                    m2 = cv2.morphologyEx(m2, cv2.MORPH_CLOSE, kernel, iterations=1)
                    results.append({"name": f"{vname}_adapt_b{bs}_C{C}", "img": m2})
                except Exception:
                    pass
    
    # 去重
    uniq = []
    seen = set()
    for d in results:
        im = d["img"]
        key = (im.shape, int(im.mean()), int(im.std()))
        if key not in seen:
            seen.add(key)
            uniq.append(d)
    
    return uniq


def _ring_contrast(gray: np.ndarray, cnt: np.ndarray, inner_inflate: int = 2, ring: int = 4) -> float:
    """计算轮廓内部与环形边界的对比度"""
    x, y, w, h = cv2.boundingRect(cnt)
    pad = ring + 2
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(gray.shape[1], x + w + pad)
    y1 = min(gray.shape[0], y + h + pad)
    roi = gray[y0:y1, x0:x1]
    
    if roi.size == 0:
        return 0.0
    
    cnt_shift = cnt.copy()
    cnt_shift[:, 0, 0] -= x0
    cnt_shift[:, 0, 1] -= y0
    
    mask_in = np.zeros(roi.shape[:2], np.uint8)
    cv2.drawContours(mask_in, [cnt_shift], -1, 255, -1)
    
    if inner_inflate > 0:
        k = inner_inflate * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask_in = cv2.dilate(mask_in, kernel, iterations=1)
    
    mask_ring = cv2.dilate(
        mask_in,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ring * 2 + 1, ring * 2 + 1)),
        1
    )
    mask_ring = cv2.subtract(mask_ring, mask_in)
    
    if int(mask_ring.sum()) == 0:
        return 0.0
    
    mean_in = float(cv2.mean(roi, mask=mask_in)[0])
    mean_out = float(cv2.mean(roi, mask=mask_ring)[0])
    return max(0.0, mean_out - mean_in)


def _quad_score(cnt: np.ndarray, gray: np.ndarray) -> Optional[dict]:
    """评估轮廓是否为方形黑块"""
    area = cv2.contourArea(cnt)
    if area <= 1:
        return None
    
    rect = cv2.minAreaRect(cnt)
    (cx, cy), (w, h), angle = rect
    bw, bh = (w, h) if w >= h else (h, w)
    
    if bw <= 2 or bh <= 2:
        return None
    
    ar = bw / float(bh)
    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull)
    
    if hull_area <= 1:
        return None
    
    solidity = area / float(hull_area)
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
    box = cv2.boxPoints(rect)
    x, y, ww, hh = cv2.boundingRect(cnt)
    extent = area / float(max(1, ww * hh))
    contrast = _ring_contrast(gray, cnt, inner_inflate=1, ring=5)
    
    # 计算综合得分
    score = 0.0
    if len(approx) == 4:
        score += 1.0
    score += max(0.0, 1.0 - abs(ar - 1.0))
    score += max(0.0, min(solidity, 1.0))
    score += max(0.0, min(extent, 1.0))
    score += min(1.0, contrast / 20.0)
    
    return {
        'center': (float(cx), float(cy)),
        'area': float(area),
        'rect': rect,
        'box': box.astype(np.float32),
        'aspect': float(ar),
        'solidity': float(solidity),
        'extent': float(extent),
        'contrast': float(contrast),
        'size_hint': float((bw + bh) * 0.5),
        'score': float(score)
    }


def _find_black_quads(bin_img: np.ndarray, gray: np.ndarray, 
                      min_area_ratio=0.00015, max_area_ratio=0.35) -> List[dict]:
    """在二值图中查找黑色方块"""
    h, w = bin_img.shape[:2]
    img_area = float(h * w)
    contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    cand = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (min_area_ratio * img_area <= area <= max_area_ratio * img_area):
            continue
        
        qs = _quad_score(cnt, gray)
        if qs is None:
            continue
        
        # 过滤条件
        if qs['aspect'] < 0.8 or qs['aspect'] > 1.25:
            continue
        if qs['solidity'] < 0.9 or qs['extent'] < 0.6:
            continue
        if qs['contrast'] < 8.0:
            continue
        
        cand.append(qs)
    
    cand.sort(key=lambda d: d['score'], reverse=True)
    return cand


def _merge_duplicates(cands: List[dict], dist_thresh: float) -> List[dict]:
    """合并重复检测"""
    kept = []
    for c in cands:
        cx, cy = c['center']
        ok = True
        for k in kept:
            kx, ky = k['center']
            if (cx - kx) ** 2 + (cy - ky) ** 2 <= dist_thresh ** 2:
                ok = False
                break
        if ok:
            kept.append(c)
    return kept


def _pca_axes(points: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """PCA主成分分析"""
    m = points.mean(axis=0)
    X = points - m
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    u = Vt[0]
    v = Vt[1] if Vt.shape[0] > 1 else np.array([0.0, 1.0])
    return m, u, v


def _order_grid_by_pca(centers: np.ndarray, rows: int, cols: int) -> List[Tuple[float, float]]:
    """使用PCA对网格点排序"""
    m, u, v = _pca_axes(centers)
    proj_u = (centers - m) @ u
    proj_v = (centers - m) @ v
    
    if rows >= 2:
        data = proj_v.astype(np.float32).reshape(-1, 1)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-4)
        ret, labels, centers_k = cv2.kmeans(data, rows, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
        order = np.argsort(centers_k.reshape(-1))
        label_map = {int(lbl): int(i) for i, lbl in enumerate(order)}
        row_ids = np.array([label_map[int(l)] for l in labels.reshape(-1)])
        
        rows_list = []
        for r in range(rows):
            idxs = np.where(row_ids == r)[0]
            if idxs.size == 0:
                rows_list.append([])
                continue
            row_pts = centers[idxs]
            row_proj_u = proj_u[idxs]
            order_in_row = np.argsort(row_proj_u)
            rows_list.append(row_pts[order_in_row])
    else:
        order_u = np.argsort(proj_u)
        rows_list = [centers[order_u]]
    
    ordered = []
    for r in range(len(rows_list)):
        row = rows_list[r]
        if row is None or len(row) == 0:
            continue
        if cols and len(row) > cols:
            step = len(row) / float(cols)
            take = [int(round(i * step + 0.49)) for i in range(cols)]
            take = np.clip(take, 0, len(row) - 1)
            row = row[take]
        ordered.append(row)
    
    if rows and len(ordered) > rows:
        ordered = ordered[:rows]
    
    pts = []
    for r in ordered:
        for p in r:
            pts.append((float(p[0]), float(p[1])))
    return pts


def detect_black_blocks(image: np.ndarray, max_blocks: int = 12, 
                        rows: int = 3, cols: int = 4) -> List[BlackBlock]:
    """
    检测图像中的黑色标记块
    
    Args:
        image: 输入图像（灰度或彩色）
        max_blocks: 最大检测数量
        rows: 网格行数
        cols: 网格列数
    
    Returns:
        检测到的黑块列表，按网格顺序排列
    """
    if image is None:
        return []
    
    # 转为灰度图
    if len(image.shape) == 2:
        gray = image
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 生成多种二值化
    binaries = _build_binaries(gray)
    
    # 从所有二值图中收集候选
    all_cands = []
    h, w = gray.shape[:2]
    approx_tile = max(8.0, min(h, w) * 0.04)
    
    for d in binaries:
        b = d["img"]
        cands = _find_black_quads(b, gray)
        all_cands.extend(cands)
    
    # 按得分排序并去重
    all_cands.sort(key=lambda d: d['score'], reverse=True)
    all_cands = _merge_duplicates(all_cands, dist_thresh=approx_tile * 0.6)
    
    # 尺寸过滤
    if all_cands:
        sizes = np.array([c['size_hint'] for c in all_cands], dtype=np.float32)
        med = float(np.median(sizes))
        keep = []
        for c in all_cands:
            if med <= 0:
                keep.append(c)
                continue
            if 0.65 * med <= c['size_hint'] <= 1.5 * med:
                keep.append(c)
        all_cands = keep
    
    # 距离过滤（剔除孤立点）
    if len(all_cands) >= 3:
        centers_tmp = np.array([c['center'] for c in all_cands], dtype=np.float32)
        dists = []
        for i in range(len(centers_tmp)):
            di = np.sqrt(((centers_tmp[i] - centers_tmp) ** 2).sum(axis=1))
            di.sort()
            if len(di) > 1:
                dists.append(di[1])
        if dists:
            dists = np.array(dists, dtype=np.float32)
            md = float(np.median(dists))
            filtered = []
            for idx, c in enumerate(all_cands):
                if dists[idx] <= 1.8 * md:
                    filtered.append(c)
            all_cands = filtered
    
    # 凸包过滤
    if len(all_cands) >= 4:
        pts_all = np.array([c['center'] for c in all_cands], dtype=np.float32)
        rect = cv2.minAreaRect(pts_all.reshape(-1, 1, 2))
        box = cv2.boxPoints(rect)
        inliers = []
        for c in all_cands:
            p = c['center']
            inside = cv2.pointPolygonTest(box, (p[0], p[1]), False)
            if inside >= 0:
                inliers.append(c)
        if len(inliers) >= max(4, len(all_cands) // 2):
            all_cands = inliers
    
    if not all_cands:
        return []
    
    # 按网格排序
    centers = np.array([c['center'] for c in all_cands], dtype=np.float32)
    if rows > 0 and cols > 0 and centers.shape[0] >= max(rows * cols // 2, 4):
        ordered_pts = _order_grid_by_pca(centers, rows, cols)
    else:
        ordered_pts = [(float(x), float(y)) for x, y in centers]
    
    # 限制数量
    ordered_pts = ordered_pts[:min(max_blocks, len(ordered_pts))]
    
    # 转换为BlackBlock对象
    blocks = []
    for u, v in ordered_pts:
        # 查找对应的候选以获取完整信息
        best_cand = None
        best_dist = float('inf')
        for c in all_cands:
            cx, cy = c['center']
            dist = (u - cx) ** 2 + (v - cy) ** 2
            if dist < best_dist:
                best_dist = dist
                best_cand = c
        
        if best_cand:
            blocks.append(BlackBlock(
                center_u=int(round(u)),
                center_v=int(round(v)),
                area_px=best_cand['area'],
                score=best_cand['score']
            ))
    
    return blocks

