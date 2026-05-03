# PoC-6 Foreground Service — Per-ROM Test Results

> Append a row each time you complete a 12h+ run on a real device.
> Pull the CSV via `adb pull` and run `analyze_heartbeat.py` first.

| Date | ROM / Brand | Model | Android | Battery whitelisted | Runtime (h) | Gaps > 60s | Longest gap | Verdict | Notes |
|---|---|---|---|---|---|---|---|---|---|
| _example_ | MIUI 14 | Redmi Note 12 | 13 | yes | 14.2 | 0 | 7s | ✓ PASS | first run, plugged in |
|  |  |  |  |  |  |  |  |  |  |

## Aggregate verdict (target: ≥ 90% pass per priority ROM, ≥ 3 phones each)

| ROM family | Phones tested | Phones passed | Result |
|---|---|---|---|
| MIUI / HyperOS (Xiaomi/Redmi) | 0 | 0 | TBD |
| MagicOS (Honor) | 0 | 0 | TBD |
| ColorOS (OPPO/Realme) | 0 | 0 | TBD |
| OriginOS (vivo/iQOO) | 0 | 0 | TBD |
| Flyme (Meizu) — optional | 0 | 0 | TBD |
| AOSP / Pixel (control) | 0 | 0 | TBD |

## If results are bad...

See engineering plan §5 R2:
  - Strengthen battery whitelist guidance (add per-ROM animated GIFs)
  - Fall back to WorkManager periodic wakeups (intermittent mode)
  - Worst case: require app to stay foreground (sacrifices "passive" UX)
