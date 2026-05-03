param(
  [Parameter(Mandatory=$true)][string]$Root,
  [Parameter(Mandatory=$true)][int]$BasePid,
  [Parameter(Mandatory=$true)][string]$Python,
  [Parameter(Mandatory=$true)][string]$WorkDir,
  [Parameter(Mandatory=$true)][string]$WatcherLog
)

$ErrorActionPreference = "Stop"

function Write-Log([string]$Message) {
  $line = "$(Get-Date -Format o) $Message"
  Add-Content -LiteralPath $WatcherLog -Value $line -Encoding UTF8
}

trap {
  try {
    Write-Log "FATAL $($_.Exception.Message)"
  } catch {
  }
  exit 99
}

function Get-DescendantProcessIds([int]$TargetPid) {
  $all = Get-CimInstance Win32_Process
  $children = @($all | Where-Object { $_.ParentProcessId -eq $TargetPid })
  $ids = @()
  foreach ($child in $children) {
    $ids += [int]$child.ProcessId
    $ids += Get-DescendantProcessIds -TargetPid ([int]$child.ProcessId)
  }
  return $ids
}

function Test-ProcessTreeAlive([int]$TargetPid) {
  $p = Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
  if ($p) { return $true }
  $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $TargetPid }
  if ($children) { return $true }
  return $false
}

function Get-LatestBaseRun([string]$RootPath) {
  Get-ChildItem -LiteralPath (Join-Path $RootPath "runs") -Directory |
    Where-Object { $_.Name -like "bwe_complete_strategy_v6_max_alpha_*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
}

function Test-BaseComplete([string]$RunDir) {
  $required = @(
    "run_summary.json",
    "complete_strategy_leaderboard.csv",
    "baseline_comparison.csv",
    "execution_cost_model.json",
    "fee_slippage_latency_stress.csv",
    "strategy_similarity_clusters.csv",
    "bootstrap_confidence_intervals.csv",
    "permutation_test_results.csv",
    "effective_sample_size_report.csv",
    "reject_log.csv",
    "future_safety_report.csv",
    "leaderboard_top200.md",
    "reject_cluster_summary.md",
    "llm_brief_round_1.md",
    "paper_forward_plan.md"
  )
  foreach ($name in $required) {
    $path = Join-Path $RunDir $name
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    if ((Get-Item -LiteralPath $path).Length -le 0) { return $false }
  }
  $summary = Get-Content -LiteralPath (Join-Path $RunDir "run_summary.json") -Raw | ConvertFrom-Json
  if ($summary.stage -ne "max_alpha") { return $false }
  if ([int64]$summary.coarse_eval_actual -lt 100000000) { return $false }
  if ([int64]$summary.medium_eval_actual -lt 1000000) { return $false }
  if ([int64]$summary.deep_eval_actual -lt 50000) { return $false }
  if ($summary.path_resolution -ne "1m_trade_kline") { return $false }
  if ($summary.paper_only -ne $true) { return $false }
  if ($summary.live_allowed -ne $false) { return $false }
  return $true
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $WatcherLog) | Out-Null
Write-Log "watcher started root=$Root base_pid=$BasePid"

while (Test-ProcessTreeAlive -TargetPid $BasePid) {
  $run = Get-LatestBaseRun -RootPath $Root
  if ($run) {
    $progressPath = Join-Path $run.FullName "checkpoints\max_alpha_progress.json"
    if (Test-Path -LiteralPath $progressPath) {
      $progress = Get-Content -LiteralPath $progressPath -Raw | ConvertFrom-Json
      Write-Log "base still running evaluated=$($progress.evaluated)/$($progress.coarse_eval) elapsed=$($progress.elapsed_seconds)"
    } else {
      Write-Log "base still running waiting_for_progress"
    }
  }
  Start-Sleep -Seconds 600
}

Write-Log "base process tree exited"
$baseRun = Get-LatestBaseRun -RootPath $Root
if (-not $baseRun) {
  Write-Log "ERROR no max_alpha base run directory found"
  exit 2
}

if (-not (Test-BaseComplete -RunDir $baseRun.FullName)) {
  Write-Log "ERROR base run did not pass completion audit: $($baseRun.FullName)"
  exit 3
}

$audit = [ordered]@{
  created_at = (Get-Date -Format o)
  base_run_dir = $baseRun.FullName
  base_complete = $true
  start_strong = $true
  strong_budget = "coarse=100000000,medium_top=5000000,deep=200000,stress=20000,portfolio=2000"
}
$audit | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Root "runs\max_alpha_base_completion_audit_before_strong.json") -Encoding UTF8
Write-Log "base completion audit passed: $($baseRun.FullName)"

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$strongLog = Join-Path $Root "runs\max_alpha_strong_run_$ts.out.log"
$strongErr = Join-Path $Root "runs\max_alpha_strong_run_$ts.err.log"
$args = @(
  "-m", "bwe_autoresearch.v6_complete_strategy",
  "--root", $Root,
  "max-alpha",
  "--medium-eval", "5000000",
  "--deep-eval", "200000",
  "--stress-eval", "20000",
  "--portfolio-eval", "2000",
  "--checkpoint-every", "1000000"
)
$proc = Start-Process -FilePath $Python -ArgumentList $args -WorkingDirectory $WorkDir -RedirectStandardOutput $strongLog -RedirectStandardError $strongErr -PassThru -WindowStyle Hidden
[ordered]@{
  Pid = $proc.Id
  Stage = "max_alpha_strong"
  Log = $strongLog
  Err = $strongErr
  Started = (Get-Date -Format o)
  Budget = $audit.strong_budget
  BaseRunDir = $baseRun.FullName
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Root "runs\max_alpha_strong_current_process.json") -Encoding UTF8
Write-Log "strong started pid=$($proc.Id) log=$strongLog"
