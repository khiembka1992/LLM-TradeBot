with open('main.py', 'r') as f:
    lines = f.readlines()

# Find the line with "def _build_market_context" and insert the method before it
for i, line in enumerate(lines):
    if 'def _build_market_context(self, quant_analysis: Dict, predict_result, market_data: Dict, regime_info: Dict = None, position_info: Dict = None) -> str:' in line:
        # Insert the _format_choppy_analysis method before this
        method_code = '''    def _format_choppy_analysis(self, regime_info: Dict) -> str:
        """Format CHOPPY market analysis for DeepSeek prompt"""
        if not regime_info or regime_info.get('regime') != 'choppy':
            return ""
        
        choppy = regime_info.get('choppy_analysis', {})
        if not choppy:
            return ""
        
        range_info = choppy.get('range', {})
        
        lines_text = [
            "",
            "### ⚠️ CHOPPY MARKET ANALYSIS (Range Trading Intelligence)",
            f"- **Squeeze Active**: {'YES 🔴' if choppy.get('squeeze_active') else 'NO'}",
            f"- **Squeeze Intensity**: {choppy.get('squeeze_intensity', 0):.0f}% (Higher = Breakout More Likely)",
            f"- **Breakout Probability**: {choppy.get('breakout_probability', 0):.0f}%",
            f"- **Potential Direction**: {choppy.get('breakout_direction', 'unknown').upper()}",
            f"- **Range Support**: ${range_info.get('support', 0):,.2f}",
            f"- **Range Resistance**: ${range_info.get('resistance', 0):,.2f}",
            f"- **Mean Reversion Signal**: {choppy.get('mean_reversion_signal', 'neutral').upper().replace('_', ' ')}",
            f"- **Consolidation Bars**: {choppy.get('consolidation_bars', 0)}",
            f"- **💡 Strategy Hint**: {choppy.get('strategy_hint', 'N/A')}",
            ""
        ]
        return "\\n".join(lines_text)

'''
        lines.insert(i, method_code)
        break

with open('main.py', 'w') as f:
    f.writelines(lines)

print("✅ Added _format_choppy_analysis method")
