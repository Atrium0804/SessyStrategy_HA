#!/usr/bin/env python3

# Debug the charge setpoint calculation
def debug_charge_setpoint(soc, soc_target, prepeak_window_h, capacity_wh=5000, max_power_w=2200):
    print(f"Input: soc={soc}, soc_target={soc_target}, prepeak_window_h={prepeak_window_h}")
    print(f"Capacity: {capacity_wh} Wh, Max power: {max_power_w} W")
    
    gap_wh = (soc_target - soc) / 100.0 * capacity_wh
    print(f"gap_wh = ({soc_target}-{soc})/100 * {capacity_wh} = {gap_wh} Wh")
    
    spread_w = gap_wh / prepeak_window_h
    print(f"spread_w = {gap_wh} / {prepeak_window_h} = {spread_w} W")
    
    power_w = spread_w * 1.5
    print(f"power_w = {spread_w} * 1.5 = {power_w} W")
    
    power_w = min(power_w, max_power_w)
    print(f"power_w (capped) = min({power_w}, {max_power_w}) = {power_w} W")
    
    min_power_w = max_power_w * 0.66
    print(f"min_power_w = {max_power_w} * 0.66 = {min_power_w} W")
    
    result = max(min_power_w, power_w)
    print(f"result = max({min_power_w}, {power_w}) = {result} W")
    
    return result

if __name__ == "__main__":
    print("=== Test 1: Basic gap ===")
    result = debug_charge_setpoint(50, 90, 2.0)
    print(f"Final result: {result} W")
    
    print("\n=== Test 2: Large gap ===")
    result = debug_charge_setpoint(10, 90, 1.0)
    print(f"Final result: {result} W")
    
    print("\n=== Test 3: Tiny gap ===")
    result = debug_charge_setpoint(89, 90, 2.0)
    print(f"Final result: {result} W")