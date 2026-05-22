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

    def __init__(self, schema: PlantSchema):
        self.schema = schema
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
           style_key: str = "", style: str = "") -> int:
        id_ = self._nid()
        style_str = style if style else self.STYLES.get(style_key, "")
        self.cells.append({
            "t": "v", "id": id_, "label": label,
            "x": round(x, 1), "y": round(y, 1),
            "w": round(w, 1), "h": round(h, 1),
            "style": style_str,
        })
        return id_

    def _e(self, src: int, tgt: int, label: str = "",
           exit_side: Optional[str] = None, entry_side: Optional[str] = None,
           points: Optional[List[Tuple[float, float]]] = None) -> int:
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
        })
        return id_

    # ------------------------------------------------------------------
    # 辅助布局方法
    # ------------------------------------------------------------------
    def _layout_reaction_group(self, x: float, y: float, width: float,
                               rg: ReactionGroup) -> Tuple[int, float]:
        """布局反应池组：参数框 → 格次标签 → 池体"""
        y0 = y
        if rg.specs:
            col_w = width / len(rg.labels)
            for spec in rg.specs:
                px = x + col_w * spec.start_col
                pw = col_w * (spec.end_col - spec.start_col + 1)
                self._v(spec.text, px, y0, pw, self.PRM_H, "PRM")
            y0 += self.PRM_H + self.GAP_PRM_TNK

        if rg.note:
            self._v(rg.note, x, y0, width, self.NOTE_H, "NOTE")
            y0 += self.NOTE_H + self.GAP_NOTE_TNK

        col_w = width / len(rg.labels)
        label_y = y0
        for i, label in enumerate(rg.labels):
            self._v(label, x + i * col_w, label_y, col_w, self.LAB_H, "BX")

        tank_y = label_y + self.LAB_H
        tank_id = self._v(rg.title, x, tank_y, width, self.TNK_H, "TNK")
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
                            st: SingleTank) -> Tuple[int, float]:
        y0 = y
        if st.prm_text:
            self._v(st.prm_text, x, y0, width, 28, "PRM")
            y0 += 28 + self.GAP_PRM_TNK
        if st.note_text:
            self._v(st.note_text, x, y0, width, self.NOTE_H, "NOTE")
            y0 += self.NOTE_H + self.GAP_NOTE_TNK
        tank_id = self._v(st.title, x, y0, width, self.TNK_H, "TNK")
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
        self._layout_streams()
        self._layout_combined()
        self._layout_bio()
        self._route_edges()
        self._auto_size_page()
        return LayoutResult(self.cells, self.page_w, self.page_h)

    # ------------------------------------------------------------------
    # 支流布局
    # ------------------------------------------------------------------
    def _layout_streams(self):
        margin_left, margin_top = self.schema.page_margin
        x = margin_left

        for stream in self.schema.streams:
            y = margin_top
            prev_id = None

            for unit in stream.units:
                y += unit.gap_before
                curr_id = None

                if unit.kind == "header":
                    text = f"{unit.data}（{stream.flow_rate}）"
                    curr_id = self._v(text, x, y, stream.width, self.HDR_H, "HDR")
                    y += self.HDR_H + 2

                elif unit.kind == "reaction_group":
                    rg = unit.data
                    tank_id, y = self._layout_reaction_group(x, y, stream.width, rg)
                    curr_id = tank_id
                    y += self.GAP_AFTER_TANK

                elif unit.kind == "single_tank":
                    st = unit.data
                    tank_id, y = self._layout_single_tank(x, y, stream.width, st)
                    curr_id = tank_id
                    y += self.GAP_AFTER_TANK

                elif unit.kind == "flow":
                    text = unit.data
                    fw = stream.width * 0.6
                    fx = x + (stream.width - fw) / 2
                    curr_id = self._v(text, fx, y, fw, self.FLOW_H, "FLOW")
                    y += self.FLOW_H + 18

                elif unit.kind == "note":
                    self._v(unit.data, x, y, stream.width, self.NOTE_H, "NOTE")
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

    # ------------------------------------------------------------------
    # 综合区布局（无 A4 约束：横向自由延伸，自然换行）
    # ------------------------------------------------------------------
    def _layout_combined(self):
        if not self.schema.combined:
            return

        cs = self.schema.combined
        margin_left, _ = self.schema.page_margin
        cx = margin_left

        # 综合区宽度 = 支流总宽（作为参考，不再严格限制）
        total_width = sum(s.width for s in self.schema.streams)
        total_width += self.schema.stream_gap * (len(self.schema.streams) - 1)

        max_bottom = max(info["bottom_y"] for info in self._stream_info)
        y = max_bottom + self.schema.section_gap

        # 标题（全宽）
        title = cs.title
        if cs.flow_rate:
            title = f"{title}（{cs.flow_rate}）"
        hdr_id = self._v(title, cx, y, total_width, self.HDR_H, "HDR")
        y += self.HDR_H + 8

        # 汇入说明
        prev_id = hdr_id
        if cs.header:
            flow_id = self._v(cs.header, cx, y, total_width, self.FLOW_H, "FLOW")
            self._e(prev_id, flow_id)
            y += self.FLOW_H + 8
            prev_id = flow_id

        # 调节池（全宽）
        if cs.adjuster:
            adj_id, y = self._layout_single_tank(cx, y, total_width, cs.adjuster)
            self._e(prev_id, adj_id)
            y += self.GAP_AFTER_TANK
            self._combined_top_id = adj_id
            prev_id = adj_id
        else:
            self._combined_top_id = prev_id

        # 处理单元行：横向自由排列，超出参考宽度时自然换行
        if not cs.rows:
            self._combined_bottom_id = prev_id
            return

        y += 10

        for row_idx, row in enumerate(cs.rows):
            # 计算每个单元的宽度
            def calc_unit_width(unit):
                if unit.width:
                    return unit.width
                if unit.kind == "reaction_group":
                    rg = unit.data
                    n_cols = len(rg.labels)
                    return max(cs.box_width, n_cols * self.MIN_COL_WIDTH)
                return cs.box_width

            col_widths = [calc_unit_width(u) for u in row]
            total_row_w = sum(col_widths) + (len(row) - 1) * cs.col_gap

            # 布局位置：左对齐，自然延伸
            xs = []
            curr_x = cx
            for w in col_widths:
                xs.append(curr_x)
                curr_x += w + cs.col_gap

            # 计算行高
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

            # 布局每个单元
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

                if unit.kind in ("reaction_group", "single_tank"):
                    uy = y
                else:
                    uy = y + (row_height - unit_h) / 2

                if unit.kind == "reaction_group":
                    uid, _ = self._layout_reaction_group(ux, uy, uw, unit.data)
                elif unit.kind == "single_tank":
                    uid, _ = self._layout_single_tank(ux, uy, uw, unit.data)
                elif unit.kind == "flow":
                    uid = self._v(unit.data, ux, uy, uw, self.FLOW_H, "FLOW")
                elif unit.kind == "note":
                    uid = self._v(unit.data, ux, uy, uw, self.NOTE_H, "NOTE")
                else:
                    uid = None

                if uid is not None:
                    row_ids.append(uid)

            # 行内顺序连接（统一左→右，不再折返）
            for i in range(len(row_ids) - 1):
                self._e(row_ids[i], row_ids[i + 1],
                        exit_side="right", entry_side="left")

            # 行间连接：上一行最后一个 → 本行第一个
            if prev_id is not None and row_ids:
                self._e(prev_id, row_ids[0],
                        exit_side="bottom", entry_side="top")

            if row_ids:
                prev_id = row_ids[-1]

            y += row_height + cs.row_gap

        self._combined_bottom_id = prev_id

    # ------------------------------------------------------------------
    # 生化区布局（无 A4 约束：横向自由延伸）
    # ------------------------------------------------------------------
    def _layout_bio(self):
        if not self.schema.bio:
            return

        bs = self.schema.bio
        margin_left, _ = self.schema.page_margin
        cx = margin_left

        # 生化区宽度不再绑定支流总宽
        y = self._combined_bottom_y() + self.schema.section_gap

        # 标题（宽度按主线内容计算）
        main_width = self._calc_bio_line_width(bs.main_line, bs.col_gap) if bs.main_line else 400
        self._bio_hdr_id = self._v(bs.title, cx, y, main_width, self.HDR_H, "HDR")
        y += self.HDR_H + 8

        # 主线层
        if bs.main_line:
            y = self._layout_bio_line(bs.main_line, cx, y, bs.col_gap)
            self._bio_main_bottom_id = self._last_bio_id

        # 回流支线（放在主线下方）
        if bs.recycle_line:
            y += bs.layer_gap
            y = self._layout_bio_line(bs.recycle_line, cx, y, bs.col_gap)
            self._bio_recycle_bottom_id = self._last_bio_id

        self._bio_bottom_y = y

    def _calc_bio_line_width(self, units: List[BioUnit], col_gap: int) -> float:
        """计算生化行自然宽度"""
        if not units:
            return 400
        col_widths = [u.width for u in units]
        return sum(col_widths) + (len(units) - 1) * col_gap

    def _layout_bio_line(self, units: List[BioUnit], cx: float, y: float,
                         col_gap: int) -> float:
        """布局生化区的一行，横向自由延伸"""
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
                uid, _ = self._layout_reaction_group(ux, y, uw, unit.data)
            elif unit.kind == "single_tank":
                uid, _ = self._layout_single_tank(ux, y, uw, unit.data)
            elif unit.kind == "flow":
                uid = self._v(unit.data, ux, y + (row_height - self.FLOW_H) / 2,
                              uw, self.FLOW_H, "FLOW")
            elif unit.kind == "note":
                uid = self._v(unit.data, ux, y + (row_height - self.NOTE_H) / 2,
                              uw, self.NOTE_H, "NOTE")
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
        # 支流 → 综合区（智能走线：侧边引出 → 水平移动 → 垂直下降）
        if self._combined_top_id is not None:
            target_x = self._combined_top_x()
            target_y = self._combined_top_y()

            for info in self._stream_info:
                sid = info["join_id"]
                sx = info["x"] + info["width"] / 2
                sy = info["bottom_y"]

                # 判断支流在综合区入口的左侧还是右侧
                if sx < target_x - 5:
                    # 支流在左侧：从右侧边引出，向右水平移动
                    exit_s = "right"
                    # 水平走到支流右边缘外一点
                    h1_x = info["x"] + info["width"] + 8
                    # 再水平走到目标正上方
                    points = [
                        (h1_x, sy + 8),
                        (h1_x, target_y - 20),
                        (target_x, target_y - 20),
                    ]
                elif sx > target_x + 5:
                    # 支流在右侧：从左侧边引出，向左水平移动
                    exit_s = "left"
                    h1_x = info["x"] - 8
                    points = [
                        (h1_x, sy + 8),
                        (h1_x, target_y - 20),
                        (target_x, target_y - 20),
                    ]
                else:
                    # 正上方：直接垂直向下
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
        self._e(src_id, tgt_id, edge.label,
                exit_side=edge.exit_side, entry_side=edge.entry_side,
                points=list(edge.waypoints) if edge.waypoints else None)

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
    # 页面尺寸自动计算（无 A4 约束）
    # ------------------------------------------------------------------
    def _auto_size_page(self):
        margin_right = 40
        margin_bottom = 60

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

        self.page_w = max_x + margin_right
        self.page_h = max_y + margin_bottom
