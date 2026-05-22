"""
示例厂站工艺流程图 — 预置 schema（脱敏演示数据）

展示完整布局：双支流 → 综合区（蛇形两行）→ 生化区（主线 + 污泥回流）

运行方式：
    python scripts/generate_from_data.py example/demo/draft/demo_schema.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine import (
    PlantSchema, Stream, StreamUnit, ReactionGroup, SingleTank,
    ParamSpec, CombinedSection, CombinedUnit, BioSection, BioUnit,
    EdgeDef, LayoutEngine, DrawioRenderer,
)

# ── 支流：酸性废水 ──────────────────────────────────────────────
acid = Stream(
    name="酸性废水",
    flow_rate="50m³/h",
    width=220,
    units=[
        StreamUnit("header", "酸性废水"),
        StreamUnit("single_tank", SingleTank("收集池")),
        StreamUnit("reaction_group", ReactionGroup(
            title="一级中和池",
            labels=["1池", "2池"],
            specs=[
                ParamSpec(0, 0, "石灰-pH=8.5~9"),
                ParamSpec(1, 1, "石灰-pH=8.5~9"),
            ]
        )),
        StreamUnit("single_tank", SingleTank("沉淀池", prm_text="PAM-10mg/L")),
    ]
)

# ── 支流：碱性废水 ──────────────────────────────────────────────
alkali = Stream(
    name="碱性废水",
    flow_rate="30m³/h",
    width=220,
    units=[
        StreamUnit("header", "碱性废水"),
        StreamUnit("single_tank", SingleTank("收集池")),
        StreamUnit("single_tank", SingleTank("调节池")),
        StreamUnit("single_tank", SingleTank("气浮池", prm_text="PAC-50mg/L")),
    ]
)

# ── 综合区（蛇形两行）──────────────────────────────────────────
combined = CombinedSection(
    title="综合废水处理系统",
    adjuster=SingleTank("综合调节池"),
    rows=[
        # 第一行：左 → 右
        [
            CombinedUnit("reaction_group", ReactionGroup(
                title="芬顿反应池",
                labels=["1池", "2池"],
                specs=[
                    ParamSpec(0, 0, "H₂O₂-100~200L/h"),
                    ParamSpec(1, 1, "FeSO₄-pH=3~4"),
                ]
            )),
            CombinedUnit("single_tank", SingleTank("芬顿沉淀池", prm_text="PAM-5mg/L")),
            CombinedUnit("single_tank", SingleTank("中间水池")),
        ],
        # 第二行：左 → 右（末→首连接形成蛇形折返）
        [
            CombinedUnit("single_tank", SingleTank("中和回调池", prm_text="石灰-pH=8~9")),
            CombinedUnit("single_tank", SingleTank("二沉池", prm_text="PAM-3mg/L")),
            CombinedUnit("single_tank", SingleTank("综合中间水池")),
        ],
    ],
    box_width=185,
)

# ── 生化区（主线 + 污泥回流）──────────────────────────────────
bio = BioSection(
    title="生化处理系统",
    main_line=[
        BioUnit("single_tank", SingleTank("生化调节池"), width=160),
        BioUnit("reaction_group", ReactionGroup(
            title="好氧池",
            labels=["1池", "2池", "3池"],
            specs=[
                ParamSpec(0, 1, "DO=2~4mg/L"),
                ParamSpec(2, 2, "DO=2~4mg/L"),
            ]
        ), width=280),
        BioUnit("single_tank", SingleTank("二沉池"), width=160),
        BioUnit("single_tank", SingleTank("达标排放"), width=140),
    ],
    recycle_line=[
        BioUnit("single_tank", SingleTank("污泥浓缩池"), width=180),
        BioUnit("single_tank", SingleTank("板框压滤机"), width=160),
        BioUnit("single_tank", SingleTank("泥饼外运"), width=140),
    ],
)

demo_schema = PlantSchema(
    name="示例厂站",
    version="2026",
    streams=[acid, alkali],
    combined=combined,
    bio=bio,
)

if __name__ == "__main__":
    engine = LayoutEngine(demo_schema)
    result = engine.layout()
    renderer = DrawioRenderer(
        result.cells, result.page_w, result.page_h,
        diagram_id="demo",
        diagram_name="示例厂站工艺流程图"
    )
    out_file = os.path.join(os.path.dirname(__file__), "demo.drawio")
    renderer.write(out_file)
    print(f"Generated: {out_file}")
