# -*- coding: utf-8 -*-
"""更新检查器：验证采集是否追上了信息源的最新内容。

对每个源对比三个时点：
  db_latest   主档里该源最新文章的发布日期
  live_latest 信息源此刻能看到的最新发布日期（实时探测）
  today       今天（北京时间）

判定：db_latest 落后 live_latest ≥1 天，或落后今天 ≥2 天 → WARN。
用法：python scripts/fresh_check.py   （run_all 末尾自动调用）
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
import collect_aiera
import collect_jiqizhixin
import yaml


def _days_ago(date_str: str) -> int | None:
    try:
        return (datetime.now(lib.CST).date() - datetime.strptime(date_str[:10], "%Y-%m-%d").date()).days
    except (ValueError, TypeError):
        return None


def _aiera_live(src: dict) -> str:
    posts = collect_aiera.fetch_posts(src["aiera"]["api"], src["user_agent"], 1, 1, 1)
    return (posts[0].get("date") or "")[:10] if posts else ""


def _jiqizhixin_live(src: dict) -> tuple[str, str]:
    cfg = src["jiqizhixin"]
    # 1) jina 列表接口
    try:
        items = collect_jiqizhixin.fetch_list_via_jina(cfg)
        return collect_jiqizhixin.parse_dt(items[0].get("publishedAt")), "jina"
    except Exception:
        pass
    # 2) 本机 Playwright 回落
    try:
        items = collect_jiqizhixin.fetch_list_via_playwright(cfg)
        return collect_jiqizhixin.parse_dt(items[0].get("publishedAt")), "playwright"
    except Exception:
        pass
    # 3) sitemap（每日 05:00 重建，最新 slug 日期即最新文章日）
    entries = collect_jiqizhixin.sitemap_entries(cfg, "2000-01-01")
    if entries:
        return max(d for _, d in entries), "sitemap"
    return "", "failed"


def run() -> dict:
    src = yaml.safe_load((lib.CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))
    today = lib.today_str()
    conn = lib.init_db()
    out = {"today": today, "sources": [], "ok": True}
    for sid, name in (("aiera", "新智元"), ("jiqizhixin", "机器之心")):
        row = conn.execute(
            "SELECT MAX(publish_date) m FROM articles WHERE source=? AND publish_date != ''", (sid,)
        ).fetchone()
        db_latest = (row["m"] or "")[:10] if row else ""
        try:
            if sid == "aiera":
                live, channel = _aiera_live(src), "wp-api"
            else:
                live, channel = _jiqizhixin_live(src)
        except Exception as e:  # noqa: BLE001
            live, channel = "", f"error({str(e)[:80]})"
        lag_live = _days_ago(db_latest) if db_latest else None
        live_lag = _days_ago(live) if live else None
        warn = []
        if live and db_latest and live > db_latest:
            warn.append(f"落后实时源 {live}")
        if lag_live is not None and lag_live >= 2:
            warn.append(f"库内最新已是 {lag_live} 天前")
        if not db_latest:
            warn.append("库内无日期")
        status = "WARN" if warn else "OK"
        if warn:
            out["ok"] = False
        out["sources"].append({
            "source": name, "db_latest": db_latest, "live_latest": live,
            "live_channel": channel, "today": today, "status": status, "warn": warn,
        })
    conn.close()
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(), ensure_ascii=False, indent=1))
