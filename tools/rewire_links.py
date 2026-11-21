"""删一批文档之前，把还活着的文档里指向它们的链接改掉（WORKFLOW §4「收尾」）。

用法（在设计仓根目录）：

    python tools/rewire_links.py <计划.json>            只打印要改什么，不写文件
    python tools/rewire_links.py <计划.json> --apply    照改

计划文件（UTF-8 JSON）：

    {
      "delete": ["canon/gameplay/战斗与关卡.md", "design/伤害系统.md", ...],
      "retarget": {
        "canon/gameplay/战斗与关卡.md": {
          "default": "../desc/战斗规则.md",
          "by_section": {"打击反馈": ["production/像素绘制原则.md", "战斗表现"]}
        }
      },
      "names": {"README.md": "总索引"}
    }

路径都相对设计仓根目录；`../desc/…` 指工作区根的 desc。`names` 给新目标起链接里显示的
名字（默认是文件名去掉扩展名，`README` 这种不好读的才需要写）；`by_section` 的节名写
`null` 表示只指到那份文件；`relabel` 列出按旧文档身份起的链接文字（例如「正典」），
改指时整个换成新目标的名字；`drop_leads` 列出「只是指过去」的句首（例如「理由在」）：
没有改指的链接前面紧挨着这几个字、后面紧跟句号或格末时，连这几个字整句删掉，
而不是留下一句「理由在条目文件」这样指向空处的话；`drop_trails` 列出紧跟在链接后面、
只为那条链接而写的标注（例如「（**历史背景·非依据**）」），链接变成纯文字时一起删掉。

每一处 `[文字](路径)`，路径落在 `delete` 里时：

- **有改指的**：先按旧节名找 `by_section`（键是旧节名里的一段），找不到用 `default`。
  链接文字是「旧文档名 · 节名」的，旧文档名换成新文档名；节名只有在新目标里真有那个
  标题或行首加粗小标题时才留下（用 check_docs 的同一个判法），否则只留新文档名 ——
  这样改完的链接一定过得了节名引用那条守卫。别的链接文字原样留着，只换路径。
- **没有改指的**：整个链接换成它的文字，不再是链接。

不碰 `decisions/`（ADR-0036：已接受的 ADR 冻结，断链不再修），也不碰要删的文件本身。
只改链接，不改别的字；一个文件里的改动全部算完再一次写回，UTF-8、LF。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_docs as cd  # noqa: E402  复用同一个链接正则与节名判法

ROOT = cd.ROOT
SKIP_PREFIXES = ("decisions/",)


def rel_to_root(p: Path) -> str | None:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None


def anchors_of(path: Path, cache: dict[Path, list[str]]) -> list[str]:
    if path not in cache:
        cache[path] = cd.section_anchors(path.read_text(encoding="utf-8")) if path.is_file() else []
    return cache[path]


def split_label(label: str) -> tuple[str, str | None]:
    """「文档 · 节名」拆成（文档, 节名）；没有分隔符时节名是 None。"""
    if cd.SECTION_SEP not in label:
        return label, None
    head, _, tail = label.partition(cd.SECTION_SEP)
    return head.strip(), tail.strip()


def bare(text: str) -> str:
    return text.replace("**", "").replace("`", "").strip()


def rewrite_label(label: str, old_stem: str, new_path: Path, new_stem: str, new_section: str | None,
                  cache: dict[Path, list[str]]) -> str:
    """改指之后的链接文字。保证「文档 · 节名」的节名在新目标里找得到，找不到就去掉节名。"""
    head, section = split_label(label)
    anchors = anchors_of(new_path, cache)

    def found(s: str | None) -> bool:
        return bool(s) and any(s in a for a in anchors)

    if bare(head) == old_stem:
        wrap = "`" if head.strip().startswith("`") else ""
        name = f"{wrap}{new_stem}{wrap}"
        want = new_section if new_section is not None else (bare(section) if section else None)
        return f"{name} {cd.SECTION_SEP} {want}" if found(want) else name
    if section is None:
        return label                      # 自定义的链接文字，原样留着
    if bare(section) == old_stem:          # 「分类 · 文档名」那种写法
        return f"{head} {cd.SECTION_SEP} {new_stem}"
    return label if found(bare(section)) else head


def plan_for(doc_path: Path, text: str, plan: dict, cache: dict) -> tuple[str, list[str]]:
    deleted = set(plan["delete"])
    retarget = plan.get("retarget", {})
    changes: list[str] = []
    out, last = [], 0
    for m in cd.MD_LINK_RE.finditer(text):
        label, target = m.group(1), m.group(2)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        rel = rel_to_root(doc_path.parent / target)
        if rel is None or rel not in deleted:
            continue
        old_stem = Path(rel).stem
        rule = retarget.get(rel)
        lead = next((w for w in plan.get("drop_leads", [])
                     if text.endswith(w, 0, m.start())), None)
        after = text[m.end():m.end() + 2].lstrip(" ")
        if rule is None and lead is not None and (after[:1] in ("。", "；", "|", "") or after.startswith("\n")):
            # 「理由在[条目文件](…)」这种只是指过去的一句：去处删了，整句一起删，不留一句空话
            start = m.start() - len(lead)
            end = m.end() + (1 if text[m.end():m.end() + 1] in ("。", "；") else 0)
            out.append(text[last:start])
            last = end
            line_no = text.count("\n", 0, m.start()) + 1
            changes.append(f"L{line_no}: {lead}{m.group(0)}  →  （整句删掉）")
            continue
        if rule is None:
            new = label
            trail = next((t for t in plan.get("drop_trails", []) if text.startswith(t, m.end())), None)
            if trail is not None:
                # 「[某份](…)（历史背景·非依据）」：链接没了，跟着它的那句标注也没了着落
                out.append(text[last:m.start()])
                out.append(new)
                last = m.end() + len(trail)
                line_no = text.count("\n", 0, m.start()) + 1
                changes.append(f"L{line_no}: {m.group(0)}{trail}  →  {new}")
                continue
        else:
            _, section = split_label(label)
            if section is None and bare(label) != old_stem:
                section = label            # 「[内容规模基准](…玩法定位.md)」：链接文字本身就是节名
            dest, new_section = rule["default"], None
            for key, (path, sec) in rule.get("by_section", {}).items():
                if section and key in bare(section):
                    dest, new_section = path, sec
                    break
            new_abs = (ROOT / dest).resolve()
            new_name = plan.get("names", {}).get(dest, Path(dest).stem)
            href = Path(os.path.relpath(new_abs, doc_path.parent.resolve())).as_posix()
            if bare(label) in plan.get("relabel", []):
                text_ = new_name           # 「[玩法正典](…)」这种按旧文档身份起的文字，换成新名字
            else:
                text_ = rewrite_label(label, old_stem, new_abs, new_name, new_section, cache)
            new = f"[{text_}]({href})"
        out.append(text[last:m.start()])
        out.append(new)
        last = m.end()
        line_no = text.count("\n", 0, m.start()) + 1
        changes.append(f"L{line_no}: {m.group(0)}  →  {new}")
    out.append(text[last:])
    return "".join(out), changes


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    apply = "--apply" in sys.argv[2:]
    missing = [p for p in plan["delete"] if not (ROOT / p).exists()]
    if missing:
        print("计划里有不存在的文件（已经删了？先核对）：", "、".join(missing))
        return 1
    deleted = set(plan["delete"])
    cache: dict[Path, list[str]] = {}
    files = touched = links = 0
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(".git/") or rel.startswith(SKIP_PREFIXES) or rel in deleted:
            continue
        files += 1
        text = p.read_text(encoding="utf-8")
        new_text, changes = plan_for(p, text, plan, cache)
        if not changes:
            continue
        touched += 1
        links += len(changes)
        print(f"== {rel}（{len(changes)} 处）")
        for c in changes:
            print("   ", c)
        if apply:
            p.write_text(new_text, encoding="utf-8", newline="\n")
    verb = "改了" if apply else "要改"
    print(f"\n扫了 {files} 份，{verb} {touched} 份里的 {links} 处链接")
    return 0


if __name__ == "__main__":
    sys.exit(main())
