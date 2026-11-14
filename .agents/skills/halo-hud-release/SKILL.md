---
name: halo-hud-release
description: Check, package or install this Halo Glass HUD project through its existing SWOFTY pipeline. Use for project status, release preparation and requested build/install work.
---

Read the root AGENTS.md and local PROJECT_STATE.md when starting a chat.
Use the project root as the working directory. Machine paths come from project.local.json.

- Run `python -B tools/project.py status` for a compact environment/input check.
- Run `python -B tools/project.py check` for focused Python/workflow checks.
- Run `python -B tools/project.py release` to compose, validate and package.
- For an authorized build/install request, use `python -B tools/project.py release --install`.
- Add `--native` when C++ changes require recompilation and native tests.

The release command preserves the installed addon, logs composition/cache output,
checks game closure before installation, snapshots the profile and verifies the cache.
If the game is running, repeat the same command after normal game closure. Matching
inputs and outputs reuse the validated composition and package. Matching installed
files and enabled state skip redundant SWOFTY commands. Stage timings are recorded
in build/build-timings.json and build/release-timings.json.
Use the reported log path to investigate failures. Generated release facts in
PROJECT_STATE.md update automatically. Keep owner feedback in its notes section and
distinguish offline from in-game verification.
