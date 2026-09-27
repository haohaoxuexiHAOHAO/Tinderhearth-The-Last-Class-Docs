#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把移进 archive/ 的过程件里那些相对链接按新位置重算深度。

为什么要这个入口：归档时文件从 `spec/` 移到 `archive/spec/<编号>-<slug>/`，目录深度变了，
于是每条 `../../design/X.md` 都少一级。这件事每归档一个需求就要做一次，所以它是
`tools/` 入口而不是现场命令（[WORKFLOW § 5](../WORKFLOW.md) 的命令纪律）。

它只改**深度**，不改链接指向谁：把解析不到的相对链接剥掉开头那串 `../`，拿剩下的部分
当仓库根下的路径试一次；试得到就按文件的新位置重算相对路径。**改名与重定向它不猜** ——
剥完仍然找不到的一律只报出来，留给人改。这条边界是有意的：猜错的链接看起来是好的。

用法（从设计仓根目录运行）：
    python tools/rebase_archive_links.py archive/spec/GP-76-attribute-payoff-rebalance
    python tools/rebase_archive_links.py <目录> --dry-run   # 只看会改什么，不写

退出码：0 全部解决；1 有解析不到的链接（连同清单一起打出来）。**退出码 0 不等于没事**，
还要看它自报的三个数：扫了几份、改了几处、剩几处没解决。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Markdown 行内链接。只认相对链接：带协议的、锚点开头的、绝对路径的都不碰。
LINK_RE = re.compile(r"\]\((?!https?://|#|/)([^)#]+?)(#[^)]*)?\)")


def rebase(text: str, doc: Path) -> tuple[str, list[tuple[str, str]], list[str]]:
    """返回（新正文, 改动列表, 解析不到的清单）。"""
    changed: list[tuple[str, str]] = []
    unresolved: list[str] = []

    def fix(m: re.Match[str]) -> str:
        target, anchor = m.group(1), m.group(2) or ""
        if (doc.parent / target).resolve().exists():
            return m.group(0)
        # 剥掉开头那串 `../`，拿剩下的当仓库根下的路径试一次。
        bare = re.sub(r"^(?:\.\./)+", "", target)
        if not (REPO / bare).exists():
            unresolved.append(target)
            return m.group(0)
        rel = (REPO / bare).resolve().relative_to(REPO)
        up = "../" * len(doc.resolve().parent.relative_to(REPO).parts)
        new = up + rel.as_posix()
        changed.append((target, new))
        return f"]({new}{anchor})"

    return LINK_RE.sub(fix, text), changed, unresolved


def main() -> int:
    ap = argparse.ArgumentParser(description="按新位置重算归档件里相对链接的深度")
    ap.add_argument("directory", help="归档目录，例如 archive/spec/GP-76-xxx")
    ap.add_argument("--dry-run", action="store_true", help="只打算改什么，不写文件")
    args = ap.parse_args()

    root = (REPO / args.directory).resolve()
    if not root.is_dir():
        print(f"[FAIL] 找不到目录 `{args.directory}`")
        print("EXIT=1")
        return 1

    docs = sorted(root.rglob("*.md"))
    if not docs:
        print(f"[FAIL] `{args.directory}` 下一份 .md 都没有，这一轮**没有执行**（不是通过）")
        print("EXIT=1")
        return 1

    fixed = 0
    leftovers: list[str] = []
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        new, changed, unresolved = rebase(text, doc)
        for old, now in changed:
            print(f"  {doc.relative_to(REPO).as_posix()}：`{old}` → `{now}`")
        for bad in unresolved:
            leftovers.append(f"{doc.relative_to(REPO).as_posix()}：`{bad}`")
        fixed += len(changed)
        if changed and not args.dry_run:
            # **必须显式 newline=""**：默认的文本模式会在 Windows 上把 `\n` 翻成 CRLF，
            # 而 `.gitattributes` 要 LF —— 写完整个仓库的行尾守卫就会报一片。
            with doc.open("w", encoding="utf-8", newline="") as fh:
                fh.write(new)

    print(f"\n覆盖量：扫了 {len(docs)} 份、改了 {fixed} 处"
          f"{'（--dry-run，没写）' if args.dry_run else ''}")
    if leftovers:
        print(f"[FAIL] {len(leftovers)} 处剥完 `../` 仍然解析不到，**本工具不猜**，留给人改：")
        for line in leftovers:
            print(f"  {line}")
        print("EXIT=1")
        return 1
    print("[OK] 没有解析不到的相对链接")
    print("EXIT=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
