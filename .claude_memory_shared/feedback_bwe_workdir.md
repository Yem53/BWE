---
name: BWE 工作目录约定
description: 用户要求所有 BWE 相关操作以 H:\BWE 为主目录，并使用 claude-mem + superpowers 两个插件
type: feedback
originSessionId: 9aa9a58b-6062-4d43-83be-5004328027b2
---
**主目录优先 H:\BWE，操作不要散到 H:\ 根目录其他位置。**

**Why:** 用户在 2026-04-26 明确表示"主要的操作都在这个文件夹里面进行"，并已把 BWE 项目按规范组织成 9 个编号子目录（00_PROJECT_REQUIREMENTS、20_CODE、30_DATA、40_EXPERIMENTS、50_ANALYSIS_REPORTS、60_NEXT_ROUND、90_SOURCE_POINTERS、99_ADMIN）+ README.md + 中文导航.md。散乱写到 H:\ 根目录或其他位置会破坏这个组织结构。

**How to apply:**
- 任何 BWE 相关的代码、实验产物、报告、配置默认写到 H:\BWE 下对应编号目录
- 实验产物 → 40_EXPERIMENTS/<run_id>/
- 分析报告 → 50_ANALYSIS_REPORTS/
- 下一轮规划 → 60_NEXT_ROUND/
- 不要在 H:\ 根目录创建新的 BWE_* 平级目录（H:\BWE_autoresearch、H:\BWE_data_backups 是已有的，可以继续用，但新增内容默认进 H:\BWE）
- 当不确定该写到哪个编号子目录时，先读 H:\BWE\README.md 和 H:\BWE\中文导航.md 确认

**插件偏好：**
用户希望使用 `claude-mem@thedotmack` 和 `superpowers@superpowers-marketplace` 两个插件。它们提供的 skill（如 `/brainstorm`、`/execute-plan`、`/write-plan`、`/mem-search`、`/smart-explore` 等）只在新启动的会话里才会出现在可用列表中——如果当前会话看不到它们，提醒用户重启 Claude Code。
