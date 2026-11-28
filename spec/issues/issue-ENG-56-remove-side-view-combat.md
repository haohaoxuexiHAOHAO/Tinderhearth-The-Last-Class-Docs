---
type: workdoc
status: draft
owner: project
last_verified: 2026-11-28
---

# ENG-56：删掉侧视即时那一套战斗代码

## 目标

代码里不再有侧视即时战斗那一批，以后读代码不会照着它改。

## 来源

- PRD：[`spec/prd-first-grid-battle.md`](../prd-first-grid-battle.md) 的 `US-012`。台账里侧视那一套的待办怎么作废或改写归 `DOC-160`。

## 依赖

- `ENG-55`：排在最后，新的那一套接上之后再删。

## 验收标准

- [ ] 可核对：代码仓 `rules/Combat/` 下侧视那一批、测它们的用例、`src/` 里只给它们用的那些文件删掉；删之前按类名搜过，没有别的调用方。
- [ ] 可核对：设计仓与代码仓里指着这些文件的地方跟着改。
- [ ] 可核对：代码仓 `python tools/verify.py` 全绿；设计仓 `python tools/check_docs.py` 0 FAIL。

## 实现笔记

> 实现与评审之后填：设计决策、偏离、权衡、待确认。

## 验证结果

> 只写实际运行过的内容。

| 命令 | 结果 | 判定 |
| --- | --- | --- |
|  |  |  |
