# Halo Glass HUD v2

Use this file's directory as the project root. At the start of a chat, read
PROJECT_STATE.md for the installed version, pending feedback and verified results.
Machine-specific paths are in ignored project.local.json. Read other documents and
historical notes when they are relevant to the current task. Confirm that the chat's
active workspace is this directory if file access needs repeated escalation.

## Code map

- style.json and halo/tuning.py hold supported shared styling controls and ranges.
- halo/layout.py defines geometry and sizing. artwork.py, material.py and
  feature_assets.py render assets. instruments.py holds shared instrument definitions.
- halo/composition.py authors both dial records. dials.py defines their namespaces.
  f126.py supplies the 2026-specific record additions.
- halo/sectors.py projects sector text. rpm_mask.py defines the rounded RPM cap/path.
- tools/native_interop.py connects shared native controls. f126_interop.py handles
  2026-specific mode controls. prepare_runtime.py repairs and validates native resources.
- native/src contains the live instrument and executable-guarded sector publishers.
- README.md covers setup, docs/DEVELOPMENT.md covers implementation/history, and
  THIRD_PARTY_NOTICES.md records licences and captured-resource provenance.

## Scope and iteration

- Apply shared instrument/design changes once so they carry into both 2025 and 2026.
  Preserve each generation's native mode/data bindings when editing shared visuals.
- For routine styling, read the exact definitions and required callers. Reuse current
  context and PROJECT_STATE.md. Investigate further when evidence requires it.
- Batch the user's requested edits. A concise summary suffices for isolated text,
  colour, weight and size tweaks. Generate one focused preview for layout/shape work
  when useful or requested. Inspect images before presenting them and synchronize
  preview/runtime definitions. Follow explicit requests to skip previews.
- Use focused checks during iteration. Research formats or broaden regression checks
  when the change or a failure warrants it. Recompile affected DLLs/tests for C++ changes.
- Reuse cached assets and tested DLLs through the existing content/freshness checks.
- Reuse already-read instructions and code within the ongoing change. Read changed
  sections or new dependencies when needed.
- Keep progress updates brief. Report material findings, blockers and completion.

## Requested release build

The established build request includes packaging, installation into the configured
SWOFTY profile and cache verification. Continue through those steps with existing
authorization. Explicit user instructions can narrow the requested deliverable.

1. Use `python -B tools/project.py release --install` for the requested release.
   It manages preparation, rollback, profile snapshot, installation and exact-cache
   verification. Use `release` for explicitly offline packaging. Add `--native` for
   C++ changes. Run the relevant focused tests once for the change.
2. The helper reuses matching artwork, validated composition, packages and installed
   addon files. Source or output changes invalidate the relevant reuse. New native
   composition and texture refresh run both validators. Unchanged composition reuses
   their saved results after matching input/output hashes.
3. If F1 25 is running, continue authorized offline work and request normal game
   closure before installation. Repeat the same command afterward to resume.
4. Review the compact result and new warnings. Open raw logs or timing reports for
   failures or unexplained slowness. Use lower-level scripts for a specific diagnostic.
5. The helper refreshes generated PROJECT_STATE.md facts. Keep owner feedback and
   pending work in its manual notes. Report offline and in-game verification separately.

## Completion and context

- Verify the requested source changes and release deliverables before finishing.
  Distinguish offline checks from observed or user-confirmed in-game results.
- Keep volatile release facts in PROJECT_STATE.md and durable working rules here.
- Use local configuration/CLI options for machine-specific paths.
- Keep routine changes scoped. Add helpers, tests or documentation when the requested
  behavior, a concrete regression or the established release process requires them.

## Reusable command

Repeat the same release command to resume after game closure. Hash-verified outputs
are reused, and matching installed/enabled state skips redundant SWOFTY actions.
Use tools/project.py for status, check, release, state, logs and tune operations. See
docs/REPOSITORY.md for setup and .agents/skills/halo-hud-release/SKILL.md for release use.

For supported visual controls, prefer shared style.json. The local halo-hud-styling
skill describes draft previews and texture-only candidates. Per-asset hashes and
native compatibility checks select reuse automatically. Keep source changes outside
an active build so its captured fingerprints remain consistent.
