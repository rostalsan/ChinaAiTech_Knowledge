# -*- coding: utf-8 -*-
"""新机环境自检：python scripts/env_check.py

检查运行时版本、第三方包、数据完整性与前端产物，输出缺失项及修复命令。
全部必需项通过时退出码 0，可直接交付 ZCode/人工判断。
"""
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_MIN = (3, 10)
NODE_MIN = (18, 0)

# import 名 -> pip 包名
PKGS = {
    "requests": "requests",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "markdownify": "markdownify",
    "rapidfuzz": "rapidfuzz",
    "playwright": "playwright",
}


def ver_tuple(s):
    nums = re.findall(r"\d+", s or "")
    return tuple(int(x) for x in nums[:2]) if len(nums) >= 2 else (0, 0)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok = True
    rows = []

    # ---- Python ----
    py = sys.version_info[:2]
    py_ok = py >= PY_MIN
    rows.append((py_ok, f"Python {'.'.join(map(str, py))}",
                 "" if py_ok else f"需 ≥ {'.'.join(map(str, PY_MIN))}，请安装 Python"))

    # ---- 第三方包 ----
    missing = [pip for mod, pip in PKGS.items() if importlib.util.find_spec(mod) is None]
    rows.append((not missing, "Python 包：" + ("、".join(pip for pip in PKGS.values())),
                 f"缺 {'、'.join(missing)} → pip install -r requirements.txt" if missing else ""))

    # ---- Node ----
    node_bin = shutil.which("node")
    node_ver = None
    if node_bin:
        try:
            node_ver = ver_tuple(subprocess.run([node_bin, "--version"], capture_output=True, text=True).stdout)
        except OSError:
            node_ver = None
    rows.append((bool(node_ver and node_ver >= NODE_MIN),
                 f"Node {'.'.join(map(str, node_ver)) if node_ver else '未安装'}",
                 "" if node_ver and node_ver >= NODE_MIN else f"需 ≥ {'.'.join(map(str, NODE_MIN))}，看板服务与前端构建依赖 Node"))

    # ---- 数据完整性 ----
    for rel, desc, required in [
        ("data/kb.db", "主档数据库", True),
        ("data/fulltext", "全文目录", True),
        ("config/tree.yaml", "知识树骨架", True),
        ("config/app-tree.yaml", "应用分类骨架", True),
        ("config/curate-sop.md", "更新知识库 SOP", True),
        ("web/server/data/overview.json", "看板数据快照", True),
        ("web/dist/index.html", "前端构建产物（缺了可 npm run build 重建）", False),
        ("web/node_modules", "前端依赖（同系统可直接用；跨系统需 npm install）", False),
    ]:
        p = ROOT / rel
        rows.append((p.exists(), f"{rel}（{desc}）", "" if p.exists() else "缺失"))

    # ---- 输出 ----
    print("AI 知识库新机环境自检")
    print("=" * 56)
    fixes = []
    for passed, desc, fix in rows:
        mark = "✅" if passed else "❌"
        print(f"{mark} {desc}" + (f"  —— {fix}" if fix else ""))
        if not passed and fix:
            fixes.append(fix)
        ok = ok and passed
    print("=" * 56)
    if ok:
        # 可选项缺失给出提示但不影响通过
        print("必需项全部通过。下一步：")
        print("  python scripts/run_all.py          # 跑一轮采集验证（fresh_check 两源应 OK）")
        print("  node web/server/index.js           # 起看板 http://localhost:8787")
    else:
        print("存在缺失项，按上面的修复命令处理后重跑本脚本。")
        for f in fixes:
            print(f"  → {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
