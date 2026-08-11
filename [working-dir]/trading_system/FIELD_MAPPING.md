# FIELD MAPPING - Backend to Frontend
## API Consistency Matrix

### Position Object

| Backend Field | Frontend Expects | Type | Status |
|--------------|------------------|------|--------|
| `position_id` | `id` | string | ✅ mapped |
| `ticket` | `ticket` | number | ✅ optional |
| `direction` → `"BUY"/"SELL"` | `type: "BUY"/"SELL"` | string | ✅ mapped |
| `quantity` | `lot` | float | ✅ mapped |
| `quantity` | `volume` | float | ✅ mapped |
| `entry_price` | `entry` | float | ✅ mapped |
| `entry_price` | `price_open` | float | ✅ mapped |
| `current_price` | `current_price` | float | ✅ |
| `stop_loss` | `sl` | float | ✅ mapped |
| `take_profit` | `tp` | float | ✅ mapped |
| `unrealized_pnl` | `profit` | float | ✅ **FIXED** |
| `unrealized_pnl` | `pnl` | float | ✅ **FIXED** |
| `pips` | `pips` | float | ✅ calculated |

### Candle Object

| Backend Field | Frontend Expects | Type | Status |
|--------------|------------------|------|--------|
| `timestamp` | `t` | string | ✅ mapped |
| `timestamp` | `ts` | string | ✅ optional |
| `open` | `o` | number | ✅ mapped |
| `high` | `h` | number | ✅ mapped |
| `low` | `l` | number | ✅ mapped |
| `close` | `c` | number | ✅ mapped |
| `volume` | `v` | number | ✅ mapped |

### Indicators Object

| Backend Field | Frontend Expects | Type | Status |
|--------------|------------------|------|--------|
| `rsi` | `rsi` | number | ✅ |
| `atr` | `atr` | number | ✅ |
| `macd` | `macd` | string | ✅ |
| `stoch` | `stoch` | string | ✅ |
| `ema_fast` | `ema20` | number | ✅ |
| `ema_medium` | `ema50` | number | ✅ |
| `ema_slow` | `ema200` | number | ✅ |
| `volume` | `volume` | number | ✅ |
| `pivot` | `pivot` | number | ✅ |

### Trade History Object

| Backend Field | Frontend Expects | Type | Status |
|--------------|------------------|------|--------|
| `closed_at.strftime("%H:%M")` | `time` | string | ✅ |
| `direction` | `type` | string | ✅ |
| `quantity` | `lot` | float | ✅ |
| `symbol` | `symbol` | string | ✅ |
| `exit_price` | `price` | float | ✅ |
| `stop_loss` | `sl` | float | ✅ |
| `take_profit` | `tp` | float | ✅ |
| `pnl` | `pl` | float | ✅ |
| `exit_reason` | `reason` | string | ✅ |

---

## SUMMARY

All field mappings are now consistent between:
- `[working-dir]/trading_system/app/main_fixed.py`
- `dashboard/server.py`
- `web/lib/api.ts`
- `web/app/page.tsx`
