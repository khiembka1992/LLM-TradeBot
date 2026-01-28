"""
🔝 Symbol Selector Agent - AUTO3 Backtest + AUTO1 Momentum Selection
====================================================================

Responsibilities:
1. Get AI500 Top 10 by volume
2. Stage 1: Coarse filter (1h backtest) → Top 5
3. Stage 2: Fine filter (15m backtest) → Top 3
4. 6-hour refresh cycle
5. Startup execution (mandatory)

AUTO1 (Lightweight):
1. Use last 30 minutes momentum (clear up/down)
2. Select the strongest mover as the single symbol

Author: AI Trader Team
Date: 2026-01-07
Updated: 2026-01-10 (Two-stage selection)
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import threading
import time

from src.utils.logger import log
from src.backtest.engine import BacktestEngine, BacktestConfig


def calculate_adx(klines: List[Dict], period: int = 14) -> float:
    """
    计算 ADX 趋势强度指标
    
    ADX > 25: 强趋势
    ADX 20-25: 趋势形成中
    ADX < 20: 无趋势/震荡
    """
    if len(klines) < period + 2:
        return 0.0
    
    try:
        highs = [float(k['high']) for k in klines]
        lows = [float(k['low']) for k in klines]
        closes = [float(k['close']) for k in klines]
        
        # TR, +DM, -DM 计算
        tr_list, plus_dm_list, minus_dm_list = [], [], []
        for i in range(1, len(klines)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            tr = max(highs[i] - lows[i], 
                     abs(highs[i] - closes[i-1]), 
                     abs(lows[i] - closes[i-1]))
            
            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
            
            tr_list.append(tr)
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        if len(tr_list) < period:
            return 0.0
        
        # Wilder's smoothing
        def smooth(values, period):
            if len(values) < period:
                return []
            result = [sum(values[:period])]
            for v in values[period:]:
                result.append(result[-1] - result[-1]/period + v)
            return result
        
        atr = smooth(tr_list, period)
        if not atr:
            return 0.0
            
        smoothed_plus_dm = smooth(plus_dm_list, period)
        smoothed_minus_dm = smooth(minus_dm_list, period)
        
        if not smoothed_plus_dm or not smoothed_minus_dm:
            return 0.0
        
        # +DI, -DI
        plus_di = [(pdm / atr[i] * 100) if atr[i] > 0 else 0 
                   for i, pdm in enumerate(smoothed_plus_dm)]
        minus_di = [(mdm / atr[i] * 100) if atr[i] > 0 else 0 
                    for i, mdm in enumerate(smoothed_minus_dm)]
        
        # DX
        dx = []
        for i in range(len(plus_di)):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx.append(abs(plus_di[i] - minus_di[i]) / di_sum * 100)
            else:
                dx.append(0)
        
        # ADX = smoothed DX
        if len(dx) >= period:
            adx = sum(dx[-period:]) / period
            return round(adx, 1)
        return 0.0
        
    except Exception as e:
        return 0.0


class SymbolSelectorAgent:
    """
    Automated symbol selection based on backtest performance (AUTO3)
    
    Two-Stage Workflow:
    1. Get AI500 Top 10 by 24h volume
    2. Stage 1: Coarse filter (1h backtest, step=12) → Top 5
    3. Stage 2: Fine filter (15m backtest, step=3) → Top 3
    4. Cache results for 6 hours
    5. Auto-refresh every 6 hours
    """
    
    # AI500 Candidate Pool (30+ AI/Data/Compute coins)
    AI500_CANDIDATES = [
        "FETUSDT", "RENDERUSDT", "TAOUSDT", "NEARUSDT", "GRTUSDT", 
        "WLDUSDT", "ARKMUSDT", "LPTUSDT", "THETAUSDT", "ROSEUSDT",
        "PHBUSDT", "CTXCUSDT", "NMRUSDT", "RLCUSDT", "GLMUSDT",
        "IQUSDT", "MDTUSDT", "AIUSDT", "NFPUSDT", "XAIUSDT",
        "JASMYUSDT", "ICPUSDT", "FILUSDT", "VETUSDT", "LINKUSDT",
        "ACTUSDT", "GOATUSDT", "TURBOUSDT", "PNUTUSDT"
    ]
    
    
    FALLBACK_SYMBOLS = ["FETUSDT", "RENDERUSDT", "TAOUSDT"]  # AI500 fallback

    AUTO1_WINDOW_MINUTES = 30
    AUTO1_THRESHOLD_PCT = 0.8
    AUTO1_INTERVAL = "1m"
    AUTO1_VOLUME_RATIO_THRESHOLD = 1.2
    AUTO1_MIN_ADX = 20  # 最小 ADX 要求（>20 = 有趋势，<20 = 震荡）
    
    def __init__(
        self,
        candidate_symbols: Optional[List[str]] = None,
        cache_dir: str = "config",
        refresh_interval_hours: int = 6,
        lookback_hours: int = 24
    ):
        """
        Initialize Symbol Selector Agent
        
        Args:
            candidate_symbols: List of symbols to evaluate (default: 20 symbols)
            cache_dir: Directory for cache storage
            refresh_interval_hours: Auto-refresh interval (default: 6h)
            lookback_hours: Backtest lookback period (default: 24h)
        """
        self.ai500_candidates = self.AI500_CANDIDATES
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "auto_top3_cache.json"
        
        self.refresh_interval = refresh_interval_hours
        self.lookback_hours = lookback_hours
        
        # Background refresh thread
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_refresh = threading.Event()
        self.last_auto1: Dict[str, Dict] = {}
        
        log.info(
            f"🔝 SymbolSelectorAgent initialized: AUTO3 backtest ({refresh_interval_hours}h refresh) + AUTO1 momentum"
        )

    def _interval_to_minutes(self, interval: str) -> int:
        if not interval:
            return 1
        unit = interval[-1]
        try:
            value = int(interval[:-1])
        except ValueError:
            return 1
        if unit == 'm':
            return max(1, value)
        if unit == 'h':
            return max(1, value * 60)
        if unit == 'd':
            return max(1, value * 60 * 24)
        return 1

    async def select_auto1_recent_momentum(
        self,
        candidates: Optional[List[str]] = None,
        window_minutes: int = AUTO1_WINDOW_MINUTES,
        interval: str = AUTO1_INTERVAL,
        threshold_pct: float = AUTO1_THRESHOLD_PCT,
        volume_ratio_threshold: float = AUTO1_VOLUME_RATIO_THRESHOLD
    ) -> List[str]:
        """
        Select symbols by recent momentum (AUTO1).

        Picks the strongest UP and DOWN movers over the last N minutes.
        If a direction is not "clear" (below threshold), it will still
        return the strongest mover but log the weak signal.
        """
        try:
            from src.api.binance_client import BinanceClient
        except Exception as e:
            log.error(f"❌ AUTO1 failed: BinanceClient unavailable: {e}")
            return [self.FALLBACK_SYMBOLS[0]]

        symbols = candidates or await self._get_expanded_candidates()
        if not symbols:
            return [self.FALLBACK_SYMBOLS[0]]

        interval_minutes = self._interval_to_minutes(interval)
        window_count = max(2, int(window_minutes / interval_minutes))
        limit = max(4, window_count * 2)
        client = BinanceClient()

        results = []
        skipped_low_adx = []  # 记录因 ADX 低而跳过的币种
        for symbol in symbols:
            try:
                klines = client.get_klines(symbol, interval, limit=limit)
                if len(klines) < window_count + 1:
                    continue
                recent = klines[-window_count:]
                previous = klines[:-window_count] if len(klines) > window_count else []

                start_price = recent[0]['close']
                end_price = recent[-1]['close']
                if not start_price:
                    continue
                change_pct = ((end_price - start_price) / start_price) * 100
                recent_volume = sum(k.get('volume', 0.0) for k in recent)
                prev_volume = sum(k.get('volume', 0.0) for k in previous) if previous else 0.0
                volume_ratio = (recent_volume / prev_volume) if prev_volume > 0 else 1.0
                
                # 🆕 获取 1h K线计算 ADX 趋势强度
                try:
                    klines_1h = client.get_klines(symbol, "1h", limit=50)
                    adx = calculate_adx(klines_1h, period=14)
                except Exception:
                    adx = 0.0
                
                # 🆕 过滤无趋势币种 (ADX < 20)
                if adx < self.AUTO1_MIN_ADX:
                    skipped_low_adx.append(f"{symbol}(ADX={adx:.0f})")
                    continue
                
                # 🆕 ADX 增强评分: 动量 × 成交量 × ADX增强因子
                adx_boost = 1.0 + max(0, (adx - 20)) / 50  # ADX=20→1.0, ADX=50→1.6
                score = abs(change_pct) * volume_ratio * adx_boost
                
                results.append({
                    "symbol": symbol,
                    "change_pct": change_pct,
                    "volume_ratio": volume_ratio,
                    "adx": adx,
                    "score": score
                })
            except Exception as e:
                log.warning(f"⚠️ AUTO1 skip {symbol}: {e}")
        
        # 🆕 记录被 ADX 过滤的币种
        if skipped_low_adx:
            log.info(f"📊 AUTO1 跳过低趋势币种 (ADX<{self.AUTO1_MIN_ADX}): {', '.join(skipped_low_adx[:5])}{'...' if len(skipped_low_adx) > 5 else ''}")

        if not results:
            fallback = symbols[0] if symbols else self.FALLBACK_SYMBOLS[0]
            log.warning(f"⚠️ AUTO1 empty results, fallback to {fallback}")
            return [fallback]

        best_up = max(results, key=lambda x: x["change_pct"])
        best_down = min(results, key=lambda x: x["change_pct"])

        strong_ups = [
            r for r in results
            if r["change_pct"] > 0
            and abs(r["change_pct"]) >= threshold_pct
            and r["volume_ratio"] >= volume_ratio_threshold
        ]
        strong_downs = [
            r for r in results
            if r["change_pct"] < 0
            and abs(r["change_pct"]) >= threshold_pct
            and r["volume_ratio"] >= volume_ratio_threshold
        ]

        if strong_ups:
            best_up = max(strong_ups, key=lambda x: x["score"])
        if strong_downs:
            best_down = max(strong_downs, key=lambda x: x["score"])

        selected = []
        if best_up["change_pct"] > 0:
            selected.append(best_up["symbol"])
        if best_down["change_pct"] < 0 and best_down["symbol"] not in selected:
            selected.append(best_down["symbol"])

        if not selected:
            results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
            best = results[0]
            selected.append(best["symbol"])

        def log_selection(label: str, entry: Dict[str, float], strong: bool) -> None:
            magnitude = abs(entry["change_pct"])
            direction = "UP" if entry["change_pct"] >= 0 else "DOWN"
            vol_ratio = entry.get("volume_ratio", 1.0)
            adx_val = entry.get("adx", 0)
            vol_text = f"VOL x{vol_ratio:.2f}"
            adx_text = f"ADX={adx_val:.0f}"
            if strong:
                log.info(
                    f"🎯 AUTO1 {label}: {entry['symbol']} ({direction} {entry['change_pct']:+.2f}% | {vol_text} | {adx_text})"
                )
            else:
                log.info(
                    f"ℹ️ AUTO1 {label} weak (<{threshold_pct:.2f}% or VOL<{volume_ratio_threshold:.2f}x): "
                    f"{entry['symbol']} ({direction} {entry['change_pct']:+.2f}% | {vol_text} | {adx_text})"
                )

        if best_up["symbol"] in selected:
            is_strong = best_up in strong_ups
            log_selection("UP", best_up, is_strong)
        if best_down["symbol"] in selected and best_down["symbol"] != best_up["symbol"]:
            is_strong = best_down in strong_downs
            log_selection("DOWN", best_down, is_strong)

        self.last_auto1 = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "window_minutes": window_minutes,
            "threshold_pct": threshold_pct,
            "volume_ratio_threshold": volume_ratio_threshold,
            "selected": list(selected),
            "results": {entry["symbol"]: dict(entry) for entry in results}
        }

        return selected
    
    async def select_top3(self, force_refresh: bool = False) -> List[str]:
        """
        Select top 3 symbols using two-stage filtering
        
        Stage 1: Coarse filter (1h backtest) on ~16 symbols → Top 5
        Stage 2: Fine filter (15m backtest) on Top 5 → Top 3
        
        Args:
            force_refresh: Force re-run backtests even if cache valid
            
        Returns:
            List of 3 symbol names
        """
        # Check cache validity
        if not force_refresh and self._is_cache_valid():
            cached = self._load_cache()
            symbols = [item['symbol'] for item in cached.get('top3', cached.get('top2', []))]
            if symbols:
                log.info(f"🔝 Using cached AUTO3: {symbols} (age: {self._get_cache_age():.1f}h)")
                return symbols
            else:
                log.warning("⚠️ Cache has empty top3, forcing refresh...")
        
        start_time = time.time()
        
        try:
            # ============================================================
            # STAGE 1: Coarse Filter (1h backtest) → Top 5
            # ============================================================
            log.info("=" * 60)
            log.info("🔄 STAGE 1: Coarse Filter (1h backtest)")
            log.info("=" * 60)
            
            # Get AI500 Top 10
            candidates = await self._get_expanded_candidates()
            log.info(f"📊 Candidates ({len(candidates)}): {candidates}")
            
            # Run 1h backtests (step=12, faster)
            stage1_results = await self._run_backtests_stage(
                symbols=candidates,
                step=12,  # 1-hour intervals
                stage_name="Stage 1"
            )
            
            # Rank and get Top 5
            ranked_stage1 = self._rank_symbols(stage1_results)
            top5_symbols = [item['symbol'] for item in ranked_stage1[:5]]
            
            log.info(f"✅ Stage 1 complete: Top 5 = {top5_symbols}")
            
            # ============================================================
            # STAGE 2: Fine Filter (15m backtest) → Top 2
            # ============================================================
            log.info("=" * 60)
            log.info("🔄 STAGE 2: Fine Filter (15m backtest)")
            log.info("=" * 60)
            
            # Run 15m backtests on Top 5 (step=3, more precise)
            stage2_results = await self._run_backtests_stage(
                symbols=top5_symbols,
                step=3,  # 15-minute intervals
                stage_name="Stage 2"
            )
            
            # Rank and get Top 3
            ranked_stage2 = self._rank_symbols(stage2_results)
            top3_data = ranked_stage2[:3]
            top3_symbols = [item['symbol'] for item in top3_data]
            
            # Save to cache (include both stages for reference)
            self._save_cache(top3_data, {
                "stage1_results": stage1_results,
                "stage2_results": stage2_results,
                "top5": top5_symbols
            })
            
            elapsed = time.time() - start_time
            log.info("=" * 60)
            log.info(f"✅ AUTO3 Two-Stage Selection Complete in {elapsed:.1f}s")
            log.info(f"   Stage 1: {len(candidates)} → 5 symbols (1h backtest)")
            log.info(f"   Stage 2: 5 → 3 symbols (15m backtest)")
            log.info(f"   🎯 Selected: {top3_symbols}")
            log.info("=" * 60)
            
            return top3_symbols
            
        except Exception as e:
            log.error(f"❌ AUTO3 selection failed: {e}", exc_info=True)
            log.warning(f"⚠️ Falling back to default symbols: {self.FALLBACK_SYMBOLS}")
            return self.FALLBACK_SYMBOLS
    
    async def _get_expanded_candidates(self) -> List[str]:
        """Get AI500 Top 10 by 24h volume"""
        try:
            from src.api.binance_client import BinanceClient
            
            client = BinanceClient()
            tickers = client.get_all_tickers()
            
            # Filter AI500 candidates and sort by volume
            ai_stats = []
            for t in tickers:
                if t['symbol'] in self.ai500_candidates:
                    try:
                        quote_vol = float(t.get('quoteVolume', 0))
                        ai_stats.append((t['symbol'], quote_vol))
                    except (ValueError, TypeError):
                        pass
            
            # Sort by volume descending and get Top 10
            ai_stats.sort(key=lambda x: x[1], reverse=True)
            ai500_top10 = [x[0] for x in ai_stats[:10]]
            
            log.info(f"📊 AI500 Top 10: {ai500_top10}")
            
            return ai500_top10
            
        except Exception as e:
            log.error(f"Failed to get expanded candidates: {e}")
            # Fallback: first 10 AI500
            return self.ai500_candidates[:10]
    
    async def _run_backtests_stage(
        self,
        symbols: List[str],
        step: int,
        stage_name: str
    ) -> List[Dict]:
        """Run backtests for a specific stage"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=self.lookback_hours)
        
        valid_results = []
        total = len(symbols)
        
        for i, symbol in enumerate(symbols):
            log.info(f"🔄 [{stage_name}] [{i+1}/{total}] Backtesting {symbol}...")
            try:
                result = await self._backtest_symbol(symbol, start_time, end_time, step)
                if result:
                    valid_results.append(result)
                    log.info(f"   ✅ {symbol}: Return {result['total_return']:+.2f}%, Trades {result['trades']}")
            except Exception as e:
                log.warning(f"   ⚠️ {symbol} failed: {e}")
        
        return valid_results
    
    async def _backtest_symbol(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        step: int = 12
    ) -> Optional[Dict]:
        """Run backtest for a single symbol using thread executor"""
        try:
            config = BacktestConfig(
                symbol=symbol,
                start_date=start_time.strftime('%Y-%m-%d %H:%M'),
                end_date=end_time.strftime('%Y-%m-%d %H:%M'),
                initial_capital=10000.0,
                strategy_mode="technical",  # Use simple mode for speed
                use_llm=False,
                step=step
            )
            
            # Run sync backtest in thread executor to avoid blocking
            loop = asyncio.get_event_loop()
            engine = BacktestEngine(config)
            result = await loop.run_in_executor(None, lambda: asyncio.run(engine.run(progress_callback=None)))
            
            # BacktestResult has .metrics attribute with MetricsResult
            metrics = result.metrics
            
            return {
                "symbol": symbol,
                "total_return": metrics.total_return,
                "sharpe_ratio": metrics.sharpe_ratio,
                "win_rate": metrics.win_rate,
                "max_drawdown": metrics.max_drawdown_pct,
                "trades": metrics.total_trades,
                "profit_factor": metrics.profit_factor
            }
            
        except Exception as e:
            log.error(f"Backtest error for {symbol}: {e}")
            return None
    
    def _rank_symbols(self, results: List[Dict]) -> List[Dict]:
        """
        Rank symbols by composite score
        
        Scoring Formula:
        - Total Return: 30%
        - Sharpe Ratio: 20%
        - Win Rate: 25%
        - Max Drawdown: 15% (inverted penalty)
        - Trade Count: 10% (prefer 3-5 trades)
        """
        scored = []
        
        for result in results:
            # Extract metrics
            ret = result["total_return"]
            sharpe = max(result["sharpe_ratio"], 0)  # No negative Sharpe
            win_rate = result["win_rate"]
            dd = result["max_drawdown"]
            trades = result["trades"]
            
            # Composite score (0-100)
            score = (
                ret * 30 +                           # Return weight
                sharpe * 20 +                        # Sharpe weight
                win_rate * 0.25 +                    # Win rate weight
                max(0, 100 + dd) * 0.15 +           # Drawdown penalty
                min(trades / 5 * 10, 10)            # Trade frequency
            )
            
            result["composite_score"] = round(score, 2)
            scored.append(result)
        
        # Sort by score (descending)
        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        
        return scored
    
    def _is_cache_valid(self) -> bool:
        """Check if cache exists and is still valid"""
        if not self.cache_file.exists():
            return False
        
        try:
            cache = self._load_cache()
            valid_until = datetime.fromisoformat(cache["valid_until"])
            return datetime.now() < valid_until
        except Exception:
            return False
    
    def _get_cache_age(self) -> float:
        """Get cache age in hours"""
        try:
            cache = self._load_cache()
            timestamp = datetime.fromisoformat(cache["timestamp"])
            return (datetime.now() - timestamp).total_seconds() / 3600
        except Exception:
            return 999
    
    def _load_cache(self) -> Dict:
        """Load cache from file"""
        with open(self.cache_file, 'r') as f:
            return json.load(f)
    
    def _save_cache(self, top3: List[Dict], all_results: Dict):
        """Save results to cache"""
        now = datetime.now()
        cache_data = {
            "timestamp": now.isoformat(),
            "valid_until": (now + timedelta(hours=self.refresh_interval)).isoformat(),
            "lookback_hours": self.lookback_hours,
            "selection_method": "two_stage",
            "top3": top3,
            "top5": all_results.get("top5", []),
            "stage1_results": all_results.get("stage1_results", []),
            "stage2_results": all_results.get("stage2_results", [])
        }
        
        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        log.info(f"💾 AUTO3 cache saved: valid until {cache_data['valid_until']}")
    
    def start_auto_refresh(self):
        """Start background thread for auto-refresh every 6 hours"""
        if self._refresh_thread and self._refresh_thread.is_alive():
            log.warning("Auto-refresh thread already running")
            return
        
        def refresh_loop():
            """Background refresh loop"""
            while not self._stop_refresh.is_set():
                # Wait for refresh interval
                if self._stop_refresh.wait(timeout=self.refresh_interval * 3600):
                    break  # Stop signal received
                
                # Run refresh
                log.info(f"🔄 AUTO3 auto-refresh triggered ({self.refresh_interval}h interval)")
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.select_top3(force_refresh=True))
                    loop.close()
                except Exception as e:
                    log.error(f"❌ Auto-refresh failed: {e}", exc_info=True)
        
        self._refresh_thread = threading.Thread(target=refresh_loop, daemon=True, name="AUTO3-Refresh")
        self._refresh_thread.start()
        log.info(f"🔄 AUTO3 auto-refresh started ({self.refresh_interval}h interval)")
    
    def stop_auto_refresh(self):
        """Stop background refresh thread"""
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._stop_refresh.set()
            self._refresh_thread.join(timeout=5)
            log.info("🛑 AUTO3 auto-refresh stopped")
    
    def get_symbols(self, force_refresh: bool = False) -> List[str]:
        """
        Synchronous wrapper for select_top3
        
        Args:
            force_refresh: Force re-run backtests even if cache valid
            
        Returns:
            List of 3 symbol names
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self.select_top3(force_refresh))
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.select_top3(force_refresh))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.select_top3(force_refresh))


# Global instance
_selector_instance: Optional[SymbolSelectorAgent] = None

def get_selector() -> SymbolSelectorAgent:
    """Get global SymbolSelectorAgent instance (singleton)"""
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = SymbolSelectorAgent()
    return _selector_instance
