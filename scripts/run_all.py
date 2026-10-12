# -*- coding: utf-8 -*-
"""一键流水线：采集 → 去重 → 生成知识库与队列 → 日报。

用法：
  python scripts/run_all.py               # 每日增量（ZCode 每日自动化调用这个）
  python scripts/run_all.py --backfill    # 采集时带回填语义
  python scripts/run_all.py --skip-aiera / --skip-jiqizhixin / --skip-dedup
  python scripts/run_all.py --ingest      # 先合并 classified.jsonl（整理会话收尾可用）
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
import build_kb
import collect_aiera
import collect_jiqizhixin
import dedup
import yaml


def write_report(s: dict) -> Path:
    p = lib.REPORTS_DIR / f"{lib.today_str()}.md"
    lines = []
    if not p.exists():
        lines += [f"# 采集报告 · {lib.today_str()}", ""]
    lines.append(f"## {lib.now_str()[11:16]} 运行")
    a, j, d, k = s["aiera"], s["jiqizhixin"], s["dedup"], s["kb"]
    if a.get("skipped"):
        lines.append(f"- 新智元：跳过（配置禁用）")
    else:
        health = "" if a.get("healthy") else " ⚠ 健康异常"
        lines.append(f"- 新智元：模式 {a.get('mode')}，新增 {a.get('inserted', 0)}"
                     f"（页 {a.get('pages', 0)}，已存在 {a.get('exists', 0)}，跳过窗口外 {a.get('skipped_old', 0)}）{health}")
    if j.get("skipped"):
        lines.append("- 机器之心：跳过（配置禁用）")
    else:
        lines.append(f"- 机器之心：列表新增 {j.get('list_new', 0)} / 更新 {j.get('list_updated', 0)}；"
                     f"sitemap 新增 {j.get('sitemap_new', 0)}；全文补抓 {j.get('content_ok', 0)}"
                     f"（失败 {j.get('content_fail', 0)}，待补 {j.get('remaining', 0)}）；通道 {j.get('channels', {})}")
    lines.append(f"- 去重：处理 {d.get('processed', 0)}，新组 {d.get('groups_new', 0)}，"
                 f"并入已有组 {d.get('merged_into_existing', 0)}")
    lines.append(f"- 知识库：待分类 {k.get('pending_count', 0)} 篇；快讯 {k.get('months', 0)} 个月；"
                 f"主题库 {k.get('topic_files', 0)} 个节点")
    fr = s.get("fresh") or {}
    if fr.get("sources"):
        for fs in fr["sources"]:
            mark = "✓" if fs["status"] == "OK" else "⚠"
            lines.append(f"- {mark} 更新检查[{fs['source']}]：库内最新 {fs['db_latest'] or '无'} ｜ "
                         f"实时最新 {fs['live_latest'] or '探测失败'}({fs['live_channel']}) ｜ 今天 {fs['today']}"
                         + (f" ｜ {'；'.join(fs['warn'])}" if fs["warn"] else ""))
    errors = (a.get("errors") or []) + (j.get("errors") or [])
    if errors:
        lines.append("- ⚠ 异常：")
        lines += [f"  - {e}" for e in errors[:8]]
    lines.append("")
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return p


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--skip-aiera", action="store_true")
    ap.add_argument("--skip-jiqizhixin", action="store_true")
    ap.add_argument("--skip-dedup", action="store_true")
    ap.add_argument("--ingest", action="store_true", help="先合并 classified.jsonl")
    args = ap.parse_args()

    src = yaml.safe_load((lib.CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))
    summary = {}

    if args.skip_aiera or not src["aiera"]["enabled"]:
        summary["aiera"] = {"skipped": True}
    else:
        summary["aiera"] = collect_aiera.collect(backfill=args.backfill)

    if args.skip_jiqizhixin or not src["jiqizhixin"]["enabled"]:
        summary["jiqizhixin"] = {"skipped": True}
    else:
        summary["jiqizhixin"] = collect_jiqizhixin.collect(backfill=args.backfill)

    if args.ingest:
        import ingest_classified
        summary["ingest"] = ingest_classified.run()

    if args.skip_dedup:
        summary["dedup"] = {"skipped": True}
    else:
        summary["dedup"] = dedup.run()

    summary["kb"] = build_kb.rebuild()

    # 更新检查器：库内最新 vs 信息源实时最新 vs 今天
    try:
        import fresh_check
        summary["fresh"] = fresh_check.run()
    except Exception as e:  # noqa: BLE001
        summary["fresh"] = {"ok": None, "error": str(e)[:150]}

    report = write_report(summary)
    summary["report"] = str(report)

    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
