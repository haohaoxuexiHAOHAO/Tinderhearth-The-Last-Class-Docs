---
type: index
status: active
owner: project
last_verified: 2026-08-25
---

# 《火种：最后一届》设计文档

> 本页是设计仓库的**唯一入口**。进行中的需求在 [spec/](./spec/README.md)，待办统一在 [待办台账](./spec/issues/README.md)，工作流规则见 [WORKFLOW.md](./WORKFLOW.md)。

## 30 秒恢复上下文

1. 看 [spec/](./spec/README.md) 下有哪份 `prd-*.md` —— 那就是当前需求；再看对应 issue 文件的验收勾选情况 —— 那就是进度。会话开始时钩子会自动打印这两项。
2. 按任务只打开下表中的权威文档；不要先读 `archive/`。
3. 需要核对实现时，再按顺序读取代码仓库的 `README.md → ARCHITECTURE.md → CONVENTIONS.md`，最后以代码和测试为准。代码仓尚未建立时，这一步跳过。

## 权威层级

**游戏是什么只在工作区根 `desc/` 写一份**（[ADR-0036](./decisions/ADR-0036-游戏是什么只在desc写一份.md)）：规则、内容、数值、人物、剧情、世界观都在那里，作者维护，最高权威；有哪几份见下面文档地图「作者维护」那一行。这几份不在仓库里。

设计仓只留做游戏要用的文档：系统文档写代码怎么搭，只为代码开工的系统写；架构决策记录（Architecture Decision Record，简称 ADR）写跨域取舍为什么这样定；台账写进度。系统文档写到规则与数值时只写在 desc 的哪一份，不另抄。对不上时，游戏规则以 desc 为准，工程取舍以 ADR 为准；代码说明已经实现的现状。

正典（`canon/`）里还没进 desc 的规则搬进 desc 之后，正典整个删掉（台账 [`DOC-166`](./spec/issues/README.md)）；在那之前，desc 里还没写到的照正典。

## 文档地图

| 分类 | 权威内容 |
| --- | --- |
| 作者维护（游戏是什么） | [状态](../desc/状态.md) · [天赋](../desc/天赋.md) · [技能](../desc/技能.md) · [角色面板](../desc/角色面板.md) · [各类公式计算](../desc/各类公式计算.md) · [人物](../desc/人物.md)（所有角色，连同黄金时代的人物）· [剧情](../desc/剧情.md) · [特殊建筑](../desc/特殊建筑.md) · [物品](../desc/物品.md)（工作区根 `desc/`，见上面「权威层级」） |
| 系统文档 | [系统文档与提案](./design/README.md)：只为代码开工的系统写，写代码怎么搭 |
| 正典（待删，[`DOC-166`](./spec/issues/README.md)） | [世界观](./canon/world/世界观.md) · [人物](./canon/characters/人物.md) · [主线故事](./canon/narrative/主线故事.md) · [支线内容](./canon/narrative/支线内容.md) · [节点里的学生](./canon/narrative/节点里的学生.md) · [学生群像](./canon/narrative/学生群像.md) · [反派与要角](./canon/narrative/反派与要角.md) · [常驻NPC](./canon/narrative/常驻NPC.md) · [玩法定位](./canon/gameplay/玩法定位.md) · [时间与经营](./canon/gameplay/时间与经营.md) · [角色与成长](./canon/gameplay/角色与成长.md) · [战斗与关卡](./canon/gameplay/战斗与关卡.md) |
| 美术与文案 | [像素绘制原则](./production/像素绘制原则.md)（通用像素方法，含角色逐帧交付）· [场景绘制约定](./production/场景绘制约定.md)（俯视投影、瓦片拼接、侧视背景与动态水）· [界面绘制约定](./production/界面绘制约定.md)（界面件画多大、几种状态、九宫格怎么切、哪几层被染、放哪）· [文案写作规范](./production/文案写作规范.md) |
| 学习与排错 | [C# 学习](./reference/学习CSharp-Java程序员向.md) · [Godot 实现教学](./reference/godot/README.md)（引擎怎么用、作者在编辑器里做哪一半）· [踩坑记录](./reference/踩坑记录.md) · [同类游戏怎么做地图](./reference/同类游戏怎么做地图.md)（同类型的像素游戏，各个场景的地图怎么做，只记事实与出处）· [同类游戏怎么做战棋](./reference/同类游戏怎么做战棋.md)（几款战棋与回合制游戏怎么轮回合、什么时候开打、视野与小人怎么动，只记事实与出处）· [同类游戏怎么叠同一种加成](./reference/同类游戏怎么叠同一种加成.md)（同一种加成从几处来时各款怎么算合计、玩家怎么评价，只记事实与出处） |
| 词汇 | [术语表](./reference/术语表.md)（文档里那批自造词，跨多份共用的那些；只在一份里用的词在那一份自己的「术语」节） |
| 需求与待办 | [spec/](./spec/README.md)（进行中需求）· [待办台账](./spec/issues/README.md)（唯一待办索引） |
| 数值 | [数值模型](./design/数值模型.md)（判据与推演；公式的样子见[各类公式计算](../desc/各类公式计算.md)）· 值在 `design/numeric-model-params.json`，推演入口 `python tools/simulate_week.py` |
| 流程 | [WORKFLOW](./WORKFLOW.md)（工作流规则；体裁规则见 [ADR-0010](./decisions/ADR-0010-文档体裁与系统文档归位.md) 与 [ADR-0036](./decisions/ADR-0036-游戏是什么只在desc写一份.md)） |
| 决策与历史 | [ADR 索引](./decisions/README.md)（含工程性取舍，代码仓库不另设决策目录）· [历史归档](./archive/README.md)（只读，含变更日志） |

## 游戏定位

本作是 2D 像素风格的废土幻想**经营建造 + 俯视格子回合制战斗**（[ADR-0035](./decisions/ADR-0035-战斗改成俯视的格子回合制.md)）。核心主题是**守护与希望**：玩家主动帮助他人迎来高光时刻，而不是把角色当作可以替换的消耗品。基地、城区与出征都是俯视，玩家直接操作主角。上架目标是 Steam 的 Windows PC 端，买断制。

公式的样子见 [desc/各类公式计算.md](../desc/各类公式计算.md)，值与判据归[数值模型](./design/数值模型.md)。**代码里刻意没有玩法数值**；战斗手感帧数不属数值模型，归实机收敛（见[待办台账](./spec/issues/README.md) `GP-6`）。

前作《火种》的玩法明确**不予继承**，本作的回合制是重新设计的。世界观、主角设定与美术／文案方法论继承自前作，其余（剧情、九人学生名单、战斗与经营系统、任务与界面接口）一律重新设计。

## 维护入口

以下 `python tools/...` 命令都从**设计仓库根目录**运行；从工作区根目录运行时，在路径前加 `Tinderhearth-The-Last-Class-Docs/`。

- 提需求：只说目标、现状、验收和非目标就行。执行者用 `/prd` 技能问清剩下的，产出 [PRD](./templates/PRD.md) 到 [spec/](./spec/README.md)；文件定位与上下文恢复由执行者负责。
- 需求流水线（先写文档再改）：按 [WORKFLOW §1](./WORKFLOW.md) 走 `/prd → /to-issues → 实现 → /ship-it`，提交前 `/review-it`。**PRD 未经作者确认前不改代码**，这是流水线唯一的强制闸门。
- 新系统：从 [SYSTEM 模板](./templates/SYSTEM.md) 开始，写进 `design/<系统名>.md`；方案论证：从 [DESIGN 模板](./templates/DESIGN.md) 开始，写进 `design/proposals/`；跨域取舍：从 [ADR 模板](./templates/ADR.md) 开始；拆条目：从 [issue 模板](./templates/ISSUE.md) 开始。体裁怎么选见 [ADR-0010](./decisions/ADR-0010-文档体裁与系统文档归位.md)。
- 进度不单独维护状态页：它就是 issue 文件里的验收勾选框。Git 负责变更历史，不在活文档追加流水账。
- 一个需求做完：结论写进 desc 或留下的系统文档，过程件删掉，台账那一行留一句话。准出见 [WORKFLOW §4](./WORKFLOW.md)。
- 改完文档后运行 `python tools/check_docs.py`，检查文件头、断链、归档边界、入口可达性、单一台账与工作区行尾；退出码非零表示存在必须修复的问题。**改动了正典某一节之后它会报「引那一节的上游约束要复核」** —— 核完跑 `python tools/check_docs.py --repin` 重录指纹（指纹在 `tools/upstream-pins.json`，进 git，所以「我看过了」留得下痕迹）。查看规模趋势用 `python tools/check_docs.py --report`（只打表、不判定）；行尾不合规用 `python tools/check_docs.py --fix-eol` 按 `.gitattributes` 改回来。
- 动了 `design/数值模型.md` 或 `design/numeric-model-params.json` 就跑 `python tools/simulate_week.py --check-doc`，它核对文档里的参数路径与**路径旁抄的数字**都与参数表没有分叉；不带参数跑则重算七天推演与全部平衡判据，并把文档里抄的**算出来的量**（战力差、还债天数这类）与本轮算的比一遍（条数由脚本自报，散文里不复述）。加 `--set 路径=值` 可以撞它的失败路径。
- 中文像素字体（[ADR-0008](./decisions/ADR-0008-中文像素字体选型.md)）：`python tools/audit_fonts.py` 核授权原文与上游字形来源、量字形覆盖与字宽行高；`python tools/font_preview.py` 把字渲进 Godot 看实机效果（可读性只能人判），两者都用 `--clean` 收尾。
- 本机 Godot 工具链：`python tools/setup_godot.py --check` 体检已装版本；升级用 `--version <版本号>`，下载、核对官方 SHA512、解压、装导出模板、跑 `--version` 自证一步做完；清理旧版本用 `--prune <版本号>`，默认只预演，加 `--yes` 才真删。版本基线见 [ADR-0005](./decisions/ADR-0005-技术基线.md)。
