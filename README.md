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

“正典”指项目已经确认、优先级最高的设计事实。发生冲突时按以下顺序判断：

`世界观 > 人物 > 剧情 > 玩法系统 > 系统细化`

低层文档只能补充实现细节，不能静默改写高层意图；代码说明已经实现的现状。确需改变跨领域取舍时，新增架构决策记录（Architecture Decision Record，简称 ADR）。

## 文档地图

| 分类 | 权威内容 |
| --- | --- |
| 世界与人物 | [世界观](./canon/world/世界观.md) · [人物](./canon/characters/人物.md) |
| 叙事 | **待设计**。新故事尚未立项，`canon/narrative/` 暂空 |
| 玩法与系统 | [玩法定位](./canon/gameplay/玩法定位.md)（总纲）· [时间与经营](./canon/gameplay/时间与经营.md) · [角色与成长](./canon/gameplay/角色与成长.md) · [战斗与关卡](./canon/gameplay/战斗与关卡.md)。数值模型仍待设计（`GP-2`） |
| 美术与文案 | [像素绘制原则](./production/像素绘制原则.md) · [文案写作规范](./production/文案写作规范.md) |
| 学习与排错 | [C# 学习](./reference/学习CSharp-Java程序员向.md) · [踩坑记录](./reference/踩坑记录.md) |
| 需求与待办 | [spec/](./spec/README.md)（进行中需求）· [待办台账](./spec/issues/README.md)（唯一待办索引） |
| 数值 | [数值模型](./design/数值模型.md)（公式与判据）· 值在 `design/numeric-model-params.json`，推演入口 `python tools/simulate_week.py` |
| 流程与设计 | [WORKFLOW](./WORKFLOW.md)（工作流规则）· [专项设计](./design/README.md)（活跃方案） |
| 决策与历史 | [ADR 索引](./decisions/README.md)（含工程性取舍，代码仓库不另设决策目录）· [历史归档](./archive/README.md)（只读，含变更日志） |

## 游戏定位

本作是 2D 像素风格的废土幻想**角色扮演游戏**（Role-Playing Game，简称 RPG）。核心主题是**守护与希望**：玩家主动帮助他人迎来高光时刻，而不是把角色当作可以替换的消耗品。

世界与主角设定已经确定，见上表。**玩法结构与战斗形式已裁定**并落进 [canon/gameplay/](./canon/gameplay/玩法定位.md)：2D 像素废土题材的**经营建造 + 关卡制动作 RPG**，战斗与出征一律侧视、基地与城区一律俯视，玩家直接操作主角。上架目标是 Steam 的 Windows PC 端，买断制。

**数值模型仍未设计**（`GP-2`）—— 属性公式、成长曲线与判定公式在它归档前不得当成既定事实引用。

前作《火种》的回合制玩法明确**不予继承**。世界观、主角设定与美术／文案方法论继承自前作，其余（剧情、九人学员名单、战斗与经营系统、任务与界面接口）一律重新设计。

## 维护入口

以下 `python tools/...` 命令都从**设计仓库根目录**运行；从工作区根目录运行时，在路径前加 `Tinderhearth-The-Last-Class-Docs/`。

- 提需求：只说目标、现状、验收和非目标就行。执行者用 `/prd` 技能问清剩下的，产出 [PRD](./templates/PRD.md) 到 [spec/](./spec/README.md)；文件定位与上下文恢复由执行者负责。
- 需求流水线（先写文档再改）：按 [WORKFLOW §1](./WORKFLOW.md) 走 `/prd → /prd-to-spec → /to-issues → 实现 → /review-it → /ship-it → /verify-round → /ship-archive`。**PRD 未经作者确认前不改代码**，这是流水线唯一的强制闸门。
- 新设计：从 [设计模板](./templates/DESIGN.md) 开始；跨域取舍：从 [ADR 模板](./templates/ADR.md) 开始；拆条目：从 [issue 模板](./templates/ISSUE.md) 开始。
- 进度不单独维护状态页：它就是 issue 文件里的验收勾选框。Git 负责变更历史，不在活文档追加流水账。
- 改完文档后运行 `python tools/check_docs.py`，检查文件头、规模配额、断链、归档边界、入口可达性、单一台账与工作区行尾；退出码非零表示存在必须修复的问题。查看规模趋势用 `python tools/check_docs.py --report`；行尾不合规用 `python tools/check_docs.py --fix-eol` 按 `.gitattributes` 改回来。
- 改了上面那个检查器之后，跑 `python tools/selfcheck_docs_guard.py` 自证：它造真实缺陷形状的违反、确认拦得住、再还原复验，并自报覆盖量。
- 本机 Godot 工具链：`python tools/setup_godot.py --check` 体检已装版本；升级用 `--version <版本号>`，下载、核对官方 SHA512、解压、装导出模板、跑 `--version` 自证一步做完；清理旧版本用 `--prune <版本号>`，默认只预演，加 `--yes` 才真删。版本基线见 [ADR-0005](./decisions/ADR-0005-技术基线.md)。
