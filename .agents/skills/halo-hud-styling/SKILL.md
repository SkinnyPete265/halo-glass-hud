---
name: halo-hud-styling
description: Adjust shared Halo Glass HUD styling and preview its instruments using the project tuning controls. Use for HUD colour, typography, battery geometry and focused visual iterations.
---

Read the root AGENTS.md and current PROJECT_STATE.md at chat start.

Use style.json for the supported numeric and colour controls. halo/tuning.py validates
its exact schema and ranges. These settings feed both 2025 and 2026 dial records.
Other geometry remains in halo/layout.py and the component renderer named by AGENTS.md.

- Start `python -B tools/project.py tune` for the local draft editor.
- Draft changes render through the shared Python renderer. Apply settings saves
  style.json explicitly. Export draft downloads JSON without applying it.
- Preserve established anchors and spacing unless the user requests changes.
- Offline text rendering and simulated states approximate native rendering. Confirm
  actual live animation and game bindings through the established in-game test.
- Use one focused preview when requested or helpful for layout changes.

Build only when requested. The release helper chooses the compatible texture-refresh
path for GEARS caption size, weight and colour. It falls back to full composition for
registry, geometry, native-source or archive changes. New composition and texture refresh run both native validators. Matching unchanged
composition reuses saved validation after input/output hash checks.
Use `python -B tools/project.py release --install` for an authorized build/install.
Use `python -B tools/project.py logs LOGFILE` for a compact failure/warning comparison.

See docs/REPOSITORY.md for caching, local inputs and state commands.
