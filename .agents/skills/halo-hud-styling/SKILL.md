---
name: halo-hud-styling
description: Adjust shared Halo Glass HUD styling, geometry and artwork for in-game review.
---

Use style.json for supported numeric and colour controls. halo/tuning.py validates
their schema and ranges. Edit geometry in halo/layout.py or the owning component.
Preserve established anchors and native bindings for both dials.

Use matched HUD editor and gameplay captures to review appearance. For a
texture-only investigation, inspect the generated asset and its decoded runtime
copy. Use the release workflow in AGENTS.md for an authorized test build.
