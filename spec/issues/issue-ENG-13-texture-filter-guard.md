---
type: workdoc
status: draft
owner: project
last_verified: 2026-08-31
---

# ENG-13：界面节点不得局部覆盖 texture_filter 的守卫

## 目标

任何场景、资源或代码里对 `texture_filter`（`CanvasItem.TextureFilter`）的局部覆盖都在素材守卫里判失败，使「像素清晰唯一依靠项目级最近邻过滤、一律靠继承」这条约束有执行体。

## 来源

- `UI-4` 实现中发现，按「超边界不许顺手修」记账。实测（`UI-4`）：`canvas_items` 下 12px 中文清晰**唯一依靠最近邻纹理过滤** —— 改成线性则最小同色跑长从 2／3／4 塌到 1（`python tools/font_preview.py --measure --canvas-items --linear-filter`）。
- `CanvasItem.texture_filter` 可逐节点覆盖并向下继承，一次手滑（尤其误设 Linear）就静默毁掉整棵子树的文字与素材，且不报错。代码里 `GameCamera`／`CameraHarness`／`LevelHud` 都留了「不碰 `TextureFilter`，守卫归 `ENG-13`」的注释，等的就是这条。

## 依赖

无。落点是代码仓 `tools/check_assets.py`（`ENG-10` 的素材守卫，静态、快、在 `verify.py` 第一步）。

## 验收标准

- [x] 扫 `.tscn`／`.tres` 里的 `texture_filter = N`，N 非 0（非 `Inherit`／`ParentNode`）即判失败，报出文件与值 —— `check_texture_filter` 的 `TSCN_FILTER_RE`
- [x] 扫 `src/`／`rules/` 的 C# 里 `.TextureFilter =` 赋值（`(?!=)` 排除 `==` 比较，不误伤注释与 `TextureFilterEnum` 枚举引用），出现即判失败
- [x] 当前仓库基线为 0 覆盖（一律靠继承）—— 干净仓实测「扫 42 份、无 texture_filter 覆盖」，扫到文件数 42 > 0（不空转）
- [x] 自报覆盖量：`check_assets` 打「另扫 N 份场景资源与 C# 的 texture_filter 覆盖」
- [x] 自证：`.tscn` 塞 `texture_filter = 2`（Linear）拦得住、C# 塞 `.TextureFilter =` 拦得住；`texture_filter = 0` 与 `.TextureFilter ==` 不误判；`selfcheck_verify.py` 还原后复验通过（两条 DIRECT_CASE）
- [x] 改了 `check_assets.py` 跑 `python tools/selfcheck_verify.py` —— 22/22 全绿

## 实现笔记

### 设计决策

- **落在 `check_assets.py`（`ENG-10` 的素材守卫）而不是 `verify.py` 或新门禁**：它已是 `verify.py` 第一步的静态扫描（纯 Python、无引擎、最快），加一条同类的静态文本扫描最贴。ledger 两个候选里选它。
- **按后缀分两条判据**：`.tscn`／`.tres` 扫 `texture_filter = N`（N≠0，0=`ParentNode`=继承）；`.cs` 扫 `.TextureFilter =` 赋值。两种文件的覆盖语法不同（snake_case 整数 vs PascalCase 赋值）。
- **C# 用 `\.TextureFilter\s*=(?!=)` 排除 `==` 比较**：`CameraProbe` 有 `camera.TextureFilter == ParentNode`（在**核**没覆盖），不能被自己的守卫拦下。负向前瞻排掉比较；注释与 `TextureFilterEnum` 枚举引用不带「.TextureFilter =」形状，天然不误伤。干净仓实测 0 误判。
- **C# 范围限 `src/` 与 `rules/`，不扫 `tools/` 与 `tests/`**：`tools/` 是守卫代码本身（会提到属性名），`tests/` 多是比较断言。
- **扫到 0 文件判失败**：空转的检查也会全绿（同 `check_assets` 其它判据的失效方向）。

### 偏离

- **超 ledger 的「.tscn／.tres」范围，加扫了 C#**（在此记账）。ledger 只写扫场景资源，但 `GameCamera`／`CameraHarness`／`LevelHud` 三处 C# 注释都写「不碰 `TextureFilter`，守卫归 `ENG-13`」—— 只扫场景不扫代码的话，那三处注释指的守卫并不存在。机制（局部覆盖毁子树）对代码同样成立，故补上 C# 赋值扫描。干净仓实测 0 误判，不扩大到无关文件。

### 权衡

- **静态文本扫 vs 运行时核**：`CameraProbe` 已在运行时核相机节点（`==ParentNode`）。本条取静态扫，因为它覆盖所有节点／文件、快、无需起引擎，且能在覆盖进仓那一刻就拦下（运行时核只覆盖被实例化的节点）。两者互补：运行时核相机这一个高危祖先，静态扫兜住其余。
- **与 `check_hud` 的界面源码扫描重叠**：`check_hud` 静态核扫界面源码的 `TextureFilter` 覆盖（`UI-8`），本条扫 `src`／`rules` 全体，在 `src/UI` 上重叠。接受 —— 防御纵深，且本条扩到 `src/World`、`rules/` 与 `.tscn`／`.tres`。

### 待确认

- 无阻塞项。当前仓库基线 0 覆盖，守卫是给将来进仓的场景与代码兜底的 tripwire。

## 验证结果

> 由 `/verify-round` 填写。只写实际运行过的内容。

2026-08-31 实现轮（代码仓根目录）：

| 命令 | 结果 | 判定 |
| --- | --- | --- |
| `python tools/check_assets.py` | 扫 42 份场景资源与 C#、0 覆盖；比较（`==ParentNode`）与注释未误判；`EXIT=0` | 通过 |
| `python tools/verify.py` | 5/5 全过；素材步含 texture_filter 扫描（42 份），17.3s | 通过 |
| `python tools/selfcheck_verify.py` | 22/22 条按预期拦下（新增 2 条 `ENG-13`：覆盖被拦、继承与比较不误判），覆盖 13 项含 `check_texture_filter`，还原后复验通过、仓库干净 | 通过 |
