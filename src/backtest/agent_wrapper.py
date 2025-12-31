"""
Backtest Agent Wrapper
======================

Adapts the production Multi-Agent system for Backtesting.

Key Components:
1. BacktestSignalCalculator: Re-implements technical analysis logic locally (since we don't have the external DataSyncAgent in backtest).
2. BacktestAgentRunner: Orchestrates the agents (Critic, etc.) using simulated data.

Author: AI Trader Team
Date: 2025-12-31
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass

from src.agents.decision_core_agent import DecisionCoreAgent
from src.utils.logger import log


class BacktestSignalCalculator:
    """
    Re-implements core signal logic for Backtesting.
    Generates numeric scores compatible with DecisionCoreAgent.
    """
    
    @staticmethod
    def calculate_ema(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()
    
    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9, m1: int = 3, m2: int = 3):
        low_min = low.rolling(window=n).min()
        high_max = high.rolling(window=n).max()
        
        rsv = 100 * (close - low_min) / (high_max - low_min)
        
        # Use EWM for smooth K and D (classic KDJ uses SMA, but EWM is common in crypto)
        # Using com=m-1 which is equivalent to alpha=1/m
        k = rsv.ewm(alpha=1/m1, adjust=False).mean()
        d = k.ewm(alpha=1/m2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return k, d, j

    @staticmethod
    def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        macd_hist = (macd_line - signal_line) * 2
        return macd_line, signal_line, macd_hist

    def analyze_trend(self, df: pd.DataFrame) -> Dict:
        """Calculate trend score (-100 to +100)"""
        if df is None or len(df) < 60:
            return {'score': 0, 'signal': 'neutral', 'details': {}}
            
        close = df['close']
        ema20 = self.calculate_ema(close, 20)
        ema60 = self.calculate_ema(close, 60)
        
        curr_close = close.iloc[-1]
        curr_ema20 = ema20.iloc[-1]
        curr_ema60 = ema60.iloc[-1]
        
        score = 0
        details = {'ema_status': 'neutral'}
        
        # Basic EMA Alignment
        if curr_close > curr_ema20 > curr_ema60:
            score = 60
            details['ema_status'] = 'bullish_alignment'
        elif curr_close < curr_ema20 < curr_ema60:
            score = -60
            details['ema_status'] = 'bearish_alignment'
        elif curr_close > curr_ema20 and curr_ema20 < curr_ema60:
             score = 20 # Potential reversal up
             details['ema_status'] = 'potential_reversal_up'
        elif curr_close < curr_ema20 and curr_ema20 > curr_ema60:
             score = -20 # Potential reversal down
             details['ema_status'] = 'potential_reversal_down'
             
        return {'score': score, 'signal': 'long' if score > 0 else 'short', 'details': details}

    def analyze_oscillator(self, df: pd.DataFrame) -> Dict:
        """Calculate oscillator score (-100 to +100)"""
        if df is None or len(df) < 30:
            return {'score': 0, 'signal': 'neutral', 'details': {}}
            
        close = df['close']
        high = df['high']
        low = df['low']
        
        # RSI
        rsi = self.calculate_rsi(close, 14)
        curr_rsi = rsi.iloc[-1]
        
        # KDJ
        k, d, j = self.calculate_kdj(high, low, close)
        curr_j = j.iloc[-1]
        
        score = 0
        details = {'rsi_value': round(curr_rsi, 1), 'kdj_j': round(curr_j, 1)}
        
        # RSI Logic
        if curr_rsi < 30:
            score += 40 # Oversold -> Bullish
        elif curr_rsi > 70:
            score -= 40 # Overbought -> Bearish
            
        # KDJ Logic
        if curr_j < 20:
             score += 30
        elif curr_j > 80:
             score -= 30
             
        return {'score': score, 'signal': 'long' if score > 0 else 'short', 'details': details}

    def compute_all_signals(self, snapshot) -> Dict:
        """
        Compute full quant analysis structure compatible with DecisionCoreAgent
        """
        # Calculate Trend Scores
        t_5m = self.analyze_trend(snapshot.stable_5m)
        t_15m = self.analyze_trend(snapshot.stable_15m)
        t_1h = self.analyze_trend(snapshot.stable_1h)
        
        # Calculate Oscillator Scores
        o_5m = self.analyze_oscillator(snapshot.stable_5m)
        o_15m = self.analyze_oscillator(snapshot.stable_15m)
        o_1h = self.analyze_oscillator(snapshot.stable_1h)
        
        # Structure matches QuantAnalystAgent output
        return {
            'trend': {
                'trend_5m_score': t_5m['score'],
                'trend_15m_score': t_15m['score'],
                'trend_1h_score': t_1h['score'],
                'trend_5m': t_5m,
                'trend_15m': t_15m,
                'trend_1h': t_1h
            },
            'oscillator': {
                'osc_5m_score': o_5m['score'],
                'osc_15m_score': o_15m['score'],
                'osc_1h_score': o_1h['score'],
                'oscillator_5m': o_5m,
                'oscillator_15m': o_15m,
                'oscillator_1h': o_1h
            },
            'sentiment': {
                'total_sentiment_score': 0, # Placeholder, hard to simulate without global data
                'details': {'note': 'Sentiment neutral in backtest'}
            }
        }


class BacktestAgentRunner:
    """
    Wraps the Agent System for Backtesting.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        # We only need the DecisionCoreAgent (The Critic) to make final decisions
        # The other agents (Strategist, etc.) are simulated by BacktestSignalCalculator
        self.decision_core = DecisionCoreAgent()
        self.calculator = BacktestSignalCalculator()
        
        log.info("🤖 BacktestAgentRunner initialized")

    async def step(self, snapshot) -> Dict:
        """
        Process one backtest step
        """
        try:
            # 1. Calculate Signals
            quant_analysis = self.calculator.compute_all_signals(snapshot)
            
            # 2. Make Decision via Critic
            # We mock the PredictResult as None (ML disabled for speed/simplicity in backtest)
            market_data = {
                 'df_5m': snapshot.stable_5m,
                 'current_price': snapshot.live_5m.get('close', 0)
            }
            
            vote_result = await self.decision_core.make_decision(
                quant_analysis=quant_analysis,
                predict_result=None,
                market_data=market_data
            )
            
            # 3. Format result
            return {
                'action': vote_result.action, # 'long', 'short', 'hold'...
                'confidence': vote_result.confidence,
                'reason': vote_result.reason,
                'vote_details': vote_result.vote_details,
                'weighted_score': vote_result.weighted_score
            }
            
        except Exception as e:
            log.error(f"Backtest agent step error: {e}")
            return {
                'action': 'hold',
                'confidence': 0,
                'reason': f"Error: {str(e)}"
            }
