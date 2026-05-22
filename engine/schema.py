from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Literal


@dataclass
class ParamSpec:
    """参数框规格：对齐到哪些格次（0-based，闭区间）"""
    start_col: int
    end_col: int
    text: str


@dataclass
class ReactionGroup:
    """反应池组 = 参数框层 + 注释 + 池体层 + 格次标签层"""
    title: str
    labels: List[str]
    specs: Optional[List[ParamSpec]] = None
    note: Optional[str] = None


@dataclass
class SingleTank:
    """单池体（可附带参数框和注释）"""
    title: str
    prm_text: Optional[str] = None
    note_text: Optional[str] = None


@dataclass
class StreamUnit:
    """支流中的一个处理单元"""
    kind: Literal["header", "reaction_group", "single_tank", "flow", "note"]
    data: object  # str | ReactionGroup | SingleTank
    gap_before: int = 16


@dataclass
class Stream:
    """废水支流（纵向排列的一列处理单元）"""
    name: str
    flow_rate: str
    width: int = 220
    units: List[StreamUnit] = field(default_factory=list)


@dataclass
class CombinedUnit:
    """综合区中的一个单元"""
    kind: Literal["reaction_group", "single_tank", "flow", "note"]
    data: object  # ReactionGroup | SingleTank | str
    width: Optional[int] = None


@dataclass
class CombinedSection:
    """综合废水处理系统（蛇形布局）"""
    title: str
    flow_rate: Optional[str] = None
    header: Optional[str] = None
    adjuster: Optional[SingleTank] = None
    rows: List[List[CombinedUnit]] = field(default_factory=list)
    box_width: int = 175
    row_gap: int = 40
    col_gap: int = 18


@dataclass
class BioUnit:
    """生化处理单元"""
    kind: Literal["single_tank", "reaction_group", "note", "flow"]
    data: object  # SingleTank | ReactionGroup | str
    width: int = 220


@dataclass
class BioSection:
    """生化处理系统（主线 + 可选回流支线）"""
    title: str
    main_line: List[BioUnit] = field(default_factory=list)
    recycle_line: Optional[List[BioUnit]] = None
    layer_gap: int = 40
    col_gap: int = 12


@dataclass
class EdgeDef:
    """自定义连线（跨区域或特殊路由）"""
    source: str
    target: str
    label: str = ""
    exit_side: Optional[Literal["top", "bottom", "left", "right"]] = None
    entry_side: Optional[Literal["top", "bottom", "left", "right"]] = None
    waypoints: Optional[List[Tuple[float, float]]] = None


@dataclass
class PlantSchema:
    """厂站完整工艺描述"""
    name: str
    version: str = "2026"
    page_margin: Tuple[int, int] = (20, 30)
    stream_gap: int = 15
    section_gap: int = 40
    streams: List[Stream] = field(default_factory=list)
    combined: Optional[CombinedSection] = None
    bio: Optional[BioSection] = None
    custom_edges: List[EdgeDef] = field(default_factory=list)
