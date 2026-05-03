# Day 2 进度报告（2026-04-26 evening）

## 总体状态：**代码层 100% 完成；运行验证 60% 完成**

| # | 任务 | 代码 | 单元测试 | 端到端 smoke |
|---|---|:-:|:-:|:-:|
| 2.3 | bwe_loop_score_metric.py | ✅ | ✅ 6 cases pass | — |
| 2.4 | bwe_loop_results.py | ✅ | ✅ 5 cases pass (keep×2/discard/crash/skip) | — |
| 2.2 | bwe_loop_gpu_eval.py | ✅ (含 self-test) | 🚫 阻塞 | 🚫 阻塞 |
| 2.1 | bwe_loop.py | ✅ | 🚫 阻塞 | 🚫 阻塞 |
| 2.5 | smoke_test_day2_loop.py | ✅ | — | 🚫 阻塞 |
| 额外 | Registry 扩到 520 | ✅ | ✅ 0 errors | — |

**Git commit**：`7b6c21d [BWE-Day2] code: gpu_eval kernel + score metric + results logger + loop wrapper + 520 archetypes`

## 阻塞原因（单一根因）

**`import torch` 在当前 Python 3.12.10 + pip 安装环境里 hang 住**，原因可能是：
1. 早期后台 `pip install --index-url cu128 torch==2.9.1` 命令半路被 Claude Code 的 sandbox 杀掉（所有 background python 都是 sandbox spawn 的临时进程）
2. 留下的 torch 文件系统状态污染了后续 import（即使删除 + 重装也复发）
3. 多次 reinstall 都"completed exit 0"但 `import torch` 仍 hang 在 native dll 加载阶段

**已验证的事实**：
- 删 site-packages\torch* 后 import 报 ModuleNotFoundError ✓（说明删除有效）
- pip install 看似完成但 import 又 hang ✓（说明安装有问题）
- `python -c "print('hello')"` 不依赖 torch 时正常 ✓
- 所有 Bash/PowerShell 启动的 python 都被算作 background task，sandbox 限时

## 已尝试且失败的修复

1. `pip install --upgrade torch==2.9.1 --index-url cu128`（CUDA 版）—— 后台任务被杀
2. `pip install --force-reinstall --no-cache-dir torch==2.9.0`—— 同上
3. `pip install --force-reinstall --no-deps --no-cache-dir torch==2.9.0`—— 同上
4. 手动删 `site-packages\torch*` + `pip install torch==2.9.0`—— 同上
5. 通过 `cmd.exe /c install.bat` 间接执行 —— log 文件 0 字节
6. PowerShell `Start-Process` —— 输出文件 0 字节
7. PowerShell `Tee-Object` —— log 不创建

## 推荐解决方案（**用户在终端里手动跑一次**）

在你自己的 PowerShell（**不是 Claude Code 内嵌**）里跑：

```powershell
cd H:\BWE\20_CODE\Autoresearch
python -m pip install --no-cache-dir --force-reinstall torch==2.9.0
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

如果 torch 装好了报 cuda False，那就再装 CUDA 版：
```powershell
python -m pip install --no-cache-dir --force-reinstall --index-url https://download.pytorch.org/whl/cu128 torch==2.9.1
python -m pip install numba
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

期望最后一行：`2.9.1+cu128 True`

**根本原因**：Claude Code 的 bash sandbox 给 background task 的存活时间太短，pip install torch（要下 ~200MB 然后解压几千个 dll）跑不完。手动终端跑就没限时。

## torch 装好后的验证清单（你跑一次）

```powershell
cd H:\BWE\20_CODE\Autoresearch
# 1. Kernel self-test (~15 sec)
python -m bwe_autoresearch.bwe_loop_gpu_eval

# 2. Loop wrapper smoke (synthetic, no git, no real data) (~10 sec)
python -m bwe_autoresearch.bwe_loop --synthetic --no-git --max-experiments 1

# 3. Day 2.5 真实数据 smoke (~30 sec)
python scripts/smoke_test_day2_loop.py
```

期望全部输出 `PASS`。

## 备用方案：用 uv（Karpathy 原始推荐）

如果直接 pip 还是问题，按 Karpathy 原项目用 uv：

```powershell
# 装 uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 重启终端
cd H:\BWE\20_CODE\Autoresearch
uv sync   # 用 pyproject.toml 自动建 .venv 装齐 deps
uv run python -m bwe_autoresearch.bwe_loop_gpu_eval
```

## Day 2 实际产出（可立即 review）

```
H:\BWE\20_CODE\Autoresearch\bwe_autoresearch\
  ├── bwe_loop.py                       (300 行 wrapper)
  ├── bwe_loop_gpu_eval.py              (~280 行 GPU kernel + self-test)
  ├── bwe_loop_results.py               (~250 行 + 5 case 自测)
  ├── bwe_loop_score_metric.py          (~200 行 + 6 case 自测)
  ├── bwe_loop_data_loader.py           (Day 1，已用)
  ├── hypothesis_registry_seed.py       (520 原型生成器)
  ├── coverage_map_gen.py               (5D 可视化)
  └── v6_complete_strategy.py           (修了 K 线路径 bug)

H:\BWE\20_CODE\Autoresearch\scripts\
  ├── smoke_test_kline_path_fix.py     (Day 1)
  └── smoke_test_day2_loop.py          (Day 2.5)

H:\BWE\40_EXPERIMENTS\
  ├── hypothesis_registry.jsonl        (520 行)
  └── coverage_map.html                (4.1 MB)
```

## 接下来可以做的事

1. **你修 torch**（5-10 分钟手动），然后跑上面 3 条验证命令 → Day 2 closure
2. **直接进 Day 3** —— LLM team debate 可以独立设计 + 测试，不依赖 torch（subprocess 调 `claude -p`）
3. **重启 Claude Code session** + 用 `--continue` 接着干 —— 新 session 没有这堆僵尸 python 进程

## 关键经验教训

- 在 Claude Code 内嵌 bash 里**不要**做长时间 pip 操作（>30 秒），用户终端跑更稳
- 安装 GPU 框架要用 uv 或独立终端，不要在 sandbox 里
