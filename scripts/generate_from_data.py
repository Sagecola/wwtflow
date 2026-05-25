#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用工艺流程图生成入口

用法:
    python scripts/generate_from_data.py <数据文件.py> [-o <输出.drawio>] [--a4]

示例:
    python scripts/generate_from_data.py examples/houjing_2026.py -o 后京.drawio --a4
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import LayoutEngine, DrawioRenderer


def load_schema(path: str):
    """从 Python 文件加载 PlantSchema 对象"""
    spec = importlib.util.spec_from_file_location("schema_module", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 优先查找常见的变量名
    for name in ["schema", "plant_schema", "houjing_schema", "haicheng_schema"]:
        if hasattr(mod, name):
            return getattr(mod, name)

    # 查找第一个 PlantSchema 实例
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if type(obj).__name__ == "PlantSchema":
            return obj

    raise ValueError(f"无法在 {path} 中找到 PlantSchema 对象")


def main():
    parser = argparse.ArgumentParser(description="废水处理厂站工艺流程图生成器")
    parser.add_argument("input", help="输入数据文件 (.py)")
    parser.add_argument("-o", "--output", default="", help="输出 .drawio 文件路径")
    parser.add_argument("--a4", action="store_true", help="自动生成 A4 横向版本")
    args = parser.parse_args()

    # 加载数据
    schema = load_schema(args.input)

    # 确定输出路径：默认与 schema 文件同目录（通常已在 draft/ 下）
    if args.output:
        out_path = args.output
    else:
        schema_dir = os.path.dirname(os.path.abspath(args.input))
        base = os.path.splitext(os.path.basename(args.input))[0]
        base = re.sub(r"_schema$", "", base)
        out_path = os.path.join(schema_dir, f"{base}.drawio")

    # 布局 + 渲染（样式模式：A3比例图框 + 工程图标题栏）
    engine = LayoutEngine(schema, styled=True)
    result = engine.layout()

    renderer = DrawioRenderer(
        result.cells, result.page_w, result.page_h,
        diagram_id=schema.name, diagram_name=f"{schema.name}工艺流程图",
        styled=True,
    )
    xml = renderer.render()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"Generated: {out_path}")
    print(f"  Vertices: {sum(1 for c in result.cells if c['t'] == 'v')}")
    print(f"  Edges:    {sum(1 for c in result.cells if c['t'] == 'e')}")
    print(f"  Page:     {result.page_w} x {result.page_h}")

    # XML 验证
    import xml.etree.ElementTree as ET
    try:
        ET.parse(out_path)
        print("  XML:      OK")
    except Exception as e:
        print(f"  XML:      FAILED ({e})")
        return 1

    # A4 缩放
    if args.a4:
        a4_path = out_path.replace(".drawio", "_A4横向.drawio")
        scale_script = os.path.join(os.path.dirname(__file__), "scale_to_a4.py")
        subprocess.run([sys.executable, scale_script, out_path, a4_path], check=True)
        print(f"  A4:       {a4_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
