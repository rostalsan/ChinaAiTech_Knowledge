// 展示层中文映射（与 config/app-tree.yaml、classify.md 的 id 对应）
export const TYPE_CN = {
  news: '新闻', paper: '论文', project: '项目', tutorial: '教程', opinion: '观点', '-': '待整理'
}

export const APP_CN = {
  coding: 'AI编程与开发',
  embodied: '具身智能与机器人',
  algo: '算法优化',
  content: '内容与创作',
  research: '科研与AI4S',
  office: '办公与生产力',
  consumer: '个人助理与消费产品',
  vertical: '行业垂直应用',
  infra: '算力与基础设施',
  safety: '安全与治理',
  news: '日常新闻'
}

export const appNames = (ids) => (ids || []).map((i) => APP_CN[i] || i)
