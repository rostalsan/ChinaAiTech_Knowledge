# ChinaAiTech_Knowledge · AI 知识库采集系统

双源采集（机器之心 × 新智元）→ 三层去重 → SQLite 主档 → 知识生成层 → Web 双脉络看板。
一套"脚本做例行工作、LLM 只做人工触发判断"的个人 AI 资讯知识库流水线。

> 本仓库**只包含程序代码与配置体系**，不含任何已抓取的文章数据、知识库内容与个人配置。
> 合规声明见文末。

## 功能特性

- **双源采集**：新智元走 WordPress REST API 直连（含全文、无反爬）；机器之心走公共阅读器代理 → 站内 API → sitemap 兜底的多级降级链
- **增量采集**：先查本地存量（uid 比对），整页无新文章即停止翻页；正文只补抓缺失项
- **三层去重**：同源 uid 硬去重 + 标题归一化指纹 + 跨源事件归并
- **知识生成**：价值分关键词预筛、主题库/新闻快讯/GitHub 速查自动生成、应用分类加权打标（标题 4 > 摘要 2 > 全文 1，单主分类 + 置信门槛 + 零命中兜底）
- **Web 看板**（Express + Vue3）：主题知识树（13 节点 × 7 阶段）、时间线 × 应用分类（11 列，按主分类归列不跨列重复）、全文阅读、人工审阅打标（多选 chip + 锁定防机器覆盖）
- **每日对表检查**：库内最新 / 源上最新 / 今天 三时点比对，对不上即报警

## 架构

```
采集层(Python, 每日定时)
  collect_aiera.py (WP API) ─┐
  collect_jiqizhixin.py (代理降级链) ┴→ dedup → SQLite 主档(kb.db) + data/fulltext/*.md
                                             │
构建层(Python)                     build_kb.py ┤→ kb/ 生成层(INDEX/快讯/主题库/GitHub速查/HTML树)
                                             └→ export_web.py → web/server/data/*.json
服务层(Node/Express, 8787)        /api/overview|articles|topics|apptree|article + /fulltext
前端层(Vue3+Vite)                 首页(双脉络入口) + 主题知识树 + 时间线×应用 + 人工审阅 + 全文抽屉
```

## 快速开始

```bash
# 0) 环境自检（Python ≥3.10、Node ≥18，按提示补齐）
python scripts/env_check.py
pip install -r requirements.txt
cd web && npm install && cd ..

# 1) 跑一轮采集验证（数据从零开始积累；报告结尾 fresh_check 两源应 OK）
python scripts/run_all.py

# 2) 构建看板并启动
cd web && npm run build && cd ..
node web/server/index.js
# 浏览器打开 http://localhost:8787
```

Windows 下也可直接双击根目录 `启动看板.bat`。

## 食用说明 · 用 AI Agent 快速上手（推荐）

本项目为 **AI Agent 友好**设计：流程入口统一（`scripts/run_all.py`）、规则全部配置化（`config/*.yaml`）、整理 SOP 内置（`config/classify.md`、`config/curate-sop.md`）——你不需要记住任何命令，用 **Codex、ZCode、WorkBuddy、Claude Code** 等 Agent 工具在项目根目录打开，说人话即可驱动整条流水线：

| 你对 Agent 说 | Agent 会做 |
|---|---|
| 「拉起本项目，跑一轮采集验证」 | 环境自检 `env_check.py` → 补装依赖 → `run_all.py` → 汇报两源对表结果 |
| 「更新知识库」 | 触发整理会话：逐篇分类判定 → 入库 → 重写知识树/学习计划/项目清单 → 播报 |
| 「启动本地看板」 | `node web/server/index.js` 起服务并验证 8787 端口 |
| 「这次采集有几篇没抓到正文？」 | 查询主档欠账队列并解释原因（如通道故障、限速退避） |
| 「帮我把 XX 源停掉/调慢采集」 | 改 `config/sources.yaml`（`enabled` / `*_delay_seconds`） |

**上手建议**：

1. 首次让 Agent 先读一遍 `README.md` 与 `scripts/env_check.py`，它会自己发现缺什么、装什么；
2. 日常只需要三句话：「采集」「更新知识库」「开看板」；
3. Agent 需要可执行 shell 命令的权限（Codex CLI / ZCode 默认具备）；涉及联网采集请在你自己授权的环境里运行；
4. `config/` 里的每个 YAML 都是"改配置即改行为"，让 Agent 帮你调参比手改更稳（它会顺带跑通验证）。

## 目录结构

```
scripts/          采集(collect_*)/去重(dedup)/构建(build_kb)/导出(export_web)/
                  入库(ingest_*)/对表检查(fresh_check)/环境自检(env_check)/总入口(run_all)
config/
  sources.yaml    信息源与采集参数（回填窗口、限速、各源 API）
  tree.yaml       主题知识树骨架（13 节点 × 7 阶段，stage=先后 requires=前置）
  app-tree.yaml   应用分类体系（11 域关键词 + 位置加权打分规则 + 兜底域）
  classify.md     LLM 分类与价值判定标准
  curate-sop.md   「更新知识库」整理会话 SOP
web/              看板（Express 后端 + Vue3 前端）
启动看板.bat      Windows 一键启动（端口检测防重复、自动开浏览器）
```

数据目录（`data/`、`kb/`、`learning/`、`reports/`）由脚本在首次采集后自动生成，已在 `.gitignore` 中排除，不入库。

## 设计原则

1. **增量优先**：采集先对本地存量，只拉增量；构建全流程幂等，可重复重建
2. **降级链内置**：单源通道失效自动切换备用通道，并在报告中如实标记
3. **成本分层**：采集/打标/重建全部脚本化零成本；LLM 只在人工触发的整理会话中出场做判定
4. **人工优先**：人工打标带锁定属性，机器重分类永不覆盖

## 合规声明

- 本工具仅用于**个人本地学习**，抓取的文章数据存储于本地、不入版本库、不对外分发
- 文章版权归原作者及原媒体（机器之心、新智元）所有
- 采集遵守基本礼貌策略（限速、UA 标识、仅增量）；如源站提出异议请停止对相应源的采集（`config/sources.yaml` 中 `enabled: false` 即可）
- 本项目与机器之心、新智元官方无任何关联

## 作者说明

- **作者 / 维护者**：[@rostalsan](https://github.com/rostalsan)
- **项目缘起**：作者长期订阅机器之心与新智元两个公号，一周上百篇 AI 资讯无从管理——信息不缺，缺的是把信息串成脉络的那根线。本仓库是这条流水线的程序部分：采集归档是电费级成本，知识组织交给规则体系，AI 判定只在人工触发的整理环节出场
- **开发方式**：与 AI 结对开发（ZCode），从立项到可用约一周；分类规则体系由人工校准样本反向迭代
- **交流**：Issue 与 PR 欢迎；采集源适配、分类策略讨论尤其欢迎

## 更新日志

### v1.0.0（2026-10-12）

首个公开版本。

- 双源采集：新智元 WP API 直连 / 机器之心多级降级链（jina → Playwright → sitemap），增量比对本地存量
- **机器之心正文抓取 Playwright 回落通道**：jina 失效时浏览器会话内直fetch站点单篇 API，命中 WAF 挑战页自动重载重试（本版本核心特性，jina 长时间故障期间实测补齐全部欠账）
- 知识构建：价值分预筛、主题库/新闻快讯/GitHub 速查自动生成、应用分类位置加权打标（单主分类 + 置信门槛 + 兜底域）
- Web 看板：主题知识树 / 时间线×应用分类双脉络视图、全文阅读、人工审阅打标（锁定防机器覆盖）

## License

本项目以 [MIT License](LICENSE) 开源发布。

Copyright (c) 2026 rostalsan。保留版权所有许可声明的前提下，任何人可免费获取、使用、修改与再分发本软件；软件按"现状"提供，不附带任何担保。
