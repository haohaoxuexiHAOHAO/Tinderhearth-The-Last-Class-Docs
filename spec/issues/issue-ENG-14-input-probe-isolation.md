---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-08
---

# ENG-14：输入专项探针互不污染

## 目标

输入专项与 HUD 验收不互相注入设备状态，启动判据能可靠反映被测输入行为。

## 来源

GP-11 收尾发现、GP-12 开工前复现，作者已授权独立登记并优先排清。
见 [GP-11 验证结果](./issue-GP-11-status-carrier-hit-resolution.md)；关联 [GP-12](./issue-GP-12-player-actor-engine.md)。
代码仓日志 `logs/input/20260908-003545.log`：16 条守卫判据中 2 失败，实际为同一个启动判据失败及其 16/17 汇总。
本轮隔离用户目录复现 `logs/input/20260908-010623.log`，仍为摇杆小幅漂移判据失败、输入 16/17，HUD 26/26。

## 依赖

既有 UI-7 输入门面与 UI-8 HUD 探针；本条通过前不推进 GP-12。

## 验收标准

- [x] 复现并记录原失败，不把六步门禁通过扩大为输入通过。
- [x] 明确根因并用变更前后运行证实，保留原有漂移阈值及判据。
- [x] 输入与 HUD 探针串扰可被自动守卫拦截，真实缺陷形状自证通过。
- [x] 输入专项、相关 HUD 回归、代码六步门禁与文档检查通过。

## 实现笔记

### 设计决策

Main 原本同时启动 InputProbe 和 WorldSpaceProbe → CameraProbe → HudProbe；两个输入注入者共享 InputRouter 与全局 Input。HudProbe 注入左扳机 1.0 的帧与 InputProbe 的 0.3 漂移断言相邻。改为 InputProbe.Finished 后启动后续链，原 17 条输入判据全过；自证重新并行时被拦，确认根因为探针串扰而非漂移阈值错误。

守卫新增 check_probe_order 核输入完成在首条 HUD 判据之前，缺失日志也失败；selfcheck_input_map 增加原缺陷注入。run_local_check 将临时用户目录放工作区 temp，导出时只读复制本机模板，退出关闭编译服务器并删除目录。

### 偏离

本条独立修验收底座，不属 GP-12 玩法实现。Main 的原有验收节点均保留。

### 权衡

不采用等待固定帧数：窗口/headless 的 HUD 步骤不同，固定延时不能约束共享输入的所有权。

### 待确认

硬件手柄行为及 GP-12 手感未验证；GP-12 尚未实现，不代勾作者确认。

### 评审

两仓未提交 diff 按八维核查：共享状态调度已串行；签名仅新增完成事件，无输入绑定变化；正常完成事件只发一次并配对解绑；不新增每帧分配或阻塞；本地入口限制工具路径及清理目录；命名对应实际行为；原缺陷自证与 HUD 回归补齐；复用现有完成事件模式、不新造调度框架。接受编译服务器锁导致清理失败的发现，关闭服务器后清理已成功。否决调高漂移阈值：日志与对照运行证明并非阈值缺陷。尚未证明所有启动异常路径或真实手柄输入隔离。

## 验证结果

| 命令 | 结果 | 判定 |
| --- | --- | --- |
| `python tools/run_local_check.py check_input_map.py`（代码仓） | `20260908-010623.log` 输入 16/17、HUD 26/26；临时用户目录已删除 | 原失败复现 |
| `python tools/run_local_check.py check_input_map.py` | `20260908-011515.log`：16 判据 0 失败，输入 17/17 | 修复后通过；新增顺序判据随后由自证复验 |
| `python tools/run_local_check.py selfcheck_input_map.py` | `selfcheck-20260908-011827.log`：10/10 缺陷被拦，检查函数 7/7，还原后全绿 | 通过 |
| `python tools/run_local_check.py check_hud.py` | `logs/hud/20260908-011901/summary.log`：14 判据 0 失败，启动 28/28 | 真窗口通过，不代表手感认可 |
| `python tools/run_local_check.py verify.py` | `logs/verify/20260908-012702/summary.md`：6/6，247/247，0 错误警告，导出 88 条无泄漏 | 通过 |
| `python tools/check_docs.py`（设计仓） | 67 文档、0 FAIL；学习文档 807 行软警告 | 沿 DOC-4 查阅型文档理由保留 |

第一次隔离构建的清理因编译器占用失败，目录 `temp/local-check-v77t8iyk` 已由 `python tools/run_local_check.py --clean local-check-v77t8iyk` 删除。首次全门禁因隔离 APPDATA 缺导出模板失败（`20260908-011922`），本地入口补复制模板后重跑通过。不清理作者 `temp/art-inbox`。未提交、未推送。
