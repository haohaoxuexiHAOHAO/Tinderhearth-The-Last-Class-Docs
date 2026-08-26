#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""本机 Godot 工具链安装器：下载 → 校验 SHA512 → 解压 → 装导出模板 → 体检。

为什么存在：升引擎是会重复做的多步操作（取四个包、核官方校验和、解压两个编辑器、
把导出模板放进 Godot 用户目录、再确认真能启动报出版本号）。手敲命令每次都可能漏掉
校验或把模板放错目录，所以按 WORKFLOW §5「命令与提交纪律」做成 Python
入口，多步逻辑在 Python 里直接干活，不回头调 PowerShell。

版本基线见 decisions/ADR-0005-技术基线.md。本机安装位置不进版本库；日志由本脚本
自己写 UTF-8 到 <install-root>/setup_godot.log，不依赖 shell 重定向。

用法（从设计仓根目录运行）：
    python tools/setup_godot.py --check
        只体检：列已解压的编辑器版本、已安装的导出模板与已缓存的包，不下载。
    python tools/setup_godot.py --version 4.7.2
        装指定版本；已在本地且 SHA512 对得上的包不重下，模板齐全就不重装。
    python tools/setup_godot.py --version 4.7.2 --std-templates
        额外安装标准版（非 .NET）导出模板；默认只装 .NET 版，与技术基线一致。
    python tools/setup_godot.py --version 4.7.2 --force
        无视本地缓存与已装内容，重下重装。
    python tools/setup_godot.py --prune 4.7
        列出属于旧版本的编辑器、模板包与已装导出模板（预演，不删）。
    python tools/setup_godot.py --prune 4.7 --yes
        真删。守卫：删完必须还剩至少一个编辑器和一套导出模板，否则拒绝执行。

输出约定（与 check_docs.py 一致）：固定 UTF-8；每步打 [OK]/[SKIP]/[..]/[FAIL]；
末尾打显式摘要与一行 EXIT=。有任何 FAIL 时退出码为 1。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    # 被 hook 或重定向调用时默认编码可能不是 UTF-8，打第一个中文就崩。
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_INSTALL_ROOT = Path(r"D:\godot\4-7")
RELEASE_BASE = "https://github.com/godotengine/godot/releases/download"
SUMS_NAME = "SHA512-SUMS.txt"
CHUNK = 1 << 20  # 1 MiB
HEADERS = {"User-Agent": "tinderhearth-setup-godot/1"}
TPL_PREFIX = "templates/"  # .tpz 内部固定的顶层目录名
MIB = 1024 * 1024


# ── 输出与日志 ────────────────────────────────────────────────────────
class Report:
    """打屏 + 自己写 UTF-8 日志。"""

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.lines: list[str] = []
        self.fails: list[str] = []

    def say(self, text: str = "") -> None:
        print(text, flush=True)
        self.lines.append(text)

    def ok(self, text: str) -> None:
        self.say(f"[OK]   {text}")

    def skip(self, text: str) -> None:
        self.say(f"[SKIP] {text}")

    def step(self, text: str) -> None:
        self.say(f"[..]   {text}")

    def fail(self, text: str) -> None:
        self.fails.append(text)
        self.say(f"[FAIL] {text}")

    def flush(self) -> None:
        """追加而不覆盖：一次失败的运行不该冲掉上一次成功安装的证据。"""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        body = "\n".join(self.lines)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(f"\n# ── setup_godot.py  {stamp} ──\n{body}\n")


# ── 官方包名与校验和 ──────────────────────────────────────────────────
def asset_names(version: str) -> dict[str, str]:
    """本机（Windows x86-64）需要的四个官方包。"""
    return {
        "editor_std": f"Godot_v{version}-stable_win64.exe.zip",
        "editor_mono": f"Godot_v{version}-stable_mono_win64.zip",
        "tpl_std": f"Godot_v{version}-stable_export_templates.tpz",
        "tpl_mono": f"Godot_v{version}-stable_mono_export_templates.tpz",
    }


def parse_sums(raw: bytes) -> dict[str, str]:
    table: dict[str, str] = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 128:
            table[parts[1].lstrip("*")] = parts[0].lower()
    return table


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def sha512_of(path: Path) -> str:
    h = hashlib.sha512()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path, expect: str, rep: Report, force: bool) -> bool:
    """下到 .part、边下边算 SHA512、只有校验通过才改名落位。"""
    if dest.exists() and not force:
        if sha512_of(dest) == expect:
            rep.skip(f"本地已有且校验通过：{dest.name}")
            return True
        rep.step(f"本地文件校验不符，重新下载：{dest.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / (dest.name + ".part")
    h = hashlib.sha512()
    got = 0
    started = time.time()
    next_mark = 10.0
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            rep.step(f"下载 {dest.name}（{total / MIB:.0f} MiB）")
            with tmp.open("wb") as out:
                while True:
                    block = resp.read(CHUNK)
                    if not block:
                        break
                    out.write(block)
                    h.update(block)
                    got += len(block)
                    if total and got / total * 100 >= next_mark:
                        rep.step(
                            f"  {dest.name} {got / total * 100:5.1f}% "
                            f"({got / MIB:.0f}/{total / MIB:.0f} MiB)"
                        )
                        next_mark += 10
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        rep.fail(f"下载失败 {dest.name}：{exc}")
        tmp.unlink(missing_ok=True)
        return False
    digest = h.hexdigest()
    if digest != expect:
        rep.fail(
            f"SHA512 不符 {dest.name}：官方 {expect[:16]}…，实得 {digest[:16]}…"
        )
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    rep.ok(
        f"下载并校验通过：{dest.name}"
        f"（{got / MIB:.0f} MiB，{time.time() - started:.0f}s）"
    )
    return True


# ── 解压编辑器 ────────────────────────────────────────────────────────
def extract_editor(
    zip_path: Path, install_root: Path, rep: Report, force: bool
) -> Path | None:
    """解压到 <install_root>/<去掉 .zip 的包名>/，与本机既有布局保持一致。"""
    dest = install_root / zip_path.name[: -len(".zip")]
    if dest.is_dir() and not force:
        exes = list(dest.rglob("*.exe"))
        if exes:
            rep.skip(f"编辑器已解压：{dest.name}（{len(exes)} 个 exe）")
            return dest
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(dest)
    except (zipfile.BadZipFile, OSError) as exc:
        rep.fail(f"解压失败 {zip_path.name}：{exc}")
        return None
    exes = sorted(p.name for p in dest.rglob("*.exe"))
    rep.ok(f"解压编辑器到 {dest}（exe：{'、'.join(exes) or '无'}）")
    return dest


# ── 安装导出模板 ──────────────────────────────────────────────────────
def _complete(dest: Path, want: dict[str, int]) -> list[str]:
    """返回缺失或大小不符的相对路径列表。"""
    bad = []
    for rel, size in want.items():
        target = dest / rel
        if not target.is_file() or target.stat().st_size != size:
            bad.append(rel)
    return bad


def install_templates(
    tpz: Path, templates_root: Path, rep: Report, force: bool
) -> Path | None:
    """把 .tpz 里的 templates/ 铺到 %APPDATA%/Godot/export_templates/<version.txt>/。

    目录名取自包内 version.txt，不靠猜；落盘后逐个核对文件大小并自报覆盖量。
    """
    try:
        with zipfile.ZipFile(tpz) as z:
            members = [n for n in z.namelist() if not n.endswith("/")]
            stray = [n for n in members if not n.startswith(TPL_PREFIX)]
            if stray:
                rep.fail(
                    f"{tpz.name} 有 {len(stray)} 个成员不在 {TPL_PREFIX} 下，"
                    f"包布局与预期不符：{stray[:3]}"
                )
                return None
            try:
                version_dir = z.read(TPL_PREFIX + "version.txt").decode("utf-8").strip()
            except KeyError:
                rep.fail(f"{tpz.name} 缺 {TPL_PREFIX}version.txt，无法确定安装目录名")
                return None
            dest = templates_root / version_dir
            want = {
                n[len(TPL_PREFIX) :]: z.getinfo(n).file_size for n in members
            }
            if dest.is_dir() and not force and not _complete(dest, want):
                rep.skip(f"导出模板已完整：{dest}（{len(want)} 个文件）")
                return dest
            rep.step(f"铺开 {len(want)} 个模板文件到 {dest}")
            dest.mkdir(parents=True, exist_ok=True)
            for name in members:
                target = dest / name[len(TPL_PREFIX) :]
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(name) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out, CHUNK)
    except (zipfile.BadZipFile, OSError) as exc:
        rep.fail(f"安装模板失败 {tpz.name}：{exc}")
        return None
    bad = _complete(dest, want)
    if bad:
        rep.fail(
            f"模板落盘不完整：{dest} 有 {len(bad)} 项缺失或大小不符，例如 {bad[:3]}"
        )
        return None
    rep.ok(f"安装导出模板：{dest}（{len(want)} 个文件，逐个核对大小通过）")
    return dest


# ── 体检 ──────────────────────────────────────────────────────────────
def editor_version(editor_dir: Path) -> str:
    """用带控制台的 exe 取版本号；GUI 版 exe 在 Windows 上不接标准输出。"""
    console = sorted(editor_dir.rglob("*_console.exe"))
    if not console:
        return "（无 *_console.exe，取不到版本）"
    try:
        out = subprocess.run(
            [str(console[0]), "--version"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"（执行失败：{exc}）"
    lines = (out.stdout or out.stderr or "").strip().splitlines()
    return lines[-1].strip() if lines else "（无输出）"


def verify_editor(editor_dir: Path, expect_prefix: str, rep: Report) -> None:
    line = editor_version(editor_dir)
    if line.startswith(expect_prefix):
        rep.ok(f"{editor_dir.name} --version → {line}")
    else:
        rep.fail(
            f"{editor_dir.name} --version 打出 {line!r}，"
            f"不以 {expect_prefix!r} 开头"
        )


def do_check(install_root: Path, templates_root: Path, rep: Report) -> None:
    rep.say(f"安装根目录：{install_root}")
    editors = sorted(p for p in install_root.glob("Godot_v*") if p.is_dir())
    if not editors:
        rep.say("  （无已解压的编辑器）")
    for d in editors:
        rep.say(f"  {d.name} → {editor_version(d)}")

    rep.say(f"导出模板目录：{templates_root}")
    installed = (
        sorted(p for p in templates_root.iterdir() if p.is_dir())
        if templates_root.is_dir()
        else []
    )
    if not installed:
        rep.say("  （无已安装的导出模板）")
    for d in installed:
        files = [p for p in d.rglob("*") if p.is_file()]
        size = sum(p.stat().st_size for p in files)
        rep.say(f"  {d.name} → {len(files)} 个文件，{size / MIB:.0f} MiB")

    tpz_dir = install_root / "export_template"
    rep.say(f"模板包缓存：{tpz_dir}")
    packs = sorted(tpz_dir.glob("*.tpz")) if tpz_dir.is_dir() else []
    if not packs:
        rep.say("  （无）")
    for p in packs:
        rep.say(f"  {p.name} → {p.stat().st_size / MIB:.0f} MiB")


# ── 清理旧版本 ────────────────────────────────────────────────────────
def path_size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(q.stat().st_size for q in p.rglob("*") if q.is_file())


def find_prunable(
    version: str, install_root: Path, templates_root: Path
) -> list[Path]:
    """列出属于某个版本的本机产物。

    匹配串带上 `-stable` / `.stable` 分隔符，所以 `4.7` 不会误命中 `4.7.2`：
    `Godot_v4.7-stable` 不是 `Godot_v4.7.2-stable` 的前缀，`4.7.stable` 也不是
    `4.7.2.stable` 的前缀。
    """
    editor_prefix = f"Godot_v{version}-stable"
    tpl_prefix = f"{version}.stable"
    found: list[Path] = []
    if install_root.is_dir():
        found += sorted(install_root.glob(f"{editor_prefix}*"))
        for sub in ("_download", "export_template"):
            d = install_root / sub
            if d.is_dir():
                found += sorted(d.glob(f"{editor_prefix}*"))
    if templates_root.is_dir():
        found += sorted(
            p for p in templates_root.iterdir()
            if p.is_dir() and p.name.startswith(tpl_prefix)
        )
    return found


def do_prune(
    version: str,
    install_root: Path,
    templates_root: Path,
    rep: Report,
    confirmed: bool,
) -> None:
    doomed = find_prunable(version, install_root, templates_root)
    rep.say(f"清理目标版本：Godot {version}")
    if not doomed:
        rep.skip(f"本机没有属于 {version} 的编辑器、模板包或已装导出模板")
        return

    # 守卫：不许把本机清空。命中集合之外必须还剩编辑器和导出模板。
    doomed_set = set(doomed)
    kept_editors = [
        p for p in install_root.glob("Godot_v*")
        if p.is_dir() and p not in doomed_set
    ]
    kept_templates = (
        [p for p in templates_root.iterdir() if p.is_dir() and p not in doomed_set]
        if templates_root.is_dir()
        else []
    )
    total = 0
    for p in doomed:
        size = path_size(p)
        total += size
        rep.say(f"  {'目录' if p.is_dir() else '文件'}  {p}  {size / MIB:.0f} MiB")
    rep.say(f"  合计 {total / MIB:.0f} MiB")
    rep.say(
        f"删完剩余：编辑器 {len(kept_editors)} 份"
        f"（{'、'.join(p.name for p in kept_editors) or '无'}）／"
        f"导出模板 {len(kept_templates)} 套"
        f"（{'、'.join(p.name for p in kept_templates) or '无'}）"
    )
    if not kept_editors or not kept_templates:
        rep.fail("拒绝清理：删完本机就没有可用的编辑器或导出模板了")
        return
    if not confirmed:
        rep.say("")
        rep.say("以上是预演，什么都没删。确认无误后加 --yes 才真删。")
        return

    for p in doomed:
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        except OSError as exc:
            rep.fail(f"删不掉 {p}：{exc}")
    left = [p for p in doomed if p.exists()]
    if left:
        rep.fail(f"{len(left)} 项仍然存在，例如 {left[:3]}")
        return
    rep.ok(f"已删除 {len(doomed)} 项，腾出 {total / MIB:.0f} MiB")


# ── 主流程 ────────────────────────────────────────────────────────────
def do_install(args: argparse.Namespace, templates_root: Path, rep: Report) -> None:
    version: str = args.version
    tag = f"{version}-stable"
    names = asset_names(version)
    zip_dir = args.install_root / "_download"
    tpz_dir = args.install_root / "export_template"

    rep.say(f"目标版本：Godot {version}（release tag {tag}）")
    rep.say(f"安装根目录：{args.install_root}")
    rep.say(f"导出模板目录：{templates_root}")
    rep.say("")

    sums_url = f"{RELEASE_BASE}/{tag}/{SUMS_NAME}"
    try:
        sums = parse_sums(http_get(sums_url))
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        rep.fail(f"取不到官方校验和 {sums_url}：{exc}")
        return
    absent = [n for n in names.values() if n not in sums]
    if absent:
        rep.fail(
            f"官方 {SUMS_NAME} 里没有这些包名，版本号可能写错：{absent}"
        )
        return
    rep.ok(
        f"取到官方 {SUMS_NAME}（覆盖 {len(sums)} 个包），"
        f"本次需要的 4 个包名全部在表内"
    )

    targets = {
        "editor_std": zip_dir / names["editor_std"],
        "editor_mono": zip_dir / names["editor_mono"],
        "tpl_std": tpz_dir / names["tpl_std"],
        "tpl_mono": tpz_dir / names["tpl_mono"],
    }
    for key, dest in targets.items():
        url = f"{RELEASE_BASE}/{tag}/{dest.name}"
        if not download(url, dest, sums[names[key]], rep, args.force):
            rep.fail("下载或校验未通过，后续步骤跳过")
            return

    rep.say("")
    std_dir = extract_editor(targets["editor_std"], args.install_root, rep, args.force)
    mono_dir = extract_editor(targets["editor_mono"], args.install_root, rep, args.force)

    rep.say("")
    installed: list[Path] = []
    tpl = install_templates(targets["tpl_mono"], templates_root, rep, args.force)
    if tpl:
        installed.append(tpl)
    if args.std_templates:
        tpl = install_templates(targets["tpl_std"], templates_root, rep, args.force)
        if tpl:
            installed.append(tpl)
    else:
        rep.skip(
            f"未安装标准版导出模板（基线是 .NET 版；要装加 --std-templates）："
            f"{targets['tpl_std'].name} 已缓存在 {tpz_dir}"
        )

    rep.say("")
    if std_dir:
        verify_editor(std_dir, f"{version}.stable", rep)
    if mono_dir:
        verify_editor(mono_dir, f"{version}.stable.mono", rep)

    rep.say("")
    rep.say("── 摘要 ──")
    rep.say(f"编辑器：{std_dir.name if std_dir else '标准版失败'}"
            f" / {mono_dir.name if mono_dir else '.NET 版失败'}")
    rep.say(
        "已装导出模板："
        + ("、".join(p.name for p in installed) if installed else "无")
    )
    rep.say(f"模板包缓存：{tpz_dir}")
    rep.say(f"编辑器包缓存：{zip_dir}")
    rep.say("旧版本未删除，需要清理时由作者确认后手动删。")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="按 ADR-0005 技术基线安装或升级本机 Godot 工具链"
    )
    ap.add_argument("--version", help="目标版本号，例如 4.7.2")
    ap.add_argument(
        "--install-root",
        type=Path,
        default=DEFAULT_INSTALL_ROOT,
        help=f"编辑器与模板包所在目录，默认 {DEFAULT_INSTALL_ROOT}",
    )
    ap.add_argument("--check", action="store_true", help="只体检本机现状，不下载")
    ap.add_argument(
        "--std-templates",
        action="store_true",
        help="额外安装标准版（非 .NET）导出模板，默认不装",
    )
    ap.add_argument("--force", action="store_true", help="无视缓存与已装内容重做")
    ap.add_argument("--prune", metavar="版本号", help="清理某个旧版本，默认只预演")
    ap.add_argument("--yes", action="store_true", help="配合 --prune 才真删")
    args = ap.parse_args()

    appdata = os.environ.get("APPDATA")
    if not appdata:
        print("[FAIL] 环境里没有 APPDATA，定位不到 Godot 用户目录")
        return 1
    templates_root = Path(appdata) / "Godot" / "export_templates"

    rep = Report(args.install_root / "setup_godot.log")
    if args.prune:
        do_prune(args.prune, args.install_root, templates_root, rep, args.yes)
    elif args.check or not args.version:
        if not args.version and not args.check:
            rep.say("没给 --version，按 --check 处理。")
        do_check(args.install_root, templates_root, rep)
    else:
        do_install(args, templates_root, rep)

    code = 1 if rep.fails else 0
    rep.say("")
    rep.say(f"EXIT={code}  FAIL={len(rep.fails)}")
    rep.flush()
    print(f"日志：{rep.log_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
