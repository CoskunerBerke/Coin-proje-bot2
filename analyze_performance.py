import json

def analyze():
    try:
        with open("bot_trades.json", "r", encoding="utf-8") as f:
            trades = json.load(f)
    except Exception as e:
        print(f"Error loading trades: {e}")
        return

    # Filter closed trades
    closed_trades = [t for t in trades if t.get("durum", "").upper() == "KAPALI"]
    
    if not closed_trades:
        print("No closed trades found to analyze.")
        return

    # Helper for safe float conversion
    def sf(val, default=0.0):
        try: return float(val) if val is not None else default
        except: return default

    wins = [t for t in closed_trades if sf(t.get("pnl_usdt")) > 0]
    losses = [t for t in closed_trades if sf(t.get("pnl_usdt")) <= 0]
    
    total_closed = len(closed_trades)
    win_rate = (len(wins) / total_closed) * 100
    
    gross_profit = sum(sf(t.get("pnl_usdt")) for t in wins)
    gross_loss = sum(sf(t.get("pnl_usdt")) for t in losses)
    net_pnl = gross_profit + gross_loss
    
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    
    profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')
    expectancy = net_pnl / total_closed
    
    small_wins = [t for t in wins if sf(t.get("pnl_yuzde")) < 1.0]
    tp1_hits = [t for t in closed_trades if bool(t.get("tp1_hit", False))]

    print("==================================================")
    print("ADVANCED PERFORMANCE & QUANT ANALYTICS")
    print("==================================================")
    print(f"Total Closed Trades: {total_closed}")
    print(f"Win Rate: %{win_rate:.2f}")
    print(f"Net USDT PnL: ${net_pnl:.2f}")
    print(f"Gross Profit: ${gross_profit:.2f} | Gross Loss: ${gross_loss:.2f}")
    print(f"Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}")
    print(f"Profit Factor: {profit_factor:.2f}")
    small_win_rate = (len(small_wins) / len(wins) * 100) if wins else 0
    tp1_hit_rate = (len(tp1_hits) / total_closed * 100) if total_closed else 0

    print(f"Expectancy per Trade: ${expectancy:.2f}")
    print(f"Small Wins (< 1.0%): {len(small_wins)} trades ({small_win_rate:.1f}% of wins)")
    print(f"TP1 Hit Rate: {tp1_hit_rate:.1f}%")
    
    timeout_wins = [
        t for t in closed_trades
        if "ZAMAN_ASIMI" in str(t.get("exit_reason", ""))
        and sf(t.get("pnl_usdt")) > 0
    ]
    print(f"Timeout Wins (AI Noise): {len(timeout_wins)} trades")
    
    # R-Multiple Analysis
    r_multiples = [sf(t.get("realized_R_multiple")) for t in closed_trades if "realized_R_multiple" in t]
    if r_multiples:
        avg_r = sum(r_multiples) / len(r_multiples)
        wins_r = [r for r in r_multiples if r > 0]
        losses_r = [r for r in r_multiples if r <= 0]
        avg_win_r = sum(wins_r)/len(wins_r) if wins_r else 0
        avg_loss_r = sum(losses_r)/len(losses_r) if losses_r else 0
        r_expectancy = (win_rate/100 * avg_win_r) - ((1 - win_rate/100) * abs(avg_loss_r))
        print(f"\n[R-Multiple Metrics]")
        print(f"Average R-Multiple: {avg_r:.3f} R")
        print(f"Expectancy (R): {r_expectancy:.3f} R")

    # Segment: Exit Reasons
    print("\n[Exit Reason Breakdown]")
    reasons = {}
    for t in closed_trades:
        r = str(t.get("exit_reason", "Unknown")).split(" (")[0] # Clean string
        if r not in reasons:
            reasons[r] = {"count": 0, "pnl": 0.0, "wins": 0}
        reasons[r]["count"] += 1
        reasons[r]["pnl"] += sf(t.get("pnl_usdt"))
        if sf(t.get("pnl_usdt")) > 0: reasons[r]["wins"] += 1

    for r, data in sorted(reasons.items(), key=lambda x: x[1]["count"], reverse=True):
        rw = (data["wins"]/data["count"])*100
        rpnl = data["pnl"]
        print(f" - {r:25} | {data['count']:3} trades | Win: %{rw:5.1f} | PnL: ${rpnl:+7.2f}")

    # 1. Exit Reason Details
    print("\n[Exit Reason Advanced Metrics]")
    reasons_adv = {}
    for t in closed_trades:
        r = str(t.get("exit_reason", "Unknown")).split(" (")[0] # Clean string
        if r not in reasons_adv:
            reasons_adv[r] = []
        reasons_adv[r].append(t)
    for r, t_list in sorted(reasons_adv.items(), key=lambda x: len(x[1]), reverse=True):
        avg_r_pnl = sum(sf(x.get("pnl_usdt")) for x in t_list) / len(t_list)
        expectancy_r = avg_r_pnl  # Expectancy for this exit route
        print(f" - {r:25} | Avg PnL: ${avg_r_pnl:+.2f} | Expectancy: ${expectancy_r:+.2f} | Trades: {len(t_list)}")

    # 2. Invalidation Close Win/Loss Ratio
    invalidation_trades = [t for t in closed_trades if "SINYAL_BOZULMA" in str(t.get("exit_reason", ""))]
    if invalidation_trades:
        inv_wins = [t for t in invalidation_trades if sf(t.get("pnl_usdt")) > 0]
        inv_losses = [t for t in invalidation_trades if sf(t.get("pnl_usdt")) <= 0]
        inv_win_rate = (len(inv_wins) / len(invalidation_trades)) * 100
        print(f"\n[Invalidation Close Metrics]")
        print(f"Total Invalidation Closes: {len(invalidation_trades)}")
        print(f"Invalidation Win/Loss Ratio: {len(inv_wins)}W / {len(inv_losses)}L (Win Rate: %{inv_win_rate:.1f})")

    # 3. TP1 Sonrası Final Outcome
    tp1_trades = [t for t in closed_trades if bool(t.get("tp1_hit", False))]
    if tp1_trades:
        tp1_wins = [t for t in tp1_trades if sf(t.get("pnl_usdt")) > 0]
        tp1_losses = [t for t in tp1_trades if sf(t.get("pnl_usdt")) <= 0]
        tp1_win_rate = (len(tp1_wins) / len(tp1_trades)) * 100
        avg_tp1_pnl = sum(sf(x.get("pnl_usdt")) for x in tp1_trades) / len(tp1_trades)
        print(f"\n[TP1 Post-Hit Outcome]")
        print(f"Total Trades hitting TP1: {len(tp1_trades)}")
        print(f"Final Outcome: {len(tp1_wins)}W / {len(tp1_losses)}L (Win Rate: %{tp1_win_rate:.1f})")
        print(f"Average Final PnL after TP1: ${avg_tp1_pnl:+.2f}")
        
        # TP1 Advanced Metrics Breakdown
        tp1_rec_trades = [t for t in closed_trades if t.get("tp1_hit_recorded", False) or t.get("tp1_hit", False)]
        if tp1_rec_trades:
            avg_giveback = sum(sf(t.get("tp1_to_exit_giveback", 0.0)) for t in tp1_rec_trades) / len(tp1_rec_trades)
            max_giveback = max(sf(t.get("tp1_to_exit_giveback", 0.0)) for t in tp1_rec_trades)
            print(f"\n[TP1 Post-Hit Advanced Analytics]")
            print(f"Average Post-TP1 Giveback: {avg_giveback:.2f}%")
            print(f"Max Post-TP1 Giveback: {max_giveback:.2f}%")
            
            post_tp1_reasons = {}
            for t in tp1_rec_trades:
                ptr = str(t.get("post_tp1_exit_reason", t.get("exit_reason", "Unknown"))).split(" (")[0]
                post_tp1_reasons[ptr] = post_tp1_reasons.get(ptr, 0) + 1
            print("Post-TP1 Exit Reason Breakdown:")
            for r, cnt in sorted(post_tp1_reasons.items(), key=lambda x: x[1], reverse=True):
                print(f" - {r:25} | {cnt:3} trades")
 
    # 4. Trailing Stop Efficiency & Peak vs Realized PNL
    trailing_trades = [t for t in closed_trades if "TRAILING" in str(t.get("exit_reason", ""))]
    if trailing_trades:
        avg_trail_eff = sum(sf(t.get("exit_efficiency", 0.0)) for t in trailing_trades) / len(trailing_trades)
        print(f"\n[Trailing Stop Metrics]")
        print(f"Trailing Stop Efficiency: {avg_trail_eff * 100:.1f}%")
         
    avg_peak_pnl = sum(sf(t.get("peak_pnl_pct", 0.0)) for t in closed_trades)
    avg_realized_pnl = sum(sf(t.get("pnl_yuzde", 0.0)) for t in closed_trades)
    avg_peak_diff = sum(sf(t.get("peak_pnl_pct", 0.0)) - sf(t.get("pnl_yuzde", 0.0)) for t in closed_trades) / total_closed
    print(f"\n[Peak vs Realized PNL]")
    print(f"Average Peak PNL: {avg_peak_pnl/total_closed:.2f}%")
    print(f"Average Realized PNL: {avg_realized_pnl/total_closed:.2f}%")
    print(f"Average Peak-to-Realized Giveback: {avg_peak_diff:.2f}%")
 
    # 5. Average Holding Time
    avg_hold_time = sum(sf(t.get("holding_time", 0.0)) for t in closed_trades) / total_closed
    print(f"\n[Holding Time Metrics]")
    print(f"Average Holding Time: {avg_hold_time:.1f} minutes")
    print("Holding Time by Exit Reason:")
    for r, t_list in sorted(reasons_adv.items(), key=lambda x: len(x[1]), reverse=True):
        avg_hold_r = sum(sf(x.get("holding_time", 0.0)) for x in t_list) / len(t_list)
        print(f" - {r:25} | Avg Holding Time: {avg_hold_r:.1f} min")
        
    # 5b. Holding Time Buckets
    print("\n[Holding Time Bucket Analysis]")
    buckets = {
        "0-15m": [],
        "15-45m": [],
        "45-120m": [],
        "120m+": []
    }
    for t in closed_trades:
        ht = sf(t.get("holding_time", 0.0))
        if ht <= 15.0:
            buckets["0-15m"].append(t)
        elif ht <= 45.0:
            buckets["15-45m"].append(t)
        elif ht <= 120.0:
            buckets["45-120m"].append(t)
        else:
            buckets["120m+"].append(t)
            
    for b_name, t_list in buckets.items():
        if t_list:
            b_pnl = sum(sf(x.get("pnl_usdt")) for x in t_list)
            b_wr = (len([x for x in t_list if sf(x.get("pnl_usdt")) > 0]) / len(t_list)) * 100
            print(f" - {b_name:8} | {len(t_list):3} trades | Win: %{b_wr:5.1f} | Net PnL: ${b_pnl:+.2f}")
 
    # 6. Momentum Score vs PNL Correlation
    try:
        import numpy as np
        pnl_vals = [sf(t.get("pnl_usdt")) for t in closed_trades]
        mom_vals = [sf(t.get("momentum_score_exit", 0.5)) for t in closed_trades]
        if len(closed_trades) > 1 and len(set(mom_vals)) > 1:
            corr = np.corrcoef(mom_vals, pnl_vals)[0, 1]
            print(f"\n[Correlation Analysis]")
            print(f"Momentum vs PNL Correlation: {corr:.3f}")
            
        # Entry Quality Score and BTC Alignment Correlation
        eq_vals = [sf(t.get("entry_features", {}).get("entry_quality_score", t.get("entry_quality_score", 0.5))) for t in closed_trades]
        btc_align_vals = [sf(t.get("entry_features", {}).get("btc_alignment_score", t.get("btc_alignment_score", 0.5))) for t in closed_trades]
        if len(closed_trades) > 1 and len(set(eq_vals)) > 1:
            corr_eq = np.corrcoef(eq_vals, pnl_vals)[0, 1]
            print(f"Entry Quality Score vs PNL Correlation: {corr_eq:.3f}")
        if len(closed_trades) > 1 and len(set(btc_align_vals)) > 1:
            corr_btc = np.corrcoef(btc_align_vals, pnl_vals)[0, 1]
            print(f"BTC Alignment Score vs PNL Correlation: {corr_btc:.3f}")
    except Exception as e_corr:
        pass

    # 7. ATR Regime vs PNL
    print("\n[ATR Volatility Regime Breakdown]")
    vol_regimes = {"Low (<0.6%)": [], "Normal (0.6%-1.5%)": [], "High (>1.5%)": []}
    for t in closed_trades:
        vol = sf(t.get("entry_features", {}).get("volatility_regime", 1.0))
        if vol < 0.6:
            vol_regimes["Low (<0.6%)"].append(t)
        elif vol <= 1.5:
            vol_regimes["Normal (0.6%-1.5%)"].append(t)
        else:
            vol_regimes["High (>1.5%)"].append(t)
            
    for regime_name, t_list in vol_regimes.items():
        if t_list:
            reg_pnl = sum(sf(x.get("pnl_usdt")) for x in t_list)
            reg_win_rate = (len([x for x in t_list if sf(x.get("pnl_usdt")) > 0]) / len(t_list)) * 100
            print(f" - {regime_name:20} | {len(t_list):3} trades | Win: %{reg_win_rate:5.1f} | Net PnL: ${reg_pnl:+.2f}")

    # Segment: Regime
    print("\n[Market Regime Breakdown]")
    regimes = {}
    for t in closed_trades:
        r = t.get("market_regime", "UNKNOWN")
        if r not in regimes: regimes[r] = {"count": 0, "pnl": 0.0}
        regimes[r]["count"] += 1
        regimes[r]["pnl"] += sf(t.get("pnl_usdt"))
    
    for r, data in sorted(regimes.items(), key=lambda x: x[1]["pnl"], reverse=True):
        print(f" - {r:15} | {data['count']:3} trades | PnL: ${data['pnl']:+7.2f}")
        
    print("==================================================")

if __name__ == "__main__":
    analyze()
