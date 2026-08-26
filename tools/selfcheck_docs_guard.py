#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_docs.py 的自证脚本（WORKFLOW §6）。

为什么存在：改了守卫必须自证，否则可能出现「跑得过但什么都没检查」的假阴性 ——
那比守卫失效更坏，因为它让人以为有护栏。手工自证每次都要重做一遍，所以做成入口。

做法：对每条规则**造一个真实缺陷形状的违反**（不是伪造断言），跑真的
check_docs.py，确认它判失败且报错指向正确位置，然后改回来确认恢复通过。

覆盖量自报：脚本会枚举 check_docs.py 里所有 `check_*` 函数，任何一条既不在
COVERED 也不在 EXEMPT 里就判失败 —— 这样新增检查却不自证会被当场拦住。

用法（从设计仓根目录运行）：
    python tools/selfcheck_docs_guard.py
    python tools/selfcheck_docs_guard.py --keep-going   # 失败后继续跑完剩余用例
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "tools" / "check_docs.py"
LEDGER = ROOT / "spec" / "issues" / "README.md"
CHANGELOG = ROOT / "archive" / "history" / "变更日志归档.md"
WORKFLOW = ROOT / "WORKFLOW.md"

# 临时文件统一用这个前缀，万一脚本被强杀，残留一眼能看出来。
TMP = "zz-selfcheck-temp"

# 本脚本实际造过违反的检查函数
COVERED = {
    "check_front_matter",
    "check_quota",
    "check_cells",
    "check_single_ledger",
    "check_issue_ids",
    "check_links",
    "check_archive_boundary",
}
# 明确不自证的，必须写理由 —— 留空理由等于没豁免
EXEMPT = {
    "check_reachable": "只产出 WARN，不影响退出码；造违反无法与真实的「新文档忘接入」区分",
}

FRONT = "---\ntype: {t}\nstatus: active\nowner: project\nlast_verified: 2026-08-26\n---\n\n# 自证临时文件\n"


class Failure(Exception):
    pass


def run_checker() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(CHECKER)],
        cwd=ROOT, capture_output=True,
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace")


@contextmanager
def patched(path: Path, new_text: str):
    """临时替换文件内容，退出时**一定**还原（含异常路径）。"""
    original = path.read_bytes() if path.exists() else None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
        yield
    finally:
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(original)


def expect_fail(name: str, expected: str, results: list) -> None:
    code, out = run_checker()
    if code == 0:
        results.append((name, False, "检查器返回 0，没有拦住这个违反"))
        return
    if expected not in out:
        results.append((name, False, f"拦住了但报错不对，期望包含「{expected}」"))
        return
    results.append((name, True, ""))


# ── 用例 ────────────────────────────────────────────────────────────────

def case_quota_by_rel_workflow(results: list) -> None:
    """配额按相对路径索引：WORKFLOW.md 行数硬上限 200。"""
    text = WORKFLOW.read_text(encoding="utf-8") + "\n" + "\n".join(f"填充第 {i} 行" for i in range(120))
    with patched(WORKFLOW, text):
        expect_fail("配额·WORKFLOW.md 行硬上限", "超过硬上限 200", results)


def case_quota_by_rel_ledger(results: list) -> None:
    """配额按相对路径索引：台账行数硬上限 250。台账叫 README.md，
    按文件名索引时这条会误伤所有 README，所以必须验它命中的是路径。"""
    text = LEDGER.read_text(encoding="utf-8") + "\n" + "\n".join(f"填充第 {i} 行" for i in range(300))
    with patched(LEDGER, text):
        expect_fail("配额·台账行硬上限", "超过硬上限 250", results)


def case_quota_spec_prefix(results: list) -> None:
    """spec/ 下 type: workdoc 走 250／350 配额。"""
    target = ROOT / "spec" / f"{TMP}-prd.md"
    body = "\n".join(f"填充第 {i} 行" for i in range(400))
    with patched(target, FRONT.format(t="workdoc") + body):
        expect_fail("配额·spec/ 工作文档行硬上限", "超过硬上限 350", results)


def case_quota_default_not_hijacked(results: list) -> None:
    """反向验证：spec/ 之外的普通文档不该被 350 行卡住（普通配额是 600／900）。
    这条防的是「前缀判断写宽了，把整库都按工作文档收紧」。"""
    target = ROOT / "reference" / f"{TMP}-normal.md"
    body = "\n".join(f"填充第 {i} 行" for i in range(400))
    with patched(target, FRONT.format(t="reference") + body):
        code, out = run_checker()
        if code != 0 and "超过硬上限 350" in out:
            results.append(("配额·普通文档未被误收紧", False, "普通文档被按 350 行判了失败"))
        else:
            results.append(("配额·普通文档未被误收紧", True, ""))


def case_cells_ledger(results: list) -> None:
    """台账逐格 360 字符。"""
    text = LEDGER.read_text(encoding="utf-8") + f"\n| `ZZ-9` | 低 | 自证 | {'超长备注' * 100} |\n"
    with patched(LEDGER, text):
        expect_fail("逐格·台账 360 字符", "超过 360", results)


def case_cells_changelog(results: list) -> None:
    """变更日志逐格 220 字符。"""
    text = CHANGELOG.read_text(encoding="utf-8") + f"\n| 2026-08-26 | 自证 | {'超长结论' * 100} | — |\n"
    with patched(CHANGELOG, text):
        expect_fail("逐格·变更日志 220 字符", "超过 220", results)


def case_cells_other_readme_untouched(results: list) -> None:
    """反向验证：别的 README.md 不受 360 字符限制。
    这条直接对着「CELL_LIMITS 曾按文件名索引」那个缺陷形状。"""
    target = ROOT / "design" / "README.md"
    text = target.read_text(encoding="utf-8") + f"\n| 列一 | {'超长内容' * 100} |\n"
    with patched(target, text):
        code, out = run_checker()
        if code != 0 and "超过 360" in out:
            results.append(("逐格·其他 README 未被误伤", False, "非台账的 README 被按 360 字符判了失败"))
        else:
            results.append(("逐格·其他 README 未被误伤", True, ""))


def case_ledger_missing(results: list) -> None:
    """唯一台账缺失必须判失败，不是静默跳过。"""
    text = LEDGER.read_text(encoding="utf-8").replace("type: backlog", "type: index", 1)
    with patched(LEDGER, text):
        expect_fail("台账·缺失判失败", "唯一待办台账缺失", results)


def case_ledger_duplicate(results: list) -> None:
    """出现第二个 type: backlog 必须判失败。"""
    target = ROOT / "reference" / f"{TMP}-ledger.md"
    with patched(target, FRONT.format(t="backlog")):
        expect_fail("台账·第二份判失败", "出现第二个待办台账", results)


def case_type_status_rejected(results: list) -> None:
    """type: status 已从允许值移除（动态状态页取消，ADR-0006）。"""
    target = ROOT / "reference" / f"{TMP}-status.md"
    with patched(target, FRONT.format(t="status")):
        expect_fail("文件头·type: status 已不允许", "不在允许值内", results)


def case_broken_link(results: list) -> None:
    """断链。"""
    target = ROOT / "reference" / f"{TMP}-link.md"
    with patched(target, FRONT.format(t="reference") + "\n[指向不存在的文件](./这个文件不存在.md)\n"):
        expect_fail("断链", "断链", results)


def case_dangling_issue_id(results: list) -> None:
    """引用台账里没有的编号必须判失败。

    这条对着真实缺陷形状：2026-08-26 发现 ADR-0005 引用 `ENG-1`、人物.md 引用
    `NR-3`，两个编号台账里都没有，而当时没有任何机制能发现。
    """
    target = ROOT / "reference" / f"{TMP}-id.md"
    body = "本条待办见 `ENG-4093`。\n"
    with patched(target, FRONT.format(t="reference") + body):
        expect_fail("编号·引用不存在的编号", "台账里没有的编号", results)


def case_issue_id_in_code_fence(results: list) -> None:
    """反向验证：围栏代码块里的示例编号不该被当成断号。
    技能与模板用围栏块举例（`ENG-5：……`），误判会让示例没法写。"""
    target = ROOT / "reference" / f"{TMP}-fence.md"
    body = "示例输出：\n\n```\nENG-4093：这是示例，不是真引用\n```\n"
    with patched(target, FRONT.format(t="reference") + body):
        code, out = run_checker()
        if code != 0 and "台账里没有的编号" in out:
            results.append(("编号·围栏块内示例未被误判", False, "围栏块里的示例编号被当成了断号"))
        else:
            results.append(("编号·围栏块内示例未被误判", True, ""))


def case_archive_boundary(results: list) -> None:
    """归档件文首 20 行必须自证只读边界。"""
    target = ROOT / "archive" / f"{TMP}-archived.md"
    text = "---\ntype: archive\nstatus: archived\nowner: project\nlast_verified: 2026-08-26\n---\n\n# 没写边界的归档件\n"
    with patched(target, text):
        expect_fail("归档·文首必须写只读边界", "只读边界", results)


CASES = [
    case_quota_by_rel_workflow,
    case_quota_by_rel_ledger,
    case_quota_spec_prefix,
    case_quota_default_not_hijacked,
    case_cells_ledger,
    case_cells_changelog,
    case_cells_other_readme_untouched,
    case_ledger_missing,
    case_ledger_duplicate,
    case_dangling_issue_id,
    case_issue_id_in_code_fence,
    case_type_status_rejected,
    case_broken_link,
    case_archive_boundary,
]


def check_coverage(results: list) -> None:
    """枚举 check_docs.py 的检查函数，确认每条都被自证或明确豁免。"""
    sys.dont_write_bytecode = True   # 别在 tools/ 里落 __pycache__
    spec = importlib.util.spec_from_file_location("check_docs_probe", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    # 必须先登记进 sys.modules 再执行：check_docs 里的 @dataclass 会通过
    # sys.modules[cls.__module__] 反查命名空间，没登记时拿到 None 直接崩。
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    found = {n for n in dir(mod) if n.startswith("check_") and callable(getattr(mod, n))}
    unproven = sorted(found - COVERED - set(EXEMPT))
    stale = sorted((COVERED | set(EXEMPT)) - found)
    ok = True
    if unproven:
        results.append(("覆盖量·全部检查已自证", False,
                        f"这些检查没有自证用例也没写豁免理由：{unproven}"))
        ok = False
    if stale:
        results.append(("覆盖量·无过期登记", False,
                        f"COVERED/EXEMPT 里登记了不存在的检查：{stale}"))
        ok = False
    if ok:
        results.append((f"覆盖量·{len(found)} 条检查全部已自证或已豁免", True, ""))
    print(f"[..] check_docs.py 共 {len(found)} 条检查："
          f"自证 {len(COVERED & found)} 条，豁免 {len(set(EXEMPT) & found)} 条")
    for name, reason in EXEMPT.items():
        print(f"     豁免 {name}：{reason}")


def main() -> int:
    ap = argparse.ArgumentParser(description="check_docs.py 自证")
    ap.add_argument("--keep-going", action="store_true", help="失败后继续跑完剩余用例")
    args = ap.parse_args()

    print("[..] 自证前先确认基线干净")
    code, out = run_checker()
    if code != 0:
        print("[FAIL] 基线本身就不干净，先修掉再自证 —— 否则分不清是用例造的还是本来就有的：")
        print(out)
        print("EXIT=1")
        return 1
    print("[OK] 基线 0 FAIL")

    results: list[tuple[str, bool, str]] = []
    for case in CASES:
        case(results)
        if not results[-1][1] and not args.keep_going:
            break

    check_coverage(results)

    print("\n[..] 还原后复验基线")
    code, out = run_checker()
    restored = code == 0
    if not restored:
        print("[FAIL] 还原后基线不干净，说明用例留下了残留：")
        print(out)
    else:
        print("[OK] 基线已还原，0 FAIL")

    print(f"\n{'用例':<44}{'结果'}")
    print("-" * 78)
    for name, passed, why in results:
        print(f"{name:<44}{'通过' if passed else 'FAIL  ' + why}")
    print("-" * 78)

    failed = [r for r in results if not r[1]]
    total = len(results) + 1
    passed_n = len(results) - len(failed) + (1 if restored else 0)
    print(f"\n结果：{total} 项断言，{passed_n} 通过，{len(failed) + (0 if restored else 1)} 失败")
    if failed or not restored:
        print("EXIT=1")
        return 1
    print("[OK] 守卫自证通过")
    print("EXIT=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
