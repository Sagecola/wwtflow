from typing import List, Dict, Any, Optional
import drawpyo
from drawpyo.diagram import Object, Edge


class DrawioRenderer:
    """将布局结果渲染为 draw.io XML

    支持两种模式：
    - 经典模式（默认）：白底黑框工程风
    - 样式模式（styled=True）：黑白工程图纸风格 + 加药/污泥管线

    样式规范（统一字号 12px，全部不加粗，框线 1px）：
    - 字体：中文微软雅黑，英文 Times New Roman
    - 主工艺池体：圆角矩形，白底，黑框 1pt，黑字 12px
    - 参数框：白底，黑框 1pt，黑字 12px
    - 标题：深灰底 #4A4A4A，白字 12px
    - 进出水节点：白底，黑框 1pt，黑字 12px
    - 主水管：黑色实线 1.5pt，实心三角箭头
    - 加药管：绿色 #82B366 虚线 1pt，小箭头
    - 污泥管：棕色 #B85450 虚线 1.5pt，实心三角箭头
    - 回流管：紫色 #9673A6 虚线 1pt，双向箭头
    """

    # ------------------------------------------------------------------
    # 经典样式
    # ------------------------------------------------------------------
    CLASSIC_STYLES = {
        "BX":   "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;",
        "HDR":  "rounded=0;whiteSpace=wrap;html=1;fontSize=9;fontStyle=1;align=center;",
        "TNK":  "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;",
        "PRM":  "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#ffffff;strokeColor=#000000;",
        "NOTE": "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#fff2cc;strokeColor=#d6b656;",
        "FLOW": "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#dae8fc;strokeColor=#6c8ebf;",
    }

    # ------------------------------------------------------------------
    # 样式模式：统一 12px，全部不加粗，框线 1px
    # ------------------------------------------------------------------
    TYPE_STYLES = {
        "tank": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 4, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "equalization": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 4, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "reaction": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 4, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "separation": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 4, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "bio": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 4, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "flow": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 4, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "param": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 2, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "note": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 0, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "header": {
            "fill": "#FFF2CC", "stroke": "#D6B656", "text": "#000000",
            "fontSize": 12, "rounded": 2, "fontStyle": 0,
            "strokeWidth": 1,
        },
        "label": {
            "fill": "#FFFFFF", "stroke": "#000000", "text": "#000000",
            "fontSize": 12, "rounded": 0, "fontStyle": 0,
            "strokeWidth": 1,
        },
    }

    # 字体：默认 Helvetica（draw.io 默认），不指定 fontFamily

    def __init__(
        self,
        cells: List[Dict[str, Any]],
        page_w: float,
        page_h: float,
        diagram_id: str = "flow",
        diagram_name: str = "工艺流程",
        styled: bool = False,
    ):
        self.cells = cells
        self.page_w = round(page_w)
        self.page_h = round(page_h)
        self.diagram_id = diagram_id
        self.diagram_name = diagram_name
        self.styled = styled
        self._styles = self.CLASSIC_STYLES.copy()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def render(self) -> str:
        return self._to_xml_string()

    def write(self, path: str) -> None:
        xml = self.render()
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)

    # ------------------------------------------------------------------
    # 内部：XML 序列化
    # ------------------------------------------------------------------
    def _to_xml_string(self) -> str:
        lines = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<mxfile host="app.diagrams.net" version="21.0.0">')
        lines.append(
            f'  <diagram id="{self._esc(self.diagram_id)}" '
            f'name="{self._esc(self.diagram_name)}">'
        )
        lines.append(
            f'    <mxGraphModel dx="1800" dy="1200" grid="0" gridSize="10" '
            f'guides="1" tooltips="1" connect="1" arrows="1" fold="1" '
            f'page="0" pageScale="1" pageWidth="{self.page_w}" '
            f'pageHeight="{self.page_h}" math="0" shadow="0">'
        )
        lines.append("      <root>")
        lines.append('        <mxCell id="0" />')
        lines.append('        <mxCell id="1" parent="0" />')

        for cell in self.cells:
            if cell["t"] == "v":
                lines.extend(self._render_vertex(cell))
            else:
                lines.extend(self._render_edge(cell))

        lines.append("      </root>")
        lines.append("    </mxGraphModel>")
        lines.append("  </diagram>")
        lines.append("</mxfile>")
        return "\n".join(lines)

    def _render_vertex(self, cell: Dict[str, Any]) -> List[str]:
        label = self._esc(cell.get("label", ""))
        style = self._build_style(cell)
        lines = [
            f'        <mxCell id="{cell["id"]}" value="{label}" '
            f'style="{style}" vertex="1" parent="1">'
        ]
        lines.append(
            f'          <mxGeometry x="{cell["x"]}" y="{cell["y"]}" '
            f'width="{cell["w"]}" height="{cell["h"]}" as="geometry" />'
        )
        lines.append("        </mxCell>")
        return lines

    def _render_edge(self, cell: Dict[str, Any]) -> List[str]:
        label = self._esc(cell.get("label", ""))
        style = self._build_edge_style(cell)
        lines = [
            f'        <mxCell id="{cell["id"]}" value="{label}" '
            f'style="{style}" edge="1" '
            f'source="{cell["src"]}" target="{cell["tgt"]}" parent="1">'
        ]
        lines.append('          <mxGeometry relative="1" as="geometry">')
        points = cell.get("points", [])
        if points:
            lines.append('            <Array as="points">')
            for px, py in points:
                lines.append(f'              <mxPoint x="{px}" y="{py}" />')
            lines.append("            </Array>")
        lines.append("          </mxGeometry>")
        lines.append("        </mxCell>")
        return lines

    # ------------------------------------------------------------------
    # 样式构建
    # ------------------------------------------------------------------
    def _build_style(self, cell: Dict[str, Any]) -> str:
        if not self.styled:
            return self._esc(cell.get("style", ""))

        kind = cell.get("kind", "")
        style_key = cell.get("style_key", "")

        if style_key == "BX":
            s = self.TYPE_STYLES["label"]
            return self._make_style(s)

        if style_key == "HDR" or kind == "header":
            s = self.TYPE_STYLES["header"]
            return self._make_style(s)

        if style_key == "PRM" or kind == "param":
            s = self.TYPE_STYLES["param"]
            return self._make_style(s)

        if style_key == "NOTE" or kind == "note":
            s = self.TYPE_STYLES["note"]
            return self._make_style(s)

        if style_key == "FLOW" or kind == "flow":
            s = self.TYPE_STYLES["flow"]
            return self._make_style(s)

        if kind in ("equalization", "reaction", "separation", "bio", "tank"):
            s = self.TYPE_STYLES["tank"]
            return self._make_style(s)

        return self._esc(cell.get("style", ""))

    def _make_style(self, s: Dict[str, Any]) -> str:
        parts = [
            f"rounded={s.get('rounded', 0)}",
            "whiteSpace=wrap",
            "html=1",
            f"fontSize={s.get('fontSize', 12)}",
            "align=center",
            f"fillColor={s['fill']}",
            f"strokeColor={s['stroke']}",
            f"fontColor={s['text']}",
        ]
        if s.get("strokeWidth"):
            parts.append(f"strokeWidth={s['strokeWidth']}")
        return self._esc(";".join(parts) + ";")

    def _build_edge_style(self, cell: Dict[str, Any]) -> str:
        base = cell.get("style", "")
        if not self.styled:
            return self._esc(base)

        parts = [base]
        edge_kind = cell.get("edge_kind", "main")

        if edge_kind == "chemical":
            # 加药管：绿色虚线 1pt，小箭头
            parts.append("strokeColor=#82B366")
            parts.append("strokeWidth=1")
            parts.append("dashed=1")
            parts.append("endArrow=classic")
            parts.append("endSize=5")
            parts.append("startArrow=none")
        elif edge_kind == "sludge":
            # 污泥管：棕色虚线 1pt，实心三角箭头
            parts.append("strokeColor=#B85450")
            parts.append("strokeWidth=1")
            parts.append("dashed=1")
            parts.append("endArrow=classic")
            parts.append("endSize=6")
            parts.append("startArrow=none")
        elif edge_kind == "recycle":
            # 回流管：紫色虚线 1pt，单向箭头（逆向）
            parts.append("strokeColor=#9673A6")
            parts.append("strokeWidth=1")
            parts.append("dashed=1")
            parts.append("endArrow=classic")
            parts.append("startArrow=none")
            parts.append("endSize=6")
        else:
            # 主水管：黑色实线 1pt
            parts.append("strokeColor=#000000")
            parts.append("strokeWidth=1")
            parts.append("endArrow=classic")
            parts.append("endSize=6")
            parts.append("startArrow=none")

        return self._esc(";".join(parts) + ";")

    @staticmethod
    def _esc(text: str) -> str:
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "&#xa;")
        )


# ----------------------------------------------------------------------
# drawpyo 辅助
# ----------------------------------------------------------------------

def validate_style(style: str, kind: str = "vertex") -> Dict[str, Any]:
    result = {"valid": True, "warnings": [], "object": None}
    try:
        if kind == "vertex":
            obj = Object(value="test")
            obj.apply_style_string(style)
            result["object"] = obj
        else:
            obj = Edge()
            obj.apply_style_string(style)
            result["object"] = obj
    except Exception as e:
        result["valid"] = False
        result["warnings"].append(str(e))
    return result
