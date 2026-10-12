# -*- coding: utf-8 -*-
"""合并人工审阅打标结果（data/queue/manual_tags.jsonl）到主档，并刷新 Web 快照。

看板「人工审阅」页保存时由 web/server 写队列后调用。幂等：逐行 UPDATE，后写覆盖先写。
行格式：{"uid": "...", "apps": ["research", "coding"], "lock": 1, "ts": "..."}
  - apps 为点选顺序（首选 = 主分类），最多 3 个，须为 app-tree.yaml 中的 id；
  - apps 为空数组且 lock=0 表示「解锁」：清空人工标签、回到待归类（机器可重新打标）；
  - app_lock=1 的文章在 build_kb 打标循环与全量重算中一律跳过（见 build_kb/lib 注释）。
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
import export_web

QUEUE = lib.QUEUE_DIR / "manual_tags.jsonl"
MAX_TAGS = 3


def load_app_ids() -> set:
    import yaml
    doc = yaml.safe_load((lib.CONFIG_DIR / "app-tree.yaml").read_text(encoding="utf-8"))
    return {a["id"] for a in doc.get("apps", [])}


def run(conn=None) -> dict:
    own = conn is None
    conn = conn or lib.init_db()
    stats = {"lines": 0, "applied": 0, "unlocked": 0, "invalid": 0, "errors": []}
    if QUEUE.exists():
        app_ids = load_app_ids()
        with QUEUE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                stats["lines"] += 1
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as e:
                    stats["invalid"] += 1
                    stats["errors"].append(f"JSON 解析失败：{str(e)[:80]}")
                    continue
                uid = str(rec.get("uid") or "")
                apps = rec.get("apps")
                if not uid:
                    stats["invalid"] += 1
                    continue
                if not isinstance(apps, list) or len(apps) > MAX_TAGS \
                        or any(a not in app_ids for a in apps):
                    stats["invalid"] += 1
                    stats["errors"].append(f"应用标签不合法：{uid}")
                    continue
                lock = 1 if rec.get("lock") else 0
                cur = conn.execute(
                    "UPDATE articles SET app_tags=?, app_lock=? WHERE uid=?",
                    (json.dumps([str(a) for a in apps], ensure_ascii=False), lock, uid),
                )
                if cur.rowcount == 0:
                    stats["invalid"] += 1
                    stats["errors"].append(f"未知 uid：{uid}")
                    continue
                if lock:
                    stats["applied"] += 1
                else:
                    stats["unlocked"] += 1
        conn.commit()
    export_web.run()  # 刷新 web/server/data 快照，看板下次请求即生效
    if own:
        conn.close()
    stats["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return stats


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(), ensure_ascii=False, indent=1))
