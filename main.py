"""cbBTC dip-rebound bot for agent-fun/bars-replay/v1 (make.fun btc-race-24h).

Strategy, written fresh for this competition:
  * Long only, one position, all-in / all-out, 1,000 USDC paper start.
  * BUY when the close has fallen at least 250 bps over the last 90 one-minute
    bars (a sharp dip: about 2.2 standard deviations of the 90-bar return on
    the dev window). The dev window fell ~4% overall, so blind trend-following
    and buy-and-hold both lose there; sharp dips in this market tended to
    rebound over the next couple of hours, and a round trip costs ~40 bps at
    the dev pool depth, so only a large, well-filtered dip is worth trading.
  * SELL at the first of: 150 bars held, +400 bps from the entry cost basis,
    or -250 bps from the entry cost basis (catastrophe stop).
  * max_slippage_bps 150 on every order: the modelled slippage plus pool
    impact of a full-size trade is ~17 bps, and the open usually lands within
    a few bps of the previous close, so 150 bps leaves ample room while still
    bounding a gap-open fill.

Determinism: integer arithmetic only, no wall clock, no randomness, no
environment or files outside /bot. All state comes from the hello and the
batches the harness sends (bar time is the batch time).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

# Strategy parameters (bps / bars).
DIP_LOOKBACK = 90        # bars over which the dip is measured
DIP_BPS = 250            # buy when the 90-bar return is below -250 bps
MAX_HOLD_BARS = 150      # sell once the position is this many bars old
TAKE_PROFIT_BPS = 400    # sell when the close is +400 bps over entry cost
STOP_LOSS_BPS = 250      # sell when the close is -250 bps under entry cost
SLIPPAGE_BPS = 150       # max_slippage_bps on every order


class DipBot:
    """Keeps the close history and the entry bookkeeping for one position."""

    def __init__(self):
        self.closes = []          # latest closes, ints at price_scale
        self.entry_seq = None     # seq of the batch on which the buy was decided
        self.entry_price = None   # cost basis per unit, at price_scale

    def on_batch(self, state, batch):
        bar = state.latest.get(SYMBOL)
        if bar is not None:
            self.closes.append(int(bar["c"]))
        holding = state.positions.get(SYMBOL)
        qty = holding.qty if holding is not None else 0

        if qty > 0:
            if bar is None:
                return []  # no bar yet this batch; cannot mark the position
            # Entry cost basis from the account: cash spent / quantity held.
            # cost is in quote units, qty at qty_scale, price at price_scale,
            # quote at quote_scale: price = cost * 10^(qty+price) / (qty * 10^quote).
            sym = state.symbols[SYMBOL]
            qscale = state.hello["capital"]["quote_scale"]
            self.entry_price = (
                holding.cost * 10 ** (sym["qty_scale"] + sym["price_scale"])
                // (qty * 10 ** qscale)
            )
            if self.entry_seq is None:
                self.entry_seq = state.seq
            close = int(bar["c"])
            held_bars = state.seq - self.entry_seq
            ret_bps = (close - self.entry_price) * 10_000 // self.entry_price
            if (
                held_bars >= MAX_HOLD_BARS
                or ret_bps >= TAKE_PROFIT_BPS
                or ret_bps <= -STOP_LOSS_BPS
            ):
                self.entry_seq = None
                self.entry_price = None
                return [
                    {
                        "side": "sell",
                        "symbol": SYMBOL,
                        "qty": qty,
                        "max_slippage_bps": SLIPPAGE_BPS,
                    }
                ]
            return []

        # Flat: forget any stale entry bookkeeping, then look for a dip.
        self.entry_seq = None
        self.entry_price = None
        if state.warming_up:
            return []
        if len(self.closes) <= DIP_LOOKBACK:
            return []
        if state.cash < 1_000_000:
            return []
        now = self.closes[-1]
        then = self.closes[-1 - DIP_LOOKBACK]
        dip_bps = (now - then) * 10_000 // then
        if dip_bps < -DIP_BPS:
            self.entry_seq = state.seq
            return [
                {
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": state.cash,
                    "max_slippage_bps": SLIPPAGE_BPS,
                }
            ]
        return []


def main():
    bot = DipBot()
    makefun_bars.run(bot.on_batch)


if __name__ == "__main__":
    main()
