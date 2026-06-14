#!/usr/bin/env python3
"""
Probe whether Binance tokenized stocks (bStocks) can be shorted, and via which path.

READ-ONLY. No orders, no transfers. Only queries instrument/market metadata.

Steps:
  1) Spot listing            (public)  GET api.binance.com/api/v3/exchangeInfo
  2) USDS-M perpetual        (public)  GET fapi.binance.com/fapi/v1/exchangeInfo
  3) COIN-M perpetual        (public)  GET dapi.binance.com/dapi/v1/exchangeInfo
  4) Margin (borrow-to-short, needs MARKET_DATA key, X-MBX-APIKEY only, no signature):
       - cross pairs    GET api.binance.com/sapi/v1/margin/allPairs
       - isolated pairs GET api.binance.com/sapi/v1/margin/isolated/allPairs
       - assets         GET api.binance.com/sapi/v1/margin/allAssets (isBorrowable)

NOTE: this probe only proves whether the *instrument/contract exists*, NOT whether
*your account* may trade it. bStocks are not offered to US users and carry
region/KYC limits; account-level permissions must be checked separately.
"""
import os
import sys
import json

import requests

TIMEOUT = 20

# Candidate tokenized-stock base symbols (all vs USDT). Focus = MRVLB.
CANDIDATES = ["MRVLB", "NVDAB", "MUB", "TSLAB", "SNDKB", "CRCLB"]
QUOTE = "USDT"

API_KEY = os.environ.get("BINANCE_API_KEY", "").strip()


def hr(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def get(url, headers=None, label=""):
    """GET wrapper with the error handling required by the task.

    Returns (data_or_None, status_code_or_None). Never raises out."""
    try:
        r = requests.get(url, headers=headers or {}, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"  [NETWORK ERROR] {label or url}: {e}")
        return None, None

    sc = r.status_code
    if sc == 200:
        try:
            return r.json(), sc
        except ValueError:
            print(f"  [PARSE ERROR] {label or url}: non-JSON 200 body")
            return None, sc

    # Required special-casing
    if sc == 451:
        print(f"  [451 region-restricted] {label or url}")
        print("    -> Likely IP geo-block (api.binance.com blocked in US / some regions).")
        print("    -> Retry from an allowed region, or use a regional domain "
              "(e.g. api.binance.us is a DIFFERENT product / not bStocks) or proxy.")
    elif sc in (401, 403):
        msg = ""
        try:
            msg = r.json().get("msg", "")
        except ValueError:
            msg = r.text[:200]
        print(f"  [{sc} auth/permission] {label or url}: x-mbx msg = {msg!r}")
        print("    -> Key permission or IP-whitelist issue. Continuing other checks.")
    else:
        body = ""
        try:
            body = r.json()
        except ValueError:
            body = r.text[:200]
        print(f"  [HTTP {sc}] {label or url}: {body}")
    return None, sc


# ---------------------------------------------------------------------------
# Step 1: Spot
# ---------------------------------------------------------------------------
def step1_spot():
    hr("STEP 1  Spot listing  (api.binance.com/api/v3/exchangeInfo)")
    data, sc = get("https://api.binance.com/api/v3/exchangeInfo", label="spot exchangeInfo")
    result = {c: None for c in CANDIDATES}   # symbol -> status string or None
    all_bstocks = []
    if not data:
        print("  Spot data unavailable; cannot determine spot listing.")
        return result, all_bstocks, sc

    symbols = data.get("symbols", [])
    print(f"  Total spot symbols returned: {len(symbols)}")

    for s in symbols:
        sym = s.get("symbol", "")
        base = s.get("baseAsset", "")
        quote = s.get("quoteAsset", "")
        status = s.get("status", "")
        # bStock heuristic: base asset ends with 'B' (tokenized equity tickers),
        # quote = USDT. We collect a broad view, then refine.
        if quote == QUOTE and base.endswith("B") and len(base) >= 3:
            all_bstocks.append((sym, base, status))
        if sym in result:
            result[sym] = status

    # Show the broad list for full visibility (may include non-stock noise).
    print(f"\n  All quote=USDT, base endswith 'B' symbols ({len(all_bstocks)}):")
    for sym, base, status in sorted(all_bstocks):
        print(f"    {sym:<14} base={base:<8} status={status}")

    print("\n  Candidate spot status:")
    for c in CANDIDATES:
        st = result[c]
        mark = "TRADING" if st == "TRADING" else (st or "NOT LISTED")
        print(f"    {c:<8} -> {mark}")
    return result, all_bstocks, sc


# ---------------------------------------------------------------------------
# Step 2: USDS-M perpetual
# ---------------------------------------------------------------------------
def step2_usdm():
    hr("STEP 2  USDS-M perpetual  (fapi.binance.com/fapi/v1/exchangeInfo)")
    data, sc = get("https://fapi.binance.com/fapi/v1/exchangeInfo", label="USDM exchangeInfo")
    result = {c: None for c in CANDIDATES}
    if not data:
        print("  USDS-M data unavailable.")
        return result, sc
    symbols = data.get("symbols", [])
    print(f"  Total USDS-M symbols: {len(symbols)}")
    by_base = {}
    for s in symbols:
        base = s.get("baseAsset", "")
        ctype = s.get("contractType", "")
        status = s.get("status", "")
        by_base.setdefault(base, []).append((s.get("symbol"), ctype, status))
    for c in CANDIDATES:
        hits = [h for h in by_base.get(c, []) if h[1] == "PERPETUAL"]
        result[c] = hits[0] if hits else None
        print(f"    {c:<8} -> {'PERPETUAL: ' + str(hits[0]) if hits else 'no perp'}")
    return result, sc


# ---------------------------------------------------------------------------
# Step 3: COIN-M perpetual
# ---------------------------------------------------------------------------
def step3_coinm():
    hr("STEP 3  COIN-M perpetual  (dapi.binance.com/dapi/v1/exchangeInfo)")
    data, sc = get("https://dapi.binance.com/dapi/v1/exchangeInfo", label="COINM exchangeInfo")
    result = {c: None for c in CANDIDATES}
    if not data:
        print("  COIN-M data unavailable.")
        return result, sc
    symbols = data.get("symbols", [])
    print(f"  Total COIN-M symbols: {len(symbols)}")
    by_base = {}
    for s in symbols:
        base = s.get("baseAsset", "")
        ctype = s.get("contractType", "")
        by_base.setdefault(base, []).append((s.get("symbol"), ctype))
    for c in CANDIDATES:
        hits = [h for h in by_base.get(c, []) if h[1] == "PERPETUAL"]
        result[c] = hits[0] if hits else None
        print(f"    {c:<8} -> {'PERPETUAL: ' + str(hits[0]) if hits else 'no perp'}")
    return result, sc


# ---------------------------------------------------------------------------
# Step 4: Margin (needs key)
# ---------------------------------------------------------------------------
def step4_margin():
    hr("STEP 4  Margin borrow-to-short  (sapi/v1/margin/*  needs MARKET_DATA key)")
    cross = {c: None for c in CANDIDATES}
    iso = {c: None for c in CANDIDATES}
    borrowable = {}  # base asset -> bool

    if not API_KEY:
        print("  BINANCE_API_KEY not set in environment.")
        print("  -> Skipping margin checks (steps 1-3 already gave public conclusions).")
        return cross, iso, borrowable, "NO_KEY"

    headers = {"X-MBX-APIKEY": API_KEY}

    # cross pairs
    data, sc = get("https://api.binance.com/sapi/v1/margin/allPairs",
                   headers=headers, label="cross margin allPairs")
    if data:
        for p in data:
            sym = p.get("symbol")
            base = p.get("base")
            if sym in cross:
                cross[sym] = p  # entry exists
            # also map by symbol membership
        present = {p.get("symbol") for p in data}
        for c in CANDIDATES:
            cross[c] = (c in present)
        print(f"  Cross margin pairs total: {len(data)}")
        for c in CANDIDATES:
            print(f"    {c:<8} cross pair exists: {bool(cross[c])}")

    # isolated pairs
    data, sc = get("https://api.binance.com/sapi/v1/margin/isolated/allPairs",
                   headers=headers, label="isolated margin allPairs")
    if data:
        present = {p.get("symbol") for p in data}
        for c in CANDIDATES:
            iso[c] = (c in present)
        print(f"  Isolated margin pairs total: {len(data)}")
        for c in CANDIDATES:
            print(f"    {c:<8} isolated pair exists: {bool(iso[c])}")

    # assets borrowable
    data, sc = get("https://api.binance.com/sapi/v1/margin/allAssets",
                   headers=headers, label="margin allAssets")
    if data:
        for a in data:
            borrowable[a.get("assetName")] = bool(a.get("isBorrowable"))
        print(f"  Margin assets total: {len(data)}")
        for c in CANDIDATES:
            print(f"    {c:<8} base isBorrowable: {borrowable.get(c)}")

    return cross, iso, borrowable, "OK"


def main():
    print("bStocks short-availability probe — READ ONLY (no orders, no transfers)")
    print(f"Candidates: {', '.join(CANDIDATES)}  (focus: MRVLB)")
    print(f"API key present: {bool(API_KEY)}")

    spot, all_bstocks, sc1 = step1_spot()
    usdm, sc2 = step2_usdm()
    coinm, sc3 = step3_coinm()
    cross, iso, borrowable, mstat = step4_margin()

    # ---- summary table ----
    hr("SUMMARY TABLE")
    cols = ["symbol", "spotTRADING", "crossMargin", "isoMargin",
            "baseBorrowable", "USDM-perp", "COINM-perp", "shortable?", "path"]
    print("{:<8} {:<11} {:<11} {:<9} {:<14} {:<9} {:<10} {:<10} {}".format(*cols))

    def yn(v):
        if v is None:
            return "?"
        return "Y" if v else "N"

    for c in CANDIDATES:
        spot_t = (spot.get(c) == "TRADING")
        cm = cross.get(c)
        im = iso.get(c)
        bb = borrowable.get(c) if borrowable else None
        um = bool(usdm.get(c))
        dm = bool(coinm.get(c))

        # shortable logic
        paths = []
        if um:
            paths.append("USDM perp")
        if dm:
            paths.append("COINM perp")
        # margin short needs: a margin pair exists AND base asset borrowable
        margin_short = ((cm or im) and bb)
        if margin_short:
            paths.append("margin borrow-sell")

        if paths:
            shortable = "YES"
        elif (cm or im) and bb is None:
            shortable = "MAYBE(no key)"
        elif spot_t and (cm is None and im is None):
            shortable = "MAYBE(no key)"
        else:
            shortable = "NO" if spot.get(c) is not None or True else "?"

        path_str = " / ".join(paths) if paths else "-"
        print("{:<8} {:<11} {:<11} {:<9} {:<14} {:<9} {:<10} {:<10} {}".format(
            c, yn(spot_t), yn(cm), yn(im), yn(bb), yn(um), yn(dm), shortable, path_str))

    print("\nLegend: Y/N/? (?=unknown, e.g. margin not checked because no API key)")
    print("\nIMPORTANT: This probe only proves whether the TOOL/CONTRACT exists,")
    print("NOT whether YOUR ACCOUNT can trade it. bStocks are not offered to US")
    print("users and carry region/KYC limits; account-level permission (margin/")
    print("futures tradeEnabled, permission bits) must be checked separately.")


if __name__ == "__main__":
    main()
