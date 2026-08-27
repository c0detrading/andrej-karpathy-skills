# Major Order Zones (TradingView)

Pine Script v6 indicator that draws major buy-side (demand) and sell-side
(supply) order zones on the chart.

## Bookmap note

TradingView cannot connect to Bookmap: Pine Script has no access to external
data feeds or order-book (DOM/heatmap) data — only price and traded volume.
This indicator approximates order zones from swing pivots that formed on
unusually high volume, which is the footprint large resting orders leave on
the tape. Run it side by side with Bookmap and use the zones as a cross-check
against the heatmap.

## Install

1. In TradingView, open **Pine Editor** (bottom panel).
2. Paste the contents of `major-order-zones.pine`.
3. Click **Add to chart**.

## How it works

- **Buy-side zone (teal):** a swing low whose volume exceeds the spike
  multiplier × 20-bar average volume. The zone spans the lower wick, where
  sell pressure was absorbed by resting bids.
- **Sell-side zone (red):** the mirror image at a swing high — the upper
  wick, where buy pressure was absorbed by resting offers.
- Zones extend to the right until price **closes through** them, at which
  point they are removed (or greyed out, if "Remove broken zones" is off).

## Settings

| Input | Default | Meaning |
| --- | --- | --- |
| Pivot length | 5 | Bars on each side of a swing for it to count as a pivot. Zones confirm this many bars after the pivot. |
| Volume spike multiplier | 1.5 | Pivot volume must exceed this × the 20-bar average volume. |
| Max zones per side | 10 | Oldest zones are dropped beyond this. |
| Remove broken zones | on | Delete zones price closes through; off keeps them greyed out. |

## Alerts

Two alert conditions are exposed (Alert dialog → Condition → *Order Zones*):

- **Price in buy-side zone**
- **Price in sell-side zone**
