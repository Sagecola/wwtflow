# wwtflow

废水处理厂站工艺流程图自动生成工具。输入原始资料（CSV / MD / TXT / SVG / PDF），输出可在 draw.io 中打开并人工微调的 `.drawio` 流程图。

## 特性

- **多格式输入**：CSV 评价体系表为主数据源，MD / TXT 补充工艺说明，SVG / PDF 列入清单供 AI 参考
- **三层架构**：Schema → Layout → Render，逻辑分离，易于扩展新厂站类型
- **AI 协作友好**：附带 `CLAUDE.md` / `AGENTS.md`，规范 AI agent 的生成行为和样式约定
- **draft/ 约定**：AI 输出统一进 `draft/` 子目录，人工调整版保留在厂站根目录

## 依赖

Python 3.9+，安装 drawpyo：

```bash
pip install drawpyo
```

## 快速上手

### 方式一：从原始资料生成

```bash
# 1. 把 CSV / MD / TXT 等文件放入 raw/ 目录
mkdir -p 新厂站/raw
cp 你的评价体系.csv 新厂站/raw/

# 2. 解析原始资料，生成 schema 草稿
python scripts/import_raw.py 新厂站/raw/
# → 自动输出到 新厂站/draft/<名称>_schema.py

# 3. （可选）用 AI 补全综合区 / 生化区 / 支流连线
# 参考 CLAUDE.md 或 AGENTS.md 中的规范

# 4. 生成流程图
python scripts/generate_from_data.py 新厂站/draft/<名称>_schema.py
# → 自动输出到同目录下的 .drawio 文件
```

### 方式二：直接运行示例

```bash
python scripts/generate_from_data.py example/demo/draft/demo_schema.py
# → 输出 example/demo/draft/demo.drawio
```

用 [draw.io](https://app.diagrams.net/) 打开生成的 `.drawio` 文件，人工微调后导出 PDF。

## 目录结构

```
wwtflow/
├── engine/
│   ├── schema.py            ← 领域模型（PlantSchema, Stream, ReactionGroup…）
│   ├── layout_engine.py     ← 布局引擎
│   └── renderer.py          ← draw.io XML 渲染器
├── scripts/
│   ├── import_raw.py        ← 原始资料 → schema 草稿
│   ├── generate_from_data.py← schema → .drawio
│   └── scale_to_a4.py       ← A4 横向缩放工具
├── example/
│   └── demo/
│       ├── raw/             ← 放原始资料
│       └── draft/
│           └── demo_schema.py ← 预置示例 schema
├── CLAUDE.md                ← Claude Code 协作规范
├── AGENTS.md                ← AI Agent 协作规范
└── .gitignore
```

每个厂站目录的约定：

```
{厂站名}/
├── raw/           ← 原始输入文件（CSV / MD / TXT / SVG / PDF）
├── draft/         ← AI 生成的 schema.py 和 .drawio 草稿
└── {厂站名}_工艺流程_{年份}.drawio  ← 最终人工调整版
```

## AI 协作

项目内置两份 AI 规范文档：

- `CLAUDE.md`：供 [Claude Code](https://claude.ai/code) 使用
- `AGENTS.md`：供其他 AI agent（Cursor、Copilot 等）使用

规范涵盖样式常量、布局约定、draft/ 目录规则、raw/ 文件处理优先级。

## License

MIT
