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
5. 最终文件交给用户，在 draw.io 打开并人工微调后导出 PDF

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

### 样式模式（默认）

生成脚本默认使用**工程图样式模式**（黑白工程图纸风格），包含 A3 比例图框、标题栏、管线图例。

| 项目 | 规范 |
|------|------|
| 页面尺寸 | A3 横向比例（420:297 ≈ 1.414），内容自适应，不强行压缩 |
| 正文字号 | `fontSize=12`，不加粗（`fontStyle=0`） |
| 主标题字号 | `fontSize=12`，不加粗，黄色背景（`fillColor=#FFF2CC;strokeColor=#D6B656`） |
| 线宽 | 统一 `strokeWidth=1`，所有边框黑色 `#000000` |
| 池体/设备 | 白底黑框，`fillColor=#FFFFFF;strokeColor=#000000;rounded=4` |
| 参数框 | 白底黑框，`fillColor=#FFFFFF;strokeColor=#000000;rounded=2`，只写药剂内容 |
| 字体 | 不指定 `fontFamily`，使用 draw.io 默认（Helvetica / 中文回退） |
| 图框 | A3 横向比例自适应，外框线宽 1pt，内框线宽 2pt，距外框 5mm |
| 标题栏 | 右下角，180mm×32mm，4 行结构，灰底名称行/白底内容行 |
| 图例 | 支流区域右侧，白底黑框，标题灰底，说明四种管线类型 |
| 编码 | UTF-8，带 `<?xml version="1.0" encoding="UTF-8"?>` 声明 |

### 管线样式（四种）

| 类型 | 颜色 | 线型 | 箭头 | 识别规则 |
|------|------|------|------|---------|
| 主水管（main） | 黑色 `#000000` | 实线 | 单向 | 默认 |
| 加药管（chemical） | 绿色 `#82B366` | 虚线 | 单向 | label 含"加药/药剂/投药" |
| 污泥管（sludge） | 棕色 `#B85450` | 虚线 | 单向 | label 含"污泥/排泥" |
| 回流管（recycle） | 紫色 `#9673A6` | 虚线 | 单向 | label 含"回流/循环" |

### 标题栏 4 行结构

```
┌──────────┬──────────┬────────┬──────┬──────┐
│ 公司     │ 项目     │ 图名   │ 图号 │ 日期 │  ← 第1行 灰底加粗
├──────────┼──────────┼────────┼──────┼──────┤
│ ××环保   │ 温州××   │ 废水处 │ ××-  │ 2026 │  ← 第2行 白底常规
│ 科技     │ 厂站     │ 理工艺 │ 2026 │ .05  │
├──────────┼──────────┼────────┼──────┼──────┤
│ 编制     │ 审核     │ 比例   │ 设计 │ 页码 │  ← 第3行 灰底加粗
├──────────┼──────────┼────────┼──────┼──────┤
│ ×××      │ ×××      │ 按实   │ 施工 │ 1/1  │  ← 第4行 白底常规
└──────────┴──────────┴────────┴──────┴──────┘
  45mm      45mm       35mm    24mm   30mm
```

### 参数框文字规范

- **去掉前缀**：不写"1池"、"2池"等格次前缀，只保留药剂内容
- **写法要短**：优先"药剂名 + 核心控制值/作用"，例如 `石灰-pH=8.5~9`、`次钠-ORP`、`双氧水-100~200L/h`
- **位置对齐**：参数框放在对应格次标签上方，通过水平对齐表明对应关系

---

## 核心架构

```
输入：PlantSchema（结构化工艺数据）
   ↓
布局引擎：LayoutEngine（engine/layout_engine.py）
   ├─ 支流纵向布局
   ├─ 综合区横向自由延伸（无蛇形折返）
   ├─ 生化区横向自由延伸
   ├─ 智能走线：支流→综合区从侧边引出，避免穿越
   ├─ A3 比例图框 + 标题栏（自动计算内容边界）
   └─ 支流右侧管线图例
   ↓
渲染器：DrawioRenderer（engine/renderer.py）
   ├─ 样式模式：统一 12px、不加粗、1px 线宽、黑色边框
   └─ 四种管线样式自动识别
   ↓
输出：.drawio XML 文件
```

### 引擎模块

| 文件 | 职责 |
|------|------|
| `engine/schema.py` | 领域模型：Stream、ReactionGroup、CombinedSection、BioSection 等 |
| `engine/layout_engine.py` | 布局引擎：计算节点坐标、连线路由、A3 图框、标题栏、图例 |
| `engine/renderer.py` | XML 渲染器：样式模式渲染、管线样式、序列化为 draw.io XML |

### 使用方式

```python
from engine import LayoutEngine, DrawioRenderer
from 厂站目录.schema文件 import plant_schema

# 默认使用样式模式（styled=True）
engine = LayoutEngine(plant_schema, styled=True)
result = engine.layout()

renderer = DrawioRenderer(result.cells, result.page_w, result.page_h)
renderer.write("输出.drawio")
```

---

## 样式常量（工程图样式模式）

```python
# 节点样式（统一 12px、不加粗、1px 黑色边框）
TNK  = "rounded=4;whiteSpace=wrap;html=1;fontSize=12;align=center;fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=1;fontStyle=0;"  # 池/罐
PRM  = "rounded=2;whiteSpace=wrap;html=1;fontSize=12;align=center;fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=1;fontStyle=0;"  # 参数框
HDR  = "rounded=2;whiteSpace=wrap;html=1;fontSize=12;align=center;fillColor=#FFF2CC;strokeColor=#D6B656;strokeWidth=1;fontStyle=0;"  # 主标题
NOTE = "rounded=2;whiteSpace=wrap;html=1;fontSize=12;align=center;fillColor=#FFF2CC;strokeColor=#D6B656;strokeWidth=1;fontStyle=0;"  # 注释

# 管线样式
EDGE_MAIN     = "strokeColor=#000000;strokeWidth=1;dashed=0;endArrow=classic;startArrow=none;"   # 主水管
EDGE_CHEMICAL = "strokeColor=#82B366;strokeWidth=1;dashed=1;endArrow=classic;startArrow=none;"   # 加药管
EDGE_SLUDGE   = "strokeColor=#B85450;strokeWidth=1;dashed=1;endArrow=classic;startArrow=none;"   # 污泥管
EDGE_RECYCLE  = "strokeColor=#9673A6;strokeWidth=1;dashed=1;endArrow=classic;startArrow=none;"   # 回流管
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

---

## 目录结构

```
drawio/
├── AGENTS.md                          ← 与 CLAUDE.md 保持同步
├── CLAUDE.md                          ← 本文件（根目录必须）
├── engine/                            ← 核心布局引擎
│   ├── __init__.py
│   ├── schema.py                      ← 领域模型
│   ├── layout_engine.py               ← 布局引擎（含 A3 图框、标题栏、图例）
│   └── renderer.py                    ← XML 渲染器（含样式模式、管线样式）
├── scripts/
│   ├── generate_from_data.py          ← 通用生成入口（默认样式模式）
│   └── import_raw.py                  ← 自动解析 raw/ 目录
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
