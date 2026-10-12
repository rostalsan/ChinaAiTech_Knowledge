# -*- coding: utf-8 -*-
"""整理会话辅助视图：分批打印 data/queue/pending.jsonl。

用法：
  python scripts/cview.py --mode full --batch 0 --size 50            # 全部队列第 0 批（含正文）
  python scripts/cview.py --mode title --guess news --batch 1        # 只看 news 预判
  python scripts/cview.py --max-days 14 --batch 0                    # 只看最近 14 天

排序与 build_kb 生成队列时的顺序一致（publish_date 降序、id 降序），
capply.py 依赖同一顺序解析批次序号。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib


def load_rows() -> list:
    rows = [json.loads(l) for l in (lib.QUEUE_DIR / "pending.jsonl").open(encoding="utf-8")]
    rows.sort(key=lambda r: r["publish_date"], reverse=True)  # 稳定排序，保持文件内 id DESC
    return rows


def select(rows: list, guess: str | None, max_days: int | None) -> list:
    if max_days is not None:
        cutoff = (lib.datetime.now(lib.CST) - lib.timedelta(days=max_days)).strftime("%Y-%m-%d")
        rows = [r for r in rows if r["publish_date"] >= cutoff]
    if guess:
        rows = [r for r in rows if r["guess"] == guess]
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["title", "full"], default="title")
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--size", type=int, default=50)
    ap.add_argument("--guess", default=None)
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--text-len", type=int, default=1100)
    args = ap.parse_args()
    rows = select(load_rows(), args.guess, args.max_days)
    b = rows[args.batch * args.size:(args.batch + 1) * args.size]
    print(f"# batch={args.batch} size={args.size} guess={args.guess or 'all'} "
          f"max_days={args.max_days or 'all'} — 本批 {len(b)} / 共 {len(rows)}")
    for i, r in enumerate(b):
        n = args.batch * args.size + i
        print(f"[{n}] {r['uid']} | {r['publish_date']} | {r['source']} | {r['title']}")
        print(f"    摘要: {r['excerpt'][:200]}")
        if args.mode == "full":
            print(f"    正文: {r['text'][:args.text_len]}")


if __name__ == "__main__":
    main()
