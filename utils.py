# utils.py
# Version 1.0
# Contains shared utility functions for calculations to prevent circular imports.

import math

# --- VDOT Pace Table (Seconds per Mile) ---
VDOT_TABLE = {
    30: {'E': 798, 'M': 688, 'T': 641, 'I': 588, 'R': 540},
    35: {'E': 708, 'M': 610, 'T': 569, 'I': 522, 'R': 480},
    40: {'E': 636, 'M': 547, 'T': 510, 'I': 468, 'R': 430},
    42: {'E': 609, 'M': 523, 'T': 488, 'I': 448, 'R': 411},
    45: {'E': 576, 'M': 494, 'T': 461, 'I': 423, 'R': 388},
    50: {'E': 528, 'M': 453, 'T': 422, 'I': 388, 'R': 355},
    55: {'E': 486, 'M': 417, 'T': 389, 'I': 357, 'R': 327},
    60: {'E': 450, 'M': 386, 'T': 360, 'I': 330, 'R': 302},
    65: {'E': 414, 'M': 355, 'T': 331, 'I': 304, 'R': 278},
    70: {'E': 384, 'M': 329, 'T': 307, 'I': 282, 'R': 258},
    75: {'E': 354, 'M': 304, 'T': 283, 'I': 260, 'R': 238},
    80: {'E': 330, 'M': 283, 'T': 264, 'I': 242, 'R': 222},
    85: {'E': 306, 'M': 262, 'T': 245, 'I': 225, 'R': 206},
}

def calculate_dew_point(temp_f, humidity_pct):
    """Calculates the dew point in Fahrenheit."""
    temp_c = (temp_f - 32) * 5 / 9
    rh = humidity_pct / 100
    b = 17.625
    c = 243.04
    gamma = (b * temp_c) / (c + temp_c) + math.log(rh)
    dew_point_c = (c * gamma) / (b - gamma)
    return (dew_point_c * 9 / 5) + 32

def adjust_pace_for_weather(base_pace_seconds, dew_point_f):
    """Adjusts pace based on dew point using a non-linear formula."""
    if dew_point_f <= 60:
        return base_pace_seconds
    
    adjustment_factor = 0.006 * (dew_point_f - 60)
    return base_pace_seconds * (1 + adjustment_factor)

def get_pace_from_vdot(vdot, pace_type):
    """Estimates running pace in seconds per mile from a VDOT score using a lookup table and linear interpolation."""
    vdot_keys = sorted(VDOT_TABLE.keys())
    if vdot <= vdot_keys[0]: return VDOT_TABLE[vdot_keys[0]][pace_type]
    if vdot >= vdot_keys[-1]: return VDOT_TABLE[vdot_keys[-1]][pace_type]
    
    vdot_low = max(k for k in vdot_keys if k <= vdot)
    vdot_high = min(k for k in vdot_keys if k >= vdot)
    
    if vdot_low == vdot_high: return VDOT_TABLE[vdot_low][pace_type]
    
    pace_low = VDOT_TABLE[vdot_low][pace_type]
    pace_high = VDOT_TABLE[vdot_high][pace_type]
    
    interpolation_factor = (vdot - vdot_low) / (vdot_high - vdot_low)
    return pace_low - ( (pace_low - pace_high) * interpolation_factor )
