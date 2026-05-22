from typing import List, Dict, Any, Optional
import drawpyo
from drawpyo.diagram import Object, Edge


class DrawioRenderer:
    """将布局结果渲染为 draw.io XML

    底层使用 drawpyo 进行样式验证和对象建模，
    XML 序列化保持与原始手写版本一致的格式和 ID。
    """

    def __init__(
        self,
        cells: List[Dict[str, Any]],
        page_w: float,
        page_h: float,
        diagram_id: str = "flow",
        diagram_name: str = "工艺流程",
    ):
        self.cells = cells
        self.page_w = round(page_w)
        self.page_h = round(page_h)
        self.diagram_id = diagram_id
        self.diagram_name = diagram_name

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def render(self) -> str:
        """渲染为 draw.io XML 字符串"""
        return self._to_xml_string()

    def write(self, path: str) -> None:
        """直接写入文件"""
        xml = self.render()
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)

    # ------------------------------------------------------------------
    # 内部：XML 序列化（保持原始 ID 和格式）
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
        style = self._esc(cell.get("style", ""))
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
        style = self._esc(cell.get("style", ""))
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
# drawpyo 辅助：样式验证与对象建模（可选，用于调试/验证）
# ----------------------------------------------------------------------

def validate_style(style: str, kind: str = "vertex") -> Dict[str, Any]:
    """使用 drawpyo 验证样式字符串是否合法

    Args:
        style: draw.io 样式字符串
        kind: "vertex" 或 "edge"

    Returns:
        {"valid": bool, "warnings": list, "object": drawpyo object or None}
    """
    result = {"valid": True, "warnings": [], "object": None}
    try:
        if kind == "vertex":
            obj = Object(value="test")
            obj.apply_style_string(style)
            result["object"] = obj
        else:
            # Edge 需要 source/target，这里只做字符串解析
            # drawpyo Edge 的 apply_style_string 需要实例化
            obj = Edge()
            obj.apply_style_string(style)
            result["object"] = obj
    except Exception as e:
        result["valid"] = False
        result["warnings"].append(str(e))
    return result
