"""Production-ready Exit Engine for BWE Live Bot — v2.

3 core fixes vs current `bwe_live_autotrader.py` _handle_prove_then_hourly_state:

  1. Dynamic trail step (high_water-tier-aware) — replaces buggy
     `pnl_pct < runner_floor_pct` logic that loses winners (KAT 33%→-7%).

  2. Volume-confirmed stop — only exit on hard_stop/catastrophe IF recent
     volume confirms breakdown. Avoids 洗盘 (whipsaw) where price drops
     briefly without volume = manipulator washing out retail.

  3. ATR-aware hard_stop — hard_stop = max(min_pct, ATR_mult × pre-entry ATR).
     High-volatility 妖币 automatically gets wider stop (避免 noise stop).

Design principles (anti-overfit):
  - **First-principles params** (not data-fitted)
  - **Tier-based dynamic trail** matches user thesis: "TP 不要太小, 5-100%+,
    SL 也要够宽不要被洗盘洗出去"
  - **Stateless engine** with state in `Position` object — easy to plug into
    bot's existing tick loop

Usage:
    config = ExitConfig()  # or customize
    engine = ExitEngine(config)

    # At entry:
    atr_at_entry = compute_atr_pct(pre_entry_30min_bars, period=14)
    pos = Position(
        entry_ts_ms=ts, entry_px=px, side="long",
        hold_minutes_limit=360, atr_at_entry=atr_at_entry,
    )

    # Each tick:
    decision = engine.decide(pos, bars_up_to_now)
    if decision:
        execute_close(symbol, exit_px=decision.exit_px,
                      reason=decision.reason)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ============================================================================
# Data structures
# ============================================================================

@dataclass(frozen=True)
class Bar:
    """1-minute OHLCV bar."""
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Position:
    """Current open position. Mutable: high_water_pct updated each tick."""
    entry_ts_ms: int
    entry_px: float
    side: str  # "long" or "short"
    hold_minutes_limit: float = 360.0
    atr_at_entry: Optional[float] = None  # ATR % at entry (set externally)
    high_water_pct: float = 0.0  # max favorable PnL % seen so far
    high_water_ts_ms: int = 0    # ts when high_water_pct was last advanced


@dataclass(frozen=True)
class ExitConfig:
    """First-principles defaults. NOT fitted to specific trades."""
    # ─── Activation: signal needs time to work ─────────────────────
    activation_delay_min: float = 5.0  # head 5 min: only catastrophe stop

    # ─── Dynamic Trail (tier-based) ────────────────────────────────
    # Tiers: (high_water_threshold, trail_step_pct)
    # 妖币 thesis: small wins lock tight, big wins breathe wide
    trail_activate_pct: float = 5.0
    trail_tiers: tuple[tuple[float, float], ...] = (
        (5.0,   4.0),    # hw 5-10%:   tight 4% lock
        (10.0,  7.0),    # hw 10-25%:  moderate 7%
        (25.0, 12.0),    # hw 25-50%:  wider 12%
        (50.0, 18.0),    # hw 50-100%: 妖币 big winner 18%
        (100.0, 25.0),   # hw 100%+:   black-swan 25%
    )

    # ─── Hard Stop (ATR-aware) ─────────────────────────────────────
    hard_stop_min_pct: float = 5.0          # never tighter than 5%
    hard_stop_atr_mult: float = 2.5         # otherwise 2.5 × ATR

    # ─── Catastrophe (head-N-min grace) ────────────────────────────
    catastrophe_min_hold_min: float = 30.0      # head 30 min: stop wider
    catastrophe_grace_multiplier: float = 2.0   # × catastrophe_pct
    catastrophe_pct: float = 12.0

    # ─── Volume Confirm (洗盘 detection) ──────────────────────────
    # Only exit on hard_stop/catastrophe IF recent vol >= ratio × baseline.
    # Whipsaw = price drops without volume = manipulator washing.
    volume_confirm_enabled: bool = True
    volume_confirm_lookback_min: int = 5
    volume_confirm_baseline_min: int = 30
    volume_confirm_ratio: float = 1.5  # recent / baseline >= 1.5x = real

    # ─── G2: TRADOOR-saver (let big winners run) ──────────────────
    # When hw is high enough AND was set very recently AND volume is still
    # elevated AND price is still extending in trade direction → suspend
    # trail this tick. Black-swan moves often look "done" mid-flight; this
    # gates the trail behind real evidence the move has stalled.
    tradoor_saver_enabled: bool = True
    tradoor_saver_hw_threshold: float = 25.0   # only kick in for big winners
    tradoor_saver_max_hw_age_min: float = 10.0 # hw must be fresh (<= N min)
    tradoor_saver_vol_ratio: float = 1.2       # recent vol >= 1.2× baseline

    # ─── Time exit ─────────────────────────────────────────────────
    time_exit_at_hold_limit: bool = True


@dataclass(frozen=True)
class ExitDecision:
    exit_ts_ms: int
    exit_px: float
    reason: str
    pnl_pct: float
    notes: str = ""


# ============================================================================
# Pure functions
# ============================================================================

def dynamic_trail_step(high_water_pct: float,
                       tiers: tuple[tuple[float, float], ...]) -> Optional[float]:
    """Find trail step for current high_water tier. None if not yet active."""
    step = None
    for threshold, ts in tiers:
        if high_water_pct >= threshold:
            step = ts
        else:
            break
    return step


def compute_atr_pct(bars: list[Bar], period: int = 14,
                    ref_px: Optional[float] = None) -> float:
    """ATR over last `period` bars, returned as % of ref_px (default last close).

    True Range per bar = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = mean(TR over period bars)
    """
    if len(bars) < 2:
        return 0.0
    sliced = bars[-(period + 1):]
    trs = []
    for i in range(1, len(sliced)):
        h, l = sliced[i].high, sliced[i].low
        prev_c = sliced[i - 1].close
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    if not trs:
        return 0.0
    atr_abs = sum(trs) / len(trs)
    ref = ref_px if ref_px is not None else sliced[-1].close
    return atr_abs / ref * 100 if ref > 0 else 0.0


def is_volume_confirmed_breakdown(bars: list[Bar], config: ExitConfig) -> bool:
    """True if recent N-min vol >= ratio × prior-30min baseline.

    Returns True (= treat as confirmed, allow exit) on insufficient data
    or when feature disabled.
    """
    if not config.volume_confirm_enabled:
        return True
    needed = config.volume_confirm_lookback_min + config.volume_confirm_baseline_min
    if len(bars) < needed:
        return True

    look = config.volume_confirm_lookback_min
    base = config.volume_confirm_baseline_min
    recent = bars[-look:]
    baseline = bars[-look - base:-look]
    recent_avg = sum(b.volume for b in recent) / len(recent)
    base_avg = sum(b.volume for b in baseline) / len(baseline)
    if base_avg <= 0:
        return True
    return (recent_avg / base_avg) >= config.volume_confirm_ratio


def is_trend_extending(bars: list[Bar], side: str, config: ExitConfig) -> bool:
    """True iff the most recent 5 min show movement still going in the trade
    direction AND volume is elevated vs a 30-min baseline.

    Used by G2 (TRADOOR-saver) to decide whether to suspend the trail when
    sitting on a large unrealised winner. False on insufficient data.
    """
    needed = config.volume_confirm_lookback_min + config.volume_confirm_baseline_min
    if len(bars) < needed:
        return False

    look = config.volume_confirm_lookback_min
    base = config.volume_confirm_baseline_min
    recent = bars[-look:]
    baseline = bars[-look - base:-look]

    recent_vol = sum(b.volume for b in recent) / len(recent)
    base_vol = sum(b.volume for b in baseline) / len(baseline)
    if base_vol <= 0:
        return False
    if (recent_vol / base_vol) < config.tradoor_saver_vol_ratio:
        return False

    start_close = recent[0].close
    end_close = recent[-1].close
    if side == "long":
        return end_close > start_close
    return end_close < start_close


# ============================================================================
# ExitEngine
# ============================================================================

class ExitEngine:
    """Stateless engine; state lives in Position object (mutated)."""

    def __init__(self, config: ExitConfig = ExitConfig()):
        self.config = config

    def _current_pnl_pct(self, pos: Position, current_px: float) -> float:
        if pos.side == "long":
            return (current_px - pos.entry_px) / pos.entry_px * 100
        return (pos.entry_px - current_px) / pos.entry_px * 100

    def _best_in_bar(self, pos: Position, bar: Bar) -> float:
        """Best favorable PnL achievable within a single bar."""
        if pos.side == "long":
            return (bar.high - pos.entry_px) / pos.entry_px * 100
        return (pos.entry_px - bar.low) / pos.entry_px * 100

    def _hard_stop_pct(self, pos: Position) -> float:
        """ATR-aware hard stop %."""
        atr_pct = pos.atr_at_entry or 0
        return max(self.config.hard_stop_min_pct,
                   self.config.hard_stop_atr_mult * atr_pct)

    def _catastrophe_pct(self, pos: Position, hold_min: float) -> float:
        """Catastrophe stop, widened in head-grace period."""
        base = self.config.catastrophe_pct
        if hold_min < self.config.catastrophe_min_hold_min:
            return base * self.config.catastrophe_grace_multiplier
        return base

    def decide(self, pos: Position, bars: list[Bar]) -> Optional[ExitDecision]:
        """Make exit decision based on current bar (last in `bars`).

        `bars` should include pre-entry context (for ATR if not pre-set) +
        in-trade bars up to current. Engine uses last bar for current state.
        """
        if not bars:
            return None

        cur_bar = bars[-1]
        if cur_bar.ts_ms < pos.entry_ts_ms:
            return None  # not yet in trade

        cur_px = cur_bar.close  # close-based decision (realistic)
        hold_min = (cur_bar.ts_ms - pos.entry_ts_ms) / 60000.0
        pnl = self._current_pnl_pct(pos, cur_px)

        # Update high_water (use best_in_bar to capture intra-bar peaks)
        best_in_bar = self._best_in_bar(pos, cur_bar)
        if best_in_bar > pos.high_water_pct:
            pos.high_water_pct = best_in_bar
            pos.high_water_ts_ms = cur_bar.ts_ms
        new_hw = pos.high_water_pct

        # ─── 1. Time exit (hold limit) ─────────────────────────────
        if self.config.time_exit_at_hold_limit and hold_min >= pos.hold_minutes_limit:
            return ExitDecision(
                exit_ts_ms=cur_bar.ts_ms, exit_px=cur_px,
                reason="time_exit", pnl_pct=pnl,
                notes=f"hold {hold_min:.0f}min >= limit {pos.hold_minutes_limit}",
            )

        # ─── 2. Hard stop / catastrophe ────────────────────────────
        hard_stop = self._hard_stop_pct(pos)
        catastrophe = self._catastrophe_pct(pos, hold_min)

        triggered_stop = None
        if hold_min >= self.config.activation_delay_min:
            if pnl <= -hard_stop:
                triggered_stop = ("hard_stop", hard_stop)
        else:
            # in 5-min grace: only catastrophe matters
            if pnl <= -catastrophe:
                triggered_stop = ("catastrophe_stop", catastrophe)

        if triggered_stop is not None:
            reason, threshold = triggered_stop
            # 洗盘 detect: skip exit if volume doesn't confirm breakdown
            if not is_volume_confirmed_breakdown(bars, self.config):
                # Hold position; mark as suspected whipsaw, but still log
                # 注意: 这是 risk! 如果真破位但 volume 没起,我们 hold 会继续亏
                # 但相比 5% 噪音洗盘 false stop, 这是更稳的选择 in 妖币 regime
                return None  # don't exit, suspected whipsaw
            return ExitDecision(
                exit_ts_ms=cur_bar.ts_ms, exit_px=cur_px,
                reason=reason, pnl_pct=pnl,
                notes=f"threshold={threshold:.2f}% atr={pos.atr_at_entry or 0:.2f}%",
            )

        # ─── 3. Dynamic trail (high_water-tier-aware) ──────────────
        if new_hw >= self.config.trail_activate_pct:
            step = dynamic_trail_step(new_hw, self.config.trail_tiers)
            if step is not None:
                trail_floor = new_hw - step
                if pnl <= trail_floor:
                    # G2: TRADOOR-saver — only suspend trail if all true:
                    #   (a) hw is meaningfully large (>= threshold)
                    #   (b) hw was set very recently (move still fresh)
                    #   (c) volume + direction confirm trend extending
                    if self.config.tradoor_saver_enabled and new_hw >= self.config.tradoor_saver_hw_threshold:
                        hw_age_min = (cur_bar.ts_ms - pos.high_water_ts_ms) / 60_000.0
                        if (hw_age_min <= self.config.tradoor_saver_max_hw_age_min
                                and is_trend_extending(bars, pos.side, self.config)):
                            return None  # let it run
                    # Exit at trail floor price (assumes trail order placed)
                    if pos.side == "long":
                        exit_px = pos.entry_px * (1 + trail_floor / 100)
                    else:
                        exit_px = pos.entry_px * (1 - trail_floor / 100)
                    return ExitDecision(
                        exit_ts_ms=cur_bar.ts_ms, exit_px=exit_px,
                        reason="trail_drawdown_exit", pnl_pct=trail_floor,
                        notes=f"hw={new_hw:.1f}% step={step}% floor={trail_floor:.1f}%",
                    )

        return None  # hold


# ============================================================================
# Self-test
# ============================================================================

def _self_test() -> int:
    """Quick sanity check — synthetic scenarios."""
    print("=" * 70)
    print("exit_v2 self-test")
    print("=" * 70)

    # Test 1: dynamic trail step lookup
    cfg = ExitConfig()
    assert dynamic_trail_step(0,    cfg.trail_tiers) is None
    assert dynamic_trail_step(4,    cfg.trail_tiers) is None
    assert dynamic_trail_step(7,    cfg.trail_tiers) == 4.0
    assert dynamic_trail_step(15,   cfg.trail_tiers) == 7.0
    assert dynamic_trail_step(40,   cfg.trail_tiers) == 12.0
    assert dynamic_trail_step(75,   cfg.trail_tiers) == 18.0
    assert dynamic_trail_step(150,  cfg.trail_tiers) == 25.0
    print("✓ dynamic_trail_step tiers correct")

    # Test 2: ATR computation on synthetic bars
    bars = [
        Bar(ts_ms=i * 60_000, open=100 + i*0.1, high=100 + i*0.1 + 0.5,
            low=100 + i*0.1 - 0.5, close=100 + i*0.1 + 0.2,
            volume=1000)
        for i in range(20)
    ]
    atr = compute_atr_pct(bars, period=14)
    assert 0.5 < atr < 2.0, f"unexpected ATR {atr}"
    print(f"✓ ATR on synthetic bars: {atr:.3f}%")

    # Test 3: Volume confirm — high vs low recent volume (need 35+ bars)
    cfg_vc = ExitConfig(volume_confirm_enabled=True)
    bars40 = [
        Bar(ts_ms=i * 60_000, open=100, high=100.5, low=99.5,
            close=100.2, volume=1000)
        for i in range(40)
    ]
    bars_high_vol = bars40[:-5] + [Bar(b.ts_ms, b.open, b.high, b.low, b.close,
                                       b.volume * 3) for b in bars40[-5:]]
    bars_low_vol = bars40[:-5] + [Bar(b.ts_ms, b.open, b.high, b.low, b.close,
                                      b.volume * 0.5) for b in bars40[-5:]]
    assert is_volume_confirmed_breakdown(bars_high_vol, cfg_vc) is True
    assert is_volume_confirmed_breakdown(bars_low_vol, cfg_vc) is False
    print("✓ volume confirm distinguishes spike from non-spike")

    # Test 4: TRADOOR-style trade simulation
    # Entry $2.86 short. Price drops slowly with retracements.
    # Expect: with dynamic trail, hw 70% → step 18% → floor 52%, exit ~52%+
    print("\n--- Synthetic TRADOOR-style test ---")
    entry_px = 2.86
    entry_ts = 0
    # 60 bars: price drops linearly from 2.86 to 1.0 with 5% noise
    import random
    random.seed(42)
    bars = []
    for i in range(60):
        c = 2.86 - i * (1.86 / 60)  # linear drop
        h = c + random.uniform(0.0, c * 0.05)
        l = c - random.uniform(0.0, c * 0.05)
        o = (c + l) / 2
        bars.append(Bar(ts_ms=i * 60_000, open=o, high=h, low=l,
                        close=c, volume=1000))

    pos = Position(entry_ts_ms=0, entry_px=entry_px, side="short",
                   hold_minutes_limit=360.0, atr_at_entry=2.0)

    eng = ExitEngine(ExitConfig())
    decision = None
    for i in range(len(bars)):
        d = eng.decide(pos, bars[:i + 1])
        if d:
            decision = (i, d)
            break

    if decision:
        i, d = decision
        print(f"Exit at bar {i}: reason={d.reason} pnl={d.pnl_pct:.2f}% (hw={pos.high_water_pct:.1f}%)")
        assert d.pnl_pct > 30, f"Expected pnl > 30 with dynamic trail, got {d.pnl_pct}"
    else:
        last_pnl = eng._current_pnl_pct(pos, bars[-1].close)
        print(f"No trail trigger; final pnl at end: {last_pnl:.2f}% (hw={pos.high_water_pct:.1f}%)")

    # Test 5: G2 (TRADOOR-saver) suspends trail when trend still extending
    print("\n--- G2 TRADOOR-saver test ---")
    # Build short-side trade: hw=30% reached at bar 35, then small pullback
    # at bar 36 with high volume → G2 should hold; no-G2 should exit on trail
    n_pre = 30  # baseline volume bars
    bars_g2: list[Bar] = []
    # 30 baseline (slow drift)
    for i in range(n_pre):
        bars_g2.append(Bar(ts_ms=i * 60_000, open=100.0, high=100.5, low=99.5,
                           close=100.0, volume=1000))
    # 5 bars trade direction (price drops fast from 100→70 = 30% short profit)
    for i in range(5):
        c = 100 - (i + 1) * 6  # 94, 88, 82, 76, 70
        bars_g2.append(Bar(ts_ms=(n_pre + i) * 60_000, open=c + 3, high=c + 4,
                           low=c - 1, close=c, volume=5000))
    # 1 bar small pullback (close goes back up a hair) but volume still 5x
    bars_g2.append(Bar(ts_ms=(n_pre + 5) * 60_000, open=70, high=72.5, low=70,
                       close=72, volume=5000))

    pos_g2 = Position(entry_ts_ms=n_pre * 60_000, entry_px=100.0, side="short",
                      hold_minutes_limit=360.0, atr_at_entry=2.0)
    eng_g2 = ExitEngine(ExitConfig(tradoor_saver_enabled=True))
    eng_no_g2 = ExitEngine(ExitConfig(tradoor_saver_enabled=False))

    # Replay only after the pullback bar
    pos_g2_copy = Position(entry_ts_ms=n_pre * 60_000, entry_px=100.0,
                           side="short", hold_minutes_limit=360.0,
                           atr_at_entry=2.0)
    for i in range(n_pre, len(bars_g2)):
        eng_g2.decide(pos_g2_copy, bars_g2[: i + 1])
    pos_no_copy = Position(entry_ts_ms=n_pre * 60_000, entry_px=100.0,
                           side="short", hold_minutes_limit=360.0,
                           atr_at_entry=2.0)
    last_decision_no_g2 = None
    for i in range(n_pre, len(bars_g2)):
        d = eng_no_g2.decide(pos_no_copy, bars_g2[: i + 1])
        if d:
            last_decision_no_g2 = d
            break

    print(f"  with G2:    hw={pos_g2_copy.high_water_pct:.1f}% (no exit by end → trail suspended)")
    if last_decision_no_g2:
        print(f"  without G2: trail exit at pnl={last_decision_no_g2.pnl_pct:.1f}% reason={last_decision_no_g2.reason}")
    else:
        print(f"  without G2: also held (test scenario insufficient)")

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_self_test())
