---
type: index
status: active
owner: project
last_verified: 2026-08-26
---

# 需求工作区

进行中需求的过程文件都在这里。规则见 [WORKFLOW](../WORKFLOW.md)，每一步的做法见 `.kiro/skills/` 里的对应技能。

## 目录形状

| 路径 | 内容 | 产出技能 |
| --- | --- | --- |
| `prd-<slug>.md` | 需求文档：US-NNN 用户故事、FR-N 功能需求、验收清单、非目标 | `/prd` |
| —— | 结构、接口与测试映射不写在本目录：一个系统的长期契约归[系统文档](../design/README.md)，一次性论证归提案 | `/to-design` |
| `推演-<slug>.md` | 纸面推演：把循环手算一遍找漏，验收用。归档时随需求一起移走 | 无（按需手写） |
| [`issues/`](./issues/README.md) | 可实现条目，一条一个文件；索引即待办台账 | `/to-issues` |

**进行中：没有。** 上一个需求「把设计评审查出来的内容与爽感缺口按批次补上」已归档到 [`archive/spec/GP-101-richness-and-feel/`](../archive/spec/GP-101-richness-and-feel/prd.md)（**历史背景·非依据**），四个批次的现行事实落在 `canon/` 那五份（[战斗与关卡](../canon/gameplay/战斗与关卡.md)、[时间与经营](../canon/gameplay/时间与经营.md)、[玩法定位](../canon/gameplay/玩法定位.md)、[主线故事](../canon/narrative/主线故事.md)、[节点里的学生](../canon/narrative/节点里的学生.md)）与 `design/` 下那二十来份系统文档，外加 [ADR-0024](../decisions/ADR-0024-学生那条战线改成一场真打.md) 与[数值模型](../design/数值模型.md)的尚未给值表；**逐条落点在那份归档件的「归档三问」里**，剩余动作（落地、反证与那份实机清单）在[待办台账](./issues/README.md)。再往前那一个「系统文档的接口节与元数据收口」已归档到 [`archive/spec/DOC-118-system-doc-completeness/`](../archive/spec/DOC-118-system-doc-completeness/prd.md)（**历史背景·非依据**），它的现行事实在[`状态效果系统`](../design/状态效果系统.md)与[`角色动作状态系统`](../design/角色动作状态系统.md)两份的接口节、[SYSTEM 模板](../templates/SYSTEM.md)那段文件头示例与 `tools/check_docs.py` 里那条按体裁分的判定，落点清单在那份归档件的「归档三问」里；后置与超边界那几项在[待办台账](./issues/README.md)。再往前那一个「节日」已归档到 [`archive/spec/GP-97-festivals/`](../archive/spec/GP-97-festivals/prd.md)（**历史背景·非依据**），它的现行事实在[`节日系统`](../design/节日系统.md)、[时间与经营 · 作息与熬夜](../canon/gameplay/时间与经营.md)、[`天气系统`](../design/天气系统.md)那一节、[`事件系统`](../design/事件系统.md)那张后果表，以及[玩法定位](../canon/gameplay/玩法定位.md)两张表与[数值模型](../design/数值模型.md)的尚未给值表；落地与界面那几项剩余动作在[待办台账](./issues/README.md)。再往前那一个「天气」已归档到 [`archive/spec/GP-93-weather/`](../archive/spec/GP-93-weather/prd.md)（**历史背景·非依据**），它的现行事实在[`天气系统`](../design/天气系统.md)、[时间与经营 · 作息与熬夜](../canon/gameplay/时间与经营.md)那三条、[`地块系统` · 浇水按天记，只改产量不改品质](../design/地块系统.md)与[数值模型](../design/数值模型.md)的尚未给值表，落地与节日那两项剩余动作在[待办台账](./issues/README.md)。再往前那一个「剩下那批设计空白，分批补完」已归档到 [`archive/spec/remaining-design-gaps/`](../archive/spec/remaining-design-gaps/prd.md)（**历史背景·非依据**），它的现行事实在[玩法定位](../canon/gameplay/玩法定位.md)（内容规模基准那张表多出「谁在等它」一列）、[世界观 · 城区各片](../canon/world/世界观.md)、[支线内容](../canon/narrative/支线内容.md)那几节与[`界面系统`](../design/界面系统.md)更新公告那一节，加上 `tools/check_docs.py` 里那条守卫自己，落点清单在那份归档件的「归档三问」里。**那一份的目录名没有编号前缀**，理由写在它文首。再往前那一个「叙事正典的矛盾修复与要角补位」已归档到 [`archive/spec/NR-29-narrative-repair-and-cast/`](../archive/spec/NR-29-narrative-repair-and-cast/prd.md)（**历史背景·非依据**），它的现行事实在 `canon/` 那六份正典（[世界观](../canon/world/世界观.md)、[人物](../canon/characters/人物.md)、[主线故事](../canon/narrative/主线故事.md)、[反派与要角](../canon/narrative/反派与要角.md)、[学生群像](../canon/narrative/学生群像.md)、[常驻NPC](../canon/narrative/常驻NPC.md)）与[`主线推进系统`](../design/主线推进系统.md)，剩余动作在[待办台账](./issues/README.md)。再往前那一个「两种视角各自的尺度与人物本体尺寸」已归档到 [`archive/spec/GP-82-view-and-sprite-scale/`](../archive/spec/GP-82-view-and-sprite-scale/prd.md)（**历史背景·非依据**），它的现行事实在[玩法定位](../canon/gameplay/玩法定位.md)、[战斗与关卡](../canon/gameplay/战斗与关卡.md)、[人物](../canon/characters/人物.md)三份正典，[场景绘制约定](../production/场景绘制约定.md)与[像素绘制原则](../production/像素绘制原则.md)两份制作规格，以及 [ADR-0020](../decisions/ADR-0020-侧视不拉近而把角色画大一档.md) 与 [ADR-0021](../decisions/ADR-0021-每个朝向各画一套不做水平翻转.md)，落点清单在那份归档件的「归档三问」里。再往前那一个「四项属性各自的回报重排」已归档到 [`archive/spec/GP-76-attribute-payoff-rebalance/`](../archive/spec/GP-76-attribute-payoff-rebalance/prd.md)（**历史背景·非依据**），它的现行事实在[角色与成长](../canon/gameplay/角色与成长.md)、[战斗与关卡](../canon/gameplay/战斗与关卡.md)那两份正典与 `design/` 下成长、伤害、装备、技能、生产、数值模型六份，落点清单在那份归档件的「归档三问」里。再往前那一个「正典对账」已归档到 [`archive/spec/DOC-97-canon-reconciliation/`](../archive/spec/DOC-97-canon-reconciliation/prd.md)（**历史背景·非依据**），它的现行事实在正典那九份自己身上、[待办台账](./issues/README.md)的「状态词」那一节，以及 `tools/check_docs.py` 里那条「不许拿已关闭的编号当归处」的守卫。再往前那一个「系统文档读得懂」已归档到 [`archive/spec/DOC-89-doc-readability/`](../archive/spec/DOC-89-doc-readability/prd.md)（**历史背景·非依据**），它的现行结论在[术语表](../reference/术语表.md)、[SYSTEM 模板](../templates/SYSTEM.md)、[ADR-0019](../decisions/ADR-0019-系统文档骨架加术语一节.md)与 `design/` 下那批系统文档自己身上，去处清单在那份归档件的文件头。再往前那一个「设计闭环」在 [`archive/spec/DOC-64-design-closure/`](../archive/spec/DOC-64-design-closure/prd.md)（**历史背景·非依据**）。**下一步做什么看 [待办台账](./issues/README.md)，不看本节** —— 本节只说上一批去了哪里，排序与优先级不在这里复述。

`<slug>` 是简短英文标识，全小写、连字符分隔，例如 `gameplay-positioning`、`combat-feel-tuning`。

## 当前进度看哪里

**没有单独的状态页。** 恢复上下文的依据是两处：

1. `spec/` 下存在哪些 `prd-*.md` —— 那就是进行中的需求。
2. 对应 `issues/issue-*.md` 里的验收清单勾选情况 —— 那就是完成到哪一步。

会话开始时 `.kiro/hooks/session-baseline.json` 会自动打印这两项，不需要问作者「上次做到哪了」。

批量实现时 `/loop-it` 另在工作区根写 `.loop-state.json` 记录逐条进度，它是崩溃恢复用的过程文件，不进 Git。

## 一次只做一个需求

`spec/` 下**同时只应有一份** `prd-*.md`。发现已有别的需求在进行时，先问作者是否切换，不要并做。

理由是验收范围：两个需求同时改动同一批文件时，回归失败说不清是哪一个引起的。

## 超出边界的发现不许顺手修

实现中发现本需求范围外的问题时，去 [issues 索引](./issues/README.md) 记一条，然后回到原需求。归档时在归档三问第 2 条列出这些编号。

不这么做的后果很具体：这轮的验收范围变模糊，回归责任说不清，而且那个「顺手」的改动没有任何测试覆盖。

## 归档

需求收尾时把 `prd-*.md` 与相关 issue 文件移入 `archive/spec/`，并在[变更日志归档](../archive/history/变更日志归档.md)加一行。步骤与准出见 [WORKFLOW §4](../WORKFLOW.md)。

移之前必须先把现行事实写进正典、ADR 或制作规格 —— 归档件不得作为现行依据，留在归档里的结论等于丢失。
