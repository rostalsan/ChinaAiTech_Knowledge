# -*- coding: utf-8 -*-
"""规则兜底分类：把队列中 LLM 未单独判定的剩余文章按规则归为新闻。

用途：首次整理或积压清理时，避免无休止的 pending。规则条目 takeaway 带
【规则】前缀，value_score 固定 2，主题按标题关键词映射——后续整理会话可复核改判。

用法：python scripts/bulk_news.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
from cview import load_rows

TOPIC_RULES = [
    ("frontier", ["数学", "猜想", "定理", "证明", "诺奖", "诺贝尔", "菲尔兹", "物理", "量子", "弦论", "图论", "统计学"]),
    ("agent", ["Agent", "agent", "智能体", "Codex", "Claude Code", "编程", "写代码", "工作流", "MCP", "Skill", "Harn"]),
    ("embodied", ["机器人", "具身", "人形", "VLA", "无人车", "驾驶", "灵巧", "智驾", "机器狗"]),
    ("multimodal", ["视频", "图像", "世界模型", "语音", "音视频", "视觉", "渲染", "图片", "漫剧", "运镜", "游戏"]),
    ("inference", ["芯片", "算力", "GPU", "推理", "部署", "Token", "TPU", "算子", "显存", "量化", "LPU", "HBM"]),
    ("training", ["训练", "微调", "RL", "蒸馏", "后训练", "Scaling"]),
    ("engineering", ["提示词", "Prompt", "评测", "基准", "Benchmark", "安全", "工程"]),
    ("apps", ["办公", "客服", "教育", "医疗", "直播", "App", "应用", "产品", "浏览器"]),
    ("llm", ["GPT", "Claude", "Gemini", "Grok", "Kimi", "DeepSeek", "大模型", "模型", "Opus", "Sonnet", "Fable", "开源", "Qwen", "GLM", "豆包", "千问", "Llama", "MiniMax"]),
]


def guess_topics(title: str) -> list:
    for topic, kws in TOPIC_RULES:
        if any(k in title for k in kws):
            return [topic]
    return ["industry"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    classified_path = lib.QUEUE_DIR / "classified.jsonl"
    done = set()
    if classified_path.exists():
        for line in classified_path.open(encoding="utf-8"):
            line = line.strip()
            if line:
                done.add(json.loads(line).get("uid"))
    written = 0
    with classified_path.open("a", encoding="utf-8", newline="\n") as out:
        for r in load_rows():  # 队列 = 全部 pending 文章
            if r["uid"] in done:
                continue
            topics = guess_topics(r["title"] or "")
            # GitHub 硬规则：带仓库的文章不可能是普通新闻（classify.md）
            if r.get("github"):
                item_type, score, tag = "project", 3, "【规则·带仓库】"
            else:
                item_type, score, tag = "news", 2, "【规则】"
            takeaway = tag + (r["excerpt"] or r["title"] or "")[:40]
            rec = {
                "uid": r["uid"], "item_type": item_type, "value_score": score,
                "takeaway": takeaway, "topics": topics,
                "project_seed": None,
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
    print(json.dumps({"bulk_classified": written}, ensure_ascii=False))


if __name__ == "__main__":
    main()
