from typing import List, Dict, Any, Optional, Tuple
from .schema import (
    PlantSchema, Stream, StreamUnit, ReactionGroup, SingleTank,
    CombinedSection, CombinedUnit, BioSection, BioUnit, EdgeDef, ParamSpec
)


class LayoutResult:
    def __init__(self, cells: List[Dict[str, Any]], page_w: float, page_h: float):
        self.cells = cells
        self.page_w = page_w
        self.page_h = page_h


class LayoutEngine:
    """废水处理厂站工艺流程图通用布局引擎（无 A4 约束版）

    布局原则：
    - 各区域按内容自然展开，不强行压缩或折返
    - 页面尺寸由内容边界自动决定
    - 保持领域语义：支流→综合→生化的纵向分区不变
    """

    STYLES = {
        "BX":   "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;",
        "HDR":  "rounded=0;whiteSpace=wrap;html=1;fontSize=9;fontStyle=1;align=center;",
        "TNK":  "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;",
        "PRM":  "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#ffffff;strokeColor=#000000;",
        "NOTE": "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#fff2cc;strokeColor=#d6b656;",
        "FLOW": "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#dae8fc;strokeColor=#6c8ebf;",
    }

    # 默认尺寸常量
    HDR_H = 22
    TNK_H = 24
    LAB_H = 18
    PRM_H = 34
    NOTE_H = 22
    FLOW_H = 22
    GAP_UNIT = 16
    GAP_PRM_TNK = 12
    GAP_NOTE_TNK = 10
    GAP_AFTER_TANK = 16
    MIN_COL_WIDTH = 40
    DEFAULT_BOX_WIDTH = 175

    def __init__(self, schema: PlantSchema, styled: bool = False):
        self.schema = schema
        self.styled = styled
        self.cells: List[Dict[str, Any]] = []
        self._id = 1
        self.page_w = 1200
        self.page_h = 800

        self._stream_info: List[Dict] = []
        self._combined_top_id: Optional[int] = None
        self._combined_bottom_id: Optional[int] = None
        self._bio_bottom_y = 0.0

    # ------------------------------------------------------------------
    # 基础方法
    # ------------------------------------------------------------------
    def _nid(self) -> int:
        self._id += 1
        return self._id

    def _v(self, label: str, x: float, y: float, w: float, h: float,
           style_key: str = "", style: str = "", kind: str = "", stream_idx: int = -1) -> int:
        id_ = self._nid()
        style_str = style if style else self.STYLES.get(style_key, "")
        cell = {
            "t": "v", "id": id_, "label": label,
            "x": round(x, 1), "y": round(y, 1),
            "w": round(w, 1), "h": round(h, 1),
            "style": style_str,
            "style_key": style_key,
            "kind": kind,
            "stream_idx": stream_idx,
        }
        self.cells.append(cell)
        return id_

    def _e(self, src: int, tgt: int, label: str = "",
           exit_side: Optional[str] = None, entry_side: Optional[str] = None,
           points: Optional[List[Tuple[float, float]]] = None,
           edge_kind: str = "main") -> int:
        id_ = self._nid()
        style = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;fontSize=9;"
        if exit_side == "bottom":
            style += "exitX=0.5;exitY=1;exitDx=0;exitDy=0;"
        elif exit_side == "top":
            style += "exitX=0.5;exitY=0;exitDx=0;exitDy=0;"
        elif exit_side == "left":
            style += "exitX=0;exitY=0.5;exitDx=0;exitDy=0;"
        elif exit_side == "right":
            style += "exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
        if entry_side == "top":
            style += "entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
        elif entry_side == "bottom":
            style += "entryX=0.5;entryY=1;entryDx=0;entryDy=0;"
        elif entry_side == "left":
            style += "entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
        elif entry_side == "right":
            style += "entryX=1;entryY=0.5;entryDx=0;entryDy=0;"
        self.cells.append({
            "t": "e", "id": id_, "src": src, "tgt": tgt,
            "label": label, "style": style,
            "points": points or [],
            "edge_kind": edge_kind,
        })
        return id_

    # ------------------------------------------------------------------
    # 辅助布局方法
    # ------------------------------------------------------------------
    def _layout_reaction_group(self, x: float, y: float, width: float,
                               rg: ReactionGroup, kind: str = "reaction",
                               stream_idx: int = -1) -> Tuple[int, float]:
        """布局反应池组：参数框 → 格次标签 → 池体，并添加加药管线"""
        y0 = y
        param_ids = []  # 记录参数框 id，用于后续连加药管线
        if rg.specs:
            col_w = width / len(rg.labels)
            for spec in rg.specs:
                px = x + col_w * spec.start_col
                pw = col_w * (spec.end_col - spec.start_col + 1)
                pid = self._v(spec.text, px, y0, pw, self.PRM_H, "PRM", kind="param", stream_idx=stream_idx)
                param_ids.append({
                    "id": pid,
                    "start_col": spec.start_col,
                    "end_col": spec.end_col,
                    "x": px + pw / 2,  # 参数框中心 x
                    "y": y0 + self.PRM_H,  # 参数框底部 y
                })
            y0 += self.PRM_H + self.GAP_PRM_TNK

        if rg.note:
            self._v(rg.note, x, y0, width, self.NOTE_H, "NOTE", kind="note", stream_idx=stream_idx)
            y0 += self.NOTE_H + self.GAP_NOTE_TNK

        col_w = width / len(rg.labels)
        label_y = y0
        for i, label in enumerate(rg.labels):
            self._v(label, x + i * col_w, label_y, col_w, self.LAB_H, "BX", kind="label", stream_idx=stream_idx)

        tank_y = label_y + self.LAB_H
        tank_id = self._v(rg.title, x, tank_y, width, self.TNK_H, "TNK", kind=kind, stream_idx=stream_idx)

        # 添加加药管线：参数框 → 池体（绿色虚线）
        for p in param_ids:
            # 从参数框底部中心 → 池体顶部中心（垂直向下）
            self._e(p["id"], tank_id,
                    exit_side="bottom", entry_side="top",
                    edge_kind="chemical")

        y0 = tank_y + self.TNK_H
        return tank_id, y0

    def _calc_reaction_group_height(self, rg: ReactionGroup) -> float:
        h = 0
        if rg.specs:
            h += self.PRM_H + self.GAP_PRM_TNK
        if rg.note:
            h += self.NOTE_H + self.GAP_NOTE_TNK
        h += self.LAB_H + self.TNK_H
        return h

    def _layout_single_tank(self, x: float, y: float, width: float,
                            st: SingleTank, kind: str = "equalization",
                            stream_idx: int = -1) -> Tuple[int, float]:
        y0 = y
        param_id = None
        if st.prm_text:
            param_id = self._v(st.prm_text, x, y0, width, 28, "PRM", kind="param", stream_idx=stream_idx)
            y0 += 28 + self.GAP_PRM_TNK
        if st.note_text:
            self._v(st.note_text, x, y0, width, self.NOTE_H, "NOTE", kind="note", stream_idx=stream_idx)
            y0 += self.NOTE_H + self.GAP_NOTE_TNK
        tank_id = self._v(st.title, x, y0, width, self.TNK_H, "TNK", kind=kind, stream_idx=stream_idx)

        # 添加加药管线：参数框 → 池体
        if param_id is not None:
            self._e(param_id, tank_id,
                    exit_side="bottom", entry_side="top",
                    edge_kind="chemical")

        y0 += self.TNK_H
        return tank_id, y0

    def _calc_single_tank_height(self, st: SingleTank) -> float:
        h = 0
        if st.prm_text:
            h += 28 + self.GAP_PRM_TNK
        if st.note_text:
            h += self.NOTE_H + self.GAP_NOTE_TNK
        h += self.TNK_H
        return h

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def layout(self) -> LayoutResult:
        # 第1步：布局所有工艺流程内容
        self._layout_streams()
        self._layout_combined()
        self._layout_bio()
        self._route_edges()
        
        # 第2步：计算内容边界（不含图框）
        content_bounds = self._calc_content_bounds()
        
        # 第3步：添加图例（基于内容边界定位）
        self._add_legend(content_bounds)
        
        # 第4步：重新计算包含图例后的内容边界
        content_bounds = self._calc_content_bounds()
        
        # 第5步：添加自适应图框 + 标题栏
        self._add_title_block(content_bounds)
        
        # 第6步：最终页面尺寸 = 图框尺寸
        self._auto_size_page()
        return LayoutResult(self.cells, self.page_w, self.page_h)

    # ------------------------------------------------------------------
    # 支流布局
    # ------------------------------------------------------------------
    def _layout_streams(self):
        margin_left, margin_top = self.schema.page_margin
        x = margin_left

        for si, stream in enumerate(self.schema.streams):
            y = margin_top
            prev_id = None

            for unit in stream.units:
                y += unit.gap_before
                curr_id = None

                if unit.kind == "header":
                    text = f"{unit.data}（{stream.flow_rate}）"
                    curr_id = self._v(text, x, y, stream.width, self.HDR_H, "HDR", kind="header", stream_idx=si)
                    y += self.HDR_H + 2

                elif unit.kind == "reaction_group":
                    rg = unit.data
                    tank_id, y = self._layout_reaction_group(x, y, stream.width, rg, kind="reaction", stream_idx=si)
                    curr_id = tank_id
                    y += self.GAP_AFTER_TANK

                elif unit.kind == "single_tank":
                    st = unit.data
                    kind = self._infer_tank_kind(st.title)
                    tank_id, y = self._layout_single_tank(x, y, stream.width, st, kind=kind, stream_idx=si)
                    curr_id = tank_id
                    y += self.GAP_AFTER_TANK

                elif unit.kind == "flow":
                    text = unit.data
                    fw = stream.width * 0.6
                    fx = x + (stream.width - fw) / 2
                    curr_id = self._v(text, fx, y, fw, self.FLOW_H, "FLOW", kind="flow", stream_idx=si)
                    y += self.FLOW_H + 18

                elif unit.kind == "note":
                    self._v(unit.data, x, y, stream.width, self.NOTE_H, "NOTE", kind="note", stream_idx=si)
                    y += self.NOTE_H + 4

                if prev_id is not None and curr_id is not None:
                    self._e(prev_id, curr_id)
                if curr_id is not None:
                    prev_id = curr_id

            self._stream_info.append({
                "join_id": prev_id,
                "bottom_y": y,
                "x": x,
                "width": stream.width,
            })
            x += stream.width + self.schema.stream_gap

    def _infer_tank_kind(self, title: str) -> str:
        """根据池体名称推断构筑物类型"""
        t = title.lower()
        if any(k in t for k in ("调节", "均化", "集水")):
            return "equalization"
        if any(k in t for k in ("沉淀", "气浮", "澄清")):
            return "separation"
        if any(k in t for k in ("a1", "o1", "a2", "o2", "厌氧", "缺氧", "好氧", "生化")):
            return "bio"
        if any(k in t for k in ("反应", "加药")):
            return "reaction"
        return "equalization"

    # ------------------------------------------------------------------
    # 综合区布局
    # ------------------------------------------------------------------
    def _layout_combined(self):
        if not self.schema.combined:
            return

        cs = self.schema.combined
        margin_left, _ = self.schema.page_margin
        cx = margin_left

        total_width = sum(s.width for s in self.schema.streams)
        total_width += self.schema.stream_gap * (len(self.schema.streams) - 1)

        max_bottom = max(info["bottom_y"] for info in self._stream_info)
        y = max_bottom + self.schema.section_gap

        # 标题
        title = cs.title
        if cs.flow_rate:
            title = f"{title}（{cs.flow_rate}）"
        hdr_id = self._v(title, cx, y, total_width, self.HDR_H, "HDR", kind="header")
        y += self.HDR_H + 8

        # 汇入说明
        prev_id = hdr_id
        if cs.header:
            flow_id = self._v(cs.header, cx, y, total_width, self.FLOW_H, "FLOW", kind="flow")
            self._e(prev_id, flow_id)
            y += self.FLOW_H + 8
            prev_id = flow_id

        # 调节池
        if cs.adjuster:
            adj_id, y = self._layout_single_tank(cx, y, total_width, cs.adjuster, kind="equalization")
            self._e(prev_id, adj_id)
            y += self.GAP_AFTER_TANK
            self._combined_top_id = adj_id
            prev_id = adj_id
        else:
            self._combined_top_id = prev_id

        # 处理单元行
        if not cs.rows:
            self._combined_bottom_id = prev_id
            return

        y += 10

        for row_idx, row in enumerate(cs.rows):
            def calc_unit_width(unit):
                if unit.width:
                    return unit.width
                if unit.kind == "reaction_group":
                    rg = unit.data
                    n_cols = len(rg.labels)
                    return max(cs.box_width, n_cols * self.MIN_COL_WIDTH)
                return cs.box_width

            col_widths = [calc_unit_width(u) for u in row]

            xs = []
            curr_x = cx
            for w in col_widths:
                xs.append(curr_x)
                curr_x += w + cs.col_gap

            unit_heights = []
            for unit in row:
                if unit.kind == "reaction_group":
                    h = self._calc_reaction_group_height(unit.data)
                elif unit.kind == "single_tank":
                    h = self._calc_single_tank_height(unit.data)
                else:
                    h = self.FLOW_H
                unit_heights.append(h)
            row_height = max(unit_heights) if unit_heights else 80

            row_ids = []
            for i, unit in enumerate(row):
                ux = xs[i]
                uw = col_widths[i]

                if unit.kind == "reaction_group":
                    unit_h = self._calc_reaction_group_height(unit.data)
                elif unit.kind == "single_tank":
                    unit_h = self._calc_single_tank_height(unit.data)
                elif unit.kind == "flow":
                    unit_h = self.FLOW_H
                elif unit.kind == "note":
                    unit_h = self.NOTE_H
                else:
                    unit_h = row_height

                # 所有构筑物底部对齐：从行底部向上偏移
                if unit.kind in ("reaction_group", "single_tank"):
                    uy = y + (row_height - unit_h)
                else:
                    uy = y + (row_height - unit_h) / 2

                if unit.kind == "reaction_group":
                    uid, _ = self._layout_reaction_group(ux, uy, uw, unit.data, kind="reaction")
                elif unit.kind == "single_tank":
                    st = unit.data
                    kind = self._infer_tank_kind(st.title)
                    uid, _ = self._layout_single_tank(ux, uy, uw, st, kind=kind)
                elif unit.kind == "flow":
                    uid = self._v(unit.data, ux, uy, uw, self.FLOW_H, "FLOW", kind="flow")
                elif unit.kind == "note":
                    uid = self._v(unit.data, ux, uy, uw, self.NOTE_H, "NOTE", kind="note")
                else:
                    uid = None

                if uid is not None:
                    row_ids.append(uid)

            for i in range(len(row_ids) - 1):
                self._e(row_ids[i], row_ids[i + 1],
                        exit_side="right", entry_side="left")

            if prev_id is not None and row_ids:
                self._e(prev_id, row_ids[0],
                        exit_side="bottom", entry_side="top")

            if row_ids:
                prev_id = row_ids[-1]

            y += row_height + cs.row_gap

        self._combined_bottom_id = prev_id

    # ------------------------------------------------------------------
    # 生化区布局
    # ------------------------------------------------------------------
    def _layout_bio(self):
        if not self.schema.bio:
            return

        bs = self.schema.bio
        margin_left, _ = self.schema.page_margin
        cx = margin_left

        y = self._combined_bottom_y() + self.schema.section_gap

        main_width = self._calc_bio_line_width(bs.main_line, bs.col_gap) if bs.main_line else 400
        self._bio_hdr_id = self._v(bs.title, cx, y, main_width, self.HDR_H, "HDR", kind="header")
        y += self.HDR_H + 8

        if bs.main_line:
            y = self._layout_bio_line(bs.main_line, cx, y, bs.col_gap)
            self._bio_main_bottom_id = self._last_bio_id

        if bs.recycle_line:
            y += bs.layer_gap
            y = self._layout_bio_line(bs.recycle_line, cx, y, bs.col_gap)
            self._bio_recycle_bottom_id = self._last_bio_id

        self._bio_bottom_y = y

    def _calc_bio_line_width(self, units: List[BioUnit], col_gap: int) -> float:
        if not units:
            return 400
        col_widths = [u.width for u in units]
        return sum(col_widths) + (len(units) - 1) * col_gap

    def _layout_bio_line(self, units: List[BioUnit], cx: float, y: float,
                         col_gap: int) -> float:
        n = len(units)
        if n == 0:
            return y

        col_widths = [u.width for u in units]

        xs = []
        curr_x = cx
        for w in col_widths:
            xs.append(curr_x)
            curr_x += w + col_gap

        heights = []
        for unit in units:
            if unit.kind == "reaction_group":
                h = self._calc_reaction_group_height(unit.data)
            elif unit.kind == "single_tank":
                h = self._calc_single_tank_height(unit.data)
            else:
                h = self.FLOW_H
            heights.append(h)
        row_height = max(heights)

        line_ids = []
        for i, unit in enumerate(units):
            ux = xs[i]
            uw = col_widths[i]

            if unit.kind == "reaction_group":
                unit_h = self._calc_reaction_group_height(unit.data)
                uy = y + (row_height - unit_h)
                uid, _ = self._layout_reaction_group(ux, uy, uw, unit.data, kind="reaction")
            elif unit.kind == "single_tank":
                unit_h = self._calc_single_tank_height(unit.data)
                uy = y + (row_height - unit_h)
                st = unit.data
                kind = self._infer_tank_kind(st.title)
                uid, _ = self._layout_single_tank(ux, uy, uw, st, kind=kind)
            elif unit.kind == "flow":
                uid = self._v(unit.data, ux, y + (row_height - self.FLOW_H) / 2,
                              uw, self.FLOW_H, "FLOW", kind="flow")
            elif unit.kind == "note":
                uid = self._v(unit.data, ux, y + (row_height - self.NOTE_H) / 2,
                              uw, self.NOTE_H, "NOTE", kind="note")
            else:
                uid = None

            if uid is not None:
                line_ids.append(uid)

        for i in range(len(line_ids) - 1):
            self._e(line_ids[i], line_ids[i + 1],
                    exit_side="right", entry_side="left")

        if line_ids:
            self._last_bio_id = line_ids[-1]

        return y + row_height + self.GAP_AFTER_TANK

    # ------------------------------------------------------------------
    # 连线路由
    # ------------------------------------------------------------------
    def _route_edges(self):
        # 支流 → 综合区
        if self._combined_top_id is not None:
            target_x = self._combined_top_x()
            target_y = self._combined_top_y()

            for info in self._stream_info:
                sid = info["join_id"]
                sx = info["x"] + info["width"] / 2
                sy = info["bottom_y"]

                if sx < target_x - 5:
                    exit_s = "right"
                    h1_x = info["x"] + info["width"] + 8
                    points = [
                        (h1_x, sy + 8),
                        (h1_x, target_y - 20),
                        (target_x, target_y - 20),
                    ]
                elif sx > target_x + 5:
                    exit_s = "left"
                    h1_x = info["x"] - 8
                    points = [
                        (h1_x, sy + 8),
                        (h1_x, target_y - 20),
                        (target_x, target_y - 20),
                    ]
                else:
                    exit_s = "bottom"
                    points = [
                        (sx, sy + 10),
                        (target_x, target_y - 15),
                    ]

                self._e(sid, self._combined_top_id,
                        exit_side=exit_s, entry_side="top",
                        points=points)

        # 综合区 → 生化区标题
        if self._combined_bottom_id is not None and hasattr(self, '_bio_hdr_id'):
            self._e(self._combined_bottom_id, self._bio_hdr_id,
                    exit_side="bottom", entry_side="top")

        # 自定义连线
        for edge in self.schema.custom_edges:
            self._resolve_and_route_edge(edge)

    def _resolve_and_route_edge(self, edge: EdgeDef):
        src_id = self._find_cell_by_label(edge.source)
        tgt_id = self._find_cell_by_label(edge.target)
        if src_id is None or tgt_id is None:
            return
        # 根据标签判断管线类型
        edge_kind = "main"
        label = edge.label.lower() if edge.label else ""
        if any(k in label for k in ("污泥", "剩余污泥", "排泥")):
            edge_kind = "sludge"
        elif any(k in label for k in ("回流", "循环", "内回流")):
            edge_kind = "recycle"
        elif any(k in label for k in ("加药", "药剂", "投加")):
            edge_kind = "chemical"
        self._e(src_id, tgt_id, edge.label,
                exit_side=edge.exit_side, entry_side=edge.entry_side,
                points=list(edge.waypoints) if edge.waypoints else None,
                edge_kind=edge_kind)

    def _find_cell_by_label(self, label: str) -> Optional[int]:
        for cell in self.cells:
            if cell["t"] == "v" and cell["label"] == label:
                return cell["id"]
        return None

    def _combined_top_x(self) -> float:
        if self._combined_top_id is None:
            return 600
        for cell in self.cells:
            if cell["t"] == "v" and cell["id"] == self._combined_top_id:
                return cell["x"] + cell["w"] / 2
        return 600

    def _combined_top_y(self) -> float:
        if self._combined_top_id is None:
            return 400
        for cell in self.cells:
            if cell["t"] == "v" and cell["id"] == self._combined_top_id:
                return cell["y"]
        return 400

    def _combined_bottom_y(self) -> float:
        if not self.schema.combined:
            return 400
        if self._combined_bottom_id is not None:
            for cell in self.cells:
                if cell["t"] == "v" and cell["id"] == self._combined_bottom_id:
                    return cell["y"] + cell["h"]
        return 400

    # ------------------------------------------------------------------
    # 内容边界计算
    # ------------------------------------------------------------------
    def _calc_content_bounds(self) -> Dict[str, float]:
        """计算所有内容（节点+连线折点）的边界框，排除图框和标题栏外框"""
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for cell in self.cells:
            if cell["t"] == "v":
                # 排除图框/标题栏外框：无label、fillColor=none、大矩形
                style = cell.get("style", "")
                if (cell.get("label", "") == "" and 
                    "fillColor=none" in style and
                    (cell["w"] > 500 or cell["h"] > 300)):
                    continue
                min_x = min(min_x, cell["x"])
                min_y = min(min_y, cell["y"])
                max_x = max(max_x, cell["x"] + cell["w"])
                max_y = max(max_y, cell["y"] + cell["h"])
            elif cell["t"] == "e" and cell.get("points"):
                for px, py in cell["points"]:
                    min_x = min(min_x, px)
                    min_y = min(min_y, py)
                    max_x = max(max_x, px)
                    max_y = max(max_y, py)
        
        # 如果没有内容，返回默认值
        if min_x == float('inf'):
            return {"x": 0, "y": 0, "w": 800, "h": 600, "max_x": 800, "max_y": 600}
        
        return {
            "x": min_x,
            "y": min_y,
            "w": max_x - min_x,
            "h": max_y - min_y,
            "max_x": max_x,
            "max_y": max_y,
        }

    # ------------------------------------------------------------------
    # 图框 + 标题栏（A3 横向比例自适应）
    # ------------------------------------------------------------------
    def _add_title_block(self, bounds: Dict[str, float]):
        """添加 A3 横向比例自适应图框 + 工程图风格标题栏
        
        A3 横向比例：420 : 297 ≈ 1.41414
        
        逻辑：
        1. 计算所有内容（流程图+图例）的边界
        2. 内框 = 内容边界 + 固定边距
        3. 按 A3 比例调整内框（保持 420:297）
        4. 外框 = 内框 + 5mm 边距
        5. 平移所有内容到内框内部
        6. 绘制外框、内框、右下角标题栏
        """
        if not self.styled:
            return

        # A3 横向比例
        A3_RATIO = 420.0 / 297.0  # ≈ 1.41414
        
        # 像素/mm 换算
        PX_PER_MM = 3.78
        
        # 外框到内框的边距
        OUTER_PAD_MM = 5
        
        # 内框到内容的边距（mm）
        INNER_PAD_LEFT_MM = 20
        INNER_PAD_RIGHT_MM = 20
        INNER_PAD_TOP_MM = 15
        INNER_PAD_BOTTOM_MM = 40  # 给标题栏留空间

        # 标题栏尺寸（mm）
        TB_W_MM = 180
        TB_H_MM = 32
        
        # 转换为像素
        OUTER_PAD = OUTER_PAD_MM * PX_PER_MM
        INNER_PAD_LEFT = INNER_PAD_LEFT_MM * PX_PER_MM
        INNER_PAD_RIGHT = INNER_PAD_RIGHT_MM * PX_PER_MM
        INNER_PAD_TOP = INNER_PAD_TOP_MM * PX_PER_MM
        INNER_PAD_BOTTOM = INNER_PAD_BOTTOM_MM * PX_PER_MM
        TB_W = TB_W_MM * PX_PER_MM
        TB_H = TB_H_MM * PX_PER_MM

        # 内容边界（已排除图框）
        cx, cy = bounds["x"], bounds["y"]
        cw, ch = bounds["w"], bounds["h"]
        cmax_x, cmax_y = bounds["max_x"], bounds["max_y"]

        # 需要的内框尺寸 = 内容 + 边距
        needed_inner_w_mm = (cw / PX_PER_MM) + INNER_PAD_LEFT_MM + INNER_PAD_RIGHT_MM
        needed_inner_h_mm = (ch / PX_PER_MM) + INNER_PAD_TOP_MM + INNER_PAD_BOTTOM_MM
        
        # 按 A3 比例调整：保持比例，以需要较大的一边为准
        needed_ratio = needed_inner_w_mm / needed_inner_h_mm
        if needed_ratio > A3_RATIO:
            # 太宽，增加高度
            inner_h_mm = needed_inner_w_mm / A3_RATIO
            inner_w_mm = needed_inner_w_mm
        else:
            # 太高，增加宽度
            inner_w_mm = needed_inner_h_mm * A3_RATIO
            inner_h_mm = needed_inner_h_mm
        
        # 确保最小 A3 尺寸且能放下标题栏
        inner_w_mm = max(inner_w_mm, 420, (TB_W_MM / PX_PER_MM) + INNER_PAD_LEFT_MM + INNER_PAD_RIGHT_MM)
        inner_h_mm = max(inner_h_mm, 297, (TB_H_MM / PX_PER_MM) + INNER_PAD_TOP_MM + INNER_PAD_BOTTOM_MM)
        
        # 转像素
        inner_w = inner_w_mm * PX_PER_MM
        inner_h = inner_h_mm * PX_PER_MM
        
        # 外框
        outer_w = inner_w + OUTER_PAD * 2
        outer_h = inner_h + OUTER_PAD * 2
        
        # 内框起点
        inner_x = OUTER_PAD
        inner_y = OUTER_PAD
        
        # 内容偏移：移到内框内部（左上留白处）
        offset_x = inner_x + INNER_PAD_LEFT - cx
        offset_y = inner_y + INNER_PAD_TOP - cy
        
        # 平移所有内容
        for cell in self.cells:
            if cell["t"] == "v":
                cell["x"] += offset_x
                cell["y"] += offset_y
            elif cell["t"] == "e" and cell.get("points"):
                cell["points"] = [
                    (px + offset_x, py + offset_y)
                    for px, py in cell["points"]
                ]
        
        # === 收集图框 cells（外框+内框+标题栏），稍后插入到最前面 ===
        frame_cells = []
        
        # 外框
        frame_cells.append({
            "t": "v", "id": self._nid(), "label": "",
            "x": 0, "y": 0, "w": outer_w, "h": outer_h,
            "style": "rounded=0;whiteSpace=wrap;html=1;"
                     "fillColor=none;strokeColor=#000000;strokeWidth=1;",
        })
        
        # 内框
        frame_cells.append({
            "t": "v", "id": self._nid(), "label": "",
            "x": inner_x, "y": inner_y, "w": inner_w, "h": inner_h,
            "style": "rounded=0;whiteSpace=wrap;html=1;"
                     "fillColor=none;strokeColor=#000000;strokeWidth=2;",
        })
        
        # 标题栏
        frame_cells.extend(
            self._draw_title_block_v4(inner_x, inner_y, inner_w, inner_h)
        )
        
        # 把图框 cells 插入到最前面（最底层）
        self.cells = frame_cells + self.cells

    def _draw_title_block_v4(self, inner_x: float, inner_y: float, inner_w: float, inner_h: float) -> List[Dict]:
        """绘制右下角标题栏（4行结构）
        
        返回所有标题栏 cells 列表（由调用方插入到最底层）
        """
        from datetime import datetime
        date_str = datetime.now().strftime("%Y.%m.%d")
        
        cells = []
        
        # 标题栏位置（紧贴内框右下，不留间隙）
        tb_x = inner_x + inner_w - (180 * 3.78)
        tb_y = inner_y + inner_h - (32 * 3.78)
        tb_w = 180 * 3.78
        tb_h = 32 * 3.78
        
        # 标题栏外框
        cells.append({
            "t": "v", "id": self._nid(), "label": "",
            "x": tb_x, "y": tb_y, "w": tb_w, "h": tb_h,
            "style": "rounded=0;whiteSpace=wrap;html=1;"
                     "fillColor=none;strokeColor=#000000;strokeWidth=1;",
        })
        
        # 列宽分配（mm → px），最后一列自动调整填满
        cols_mm = [45, 45, 35, 24, 30]
        cols = [c * 3.78 for c in cols_mm]
        # 修正舍入误差，让总宽度等于标题栏宽度
        total_w = sum(cols)
        diff = tb_w - total_w
        if abs(diff) > 0.5:
            cols[-1] += diff  # 调整最后一列
        
        # 行高（4行均分）
        row_h = tb_h / 4
        
        # ===== 第1行：名称行（灰底）=====
        labels_r1 = ["公司", "项目", "图名", "图号", "日期"]
        cx_ = tb_x
        for label, cw_ in zip(labels_r1, cols):
            cells.append(self._tb_cell_dict(label, cx_, tb_y, cw_, row_h, is_label=True))
            cx_ += cw_
        
        # ===== 第2行：内容行（白底）=====
        values_r2 = ["××环保科技有限公司", "温州海城厂站", "废水处理工艺流程图", "HC-2026-001", date_str]
        cx_ = tb_x
        for val, cw_ in zip(values_r2, cols):
            cells.append(self._tb_cell_dict(val, cx_, tb_y + row_h, cw_, row_h, is_label=False))
            cx_ += cw_
        
        # ===== 第3行：名称行（灰底）=====
        labels_r3 = ["编制", "审核", "比例", "阶段", "页码"]
        cx_ = tb_x
        for label, cw_ in zip(labels_r3, cols):
            cells.append(self._tb_cell_dict(label, cx_, tb_y + row_h * 2, cw_, row_h, is_label=True))
            cx_ += cw_
        
        # ===== 第4行：内容行（白底）=====
        values_r4 = ["×××", "×××", "按实", "施工图", "1/1"]
        cx_ = tb_x
        for val, cw_ in zip(values_r4, cols):
            cells.append(self._tb_cell_dict(val, cx_, tb_y + row_h * 3, cw_, row_h, is_label=False))
            cx_ += cw_
        
        return cells

    def _tb_cell_dict(self, text: str, x: float, y: float, w: float, h: float,
                       is_label: bool = False, align: str = "center") -> Dict:
        """返回标题栏单元格字典（每个单元格自带黑色边框）"""
        if is_label:
            fill = "#E8E8E8"
            font_color = "#000000"
            font_style = "1"
        else:
            fill = "#FFFFFF"
            font_color = "#000000"
            font_style = "0"
        
        style = (f"rounded=0;whiteSpace=wrap;html=1;fontSize=12;"
                 f"align={align};verticalAlign=middle;"
                 f"fillColor={fill};strokeColor=#000000;strokeWidth=1;"
                 f"fontColor={font_color};fontStyle={font_style};")
        return {
            "t": "v", "id": self._nid(), "label": text,
            "x": x, "y": y, "w": w, "h": h,
            "style": style,
        }

    def _tb_cell(self, text: str, x: float, y: float, w: float, h: float, 
                 is_label: bool = False, align: str = "center"):
        """标题栏单元格（直接添加到 cells）"""
        cell = self._tb_cell_dict(text, x, y, w, h, is_label=is_label, align=align)
        self.cells.append(cell)

    def _hline_dict(self, x: float, y: float, w: float) -> Dict:
        """返回水平分隔线字典"""
        return {
            "t": "v", "id": self._nid(), "label": "",
            "x": x, "y": y, "w": w, "h": 1,
            "style": "rounded=0;whiteSpace=wrap;html=1;"
                     "fillColor=none;strokeColor=#000000;strokeWidth=1;",
        }

    def _vline_dict(self, x: float, y: float, h: float) -> Dict:
        """返回垂直分隔线字典"""
        return {
            "t": "v", "id": self._nid(), "label": "",
            "x": x, "y": y, "w": 1, "h": h,
            "style": "rounded=0;whiteSpace=wrap;html=1;"
                     "fillColor=none;strokeColor=#000000;strokeWidth=1;",
        }

    def _hline(self, x: float, y: float, w: float):
        """水平分隔线"""
        self.cells.append(self._hline_dict(x, y, w))

    def _vline(self, x: float, y: float, h: float):
        """垂直分隔线"""
        self.cells.append(self._vline_dict(x, y, h))

    def _title_cell(self, text: str, x: float, y: float, w: float, h: float, 
                    is_label: bool = False, align: str = "center"):
        """兼容旧代码"""
        self._tb_cell(text, x, y, w, h, is_label=is_label, align=align)

    # ------------------------------------------------------------------
    # 图例
    # ------------------------------------------------------------------
    def _add_legend(self, bounds: Dict[str, float]):
        """在支流右侧添加管线图例
        
        图例放在支流区域（stream_idx >= 0）的右侧，
        而不是整个内容最右侧（综合区/生化区可能更宽）
        """
        if not self.styled:
            return

        # 计算支流区域的边界（stream_idx >= 0 的 cells）
        stream_min_x = float('inf')
        stream_min_y = float('inf')
        stream_max_x = float('-inf')
        stream_max_y = float('-inf')
        
        has_stream = False
        for cell in self.cells:
            if cell["t"] == "v" and cell.get("stream_idx", -1) >= 0:
                has_stream = True
                stream_min_x = min(stream_min_x, cell["x"])
                stream_min_y = min(stream_min_y, cell["y"])
                stream_max_x = max(stream_max_x, cell["x"] + cell["w"])
                stream_max_y = max(stream_max_y, cell["y"] + cell["h"])
        
        if has_stream:
            # 图例放在支流区域右侧，留一定间距
            legend_x = stream_max_x + 280
            legend_y = stream_min_y + 20
        else:
            # 没有支流，放在内容右侧
            legend_x = bounds["max_x"] + 15
            legend_y = bounds["y"] + 30

        # 图例外框（白底黑框）
        self._v("", legend_x, legend_y, 130, 120,
                style="rounded=0;whiteSpace=wrap;html=1;"
                      "fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=1;")
        
        # 图例标题
        self._v("图例", legend_x, legend_y, 130, 22,
                style="rounded=0;whiteSpace=wrap;html=1;fontSize=11;"
                      "align=center;verticalAlign=middle;"
                      "fillColor=#E8E8E8;strokeColor=none;"
                      "fontColor=#000000;")
        
        # 图例项
        items_y = legend_y + 26
        self._legend_item(legend_x + 8, items_y, "主水管", "main")
        items_y += 24
        self._legend_item(legend_x + 8, items_y, "加药管", "chemical")
        items_y += 24
        self._legend_item(legend_x + 8, items_y, "污泥管", "sludge")
        items_y += 24
        self._legend_item(legend_x + 8, items_y, "回流管", "recycle")

    def _legend_item(self, x: float, y: float, label: str, edge_kind: str):
        """添加单个图例项：线段 + 文字（作为一个整体，通过 _add_legend 统一平移）"""
        if edge_kind == "main":
            line_style = "strokeColor=#000000;strokeWidth=1;endArrow=classic;endSize=6;"
        elif edge_kind == "chemical":
            line_style = "strokeColor=#82B366;strokeWidth=1;dashed=1;endArrow=classic;endSize=5;"
        elif edge_kind == "sludge":
            line_style = "strokeColor=#B85450;strokeWidth=1;dashed=1;endArrow=classic;endSize=6;"
        elif edge_kind == "recycle":
            line_style = "strokeColor=#9673A6;strokeWidth=1;dashed=1;endArrow=classic;endSize=6;"
        else:
            line_style = "strokeColor=#000000;strokeWidth=1;endArrow=classic;"

        # 线段（用 vertex 模拟线段样式）
        self._v("", x, y + 8, 36, 1, style=line_style)
        
        # 文字
        self._v(label, x + 44, y, 80, 18,
                style="rounded=0;whiteSpace=wrap;html=1;fontSize=11;"
                      "align=left;verticalAlign=middle;"
                      "fillColor=none;strokeColor=none;fontColor=#000000;")

    # ------------------------------------------------------------------
    # 页面尺寸自动计算
    # ------------------------------------------------------------------
    def _auto_size_page(self):
        """页面尺寸 = 图框尺寸（所有元素已包含在图框内）"""
        max_x = 0
        max_y = 0

        for cell in self.cells:
            if cell["t"] == "v":
                max_x = max(max_x, cell["x"] + cell["w"])
                max_y = max(max_y, cell["y"] + cell["h"])
            elif cell["t"] == "e" and cell.get("points"):
                for px, py in cell["points"]:
                    max_x = max(max_x, px)
                    max_y = max(max_y, py)

        self.page_w = max_x + 20  # 右边留少量空白
        self.page_h = max_y + 20  # 下边留少量空白
