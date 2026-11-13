# 124 local stage reset candidate

`stage_reset.py` creates a fresh stage, records its initial census, verifies ownership
and zero physics time, clears only its two distinct anonymous layers, and checks
strict emptiness again. Failures preserve the primary exception and record a census
where possible. Old layers and edit targets are never cleared.

`build_candidate.py` requires the exact frozen 119 native source. It replaces only
the `fresh_stage` function and writes a new local candidate and manifest without
overwriting any previous artifact. Importing these modules has no SDK or network
side effects.

Run `py -3.12 -I -B src/simulation/mp18_stage_reset_124/test_stage_reset.py` for
HOST controls. The controls use doubles, including calls to the actual spliced
native function. They do not demonstrate actual USD/Kit behavior or physics.

Plan: `docs/design/124-fresh-stage-reset.md`. This candidate has no launch owner,
fresh job/bundle integration, or authorization for another SDK initialization.
Gains, caps, criteria, robot geometry, and hardware interfaces are unchanged.
