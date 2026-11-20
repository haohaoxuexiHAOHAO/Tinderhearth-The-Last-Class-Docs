---
type: workdoc
status: draft
owner: project
last_verified: 2026-11-19
---

# DOC-166：游戏是什么只在 desc 写一份，设计仓只留做游戏要用的文档

## 目标

照 [ADR-0036](../../decisions/ADR-0036-游戏是什么只在desc写一份.md) 分批做完：desc 补上世界观、战斗规则、经营规则；删掉正典、代码不用的系统文档、迁完的提案、过期指南、术语表与做完的需求；留下的文档、代码仓与检查器跟着改。

## 来源

- [ADR-0036](../../decisions/ADR-0036-游戏是什么只在desc写一份.md)。

## 依赖

- 第三批等作者看完 desc 新加的那几份。
- [`DOC-164`](./issue-DOC-164-canon-narrative-to-desc.md)、[`DOC-165`](./issue-DOC-165-renames-and-wristband-removal.md)：两条里要改正典与系统文档的部分，随这几份被删而作废；还要做的（desc 里收平矛盾、代码仓里改「手环」的名字）照旧做。

## 留下来的

| 类 | 文档 |
| --- | --- |
| 系统文档 | 地块系统、物品系统、背包系统、每日结算系统、存档系统、界面系统、生产系统、数值模型（连同 `design/numeric-model-params.json` 与 `tools/simulate_week.py`）、`design/README.md` |
| 提案 | 俯视地图用图块表拼（`DOC-161` 还在用） |
| 画图规范 | `production/` 下全部 |
| 指南 | Godot 指南里内容没过期的那几篇，加作者跟着做的那几篇 |
| 参考 | 踩坑记录、同类游戏的调研、C# 学习 |
| 流程 | 台账、进行中的需求与条目、ADR、模板、工具、总索引、WORKFLOW |

## 验收标准

- [x] 可核对：ADR-0036 已接受；WORKFLOW、`.kiro/steering/00-workflow.md`、总索引与 `design/README.md` 写的是两层的分工。
- [ ] 可核对：desc 有世界观、战斗规则、经营规则三份，作者看过。
- [ ] 可核对：`canon/` 已删；代码不用的系统文档、迁完的提案、过期指南与术语表已删。
- [ ] 可核对：正典里不进 desc 的工程约束（平台、mod 的扩展边界、内容规模基准、像素基准、场景规模这类）落进了留下的文档。
- [ ] 可核对：在设计仓（ADR 与 `archive/` 除外）与代码仓里搜被删文件的路径，为零。
- [ ] 可核对：检查器对 ADR 与 `archive/` 不查断链；上游指纹与「系统文档要有上游」只认留下的文档；`python tools/check_docs.py` 0 FAIL。
- [ ] 可核对：代码仓 `python tools/verify.py` 全绿。
- [ ] 可核对：做完的需求与条目文件已删，台账每一行只留一句话。

## 实现笔记

### 设计决策

- **正典最后删**：它链着几乎所有系统文档，先删它，指向它的链接一次断完、一次改完；先删系统文档的话，要先改一遍马上也要删的正典。

### 偏离

（实现后填写）
