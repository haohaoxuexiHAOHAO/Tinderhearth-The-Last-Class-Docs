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

**进行中**：无。上一个需求「正典对账」已归档到 [`archive/spec/DOC-97-canon-reconciliation/`](../archive/spec/DOC-97-canon-reconciliation/prd.md)（**历史背景·非依据**），它的现行事实在正典那九份自己身上、[待办台账](./issues/README.md)的「状态词」那一节，以及 `tools/check_docs.py` 里那条「不许拿已关闭的编号当归处」的守卫。再往前那一个「系统文档读得懂」已归档到 [`archive/spec/DOC-89-doc-readability/`](../archive/spec/DOC-89-doc-readability/prd.md)（**历史背景·非依据**），它的现行结论在[术语表](../reference/术语表.md)、[SYSTEM 模板](../templates/SYSTEM.md)、[ADR-0019](../decisions/ADR-0019-系统文档骨架加术语一节.md)与 `design/` 下那批系统文档自己身上，去处清单在那份归档件的文件头。再往前那一个「设计闭环」在 [`archive/spec/DOC-64-design-closure/`](../archive/spec/DOC-64-design-closure/prd.md)（**历史背景·非依据**）。**下一步做什么看 [待办台账](./issues/README.md)，不看本节** —— 排在最前面的是 `DOC-97`（正典对账），它的取舍已由作者定过、清单在那一条的条目文件里。

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
