# -*- coding: utf-8 -*-
"""把整理会话（LLM）的判定写入 data/queue/classified.jsonl。

从 stdin 读紧凑判定行，格式（| 分隔，topics 用逗号）：
  序号|item_type|value_score|topic1,topic2|takeaway
例：
  0|news|2|industry|OpenAI 宣布 28 天内发新品
  3|project|5|agent,engineering|开源 Agent 评测框架

序号与 cview.py 打印的全局序号一致（同批次参数下解析）。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
from cview import load_rows, select


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--size", type=int, default=50)
    ap.add_argument("--guess", default=None)
    ap.add_argument("--max-days", type=int, default=None)
    args = ap.parse_args()
    rows = select(load_rows(), args.guess, args.max_days)
    out_path = lib.QUEUE_DIR / "classified.jsonl"
    written, bad = 0, []
    with out_path.open("a", encoding="utf-8", newline="\n") as out:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 5:
                bad.append(f"字段不足: {raw[:60]}")
                continue
            try:
                n = int(parts[0])
                r = rows[n]
            except (ValueError, IndexError):
                bad.append(f"序号越界: {raw[:60]}")
                continue
            topics = [t for t in parts[3].split(",") if t]
            rec = {
                "uid": r["uid"], "item_type": parts[1], "value_score": int(parts[2]),
                "takeaway": parts[4], "topics": topics, "project_seed": None,
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
    print(json.dumps({"written": written, "bad": bad}, ensure_ascii=False))


if __name__ == "__main__":
    main()
