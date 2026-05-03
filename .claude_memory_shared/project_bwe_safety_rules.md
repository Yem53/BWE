---
name: BWE AutoResearch 安全边界
description: BWE 项目对 AutoResearch agent 的硬性禁止行为和数据治理规则
type: project
originSessionId: 9aa9a58b-6062-4d43-83be-5004328027b2
---
**BWE AutoResearch 的硬性禁令** —— 任何在 BWE 项目下工作的 agent 都必须严守：

**Why:** 这是一个生产级金融交易研究项目，用户明确要求所有研究全程 sandbox-only，避免任何形式的真实资金风险或敏感凭证泄露。

**How to apply:** 在 BWE 上下文中工作时，遇到以下任何操作必须立刻拒绝并提示用户：

## 严格禁止
1. 读取或输出任何 API key、token、secret、credential
2. 修改 live autotrader 的任何配置文件
3. 调用 Binance/OKX 下单或撤单 endpoint（即便是测试网，未经显式确认也不允许）
4. 自动切换 live 策略
5. 把"历史最高收益候选"直接推荐为 live —— 必须经 paper shadow + 人工确认

## 数据治理
- 所有 LLM/Codex 输入的样本必须脱敏（去掉 user id、order id、IP）
- 写入磁盘的报告必须落在 `runs/<run_id>/` 目录，不污染主代码树
- 每次实验必须有 `reject_log.csv` 记录被淘汰候选及原因

## 评分原则
**稳定性优先于绝对收益**。主排序键是 stability_score，不是 mean_return。任何"为了 leaderboard 排名而过拟合"的行为都要在 Risk Critic 阶段被识别和淘汰。
