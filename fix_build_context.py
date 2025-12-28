# Find and replace the entire _build_market_context method with the correct implementation

with open('main.py', 'r') as f:
    content = f.read()

# Find the start of the method
import re

# The method signature to find
method_start = r'    def _build_market_context\(self, quant_analysis: Dict, predict_result, market_data: Dict, regime_info: Dict = None, position_info: Dict = None\) -> str:'

# Find the next method after this one to know where to stop
next_method = r'\n    def run_once\(self\) -> Dict:'

# Extract everything between these two points
pattern = f'({method_start}.*?)({next_method})'
match = re.search(pattern, content, re.DOTALL)

if not match:
    print("❌ Could not find method boundaries")
    exit(1)

# Build the new method implementation
new_method = '''    def _build_market_context(self, quant_analysis: Dict, predict_result, market_data: Dict, regime_info: Dict = None, position_info: Dict = None) -> str:
        """
        构建 DeepSeek LLM 所需的市场上下文文本 (Four-Layer Strategy Format)
        """
        # 🚨 LAYER BLOCK PRE-CHECK (Hard Constraint)
        four_layer_status = quant_analysis.get('four_layer_result', {})
        if not four_layer_status.get('layer1_pass', True) or not four_layer_status.get('layer2_pass', True):
            reason = four_layer_status.get('blocking_reason', 'Unknown')
            return f"""⛔ LAYERS 1-2 BLOCKED: {reason}

HARD CONSTRAINT VIOLATED. Output: WAIT.

Reasoning: Four-Layer Strategy blocks this trade. All other signals irrelevant."""
        
        # Extract data
        current_price = market_data['current_price']
        
        # Four-Layer Status
        layer1_pass = four_layer_status.get('layer1_pass', False)
        layer2_pass = four_layer_status.get('layer2_pass', False)
        layer3_status = four_layer_status.get('layer3_status', 'UNKNOWN')
        layer4_status = four_layer_status.get('layer4_status', 'UNKNOWN')
        blocking_reason = four_layer_status.get('blocking_reason', 'N/A')
        
        # Build layer status text
        if not layer1_pass or not layer2_pass:
            layer_status = f"❌ **Layers 1-2 BLOCKED**: {blocking_reason}"
        else:
            layer_status = "✅ **Layers 1-2 PASSED**: Trend + Fuel OK"
        
        # Multi-Agent Analysis
        trend_analysis = quant_analysis.get('trend_analysis', 'N/A')
        setup_analysis = quant_analysis.get('setup_analysis', 'N/A')
        trigger_analysis = quant_analysis.get('trigger_analysis', 'N/A')
        
        trend_stance = quant_analysis.get('trend_stance', 'UNKNOWN')
        setup_stance = quant_analysis.get('setup_stance', 'UNKNOWN')
        trigger_stance = quant_analysis.get('trigger_stance', 'UNKNOWN')
        
        trend_metadata = quant_analysis.get('trend_metadata', {})
        setup_metadata = quant_analysis.get('setup_metadata', {})
        trigger_metadata = quant_analysis.get('trigger_metadata', {})
        
        # Bull/Bear Analysis
        bull_analysis = quant_analysis.get('bull_analysis', 'N/A')
        bear_analysis = quant_analysis.get('bear_analysis', 'N/A')
        bull_stance = quant_analysis.get('bull_stance', 'NEUTRAL')
        bear_stance = quant_analysis.get('bear_stance', 'NEUTRAL')
        bull_confidence = quant_analysis.get('bull_confidence', 50)
        bear_confidence = quant_analysis.get('bear_confidence', 50)
        
        # Regime info
        regime_type = "Unknown"
        regime_confidence = 0
        price_position = "Unknown"
        price_position_pct = 50
        if regime_info:
            regime_type = regime_info.get('regime', 'unknown')
            regime_confidence = regime_info.get('confidence', 0)
            position_info_regime = regime_info.get('position', {})
            price_position = position_info_regime.get('location', 'unknown')
            price_position_pct = position_info_regime.get('position_pct', 50)
        
        # Build context
        context = f"""# 📊 MARKET DATA INPUT


## 1. Price & Position Overview
- Symbol: {self.current_symbol}
- Current Price: ${current_price:,.2f}



## 2. Four-Layer Strategy Status
{layer_status}
⏳ **Setup (15m)**: {layer3_status}
⏳ **Trigger (5m)**: {layer4_status}

## 3. Multi-Agent Semantic Analysis (Deep Dive)

### 🔮 TREND AGENT [{trend_stance}] (Strength: {trend_metadata.get('strength', 'UNKNOWN')}, ADX: {trend_metadata.get('adx', 0):.1f})
{trend_analysis}

### 📊 SETUP AGENT [{setup_stance}] (Zone: {setup_metadata.get('zone', 'UNKNOWN')}, KDJ: {setup_metadata.get('kdj_j', 0):.0f})
{setup_analysis}

### ⚡ TRIGGER AGENT [{trigger_stance}] (Pattern: {trigger_metadata.get('pattern', 'NONE')}, RVOL: {trigger_metadata.get('rvol', 1.0):.1f}x)
{trigger_analysis}

---
## 4. Market Regime & Price Position (Auxiliary)
- Market Regime: {regime_type.upper()} ({min(max(regime_confidence, 0), 100):.0f}% confidence)
- Price Position: {price_position.upper()} ({min(max(price_position_pct, 0), 100):.1f}% of range)



---
## 🐂🐻 Adversarial Analysis

### 🐂 Bull Agent [{bull_stance}] (Confidence: {bull_confidence:.0f}%)
{bull_analysis}

### 🐻 Bear Agent [{bear_stance}] (Confidence: {bear_confidence:.0f}%)
{bear_analysis}

---

Analyze the above data following the strategy rules in system prompt. Output your decision.

"""
        return context

'''

# Replace the old method with the new one
replacement = new_method + '\n' + match.group(2)
content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Replaced _build_market_context with correct four-layer implementation")
