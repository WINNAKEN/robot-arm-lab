"""One logical full finger gap, metres; explicit raw physical coordinate mapping."""
import math
from numbers import Real

def joint_positions(opening_m):
    if isinstance(opening_m,bool) or not isinstance(opening_m,Real) or not math.isfinite(opening_m):
        raise ValueError('opening_m must be a finite real number, excluding bool')
    if not 0. <= opening_m <= .094:
        raise ValueError('opening_m outside [0, .094] metres')
    d=float(opening_m)/2-.020
    return {'KG1_slide_A':d,'KG1_slide_B':d,'KG1_pinion':-d/.0135}
