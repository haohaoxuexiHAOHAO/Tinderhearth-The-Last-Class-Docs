#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""系统文档可读性审计：术语覆盖 ＋ 句长分布 —— **只列不判**，退出码恒为 0。

为什么它不判对错：机器不知道哪个词是「自造的」。要判就得有一份普通词白名单，
而白名单是每写一份文档就补一格的债（`ENG-18` 留下的判断方向：守卫的默认面要是
「全部」）。句长同理 —— 量得出长度，判不出一句话通不通顺。所以本入口只把命中
列出来，判断留给人。

**它绿了不等于没问题。** 真正会报错的那几条在 `tools/check_docs.py` 里（`DOC-93`）：
术语节里的词必须在本页正文出现过、每张图旁有重画条件、图里的标签在正文找得到
（共用术语表随 ADR-0036 删了，游戏里的词以工作区根 desc 为准）。**句长那一条的上限要按
本入口报的分布来定**，定之前不许开成失败 —— 误报多的门禁会被绕过，而被绕过的门禁
比没有门禁更坏。

用法（从设计仓根目录运行）：
    python tools/audit_readability.py                  # 全部系统文档
    python tools/audit_readability.py 地块系统           # 只看一份（文件名可省「.md」）
    python tools/audit_readability.py --top 20         # 列最长的若干句
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
# **量法只有一份**：词条怎么取、句子怎么切、长度怎么算，都从守卫里拿。
# 本入口自己再写一份的话，这里列出来的分布就不是守卫判的那个量 ——
# 而定上限正是照这里的分布定的，两处分叉会让那个数失去依据。
from check_docs import (  # noqa: E402
    SENTENCE_LIMIT, prose_sentences, terms_section,
)

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"


def report_sentences(docs: dict[str, str], targets: list[str], top: int) -> None:
    all_len: list[tuple[int, str, str]] = []
    for name in targets:
        for _line, s in prose_sentences(docs[name]):
            all_len.append((len(s), name, s))
    if not all_len:
        print("\n句长：没有可量的正文句子")
        return
    lens = sorted(n for n, _, _ in all_len)

    def pct(p: float) -> int:
        return lens[min(len(lens) - 1, int(len(lens) * p))]

    print(f"\n── 句长分布（{len(lens)} 句）──")
    print(f"中位 {pct(0.5)}／P75 {pct(0.75)}／P90 {pct(0.90)}／P95 {pct(0.95)}"
          f"／P99 {pct(0.99)}／最长 {lens[-1]}")
    # 定上限就看这张表：把线放在「再往下调就要报一大片」的那个拐点上。
    # 候选档位**从分布本身算出来**，不写成一串字面值 —— 那串里只要出现守卫现在用的
    # 那个数，这个数就有了第二个家。
    print("\n候选上限 → 会报多少条（守卫现在的上限是 "
          f"{SENTENCE_LIMIT if SENTENCE_LIMIT else '尚未定'}）：")
    step = 10
    lo = max(step, (pct(0.90) // step) * step)
    hi = ((lens[-1] + step - 1) // step) * step
    for cand in range(lo, hi + step, step):
        over = sum(1 for n in lens if n > cand)
        print(f"  {cand:>4} 字：{over:>4} 条"
              f"（占 {over / len(lens) * 100:.2f}%，涉及 "
              f"{len({name for n, name, _ in all_len if n > cand})} 份）")
    print(f"\n最长 {top} 句（只列不判）：")
    for n, name, s in sorted(all_len, reverse=True)[:top]:
        print(f"  {n:>4} 字  {name}")
        print(f"        {s[:70]}…")


def main() -> int:
    docs = {p.stem: p.read_text(encoding="utf-8")
            for p in sorted(DESIGN.glob("*.md")) if p.name != "README.md"}

    argv = sys.argv[1:]
    top = 10
    if "--top" in argv:
        i = argv.index("--top")
        top = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    wanted = argv
    targets = [k for k in docs if not wanted or any(w.removesuffix(".md") == k for w in wanted)]
    if wanted and not targets:
        print(f"[FAIL] 没有匹配的文档：{wanted}（本入口不判定，但参数写错要说出来）")
        print("EXIT=0（只列不判）")
        return 0

    print(f"系统文档 {len(docs)} 份／本次看 {len(targets)} 份")

    no_section = []
    for name in targets:
        text = docs[name]
        body, own = terms_section(text)
        if not body:
            no_section.append(name)
            continue
        notes = []
        for t in own:
            if t not in text.replace(body, "", 1):
                notes.append(f"    {t:<10}只在术语节里出现，正文没用到")
        print(f"\n{name}：术语节 {len(own)} 条" + ("（无提示）" if not notes else ""))
        for line in notes:
            print(line)

    print("\n── 摘要 ──")
    print(f"没有「术语」节的：{len(no_section)} 份" + (f" → {'、'.join(no_section)}" if no_section else ""))

    report_sentences(docs, targets, top)

    print("\n本入口**只列不判**，上面的数字不是判定结果。会报错的那几条在 tools/check_docs.py。")
    print("EXIT=0（恒为 0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
