# How coin-proje-bot2 works

The English entry point to the code, for an engineer who has never opened the repository. Every statement was checked
against the code at the commit that added this file, and each mechanism links to the module and function behind it.
Code comments and log messages are in Turkish; the [glossary](#10-glossary) translates the field names.

> **Early prototype, kept for reference.** One of the author's first trading-bot experiments, superseded by
> [trading2](https://github.com/CoskunerBerke/trading2). It only simulates trades: no code in this repository places an
> exchange order. Nothing here claims that any strategy is profitable.

## Contents

1. [What it is and what it is not](#1-what-it-is-and-what-it-is-not)
2. [Architecture](#2-architecture)
3. [Main runtime flows](#3-main-runtime-flows)
4. [Data model](#4-data-model)
5. [Core logic in depth](#5-core-logic-in-depth)
6. [Design decisions and trade-offs](#6-design-decisions-and-trade-offs)
7. [Testing strategy](#7-testing-strategy)
8. [Limitations, known gaps and next steps](#8-limitations-known-gaps-and-next-steps)
9. [Code tour](#9-code-tour)
10. [Glossary](#10-glossary)
11. [Türkçe özet](#türkçe-özet)

## 1. What it is and what it is not

**What it is.** One Python process ([`app.py`](../app.py)) that serves a Flask REST API and runs a background engine
thread. The engine reads public Binance futures data for `ACTIVE_COINS` (BTC and SOL, [`config.py`](../config.py)),
scores long/short setups with hand-written indicator rules, filters them and opens **simulated** 3x positions on a
virtual 1,000 USDT balance. Closed trades feed a per-coin memory and a small logistic-regression "meta-filter". A static
panel ([`frontend/index.html`](../frontend/index.html)) reads the API; Telegram gets alerts and a pinned JSON backup.

**What it is not.** Not a live trading system: [`run_engine`](../bot_engine.py) forces `sim_mode = True` and leverage 3
on every loop, and nothing calls an order-placing exchange method. Not a validated strategy: "confidence" and "EV" come
from hand-tuned formulas, and there is no backtest. Not maintained: it is kept working and tested, and several
unreachable branches are listed in [section 8](#8-limitations-known-gaps-and-next-steps).

## 2. Architecture

```mermaid
flowchart TB
    subgraph EXT["External services (public data)"]
        BIN["Binance futures via ccxt"]
        CG["CoinGecko"]
        NEWS["RSS feeds, CryptoPanic, Fear & Greed"]
        FX["frankfurter.app USD/TRY"]
    end
    subgraph PROC["One Python process: app.py"]
        ENG["Engine thread: run_engine"]
        DF["DataFetcher (TTL caches)"]
        TA["TechnicalAnalyzer"]
        SA["SentimentAnalyzer"]
        MS["MacroSentinel"]
        CF["CounterfactualAnalyzer"]
        CI["CoinIntelligenceManager"]
        SG["SignalGenerator + QuantMetaFilter"]
        TE["TradeExecutor (simulated)"]
        DB["HybridDatabaseManager"]
        API["Flask REST API"]
    end
    FILES[("JSON files in the working directory")]
    PANEL["Static panel: frontend/index.html"]
    TG["Telegram: alerts + pinned backup"]

    BIN --> DF
    CG --> DF
    NEWS --> SA
    FX --> MS
    ENG -- "scan every 15 s" --> DF
    DF --> TA --> SG
    SA --> SG
    MS --> SG
    CF --> CI --> SG
    SG -- "signal" --> TE
    ENG -- "positions every 10 s" --> TE
    TE --> FILES
    TE -- "alerts" --> TG
    FILES <--> DB
    DB <-- "pinned JSON backup" --> TG
    API --> FILES
    PANEL -- "GET public, POST with X-Admin-Token" --> API
```

| Module | Responsibility |
|---|---|
| [`app.py`](../app.py) | Routes, `require_admin`, CORS, one-time archive on a fresh start, engine thread start |
| [`bot_engine.py`](../bot_engine.py) | The 24/7 loop, BTC "compass", invalidation guard, daily loss guard |
| [`data_fetcher.py`](../data_fetcher.py) | Candles, tickers, funding, open interest, spread (ccxt), CoinGecko; TTL cache |
| [`technical_analysis.py`](../technical_analysis.py) | Indicators, support/resistance, regime, squeeze, sweeps |
| [`signal_generator.py`](../signal_generator.py) | Rule votes, confidence, SL/TP, Monte Carlo, EV, filters, meta-filter |
| [`coin_intelligence.py`](../coin_intelligence.py) | Per-coin profiles ("DNA") and trade memory |
| [`sentiment_analysis.py`](../sentiment_analysis.py), [`macro_sentinel.py`](../macro_sentinel.py) | News score; macro risk level |
| [`trade_executor.py`](../trade_executor.py) | Sizing, simulated entries and exits, balance, avoided trades |
| [`counterfactual_analyzer.py`](../counterfactual_analyzer.py) | "What if I had held / had entered" for 24 h |
| [`db_manager.py`](../db_manager.py), [`telegram_notifier.py`](../telegram_notifier.py) | Telegram backup/restore; messages |

`main.py` and `dashboard.py` are an older local Streamlit front end over the same modules (it starts its own engine
thread). `analyze_performance.py` and `merge_and_push.py` are offline maintenance scripts.

## 3. Main runtime flows

### 3.1 The engine loop and one scan

[`run_engine`](../bot_engine.py) waits 30 s after start-up, then loops with a 5 s pause and reloads
`persistent_settings.json` each time. On their own timers it updates open positions (10 s), counterfactuals (30 s) and
the daily-chart spot scan (12 h), and retrains the meta-filter on every iteration; all of these run even when the bot
is inactive. Scans and entries run every 15 s only when the bot is active (`RENDER=true` or the saved `bot_active`),
on the saved `timeframe` (default `1h`).

```mermaid
sequenceDiagram
    participant E as run_engine
    participant M as MacroSentinel
    participant D as DataFetcher
    participant S as SignalGenerator
    participant X as TradeExecutor
    E->>M: get_macro_risk_score() (30 min cache)
    E->>D: BTC ticker and candles
    Note over E: BTC compass: trend and reversal trigger
    loop BTC, SOL
        E->>D: ticker, candles (scan tf, higher tf, 1h, 4h, 1d), coin info
        E->>S: generate_signal(...)
        S-->>E: direction, confidence, EV, is_tradable, reject_reason
    end
    E->>X: invalidation guard may close open trades (_save_trade)
    E->>E: write latest_opportunities.json, daily loss guard
    alt tradable, coin not open, no ban, macro not KRIZ
        E->>X: execute_trade(coin, signal)
    else rejected
        E->>X: track_avoided_trade (counterfactuals track it too)
    end
```

### 3.2 Position update

```mermaid
sequenceDiagram
    participant E as run_engine
    participant X as TradeExecutor
    participant D as DataFetcher
    participant C as Memory and counterfactuals
    participant T as Telegram
    E->>X: update_positions(fetcher)
    loop each open trade
        X->>D: ticker, 15m candles
        X->>X: momentum score, PnL, excursions, exit rules in order
        opt an exit rule fires
            X->>C: log_completed_trade, track_post_exit
            X->>T: close alert and learning update
        end
    end
    X->>X: save bot_trades.json, upload backup after 15 s
```

### 3.3 An admin request from the panel

```mermaid
sequenceDiagram
    participant P as Panel
    participant A as Flask app
    P->>P: token from sessionStorage, else prompt
    P->>A: POST /api/close-trade/id with X-Admin-Token
    alt ADMIN_TOKEN unset on the server
        A-->>P: 503
    else missing or wrong token
        A-->>P: 401 (panel forgets the token and asks once more)
    else valid
        A-->>P: 200 after closing at the last price, or 404
    end
```

## 4. Data model

Everything is JSON in the working directory (git-ignored): `bot_trades.json` (trades, newest first),
`bot_avoided_trades.json` (rejected signals tracked against their own SL/TP for 24 h), `coin_trade_memory.json` (last
100 closed trades per coin as a 6-number vector plus a 0/1 outcome), `counterfactual_data.json` and
`counterfactual_lessons.json`, `latest_opportunities.json` (last scan), `bot_spot_portfolio.json`, `bot_logs.txt` (last
100 lines, redacted) and `persistent_settings.json` (panel settings).

| Trade field | Meaning |
|---|---|
| `id` | `str(int(timestamp))`, whole seconds |
| `coin`, `yon`, `durum` | Coin; `LONG`/`SHORT`; `AÇIK` (open) or `KAPALI` (closed) |
| `giris_fiyati`, `stop_loss`, `take_profit`, `cikis_fiyati` | Entry, current stop, target, exit |
| `miktar_usdt`, `kaldirac` | Margin in USDT; leverage (3) |
| `pnl_yuzde`, `pnl_usdt` | Leveraged PnL after 2 × 0.04 % commission |
| `support_level`, `resistance_level` | 1h 20-candle low/high at entry |
| `ml_data`, `entry_features` | Indicator snapshot reused as training features |
| `max_favorable_excursion`, `max_adverse_excursion` | Excursions in units of the initial stop distance (R) |
| `tp1_hit`, `tp1_pnl_usdt`, `trailing_active` | Partial take-profit and trailing state |
| `exit_reason`, `quality_score`, `outcome` | Why it closed; 0 to 100 score; 0/1 label |

The balance is derived, not stored: [`get_balance`](../trade_executor.py) is 1,000 USDT plus closed PnL plus the booked
TP1 part of open trades.

## 5. Core logic in depth

### 5.1 Data and indicators

[`DataFetcher`](../data_fetcher.py) uses ccxt's Binance client with `defaultType: future`. Candles are cached with a TTL
that grows with the timeframe (25 s for 1m up to 7,200 s for 1d), tickers 10 s, funding/open interest/spread 2 min,
CoinGecko 2 h. Each scan loads 210 candles per timeframe so EMA 200 exists.
[`TechnicalAnalyzer.full_analysis`](../technical_analysis.py) returns RSI 14, MACD 12/26/9, EMA 9/21/50/200, Bollinger
20/2, ADX 14, ATR 14 and `atr_pct`, a 20-candle support/resistance pair, a trend (`LONG` if close > EMA 21) and a regime
from `detect_market_regime`: `COMPRESSION` (Bollinger width in its lowest 15 % of 100 candles), `VOLATILITY_EXPANSION`
(width growing, volume > 1.8× average, realised volatility > 75 % of its recent maximum), `TRENDING_BULL`/`_BEAR`
(ADX > 25, EMAs 9/21/50 stacked, spread > 0.3 %), otherwise `RANGE`.

### 5.2 The weighted long/short vote

[`SignalGenerator.generate_signal`](../signal_generator.py) asks eight rule "experts" for a vote:

| Expert | Fires when | Score |
|---|---|---|
| Trend following | ADX > 22 | ±0.8 with the EMA 21 trend |
| Mean reversion | RSI < 32 or > 68 | ±0.7 against the extreme |
| Breakout | volume ratio > 1.6 and Bollinger width > 0.06 | ±0.6 |
| Scalping | MACD histogram ≠ 0 | ±0.5 with its sign |
| Volatility expansion | Bollinger width < 0.03 and volume ratio > 1.3 | ±0.7 |
| Liquidity sweep | large last-candle move and volume ratio > 1.8 | ±0.8, fading the move |
| Momentum continuation | ADX > 25 and volume ratio > 1.2 | ±0.6 by RSI vs 52 |
| Reversal | RSI < 35 in a down trend or > 65 in an up trend | ±0.5 |

The vote is `Σ score × w_regime × (w_coin × 8)`. `w_regime` is 0.05 unless the regime favours the expert (trend 0.40 and
momentum 0.30 when trending; mean reversion 0.45 and scalping 0.30 in a range, and so on). `w_coin` is the coin's fixed
indicator weight in `COIN_DEFAULT_DNA` ([`coin_intelligence.py`](../coin_intelligence.py)). A vote above +0.03 means
`LONG`, below −0.03 `SHORT`, else `NEUTRAL`. News sentiment is not part of the vote.

### 5.3 Confidence, targets, Monte Carlo and EV

- **Confidence** = 100 · sigmoid(`3.0·|vote| + 1.2·regime + 1.0·mtf + 0.5·funding + 0.5·oi − 0.8·uncertainty`).
  `regime` is +1 when the regime matches the direction, else −0.5; `mtf` ±1 when both timeframes' regimes agree;
  `funding` +1 when funding is against the crowd, else −0.3; `oi` 0.8 when open interest grew > 1 %, else −0.2;
  `uncertainty` is the standard deviation of the eight votes.
- **Stop/target** in ATRs: 2.0/4.5 when trending, 3.2/3.2 in volatility expansion, 1.5/2.5 otherwise; the target is
  stretched ×1.35 or ×1.15 for strong momentum and by the counterfactual exit-patience factor (5.7).
- **Monte Carlo**: 10,000 random-walk paths of 24 steps with a total volatility of one ATR; survival is the share of
  paths that never touch the stop.
- **EV** in R: `p_win·reward·momentum_multiplier − (1 − p_win)·risk − (0.15 + 0.1·spread%)`.
- **Trade quality** (0 to 100) is 30 plus points for ADX, EMA stacking, volume, RSI zone, MACD sign, higher-timeframe
  alignment and breakouts; below 75 it halves the size. **Entry quality** (0 to 1) weights trend alignment 0.30,
  breakout 0.25, volume 0.20, volatility 0.15, BTC alignment 0.10; below 0.35 it cuts confidence by 10 %.
- **Adaptive threshold**: `42 + 2.5·atr% + 3·spread%`, moved for SOL by the BTC trend and reversal trigger and by the
  1d close vs EMA 200, capped at 75, then raised by the macro level.

### 5.4 Hard and soft rejects

The filters run in a fixed order and the first failure sets `reject_reason`. Because `AI_MODE` in
[`config.py`](../config.py) is `LEARN_AND_APPLY`, some rejections are then relaxed so the bot keeps collecting trades to
learn from (the reason given in the code comment).

```mermaid
flowchart TD
    A["Signal with a direction"] --> B{"Pre-filters"}
    B -- "wick trap, BTC not aligned, funding crowded, OI spike, low volume, S/R too close" --> R["Rejected with a reason"]
    B -- "pass" --> C{"Ordered checks, first failure wins"}
    C -- "HTF mismatch, quality, coin memory, EV, confidence, meta-filter, survival, R/R, spread" --> R
    C -- "all pass" --> OK["Tradable"]
    R --> H{"Hard block?"}
    H -- "yes" --> X["Stays rejected"]
    H -- "no" --> S{"Softenable and over 70 percent of its threshold?"}
    S -- "yes" --> OK
    S -- "no" --> X
```

| Class | Reasons |
|---|---|
| Hard | `BTC_CHAOTIC_VOLATILITY`, `WICK_TRAP_RISK`, `BTC_NOT_ALIGNED`, `FUNDING_OVERCROWDED_*`, `OI_SPIKE_SQUEEZE_RISK`, `VOLUME_TOO_LOW`, a coin-memory reason about edge or fakeout; and, whatever the reason, EV ≤ −0.10, survival < 25 %, reward/risk < 1.0 or spread ≥ 0.10 % |
| Soft, relaxed | confidence below threshold but above 70 % of it; meta-filter probability below threshold but above 70 % of it; HTF mismatch |
| Soft, kept | low quality, coin-memory mismatch or low combined score, S/R too close; `NEUTRAL` is never relaxed |

`BTC_NOT_ALIGNED` fires when the BTC trend points the other way. The numbers sit in `INSTITUTIONAL_THRESHOLDS`
([`config.py`](../config.py)): funding ±0.04, OI change 10 %, volume ratio 0.05, reward/risk 1.0, vote 0.03, EV −0.10,
quality 20, 3 consecutive losses, −3 % per day.

### 5.5 News sentiment and the macro filter

[`SentimentAnalyzer.full_analysis`](../sentiment_analysis.py) reads six RSS feeds (8 s timeout, 10 min cache) plus
CryptoPanic when a key is set, keeps titles containing the coin symbol or "crypto", and scores them with VADER. The score
is `0.6·(mean compound + 1)·50 + 0.2·Fear&Greed + 0.2·CoinGecko up-votes`. It is a meta-filter feature and appears in
reports; it does not change the vote, the confidence or the threshold.

[`MacroSentinel.get_macro_risk_score`](../macro_sentinel.py) runs because the bot identifier is `BOT2_AGGRESSIVE`
([`db_manager.py`](../db_manager.py)). Points: USD/TRY up > 1.5/2/3 % over five days (20/30/40), a spike-and-retrace
(+20), BTC dominance > 62 % (+15), total market cap down > 3/5 % in 24 h (10/20), Fear & Greed ≤ 15 (+20), 16 to 20
or ≥ 85 (+10).

| Score | Level | Size × | Threshold + | Engine |
|---|---|---|---|---|
| < 40 | `NORMAL` | 1.0 | 0 | |
| 40 to 64 | `DIKKATLI` | 0.75 | 5 | |
| 65 to 84 | `YUKSEK_RISK` | 0.50 | 15 | |
| ≥ 85 | `KRIZ` | 0.25 | 25 | no new entries, open trades keep running |

### 5.6 The simulated trade executor

**Entry** ([`execute_trade`](../trade_executor.py)) is skipped when the coin is already open, within 30 s of its last
close, or after three losing trades when the latest closed under 20 minutes ago. Margin is
`balance × clamp(0.06 × multipliers, 2 %, 20 %)`, at least 10 USDT. The multipliers: trade quality < 75 (0.5),
drawdown (`max(0.1, 1 − 3·drawdown)`), 3 or 5 losses in a row (0.5 or 0.25), range regime (0.7), 1h correlation ≥ 0.70
with another open coin (0.5), meta-filter probability within 0.10 of its threshold (0.5), the macro factor and the
quality multiplier (entry quality, distance to support/resistance between 1.5 and 2.5 %, fixed UTC+3 hours).

**Exit** ([`update_positions`](../trade_executor.py), first match wins): peak-profit protection (peak ≥ 1 %, now
≤ 0.2 %), momentum-decay exit, weak-momentum profit take, TP1 (book half, stop to entry, stay open), trailing stop
(armed at the TP1 level with momentum ≥ 0.65, 1 to 2 ATR wide), stop-loss, take-profit, structure exit, a 3 h stop for
trades below −0.5 %, and a 24-candle time limit. The momentum score (0 to 1) mixes ADX, EMA stacking, relative volume,
breakouts, candle body and RSI on 15m candles.

**Engine guards** ([`bot_engine.py`](../bot_engine.py)): `get_daily_loss_stats` stops new entries for the rest of the
Turkey-time day after 3 consecutive losses or a −3 % day. The invalidation guard closes a trade when the new scan points
the other way with confidence ≥ 85 (+5 in profit, +8 above +1 %, +5 with strong momentum), not in the first 15 minutes
unless the counter-signal reaches 95.

### 5.7 Learning loop

- **Coin memory**: each close stores a vector and an outcome (1 if TP1 hit, R ≥ 0.75 or PnL ≥ 1 %).
  [`evaluate_final_intelligence`](../coin_intelligence.py) compares the live vector with the three most similar past
  trades and rejects on low historical edge, a high fakeout rate in a range, or a low combined score.
- **Meta-filter**: [`update_weights_from_history`](../signal_generator.py) needs 20 closed trades. It labels the last
  100 by `0.45·R + 0.20·MFE/MAE + 0.25·exit_efficiency − duration_penalty` (drops 0.45 to 0.55) and trains
  [`QuantMetaFilter`](../signal_generator.py), a NumPy logistic regression on 15 features. Untrained it answers 0.90.
  The same function re-estimates factor weights over 50/200/1000-trade windows, but the signal path never reads them.
- **Counterfactuals**: [`CounterfactualAnalyzer`](../counterfactual_analyzer.py) follows closed trades and rejected
  directional signals for 24 h. Early exits raise "exit patience" (up to ×1.5 on the target); missed profits raise
  "entry courage" (up to ×1.3, dividing the confidence threshold).

### 5.8 Telegram, API, panel and security model

[`TelegramNotifier`](../telegram_notifier.py) sends open/close and TP1 alerts, a learning update per close, macro level
changes and a 6-hourly memory report. [`HybridDatabaseManager`](../db_manager.py) uploads trades, avoided trades and
memory as one pinned JSON document 15 s after the last trade-file write, and restores it on start-up and on
`GET /api/trades` or `/api/avoided` (at most every 20 s), ignoring backups from another sender or `bot_id` and merging
by trade id (closed beats open).

The API ([`app.py`](../app.py)) has public `GET` routes for opportunities, trades, avoided trades, memory, spot
portfolio, settings, logs, balance, counterfactuals and per-coin analysis, and five admin `POST` routes: settings,
close-trade, telegram-test, memory-report, danger-reset-db. The panel is one HTML file that polls the `GET` routes and
sends admin calls through `adminFetch`.

- `require_admin` fails closed: 503 without `ADMIN_TOKEN`, 401 for a missing or wrong `X-Admin-Token`, compared with
  `hmac.compare_digest`. The panel keeps the token in `sessionStorage` for the tab.
- CORS is opened only to `CORS_ORIGINS`; when empty, no CORS header (same origin only).
- `GET /api/settings` returns `tg_token_set`, never the token; `redact_secrets` ([`log_manager.py`](../log_manager.py))
  strips Telegram tokens from log lines on write and again on `/api/logs`.
- `/api/analysis/<coin>/<timeframe>` accepts only `^[A-Z0-9]{2,15}$` and listed timeframes, never adds a custom coin to
  the shared list, and logs to the console only.
- Not covered: all read routes are public, there is no rate limiting besides the sync throttle, and Flask's built-in
  server is used.

## 6. Design decisions and trade-offs

- **API and engine in one process** keeps hosting to a single web instance. The price is shared state and
  read-modify-write races on `bot_trades.json` between the engine and `/api/close-trade` (each write is atomic, the
  sequence is not). The `gc.collect()` calls and the 30 s start delay are memory workarounds, per the code comments.
- **JSON plus a pinned Telegram document instead of a database**: the host disk is not persistent and a pinned message
  survives restarts. The cost is whole-file rewrites and merge rules instead of transactions.
- **Simulation is locked in code**, not left to a setting.
- **Rules plus a learning layer**: rules keep each decision explainable in the log; the memory and meta-filter were
  meant to learn which setups work. `LEARN_AND_APPLY` replaced an older `LEARN` mode that entered every directional
  signal; both branches, and an `OBSERVE_ONLY` one, are still in `generate_signal`.
- **Fail closed** on admin access and hard filters, but **fail open** in data paths: an untrained meta-filter passes
  (0.90), a failed BTC analysis means no BTC block, an unknown daily trend counts as long, missing futures data or news
  fall back to neutral values, and an error in the daily loss guard means "not banned".

## 7. Testing strategy

Run for this document with `python -m pytest` on Python 3.10: **78 passed** in about 7 s, all offline.
[`tests/conftest.py`](../tests/conftest.py) imports `app` inside a temporary directory with `DISABLE_BOT_ENGINE=1` and
blank Telegram variables; each test gets its own directory.

| File | Tests | Focus |
|---|---|---|
| [`test_api_security.py`](../tests/test_api_security.py) | 52 | 503/401 on the five admin routes (20 cases), token masking, CORS, input validation, public `GET` routes changing nothing |
| [`test_log_redaction.py`](../tests/test_log_redaction.py) | 12 | No Telegram token in logs or error messages |
| [`test_trading_logic.py`](../tests/test_trading_logic.py) | 9 | Manual close PnL and time zone, daily loss guard, Telegram credential fallbacks, reset unpinning |
| [`test_demo_data.py`](../tests/test_demo_data.py) | 3 | Synthetic candles and demo trades |
| [`test_sentiment_rss.py`](../tests/test_sentiment_rss.py) | 2 | RSS timeout and filtering |

CI ([`ci.yml`](../.github/workflows/ci.yml)) byte-compiles every module and runs the suite. Coverage is strong on API
security and thin on trading logic: `generate_signal`, sizing and the exit rules have no direct tests, which is how the
dead branches below survived.

## 8. Limitations, known gaps and next steps

Found while writing this document and deliberately left unfixed (documentation-only pass):

- **BTC regime is always `RANGE`.** `run_engine` maps names such as `STRONG BULL` that `detect_market_regime` never
  returns, so `BTC_CHAOTIC_VOLATILITY` cannot fire and BTC's regime never moves SOL's threshold (its trend still does).
- **Two experts never fire**: `bb_width` is read from the indicators but never written, so it stays 0.05.
- **Time exits are shadowed.** In `update_positions` the structure-exit `elif` is entered for any long with a support
  level (or short with a resistance level) even when its price test fails, so the 3 h stop and the time limit never run
  for normal trades. Its buffer also treats `atr%` as a fraction, putting the level far beyond the stop.
- **Unreachable filters**: quality is at least 30, so the quality (< 20) and HTF (< 25) rejects never trigger;
  reward/risk is at least 1.0 by construction; the memory check wants 4 matches but gets at most 3.
- **Mismatches**: the learned factor weights are unused; live meta-filter features always carry BTC alignment 0 while
  training uses ±1; memory vectors hold zeros where the live vector has Bollinger width and ADX; the wick filter uses
  the bid and the 24 h range as its "candle"; ccxt reports funding as a fraction (about 0.0001), so ±0.04 is rarely
  reached; a signal relaxed on confidence skips the later meta-filter check; `NEUTRAL` signals are logged as avoided
  trades and close at once as "successfully avoided"; trade ids are whole seconds; `/api/danger-reset-db` imports a
  module that is not in the repository (500).
- **Method**: signals use the still-forming candle, confidence is not calibrated, and nothing measures performance out
  of sample.

The natural next steps (tests for `generate_signal` and `update_positions`, closed-candle inputs, a transactional
store, measured evaluation) were taken in a new codebase instead: [trading2](https://github.com/CoskunerBerke/trading2).

## 9. Code tour

1. [`config.py`](../config.py): coins, thresholds, `AI_MODE`.
2. [`bot_engine.py`](../bot_engine.py) `run_engine`: the loop and engine guards.
3. [`signal_generator.py`](../signal_generator.py) `generate_signal`: vote, confidence, filters, rejects.
4. [`trade_executor.py`](../trade_executor.py) `execute_trade`, `update_positions`: sizing and exits.
5. [`technical_analysis.py`](../technical_analysis.py) `full_analysis`, `detect_market_regime`.
6. [`coin_intelligence.py`](../coin_intelligence.py) `evaluate_final_intelligence`.
7. [`macro_sentinel.py`](../macro_sentinel.py) and [`sentiment_analysis.py`](../sentiment_analysis.py).
8. [`db_manager.py`](../db_manager.py): Telegram backup and merge rules.
9. [`app.py`](../app.py): routes, `require_admin`, CORS.
10. [`tests/test_api_security.py`](../tests/test_api_security.py): the security contract.

## 10. Glossary

| Term | Meaning |
|---|---|
| `yon`, `durum`, `AÇIK`, `KAPALI` | Direction, status, open, closed |
| `giris_fiyati`, `cikis_fiyati`, `miktar_usdt`, `kaldirac` | Entry price, exit price, margin, leverage |
| ATR, ADX, EMA, RSI, MACD | Standard technical indicators |
| Regime | Market-state label from `detect_market_regime` |
| HTF | Higher timeframe |
| R, MFE, MAE | Move in units of the initial stop distance; best and worst excursion |
| EV | Expected value of a trade in R |
| Meta-filter | A second model that accepts or rejects the first one's signal |
| TP1 | First take-profit: half booked, stop moved to entry |
| Funding rate, open interest | Perpetual-futures payment between longs and shorts; open contracts |
| Counterfactual | What a closed or rejected trade would have done |
| `KRIZ`, `DIKKATLI`, `YUKSEK_RISK` | Macro levels: crisis, cautious, high risk |

## Türkçe özet

**coin-proje-bot2**, yazarın ilk kripto sinyal botu denemelerinden biridir ve referans için tutulan bir demodur; gerçek
proje [trading2](https://github.com/CoskunerBerke/trading2)'dir. Tek bir Python süreci Flask API'yi sunar ve arka planda
bir motor çalıştırır. Motor, Binance vadeli piyasasının herkese açık verisiyle BTC ve SOL için göstergeleri hesaplar,
sekiz kural "uzmanın" oylarını piyasa rejimi ve coin ağırlıklarıyla birleştirip yönü bulur, güven, EV ve Monte Carlo
hesaplarından sonra filtreleri uygular ve geçen sinyalleri 1.000 USDT'lik sanal bakiyede 3x kaldıraçla **simülasyon**
işlemi olarak açar. Depoda gerçek emir gönderen kod yoktur.

Belge mimariyi, akışları, veri modelini, sert ve yumuşak red mantığını, haber ve makro filtrenin etkisini, öğrenme
döngüsünü ve güvenlik modelini koddan doğrulanmış haliyle anlatır; okurken bulunan ama düzeltilmeyen sorunlar 8.
bölümdedir.

- **Sinyal:** sekiz kural oyu × rejim ağırlığı × coin ağırlığı; ±0,03 yönü belirler. Haber duygusu oya ve güvene girmez.
- **Redler:** sert redler (fitil tuzağı, BTC uyumsuzluğu, funding, OI, hacim, negatif EV, düşük sağkalım, geniş spread)
  esnetilmez; güven ve meta-filtre redleri eşiğin %70'ini geçiyorsa `LEARN_AND_APPLY` modunda esnetilir.
- **Makro filtre:** USD/TRY, BTC dominansı, piyasa değeri ve Korku & Açgözlülük; `KRIZ` seviyesinde yeni işlem açılmaz.
- **İşlem yöneticisi:** bakiyenin %2 ile %20'si arası marjin, TP1'de yarısını realize edip stopu girişe çekme, takip
  eden stop; günde 3 ardışık zarar veya -%3 sonrası o gün yeni işlem yok.
- **Güvenlik:** durum değiştiren her uç nokta `X-Admin-Token` ister (`ADMIN_TOKEN` yoksa 503, yanlışsa 401), CORS izin
  listesi, token gizleme, coin sembolü doğrulaması.
- **Testler:** 78 çevrimdışı test geçiyor; ağırlık API güvenliğinde, sinyal ve çıkış mantığının doğrudan testi yok.
