# Bootstrap Claude Code memory on Windows from H: drive shared folder.
# Run once when entering BWE Autoresearch on a new Claude Code install on Windows.
#
# Usage (in PowerShell):
#   cd H:\BWE
#   .\.claude_memory_shared\bootstrap_windows.ps1
#
# What it does:
#   1. Resolves the Claude Code project hash for the current cwd
#   2. Creates %USERPROFILE%\.claude\projects\<hash>\memory\ if missing
#   3. Copies all .md files from .claude_memory_shared\ into it
#   4. Reports what was synced

$ErrorActionPreference = "Stop"

$SharedDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $SharedDir

# Windows Claude Code project hash: typically e.g. "H--" for H:\
# Convert path separators: "H:\BWE" → "H--BWE"
$CwdHash = $ProjectRoot -replace '[\\/:]', '-' -replace '^-', '' -replace '-$', ''

$ClaudeProjectDir = Join-Path $env:USERPROFILE ".claude\projects\$CwdHash"
$ClaudeMemoryDir = Join-Path $ClaudeProjectDir "memory"

Write-Host "[bootstrap] cwd: $ProjectRoot"
Write-Host "[bootstrap] inferred Claude project hash: $CwdHash"
Write-Host "[bootstrap] target memory dir: $ClaudeMemoryDir"

New-Item -ItemType Directory -Force -Path $ClaudeMemoryDir | Out-Null

# If target already has files, prompt before overwriting
if ((Get-ChildItem $ClaudeMemoryDir -ErrorAction SilentlyContinue).Count -gt 0) {
    Write-Host "[bootstrap] WARNING: target already has files:" -ForegroundColor Yellow
    Get-ChildItem $ClaudeMemoryDir | Select-Object Name | Format-Table
    $confirm = Read-Host "Overwrite with H: drive shared memory? [y/N]"
    if ($confirm -notmatch '^[Yy]$') {
        Write-Host "[bootstrap] aborted"
        exit 1
    }
}

Copy-Item -Path "$SharedDir\*.md" -Destination $ClaudeMemoryDir -Force -Verbose

Write-Host ""
Write-Host "[bootstrap] done. Files synced:" -ForegroundColor Green
Get-ChildItem $ClaudeMemoryDir | Format-Table

Write-Host ""
Write-Host "[bootstrap] Going forward, every memory edit must write to BOTH:"
Write-Host "  - $ClaudeMemoryDir\<file>.md"
Write-Host "  - $SharedDir\<file>.md"
Write-Host ""
Write-Host "[bootstrap] Also CLAUDE.md at $ProjectRoot\CLAUDE.md is auto-loaded."
