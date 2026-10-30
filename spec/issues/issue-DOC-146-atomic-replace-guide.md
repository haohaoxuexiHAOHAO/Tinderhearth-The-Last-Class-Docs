---
type: workdoc
status: archived
owner: project
last_verified: 2026-10-30
---

# DOC-146：指南里原子替换那一套改对，判据改成存档文件只读

## 目标

[文件读写与存档](../../reference/godot/文件读写与存档.md)教的写档做法与代码一致、在 Windows 上真的不会写坏；里程碑那条判据改成实测挡得住替换的做法。

## 来源

- PRD：[`spec/prd-sleep-advances-day.md`](../prd-sleep-advances-day.md) 的 `US-005` 第七格；「技术考虑」里「写档不用 Godot 那一套」与「只读那一条怎么做」。

## 依赖

- `GP-153`：指南写的是那一份代码的做法，那条「待验证」要先在那里实测。

## 验收标准

- [x] 可核对：[文件读写与存档 · 七、原子替换：写坏了不丢档](../../reference/godot/文件读写与存档.md)改成 .NET 那一套，写明 Godot 那一套在 Windows 上为什么不行，附源码链接。新加的小节是「为什么存档不用 Godot 那一套」「本项目的做法：.NET 写临时文件、落盘、带覆盖地改名」「怎么故意让它写不上」；.NET 那条源码链接钉在 `v10.0.0`。
- [x] 可核对：[文件读写与存档 · 二、内容走引擎的文件 API，存档走 .NET](../../reference/godot/文件读写与存档.md)写明存档这一处例外与理由。标题跟着改了，理由见下面「设计决策」；PRD 里引这一节的那一处跟着改。
- [x] 可核对：[文件读写与存档 · 十四、动手练习：写一个不会写坏的存档](../../reference/godot/文件读写与存档.md)跟着改：原子替换那几步换成 .NET，加了「设成只读」一步。
- [x] 可核对：[从哪里开始 · 睡一觉能推进一天](../../reference/godot/从哪里开始.md)与[文件读写与存档 · 十五、这一篇里只能你实机看的](../../reference/godot/文件读写与存档.md)里「把目录设成只读」改成「把存档文件设成只读」。
- [x] 可核对：设计仓 `python tools/check_docs.py` 0 FAIL。

## 实现笔记

### 设计决策

- **模糊点**：讲文件 API 选哪一套的那一节，只补一句例外，还是连标题一起改。
- **选择**：标题改成「内容走引擎的文件 API，存档走 .NET」，正文分开写内容与存档各自的理由。
- **理由**：读者先扫标题，一条写成没有例外的规矩，补在正文里的例外会被漏看。

- **模糊点**：源码事实的家放在指南里还是 PRD 里。
- **选择**：放在[文件读写与存档 · 七、原子替换：写坏了不丢档](../../reference/godot/文件读写与存档.md)，代码仓 `src/Platform/SaveStore.cs` 的注释改指过来。
- **理由**：PRD 做完要归档，指南是长期在用的那一份。

### 偏离

- **方案怎么说**：只改验收标准里点名的那几节与里程碑那条判据。
- **实际怎么做**：[文件读写与存档 · 三、`FileAccess` 用法，以及 C# 里必须 `using`](../../reference/godot/文件读写与存档.md)的示例路径从存档位换成练习用的 `user://lab/data.json`，`Flush()` 那条改成「只把缓冲交给系统」，往原子替换那一节的引用改成按节名引；[文件读写与存档 · 四、`DirAccess`：目录操作](../../reference/godot/文件读写与存档.md)在 `RenameAbsolute` 下面加了一条警告。
- **为什么**：用法那一节教的正是用 `FileAccess` 写存档、靠 `Flush()` 落盘，与原子替换那一节改过之后的说法相反。

### 权衡

- **目录只读挡不住那条只写实测，不写原因**：实测只有「Python 替换照样成功」这一条，Windows 为什么不管目录的只读属性没有查到出处。

### 待确认

无。

## 验证结果

| 命令 | 结果 | 判定 |
| --- | --- | --- |
| 对着 dotnet/runtime `v10.0.0` 与 Godot `4.7.2-stable` 的源码核链接里的说法 | `File.Move` 带覆盖是一次带 `MOVEFILE_REPLACE_EXISTING` 与 `MOVEFILE_COPY_ALLOWED` 的 `MoveFileExW`；Godot 安全保存那段重试的注释写的是杀毒软件锁文件 | 通过 |
| `python tools/check_docs.py`（设计仓） | 0 项必须修复 | 通过 |
| `python tools/verify.py`（代码仓，`src/Platform/SaveStore.cs` 的注释改指指南） | 7/7 步通过 | 通过 |
