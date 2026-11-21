---
name: halo-hud-release
description: Check, package or install Halo Glass HUD through the SWOFTY release pipeline.
---

Follow the release workflow in the root AGENTS.md. PROJECT_STATE.md is the current
handoff, and docs/REPOSITORY.md covers local inputs.

Inspect build/build-timings.json and build/release-timings.json when a stage stalls.
If the configured SWOFTY install or cache path is outside the active writable
roots, use elevated tool permissions for the authorized install. Keep existing
Windows ACLs and configured paths.
