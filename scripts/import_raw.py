#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从废水处理厂 raw/ 目录（或单个文件）生成 wwtflow schema.py 草稿。

支持格式：CSV（主数据源）、MD（补充药剂/工艺描述）、TXT（改动说明）
不可解析但在注释中列出：SVG、PDF

用法:
    python scripts/import_raw.py <目录或CSV文件> [-o <输出schema.py>] [--plant <厂站名>]

示例:
    python scripts/import_raw.py 温州海城/raw/          # 自动输出到 温州海城/draft/
    python scripts/import_raw.py 温州海城/raw/ --plant 温州海城
    python scripts/import_raw.py 温州海城/raw/标准评价体系-海城2026.4.2.csv
"""

import argparse
import csv
import os
import re
import sys

# ──────────────────────────────────────────────────────────────
# CSV 列定义（与 import_csv.py 保持一致）
# ──────────────────────────────────────────────────────────────
CSV_COLS = {
    "capacity": 0,
    "unit":     1,
    "size":     2,
    "hrt":      3,
    "drug1_name": 5,  "drug1_conc": 6,  "drug1_target": 7,
    "drug1_time": 8,  "drug1_ctrl":  9,
    "drug2_name": 12, "drug2_conc": 13, "drug2_target": 14,
    "drug2_time": 15, "drug2_ctrl": 16,
    "drug3_name": 19, "drug3_conc": 20, "drug3_target": 21,
    "drug3_time": 22, "drug3_ctrl": 23,
    "drug4_name": 26, "drug4_conc": 27, "drug4_target": 28,
    "drug4_time": 29, "drug4_ctrl": 30,
}

BLANK = {"——", "-", "—", "/", ""}
SLOT_RE = re.compile(r"(?P<num>\d+)\s*[×xX＊*]\s*\d")

# ──────────────────────────────────────────────────────────────
# 通用工具
# ──────────────────────────────────────────────────────────────

def _read_text(path: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _cell(row: list, idx: int) -> str:
    return row[idx].strip() if idx < len(row) else ""


def _blank(v: str) -> bool:
    return v in BLANK or not v


def _py_str(s: str) -> str:
    return repr(s)


# ──────────────────────────────────────────────────────────────
# 目录扫描
# ──────────────────────────────────────────────────────────────

def scan_directory(path: str) -> dict:
    """扫描目录，按扩展名分类文件，返回 {csv, md, txt, svg, pdf, other}。"""
    result: dict[str, list[str]] = {
        "csv": [], "md": [], "txt": [], "svg": [], "pdf": [], "other": []
    }
    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        bucket = ext if ext in result else "other"
        result[bucket].append(path)
        return result

    for entry in sorted(os.listdir(path)):
        full = os.path.join(path, entry)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(entry)[1].lower().lstrip(".")
        bucket = ext if ext in result else "other"
        result[bucket].append(full)
    return result


# ──────────────────────────────────────────────────────────────
# CSV 解析（保留 import_csv.py 全部逻辑）
# ──────────────────────────────────────────────────────────────

def _infer_group_count(size: str, params: list) -> int:
    m = re.search(r"[×xX＊*]\s*(\d+)\s*$", size)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 12:
            return n
    return len(params) if 2 <= len(params) <= 12 else 0


def _build_param_short(name: str, conc: str, target: str, ctrl: str) -> str:
    """生成人工基准风格的短格式参数文字：药剂-控制值"""
    parts = [name]
    if not _blank(ctrl):
        parts.append(ctrl)
    elif not _blank(target):
        parts.append(target)
    return "-".join(parts)


def _is_lower_stream(name: str) -> bool:
    tokens = ("二级（", "三级（", "生化池", "排放口", "气浮池（", "pH回调")
    return any(t in name for t in tokens)


def parse_csv(csv_path: str) -> dict:
    text = _read_text(csv_path)
    rows = list(csv.reader(text.splitlines()))
    streams: dict[str, dict] = {}
    order: list[str] = []
    current = ""

    for raw in rows[2:]:
        unit_name = _cell(raw, CSV_COLS["unit"])
        if not unit_name:
            continue
        cap = _cell(raw, CSV_COLS["capacity"])
        if cap:
            current = cap
            if current not in streams:
                streams[current] = {"name": current, "units": []}
                order.append(current)
        if not current:
            continue
        params = []
        for offset in range(4):
            base = CSV_COLS["drug1_name"] + offset * 7
            drug = _cell(raw, base)
            if _blank(drug):
                continue
            conc  = _cell(raw, base + 1)
            tgt   = _cell(raw, base + 2)
            ctrl  = _cell(raw, base + 4)
            params.append(_build_param_short(drug, conc, tgt, ctrl))
        size = _cell(raw, CSV_COLS["size"])
        group_count = _infer_group_count(size, params)
        streams[current]["units"].append({
            "name": unit_name,
            "size": size,
            "params": params,
            "group_count": group_count,
        })

    return {"streams": [streams[k] for k in order], "order": order}


# ──────────────────────────────────────────────────────────────
# MD 文件解析（补充药剂/工艺流程信息）
# ──────────────────────────────────────────────────────────────

def parse_md(md_path: str) -> dict:
    """
    解析 MD 文件，返回:
      flow_lines  : 含 → 的工艺流程描述行
      table_rows  : 含 | 的表格行（药剂投加表等）
    """
    text = _read_text(md_path)
    flow_lines: list[str] = []
    table_rows: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "→" in stripped or "->" in stripped:
            flow_lines.append(stripped)
        elif stripped.startswith("|") and stripped.endswith("|"):
            # 跳过纯分隔行（如 |---|---|）
            inner = stripped.strip("|")
            if re.fullmatch(r"[\s\-:|]+", inner):
                continue
            table_rows.append(stripped)

    return {
        "file": os.path.basename(md_path),
        "flow_lines": flow_lines,
        "table_rows": table_rows,
    }


# ──────────────────────────────────────────────────────────────
# TXT 文件解析（改动说明）
# ──────────────────────────────────────────────────────────────

def parse_txt(txt_path: str) -> dict:
    """
    解析 TXT 文件，提取 markdown 表格行（| 分隔）及普通改动说明行。
    """
    text = _read_text(txt_path)
    table_rows: list[str] = []
    plain_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            inner = stripped.strip("|")
            if re.fullmatch(r"[\s\-:|]+", inner):
                continue
            table_rows.append(stripped)
        else:
            plain_lines.append(stripped)

    return {
        "file": os.path.basename(txt_path),
        "table_rows": table_rows,
        "plain_lines": plain_lines,
    }


# ──────────────────────────────────────────────────────────────
# Schema 代码渲染（保留 import_csv.py 全部逻辑）
# ──────────────────────────────────────────────────────────────

def _render_stream(stream: dict) -> list[str]:
    name = stream["name"]
    lines = []
    var = re.sub(r"[^\w]", "_", name.lower())[:20].strip("_") or "stream"

    lines.append(f"{var} = Stream(")
    lines.append(f'    name={_py_str(name)},')
    lines.append(f'    flow_rate="",')
    lines.append(f'    width=220,')
    lines.append(f'    units=[')
    lines.append(f'        StreamUnit("header", {_py_str(name)}),')

    for unit in stream["units"]:
        uname = unit["name"]
        params = unit["params"]
        gc = unit["group_count"]

        if gc >= 2 and params:
            labels = ", ".join(_py_str(f"{i+1}池") for i in range(gc))
            lines.append(f'        StreamUnit("reaction_group", ReactionGroup(')
            lines.append(f'            title={_py_str(uname)},')
            lines.append(f'            labels=[{labels}],')
            lines.append(f'            specs=[')
            for i, p in enumerate(params):
                col = min(i, gc - 1)
                lines.append(f'                ParamSpec({col}, {col}, {_py_str(p)}),')
            lines.append(f'            ]')
            lines.append(f'        )),')
        elif params:
            prm = "\n".join(params)
            lines.append(
                f'        StreamUnit("single_tank", SingleTank({_py_str(uname)}, prm_text={_py_str(prm)})),'
            )
        else:
            lines.append(f'        StreamUnit("single_tank", SingleTank({_py_str(uname)})),')

    lines.append(f'    ]')
    lines.append(f')')
    return lines


# ──────────────────────────────────────────────────────────────
# 顶部注释块构建
# ──────────────────────────────────────────────────────────────

def _build_header_comment(
    plant_name: str,
    files: dict,
    txt_data: list[dict],
) -> list[str]:
    """构建草稿文件顶部的 raw/ 文件清单 + 改动说明注释块。"""
    out: list[str] = []
    out.append('"""')
    out.append(f'{plant_name}厂站工艺流程图 — Schema 草稿（由 import_raw.py 自动生成）')
    out.append('')
    out.append('请在 draw.io 中对照人工基准核对并补全以下内容：')
    out.append('  1. 每条支流的 flow_rate（流量）')
    out.append('  2. 参数框文字按 "药剂-控制值" 短格式核对')
    out.append('  3. 综合区和生化区（CombinedSection / BioSection）需手动补充')
    out.append('  4. 支流汇入综合区的 custom_edges 需手动添加')
    out.append('')
    out.append('── raw 目录文件清单 ──')
    for f in files.get("csv", []):
        out.append(f'  [CSV]  {os.path.basename(f)}  ← 主数据源，已解析')
    for f in files.get("md", []):
        out.append(f'  [MD]   {os.path.basename(f)}  ← 已提取工艺流程/药剂信息，见下方注释')
    for f in files.get("txt", []):
        out.append(f'  [TXT]  {os.path.basename(f)}  ← 已提取改动说明，见下方注释')
    for f in files.get("svg", []):
        out.append(f'  [SVG]  {os.path.basename(f)}  ← 未解析，请 AI 生成时参考此文件')
    for f in files.get("pdf", []):
        out.append(f'  [PDF]  {os.path.basename(f)}  ← 未解析，请 AI 生成时参考此文件')
    for f in files.get("other", []):
        out.append(f'  [其他] {os.path.basename(f)}')
    out.append('"""')
    out.append('')

    # 改动说明注释块（来自 TXT）
    for td in txt_data:
        fname = td["file"]
        rows = td["table_rows"]
        plain = td["plain_lines"]
        if not rows and not plain:
            continue
        out.append(f'# ╔══ [改动说明] 来源：{fname} ══╗')
        for r in rows:
            out.append(f'# {r}')
        for p in plain:
            out.append(f'# {p}')
        out.append(f'# ╚{"═" * (len(fname) + 18)}╝')
        out.append('')

    return out


# ──────────────────────────────────────────────────────────────
# MD 注释附加到支流定义上方
# ──────────────────────────────────────────────────────────────

def _md_comment_for_stream(stream_name: str, md_data: list[dict]) -> list[str]:
    """
    从所有 MD 解析结果中，找与 stream_name 相关的行，
    返回要插入到该 Stream 定义上方的注释行列表。
    """
    lines: list[str] = []
    for md in md_data:
        fname = md["file"]
        matched_flow = [
            l for l in md["flow_lines"]
            if stream_name in l or any(tok in l for tok in stream_name.split("（"))
        ]
        matched_table = [
            r for r in md["table_rows"]
            if stream_name in r or any(tok in r for tok in stream_name.split("（"))
        ]
        if matched_flow or matched_table:
            lines.append(f'# [MD补充] 来源：{fname}，支流：{stream_name}')
            for l in matched_flow:
                lines.append(f'#   流程: {l}')
            for r in matched_table:
                lines.append(f'#   表格: {r}')
    return lines


def _md_global_comment(md_data: list[dict]) -> list[str]:
    """返回所有 MD 内容的全局注释（未匹配到具体支流的行）。"""
    lines: list[str] = []
    for md in md_data:
        fname = md["file"]
        if not md["flow_lines"] and not md["table_rows"]:
            continue
        lines.append(f'# ── [MD全文摘要] {fname} ──')
        for l in md["flow_lines"]:
            lines.append(f'#   → {l}')
        for r in md["table_rows"]:
            lines.append(f'#   | {r}')
    return lines


# ──────────────────────────────────────────────────────────────
# 无 CSV 时的空壳草稿生成
# ──────────────────────────────────────────────────────────────

def generate_schema_no_csv(
    files: dict,
    plant_name: str,
    txt_data: list[dict],
) -> str:
    """当目录中没有 CSV 文件时，生成仅含文件清单注释和 TODO 占位的空壳草稿。"""
    var_name = re.sub(r"[^\w]", "_", plant_name.lower())[:20].strip("_") or "plant"
    out: list[str] = []

    # 顶部 docstring：文件清单
    out.append('"""')
    out.append(f'{plant_name}厂站工艺流程图 — Schema 草稿（由 import_raw.py 自动生成，无 CSV）')
    out.append('')
    out.append('未找到 CSV 文件，以下为目录中发现的所有文件，请 AI 参考后手动补全支流定义：')
    out.append('')
    out.append('── raw 目录文件清单 ──')
    for f in files.get("txt", []):
        out.append(f'  [TXT]  {os.path.basename(f)}  ← 已提取内容，见下方注释')
    for f in files.get("md", []):
        out.append(f'  [MD]   {os.path.basename(f)}  ← 请 AI 参考此文件')
    for f in files.get("svg", []):
        out.append(f'  [SVG]  {os.path.basename(f)}  ← 请 AI 参考此文件')
    for f in files.get("pdf", []):
        out.append(f'  [PDF]  {os.path.basename(f)}  ← 请 AI 参考此文件')
    for f in files.get("other", []):
        out.append(f'  [其他] {os.path.basename(f)}')
    if not any(files.get(k) for k in ("txt", "md", "svg", "pdf", "other")):
        out.append('  （目录为空或无可识别文件）')
    out.append('"""')
    out.append('')

    # TXT 内容注释
    for td in txt_data:
        fname = td["file"]
        rows = td["table_rows"]
        plain = td["plain_lines"]
        if not rows and not plain:
            continue
        out.append(f'# ╔══ [TXT 内容] 来源：{fname} ══╗')
        for r in rows:
            out.append(f'# {r}')
        for p in plain:
            out.append(f'# {p}')
        out.append(f'# ╚{"═" * (len(fname) + 14)}╝')
        out.append('')

    # imports
    out.append('import sys, os')
    out.append('sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))')
    out.append('')
    out.append('from engine import (')
    out.append('    PlantSchema, Stream, StreamUnit, ReactionGroup, SingleTank,')
    out.append('    ParamSpec, CombinedSection, CombinedUnit, BioSection, BioUnit,')
    out.append('    EdgeDef, LayoutEngine, DrawioRenderer,')
    out.append(')')
    out.append('')

    # 支流定义占位
    out.append('# ================================================================')
    out.append('# 支流定义（请根据上方文件清单和注释手动补全）')
    out.append('# ================================================================')
    out.append('')
    out.append('# TODO: 在此处添加各支流定义，例如：')
    out.append('# stream1 = Stream(')
    out.append('#     name="一级（废水）",')
    out.append('#     flow_rate="",')
    out.append('#     width=220,')
    out.append('#     units=[')
    out.append('#         StreamUnit("header", "一级（废水）"),')
    out.append('#         # ... 补充各处理单元')
    out.append('#     ]')
    out.append('# )')
    out.append('')

    # 综合区 TODO
    out.append('# ================================================================')
    out.append('# 综合区（请手动补充）')
    out.append('# ================================================================')
    out.append('')
    out.append('combined = CombinedSection(')
    out.append('    title="综合废水处理系统",')
    out.append('    adjuster=SingleTank("综合调节池"),')
    out.append('    rows=[')
    out.append('        # TODO: 根据 MD / PDF / SVG / TXT 中的综合段数据补充')
    out.append('    ],')
    out.append(')')
    out.append('')

    # 生化区 TODO
    out.append('# ================================================================')
    out.append('# 生化区（请手动补充）')
    out.append('# ================================================================')
    out.append('')
    out.append('bio = BioSection(')
    out.append('    title="生化处理系统",')
    out.append('    main_line=[')
    out.append('        # TODO: 根据 MD / PDF / SVG / TXT 中的生化段数据补充')
    out.append('    ],')
    out.append(')')
    out.append('')

    # 根对象 TODO
    out.append('# ================================================================')
    out.append('# 厂站根对象')
    out.append('# ================================================================')
    out.append('')
    out.append(f'{var_name}_schema = PlantSchema(')
    out.append(f'    name={_py_str(plant_name)},')
    out.append(f'    version="2026",')
    out.append(f'    streams=[  # TODO: 填入上方定义的支流变量名，如 stream1, stream2')
    out.append(f'    ],')
    out.append(f'    combined=combined,')
    out.append(f'    bio=bio,')
    out.append(f')')
    out.append('')

    # 生成入口
    out.append('# ================================================================')
    out.append('# 生成')
    out.append('# ================================================================')
    out.append('')
    out.append('if __name__ == "__main__":')
    out.append(f'    engine = LayoutEngine({var_name}_schema)')
    out.append(f'    result = engine.layout()')
    out.append(f'    renderer = DrawioRenderer(')
    out.append(f'        result.cells, result.page_w, result.page_h,')
    out.append(f'        diagram_id={_py_str(var_name)},')
    out.append(f'        diagram_name={_py_str(plant_name + "工艺流程图")}')
    out.append(f'    )')
    out.append(f'    out_file = {_py_str(plant_name + "_工艺流程_2026_draft.drawio")}')
    out.append(f'    renderer.write(out_file)')
    out.append(f'    print(f"Generated: {{out_file}}")')

    return "\n".join(out) + "\n"




def generate_schema(
    data: dict,
    plant_name: str,
    files: dict,
    md_data: list[dict],
    txt_data: list[dict],
) -> str:
    var_name = re.sub(r"[^\w]", "_", plant_name.lower())[:20].strip("_") or "plant"
    top_streams = [s for s in data["streams"] if not _is_lower_stream(s["name"])]
    lower_streams = [s for s in data["streams"] if _is_lower_stream(s["name"])]

    out: list[str] = []

    # 顶部注释块
    out.extend(_build_header_comment(plant_name, files, txt_data))

    # imports
    out.append('import sys, os')
    out.append('sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))')
    out.append('')
    out.append('from engine import (')
    out.append('    PlantSchema, Stream, StreamUnit, ReactionGroup, SingleTank,')
    out.append('    ParamSpec, CombinedSection, CombinedUnit, BioSection, BioUnit,')
    out.append('    EdgeDef, LayoutEngine, DrawioRenderer,')
    out.append(')')
    out.append('')

    # MD 全局摘要（若有内容）
    global_md = _md_global_comment(md_data)
    if global_md:
        out.append('# ================================================================')
        out.append('# MD 文件全文摘要（供 AI 参考，未匹配到具体支流的内容）')
        out.append('# ================================================================')
        out.extend(global_md)
        out.append('')

    out.append('# ================================================================')
    out.append('# 支流定义（上方各支流）')
    out.append('# ================================================================')
    out.append('')

    stream_vars: list[str] = []
    for s in top_streams:
        var = re.sub(r"[^\w]", "_", s["name"].lower())[:20].strip("_") or "stream"
        stream_vars.append(var)
        # 插入 MD 补充注释
        md_comments = _md_comment_for_stream(s["name"], md_data)
        if md_comments:
            out.extend(md_comments)
        out.extend(_render_stream(s))
        out.append('')

    if lower_streams:
        out.append('# ================================================================')
        out.append('# 综合/生化段支流（需手动整理为 CombinedSection / BioSection）')
        out.append('# ================================================================')
        out.append('# 以下支流来自 CSV 中标记为横向处理的段，供参考，请替换为正式结构')
        out.append('')
        for s in lower_streams:
            md_comments = _md_comment_for_stream(s["name"], md_data)
            if md_comments:
                out.extend(md_comments)
            out.extend(_render_stream(s))
            out.append('')

    return out


def _finish_schema(out: list[str], plant_name: str, stream_vars: list[str]) -> str:
    """追加综合区、生化区、根对象、生成入口，返回完整字符串。"""
    var_name = re.sub(r"[^\w]", "_", plant_name.lower())[:20].strip("_") or "plant"

    out.append('# ================================================================')
    out.append('# 综合区（请手动补充）')
    out.append('# ================================================================')
    out.append('')
    out.append('combined = CombinedSection(')
    out.append('    title="综合废水处理系统",')
    out.append('    adjuster=SingleTank("综合调节池"),')
    out.append('    rows=[')
    out.append('        # TODO: 根据 CSV / MD / PDF / SVG 中的综合段数据补充')
    out.append('        # [CombinedUnit("reaction_group", ReactionGroup(...)), ...]')
    out.append('    ],')
    out.append(')')
    out.append('')
    out.append('# ================================================================')
    out.append('# 生化区（请手动补充）')
    out.append('# ================================================================')
    out.append('')
    out.append('bio = BioSection(')
    out.append('    title="生化处理系统",')
    out.append('    main_line=[')
    out.append('        # TODO: 根据 CSV / MD / PDF / SVG 中的生化段数据补充')
    out.append('    ],')
    out.append(')')
    out.append('')
    out.append('# ================================================================')
    out.append('# 厂站根对象')
    out.append('# ================================================================')
    out.append('')
    streams_arg = ', '.join(stream_vars)
    out.append(f'{var_name}_schema = PlantSchema(')
    out.append(f'    name={_py_str(plant_name)},')
    out.append(f'    version="2026",')
    out.append(f'    streams=[{streams_arg}],')
    out.append(f'    combined=combined,')
    out.append(f'    bio=bio,')
    out.append(f')')
    out.append('')
    out.append('# ================================================================')
    out.append('# 生成')
    out.append('# ================================================================')
    out.append('')
    out.append('if __name__ == "__main__":')
    out.append(f'    engine = LayoutEngine({var_name}_schema)')
    out.append(f'    result = engine.layout()')
    out.append(f'    renderer = DrawioRenderer(')
    out.append(f'        result.cells, result.page_w, result.page_h,')
    out.append(f'        diagram_id={_py_str(var_name)},')
    out.append(f'        diagram_name={_py_str(plant_name + "工艺流程图")}')
    out.append(f'    )')
    out.append(f'    out_file = {_py_str(plant_name + "_工艺流程_2026_draft.drawio")}')
    out.append(f'    renderer.write(out_file)')
    out.append(f'    print(f"Generated: {{out_file}}")')

    return "\n".join(out) + "\n"


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────

def _infer_plant_name(input_path: str) -> str:
    """从目录名或文件名推断厂站名。"""
    base = os.path.basename(input_path.rstrip("/\\"))
    # 如果是通用目录名（raw/data/input），往上一级取厂站名
    if base in ("raw", "data", "input", "materials", "source", ""):
        parent = os.path.dirname(input_path.rstrip("/\\"))
        base = os.path.basename(parent) or base
    # 去掉扩展名
    base = os.path.splitext(base)[0]
    return base


def main() -> None:
    parser = argparse.ArgumentParser(
        description="raw/ 目录 → wwtflow schema.py 草稿生成器（支持 CSV/MD/TXT/SVG/PDF）"
    )
    parser.add_argument(
        "input",
        help="输入路径：目录（自动扫描）或单个 CSV 文件",
    )
    parser.add_argument(
        "-o", "--output",
        default="",
        help="输出 schema.py 路径（默认自动写入 <厂站目录>/draft/<名称>_schema.py）",
    )
    parser.add_argument(
        "--plant",
        default="",
        help="厂站名称（默认从目录/文件名推断）",
    )
    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        print(f"错误：路径不存在：{input_path}", file=sys.stderr)
        sys.exit(1)

    plant_name = args.plant or _infer_plant_name(input_path)

    # 默认输出路径：<厂站目录>/draft/<safe_name>_schema.py
    if not args.output:
        input_abs = os.path.abspath(input_path)
        raw_dir = input_abs if os.path.isdir(input_abs) else os.path.dirname(input_abs)
        raw_base = os.path.basename(raw_dir.rstrip("/\\"))
        if raw_base in ("raw", "data", "input", "materials", "source", ""):
            plant_dir = os.path.dirname(raw_dir)
        else:
            plant_dir = raw_dir
        draft_dir = os.path.join(plant_dir, "draft")
        os.makedirs(draft_dir, exist_ok=True)
        safe_name = re.sub(r"[^\w]", "_", plant_name.lower())[:20].strip("_") or "plant"
        args.output = os.path.join(draft_dir, f"{safe_name}_schema.py")

    # 扫描文件
    files = scan_directory(input_path)

    # 没有 CSV 时生成空壳草稿
    if not files["csv"]:
        print("警告：未找到 CSV 文件，将生成空壳草稿（仅含文件清单和 TODO 占位）。", file=sys.stderr)
        txt_data = [parse_txt(p) for p in files["txt"]]
        code = generate_schema_no_csv(files, plant_name, txt_data)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"Generated (no-CSV shell): {args.output}")
            print(f"  TXT 文件: {len(files['txt'])}")
            print(f"  MD 文件:  {len(files['md'])}")
            print(f"  SVG/PDF:  {len(files['svg']) + len(files['pdf'])} 个（见草稿顶部注释）")
        else:
            print(code)
        return

    csv_path = files["csv"][0]
    if len(files["csv"]) > 1:
        print(f"警告：找到多个 CSV 文件，使用第一个：{os.path.basename(csv_path)}", file=sys.stderr)

    # 解析各类文件
    data = parse_csv(csv_path)
    md_data = [parse_md(p) for p in files["md"]]
    txt_data = [parse_txt(p) for p in files["txt"]]

    # 生成 schema 代码（分两步：先生成支流部分，再追加尾部）
    top_streams = [s for s in data["streams"] if not _is_lower_stream(s["name"])]
    stream_vars = [
        re.sub(r"[^\w]", "_", s["name"].lower())[:20].strip("_") or "stream"
        for s in top_streams
    ]

    partial_out = generate_schema(data, plant_name, files, md_data, txt_data)
    code = _finish_schema(partial_out, plant_name, stream_vars)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"Generated: {args.output}")
        print(f"  CSV 来源:      {os.path.basename(csv_path)}")
        print(f"  Top streams:   {len(top_streams)}")
        lower = [s for s in data["streams"] if _is_lower_stream(s["name"])]
        print(f"  Lower streams: {len(lower)}")
        print(f"  MD 文件:       {len(files['md'])}")
        print(f"  TXT 文件:      {len(files['txt'])}")
        print(f"  SVG/PDF:       {len(files['svg']) + len(files['pdf'])} 个（见草稿顶部注释）")
    else:
        print(code)


if __name__ == "__main__":
    main()
