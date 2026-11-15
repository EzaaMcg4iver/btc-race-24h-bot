# cbBTC dip-rebound bot — make.fun `btc-race-24h-20261115-0828`

A Python 3.13 (stdlib only) bot for the `agent-fun/bars-replay/v1` protocol:
it trades Coinbase Wrapped BTC (CBBTC) against USDC, minute by minute, long
only, starting from 1,000 USDC of paper money.

## Strategy

The dev window (1,440 one-minute bars) fell about 4% overall, so
buy-and-hold loses ~$44 there and plain EMA trend-following loses ~$50 on
whipsaw (a full-size round trip costs ~40 bps at the dev pool depth). Sharp
dips, however, tended to rebound over the next couple of hours. The bot
therefore trades rarely and only on large dips:

- **Buy** (all cash, one position) when the close has fallen at least
  250 bps over the last 90 one-minute bars.
- **Sell** (whole position) at the first of: 150 bars held, +400 bps from
  the entry cost basis, or −250 bps from the entry cost basis (stop-loss).
- Every order names `max_slippage_bps` 150 — the modelled slippage plus pool
  impact of a full-size trade is ~17 bps, so this leaves ample room while
  still bounding a gap-open fill.

## Dev-window result (local grading)

Docker is not installed on the build VM, so the kit's
`grade-local --driver docker` cannot run, and its `--driver process` runs
Node 22 only. The bot was instead graded with a from-scratch Python replay
harness implementing the fill model in `contracts/bars-protocol.ts` exactly
(next-bar-open fills, 4 bps fee, 2 bps slippage, constant-product impact
against the bar's open depth, `max_slippage_bps` from the latest close,
end-of-window flatten at the last close). That harness was cross-validated
against the kit's own grader: buy-and-hold scores **−44.009846 USDC** under
both the official `grade-local --driver process` and the local replay,
identical to the micro-USDC.

| Metric | Dev window |
| --- | --- |
| Net PnL | **+43.795193 USDC** |
| Filled trades | 6 |
| Max drawdown | 2.53% of starting cash |
| Rejected orders | 0 |
| Determinism | two runs, action logs byte-identical |

Neighbouring parameters (lookback 80–100 bars, dip 230–270 bps, hold
120–150 bars) all stay profitable on the dev window (+$19 to +$44), and the
chosen set is profitable in both halves of the window, so the result is not
a single cherry-picked peak — though, as with any 24-hour fit, the race
window is unseen and the same dip-rebound behaviour may or may not repeat.

## Layout

- `main.py` — the bot (entrypoint; stdlib only).
- `vendor/makefun_bars.py` — byte-for-byte copy of the kit's Python SDK shim
  (`sdk/makefun_bars.py`), kept under `vendor/` as the rules allow.
- `README.md`, `LICENSE` (MIT).

## Running

The grader runs `python3 -P -s /bot/main.py` with `PYTHONHASHSEED=0`. The
bot reads newline-delimited JSON on stdin (hello, then one batch per bar,
then done) and answers every batch with exactly one reply echoing its seq.
It uses integer arithmetic only — no wall clock, no randomness, no
environment or files outside `/bot` — so repeated runs are deterministic.
