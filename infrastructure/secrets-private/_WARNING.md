# 🚨 SECRETS — REPO MUST STAY PRIVATE 🚨

This directory contains **real credentials and authenticated session tokens**:

| File | Contains |
|---|---|
| `hermes.env` | Binance API keys, OKX API keys, Telegram bot tokens, Anthropic key, etc. |
| `hermes.env_bwe_v2` | Older BWE-specific keys (legacy) |
| `bwe_matrix_monitor_state.json` | Telegram MTProto session — anyone with this file can READ messages from your Telegram channels (BWE_OI_Price_monitor 等) |

## If repo goes public, IMMEDIATELY:

1. **Rotate all keys**:
   - Binance → API Management → Delete all + recreate
   - OKX → API Center → Delete all + recreate
   - Telegram bot → @BotFather → /revoke + new token
   - Anthropic → console.anthropic.com → Revoke + new
2. **Re-auth Telegram session**:
   - Telegram → Settings → Devices → Terminate all other sessions
   - Re-run `bwe_matrix_monitor.py` on a trusted machine

## Use on Windows

```powershell
# Copy to canonical Windows path
mkdir $env:USERPROFILE\.hermes\state -Force
copy D:\BWE\infrastructure\secrets-private\hermes.env $env:USERPROFILE\.hermes\.env
copy D:\BWE\infrastructure\secrets-private\bwe_matrix_monitor_state.json $env:USERPROFILE\.hermes\state\bwe_matrix_monitor_state.json
```

## Why these are committed despite being secrets

Repo owner (Yem53) explicitly chose to keep all bootstrap material in one place since:
- Repo is **PRIVATE**
- Only one user (Yem53) has access
- Convenience > security (acceptable trade-off for personal infra)

**Do NOT change visibility to Public.**
