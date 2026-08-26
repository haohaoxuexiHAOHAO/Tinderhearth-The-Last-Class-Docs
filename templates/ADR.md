---
type: template
status: active
owner: project
last_verified: 2026-08-25
---

> **模板说明**：架构决策记录（Architecture Decision Record，简称 ADR）只记录影响多个系统、难以撤销或容易反复争论的取舍。小型实现细节留在代码、测试或提交说明中。

## 使用方法

1. 在 `decisions/` 新建 `ADR-NNNN-简短标题.md`，编号接在现有记录之后。
2. 把文件头改成下面的形状；`proposed` 表示待决定，作者确认后改为 `accepted`。
3. 如果新记录取代旧记录，在双方文件头写清 `supersedes` 与 `superseded_by`，不要让两条决定同时冒充现行规则。
4. 新增后在 [ADR 索引](../decisions/README.md) 加一行。

```yaml
type: adr
status: proposed
owner: project
last_verified: YYYY-MM-DD
decided: YYYY-MM-DD
supersedes: none
```

# ADR-NNNN：短标题

## 背景

用普通话说明问题、已有约束，以及不作决定会造成什么后果。只引用上游正典或现行规范，不复制整段背景。

## 候选

列出真正可选的方案。每项都写清收益、代价和被否决的原因，不设置假选项凑数。

## 决策

写明采用哪项、适用条件、边界和明确不包含的范围。项目专用词或英文缩写首次出现时给出中文解释。

## 后果

- 正面影响：
- 代价与风险：
- 落地要求：
- 验证方法：

只保留已经决定的事实。落地时的测试数量必须注明日期，并写出复现命令，避免历史数字被误读为现状。
