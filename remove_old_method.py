with open('main.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
skip_count = 0

for i, line in enumerate(lines):
    # Start skipping at the OLD _build_market_context (line 1270, index 1269)
    if i == 1269 and 'def _build_market_context(self, quant_analysis: Dict, predict_result, market_data: Dict) -> str:' in line:
        skip = True
        print(f"Found old method at line {i+1}, starting skip")
        continue
    
    # Stop skipping when we hit the NEW _build_market_context
    if skip and 'def _build_market_context(self, quant_analysis: Dict, predict_result, market_data: Dict, regime_info: Dict = None, position_info: Dict = None) -> str:' in line:
        skip = False
        print(f"Found new method at line {i+1}, stopping skip. Removed {skip_count} lines")
    
    if skip:
        skip_count += 1
        continue
    
    new_lines.append(line)

with open('main.py', 'w') as f:
    f.writelines(new_lines)

print(f"✅ Removed old _build_market_context method ({skip_count} lines deleted)")
