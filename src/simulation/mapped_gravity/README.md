# 062 generalized-force mapping

Preserves the zero-gravity baseline, then maps full 6 or 12 generalized-force columns to six named joints. Root-wrench prefixes are recorded but never sent as joint efforts. Native values must agree with actual LINK/COM mathematics before each command. Records 240 gravity steps with zero PD, unchanged effort caps, probe fall/contact, and independent root validation. Diagnostic failure, invalid evidence, and the earlier 047 motion result remain separate.

Version-pinned SDK; no installation or hardware operations. Use launch.ps1 -Role test|prepare|run|verify. Each actual purpose is allowed once. Results: outputs/isaac-mapped-gravity-v1/HANDOFF.md.
