#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 draw.io 文件缩放至 A4 横向比例页面。

用法：
    python scale_to_a4.py <输入文件> <输出文件>

逻辑：
1. 扫描所有 mxGeometry 找内容边界
2. 计算 fit_scale = min((1123-30)/content_w, (794-30)/content_h)
3. 若 fit_scale >= MIN_SCALE，则缩放内容并放入真实 A4 页面
4. 若 fit_scale < MIN_SCALE，则等比放大页面，保持 1123:794 比例，
   确保内容可读性
5. 变换所有节点坐标、边折点坐标
"""

from __future__ import annotations

import argparse
import math
import sys
import xml.etree.ElementTree as ET

A4W, A4H = 1123.0, 794.0
MARGIN = 15.0
MIN_SCALE = 0.76


def main() -> int:
    parser = argparse.ArgumentParser(
        description="将 draw.io 文件缩放至 A4 横向比例页面"
    )
    parser.add_argument("input", help="输入 .drawio 文件路径")
    parser.add_argument("output", help="输出 .drawio 文件路径")
    args = parser.parse_args()

    in_file = args.input
    out_file = args.output

    tree = ET.parse(in_file)
    root = tree.getroot()

    min_x = math.inf
    min_y = math.inf
    max_x = -math.inf
    max_y = -math.inf

    def touch(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    for cell in root.iter("mxCell"):
        geo = cell.find("mxGeometry")
        if geo is None:
            continue

        if cell.get("vertex") == "1":
            x = float(geo.get("x", "0"))
            y = float(geo.get("y", "0"))
            w = float(geo.get("width", "0"))
            h = float(geo.get("height", "0"))
            touch(x, y)
            touch(x + w, y + h)

        for pt in geo.findall("mxPoint"):
            if pt.get("x") is not None and pt.get("y") is not None:
                touch(float(pt.get("x")), float(pt.get("y")))

        arr = geo.find("Array")
        if arr is not None:
            for pt in arr.findall("mxPoint"):
                if pt.get("x") is not None and pt.get("y") is not None:
                    touch(float(pt.get("x")), float(pt.get("y")))

    content_w = max_x - min_x
    content_h = max_y - min_y
    fit_scale = min((A4W - 2 * MARGIN) / content_w, (A4H - 2 * MARGIN) / content_h)
    scale = max(fit_scale, MIN_SCALE)
    page_factor = 1.0 if fit_scale >= MIN_SCALE else MIN_SCALE / fit_scale
    page_w = round(A4W * page_factor)
    page_h = round(A4H * page_factor)

    def tx(x: str) -> float:
        return (float(x) - min_x) * scale + MARGIN

    def ty(y: str) -> float:
        return (float(y) - min_y) * scale + MARGIN

    def ts(v: str) -> float:
        return float(v) * scale

    for cell in root.iter("mxCell"):
        geo = cell.find("mxGeometry")
        if geo is None:
            continue

        if cell.get("vertex") == "1":
            for attr, fn in [("x", tx), ("y", ty), ("width", ts), ("height", ts)]:
                if geo.get(attr) is not None:
                    geo.set(attr, f"{fn(geo.get(attr)):.2f}")

        for pt in geo.findall("mxPoint"):
            for attr, fn in [("x", tx), ("y", ty)]:
                if pt.get(attr) is not None:
                    pt.set(attr, f"{fn(pt.get(attr)):.2f}")

        arr = geo.find("Array")
        if arr is not None:
            for pt in arr.findall("mxPoint"):
                for attr, fn in [("x", tx), ("y", ty)]:
                    if pt.get(attr) is not None:
                        pt.set(attr, f"{fn(pt.get(attr)):.2f}")

    model = root.find(".//mxGraphModel")
    model.set("pageWidth", str(page_w))
    model.set("pageHeight", str(page_h))
    model.set("dx", "1400")
    model.set("dy", "900")
    model.set("grid", "0")

    with open(out_file, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write(ET.tostring(root, encoding="unicode"))

    print("Done ->", out_file)
    print("Content :", round(content_w, 2), "x", round(content_h, 2))
    print("Scale   :", round(scale, 4))
    print("Page    :", page_w, "x", page_h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
