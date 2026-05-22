# wwtflow — 厂站工艺流程图生成项目

## 项目说明

本项目用于为各废水处理厂站生成工艺流程图，输出格式为 draw.io（`.drawio`）。

后续 AI 执行时，默认应直接读取本文件和 `AGENTS.md` 作为主要规范来源；除非版式细节拿不准，否则不要依赖历史对话。最多只把温州后京最终成品作为版式参照。

`CLAUDE.md` 与 `AGENTS.md` 当前应保持内容基本一致。保留两份文件的目的主要是兼容不同 AI/代理入口：有的默认优先读 `AGENTS.md`，有的优先读 `CLAUDE.md`。后续更新规范时，默认两份同步修改，不要只改其中一份。

已完成厂站：
- 温州桥头绿安厂站（24年原版 + 2026年改动版）
- 温州后京厂站（2026年完整版）
- 温州海城厂站（2026年完整版）

---

## 工作流程

### 新厂站标准流程

1. 用户提供厂站 raw/ 目录（可包含 CSV、MD、TXT、SVG、PDF 等任意格式）
2. **先运行导入脚本**，自动解析 raw/ 目录并生成 schema 草稿：
   ```bash
   python scripts/import_raw.py <厂站目录/raw>   # 自动输出到 <厂站目录>/draft/
   ```
   - 有 CSV：自动解析支流结构和药剂参数
   - 有 MD：提取工艺流程链和药剂信息，嵌入草稿注释
   - 有 TXT：提取改动说明，嵌入草稿注释
   - 有 SVG/PDF：列入清单，提示 AI 参考
3. **AI 读取草稿和 raw/ 下所有文件**，补全综合区（CombinedSection）、生化区（BioSection）、支流汇入连线（custom_edges），核对参数框文字
4. 运行生成脚本，验证 XML 合法性：
   ```bash
   python scripts/generate_from_data.py <厂站目录>/draft/<schema.py>   # 自动输出到同目录
   ```
5. 字号统一为 9px，主标题 9px+粗体
6. 最终文件交给用户，在 draw.io 打开并人工微调后导出 PDF

### raw/ 目录处理规则

| 格式 | 处理方式 |
|------|---------|
| CSV（评价体系表） | 主数据源，自动解析支流/池体/药剂结构 |
| MD（工艺说明） | 提取 `→` 流程链和表格，作为注释嵌入草稿 |
| TXT（改动说明） | 提取改动表格，作为注释嵌入草稿顶部 |
| SVG/PDF（流程图） | 不自动解析，AI 生成时必须主动读取参考 |
| 旧版 `.drawio` | AI 直接读取，作为版式参照 |

当模板与 raw/ 目录内容冲突时，优先以 raw/ 目录和用户最新口头说明为准。

---

## 输出规范

| 项目 | 规范 |
|------|------|
| 页面尺寸 | 由内容自然展开自动计算，不强行压缩 |
| 正文字号 | `fontSize=9` |
| 主标题字号 | `fontSize=9; fontStyle=1`（粗体） |
| 参数框背景 | `fillColor=#ffffff; strokeColor=#000000` |
| 编码 | UTF-8，带 `<?xml version="1.0" encoding="UTF-8"?>` 声明 |

---

## 核心架构

```
输入：PlantSchema（结构化工艺数据）
   ↓
布局引擎：LayoutEngine（engine/layout_engine.py）
   ├─ 支流纵向布局
   ├─ 综合区横向自由延伸（无蛇形折返）
   ├─ 生化区横向自由延伸
   └─ 智能走线：支流→综合区从侧边引出，避免穿越
   ↓
渲染器：DrawioRenderer（engine/renderer.py）
   ↓
输出：.drawio XML 文件
```

### 引擎模块

| 文件 | 职责 |
|------|------|
| `engine/schema.py` | 领域模型：Stream、ReactionGroup、CombinedSection、BioSection 等 |
| `engine/layout_engine.py` | 布局引擎：根据 Schema 计算所有节点坐标和连线路由 |
| `engine/renderer.py` | XML 渲染器：将布局结果序列化为 draw.io XML |

### 使用方式

```python
from engine import LayoutEngine, DrawioRenderer
from 厂站目录.schema文件 import plant_schema

engine = LayoutEngine(plant_schema)
result = engine.layout()

renderer = DrawioRenderer(result.cells, result.page_w, result.page_h)
renderer.write("输出.drawio")
```

---

## 样式常量

```python
BX  = "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;"           # 普通格子
HDR = "rounded=0;whiteSpace=wrap;html=1;fontSize=9;fontStyle=1;align=center;" # 粗体主标题
TNK = "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;" # 池/罐
PRM = "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#ffffff;strokeColor=#000000;" # 参数框
NOTE= "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#fff2cc;strokeColor=#d6b656;" # 黄色注释
FLOW= "rounded=0;whiteSpace=wrap;html=1;fontSize=9;align=center;fillColor=#dae8fc;strokeColor=#6c8ebf;" # 流程节点
```

---

## 典型布局参考

### 顶部多支流

每支流纵向顺序：
```
主标题(HDR) → 进水/调节池(TNK) → 参数框(PRM) → 格次标签(grids)
→ 反应池组/池体(TNK) → 参数框(PRM) → 格次标签 → 下一级池体
→ 汇入综合调节池
```

### 后京版式偏好（后续新厂站优先按此生成）

1. 反应池组的表达要拆成三层：
   参数框（写药剂、控制参数、流量或备注） → 格次标签（1池/2池/3池...） → 池体（一级反应池组等）。

2. 池体与格次标签要贴合：
   池体在上，格次标签紧贴池体下边；不要把格次标签单独悬空放在上方。

3. 参数框不要贴住池体：
   参数框与池体/气浮池/沉淀池之间要留出明显空隙，默认预留给箭头和短连线，不要只剩箭头头部。

4. 参数框优先对应具体格次：
   如果药剂只投在 1池、4池、6池，就拆成多个小参数框，分别对齐对应格次；不要合成一个"大说明框"。

5. 综合废水段横向自由延伸：
   不要一整段自上而下拉很长。横向排一行，自然延伸不折返，页面宽度由内容决定。

6. 主流程与回流支线要分层：
   主流程走最直观的一条线；回流、旁路、应急支线单独留侧边或下一行，不要和主线混在同一条走廊里。

7. 药剂文案写法要短：
   优先写成"药剂名 + 核心控制值/作用"，例如 `石灰-pH=11`、`次钠-ORP`、`双氧水-100~200L/h`，避免整段口语说明。

8. 进水预投和特殊前置投药要单独画：
   例如"集水井双氧水预投""池前管道加 PAM"这类，单独成框，不要并进后续反应池组说明里。

9. 线段长度要看得见：
   节点之间至少留出一小段可见连线，不允许大面积出现"只有箭头、几乎无线段"的情况。

10. 走线避免穿越：
    支流汇入综合区时，从方框侧边（左/右）水平引出，再垂直下降，不要直接垂直向下穿越其他支流区域。

---

## A4 缩放脚本（scripts/scale_to_a4.py）

如需导出 A4 横向 PDF，先生成后运行缩放脚本：

```bash
python scripts/scale_to_a4.py <输入.drawio> <输出_A4横向.drawio>
```

脚本逻辑：
1. 扫描所有 mxGeometry 找内容边界
2. 计算 `fit_scale = min((1123-30)/content_w, (794-30)/content_h)`
3. 若 `fit_scale >= MIN_SCALE(0.76)`，缩放内容并放入真实 A4 页面
4. 若 `fit_scale < MIN_SCALE`，等比放大页面，保持 `1123:794` 比例，确保内容可读性
5. 变换所有节点坐标、边折点坐标

---

## 目录结构

```
drawio/
├── AGENTS.md                          ← 与 CLAUDE.md 保持同步
├── CLAUDE.md                          ← 本文件（根目录必须）
├── engine/                            ← 核心布局引擎
│   ├── __init__.py
│   ├── schema.py                      ← 领域模型
│   ├── layout_engine.py               ← 布局引擎
│   └── renderer.py                    ← XML 渲染器
├── scripts/
│   └── scale_to_a4.py                 ← 通用 A4 缩放工具
└── {厂站名}/                          ← 每个厂站一个文件夹
    ├── raw/                           ← 原始输入文件放入此子目录
    │   ├── 工艺流程图.pdf / .svg
    │   ├── 药剂点位.csv / .xlsx
    │   ├── 说明.md / .txt
    │   └── 其他辅助资料
    ├── draft/                         ← AI 生成的所有文件（schema.py、.drawio 草稿）
    │   ├── {名称}_schema.py           ← import_raw.py 自动生成的 schema 草稿
    │   └── {名称}.drawio              ← generate_from_data.py 自动生成的流程图草稿
    ├── {厂站名}_工艺流程_{年份}.drawio ← 最终人工调整版（根目录）
    ├── {厂站名}_工艺流程_{年份}.drawio.html  ← draw.io 导出（可选保留）
    └── {厂站名}_工艺流程_{年份}.pdf          ← draw.io 导出（可选保留）
```

---

## 注意事项

- 若厂站 raw/ 目录下有文件，必须优先结合这些文件理解工艺，再补足缺项
- raw/ 常见形式包括：`csv`、`xlsx`、`pdf`、`svg`、`md`、`txt`、旧版 `.drawio`、导出的 `.html`、截图等
- 当 raw/ 内容与其他来源冲突时，优先以 raw/ 和用户最新口头说明为准；必要时在输出中标记推断项
- draw.io XML 必须 UTF-8 编码，不加 BOM
- 所有文字用 `&#xa;` 换行（XML 内），不用 `\n`
- HTML 内容用 `html=1` 样式时，`<` `>` `&` 用 HTML 实体转义
- 每次生成后运行 `python -c "import xml.etree.ElementTree as ET; ET.parse('文件名')"` 验证 XML 合法性
- 生成时先保留全部连接线；若用户后续准备手工重连，可再统一删除 edge 节点
