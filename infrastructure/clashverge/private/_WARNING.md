# ⚠ PRIVATE — NEVER MAKE THIS REPO PUBLIC

This directory contains **actual** Clash Verge credentials:
- Proton VPN OpenVPN username/password (in `proxies:` block of `LProtonCrypto.yaml`)
- WgetCloud paid subscription URL with access token (in `proxy-providers:`)
- Personal proxy server endpoints

**If repo is ever made public, ALL credentials leak.**

## How to use on Windows

1. Install Clash Verge Rev: `winget install --id ClashVergeRev.ClashVergeRev`
2. Copy `LProtonCrypto.yaml` to `%APPDATA%\io.github.clash-verge-rev.clash-verge-rev\profiles\`
3. Copy `clash-verge-main.yaml` to `%APPDATA%\io.github.clash-verge-rev.clash-verge-rev\clash-verge.yaml`
4. Restart Clash Verge → it auto-imports.
5. Enable Tun mode (Settings → Tun Mode → ON).

## Verify

```powershell
curl --max-time 5 -o $null -w "fapi: %{http_code}`n" https://fapi.binance.com/fapi/v1/exchangeInfo
# Expect 200
```

## Rotation policy

If credentials leaked or you suspect compromise:
1. Proton dashboard → Account → Reset OpenVPN credentials → update `LProtonCrypto.yaml`
2. WgetCloud dashboard → Generate new subscription URL → update yaml
3. `cd D:\BWE && git pull` on all machines using these
