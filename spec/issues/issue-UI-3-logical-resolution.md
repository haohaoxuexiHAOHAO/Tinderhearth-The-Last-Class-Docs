---
type: workdoc
status: draft
owner: project
last_verified: 2026-08-30
---

# UI-3：逻辑分辨率与缩放链路落进工程

## 目标

工程以 640×360 为逻辑分辨率、只按整数倍放大到窗口、所有纹理最近邻过滤，使像素素材与 12px 中文进去就是清晰的。

## 来源

- PRD：[`spec/prd-ui-framework.md`](../prd-ui-framework.md) 的 `US-001`
- 分辨率取 640×360 由作者 2026-08-30 定；判据见 [ADR-0008](../../decisions/ADR-0008-中文像素字体选型.md) 与[玩法定位 · 像素基准](../../canon/gameplay/玩法定位.md)

## 依赖

无。它是本轮的第一件事，其余 `UI-*` 条目都依赖它。

## 验收标准

- [x] `project.godot` 有 `window/size/viewport_width=640`、`viewport_height=360`
- [x] `project.godot` 有 `window/stretch/scale_mode="integer"`
- [x] `project.godot` 有 `rendering/textures/canvas_textures/default_texture_filter=0`
- [x] `window/stretch/mode="canvas_items"` 与 `aspect="expand"` 未被改动（正典要求保持不动）
- [x] 窗口 1280×720／1920×1080／2560×1440 时实际缩放倍数为 2／3／4；**3840×2160 本机屏幕装不下**（系统裁成 3840×2130），该档按实际窗口判定为 ×5，整数与两轴一致都成立 —— ×6 这一档在本机无法验证，另需 4K 屏或 `--fullscreen`
- [x] 判据改成守不变量而不是守定值：缩放为整数、两轴相等、逻辑尺寸不小于 640×360。理由是实测发现 `expand` 把高度锁在 360、按窗口宽高比撬宽（3840×2130 得到逻辑 649×360），逻辑宽度是下限不是定值
- [x] 代码仓 `python tools/verify.py` 全绿：4/4 步通过（构建 0 错 0 警、测试 10/10、导出包内 15 条泄漏 0、产物启动正常），2026-08-30 实测 22.8s
- [x] 产物侧复验：`python tools/check_scaling.py --exported` 四档全过
- [ ] 作者实机确认

守卫：代码仓 `python tools/check_scaling.py`（跑工程源码）／`--exported`（跑产物）。它从引擎 `--log-file` 里读 `[显示]` 那一行判定，不靠人看。一档都没读到就判失败，避免空转全绿。

## 实现笔记

> 由 `/note-it` 填写。

### 设计决策

### 偏离

### 权衡

### 待确认

## 验证结果

> 由 `/verify-round` 填写。只写实际运行过的内容。

| 命令 | 结果 | 判定 |
| --- | --- | --- |
|  |  |  |
