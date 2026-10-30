---
type: workdoc
status: draft
owner: project
last_verified: 2026-10-30
---

# DOC-146：指南里原子替换那一套改对，判据改成存档文件只读

## 目标

[文件读写与存档](../../reference/godot/文件读写与存档.md)教的写档做法与代码一致、在 Windows 上真的不会写坏；里程碑那条判据改成实测挡得住替换的做法。

## 来源

- PRD：[`spec/prd-sleep-advances-day.md`](../prd-sleep-advances-day.md) 的 `US-005` 第七格；「技术考虑」里「写档不用 Godot 那一套」与「只读那一条怎么做」两条。

## 依赖

- `GP-153`：指南写的是那一份代码的做法，那条「待验证」要先在那里实测。

## 验收标准

- [ ] 可核对：[文件读写与存档 · 七、原子替换：写坏了不丢档](../../reference/godot/文件读写与存档.md)改成 .NET 那一套，写明 Godot 那一套在 Windows 上为什么不行，附源码链接。
- [ ] 可核对：[文件读写与存档 · 二、必须用引擎的文件 API，不能用 .NET 自带的](../../reference/godot/文件读写与存档.md)写明存档这一处例外与理由。
- [ ] 可核对：[文件读写与存档 · 十四、动手练习：写一个不会写坏的存档](../../reference/godot/文件读写与存档.md)跟着改。
- [ ] 可核对：[从哪里开始 · 睡一觉能推进一天](../../reference/godot/从哪里开始.md)与[文件读写与存档 · 十五、这一篇里只能你实机看的](../../reference/godot/文件读写与存档.md)里「把目录设成只读」改成「把存档文件设成只读」。
- [ ] 可核对：设计仓 `python tools/check_docs.py` 0 FAIL。

## 实现笔记

> 由 `/note-it` 在实现和评审之后填写。

## 验证结果

> 由 `/verify-round` 填写。**只写实际运行过的内容。**

| 命令 | 结果 | 判定 |
| --- | --- | --- |
|  |  |  |
