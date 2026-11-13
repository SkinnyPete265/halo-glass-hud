# Halo Glass HUD v2

Use this file's directory as the project root. At the start of a chat, read
PROJECT_STATE.md for the installed version, pending feedback and verified results.
Machine-specific paths are in ignored project.local.json.

## Code map

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
- Keep progress updates brief. Report material findings, blockers and completion.

## Requested release build

The established build request includes packaging, installation into the configured
SWOFTY profile and cache verification. Continue through those steps with existing
authorization. Explicit user instructions can narrow the requested deliverable.

1. Run tools/build.py --compose --skip-preview, then tools/package.py. The compose
   step runs the full native runtime validator. Run relevant regression tests once.
   Run tools/test_workflow.py when changing caching, fingerprints or publication.
2. Preserve the installed release package for rollback. Check whether F1 25 is running
   before updating SWOFTY. If necessary, request normal game closure and continue
   authorized offline work while waiting.
3. Capture build/profile-before-PROFILE-vVERSION.json. Install/enable this addon using
   the configured data directory/profile and build its SWOFTY cache.
4. Run tools/verify_install.py against the exact new cache. Use --same-dlls-as with
   the rollback folder when all DLLs are unchanged. Record intentional DLL changes.
5. Update PROJECT_STATE.md with the installed version, concise pending work and
   verification/report paths. Report relevant warnings and in-game verification status.

## Completion and context

- Verify the requested source changes and release deliverables before finishing.
  Distinguish offline checks from observed or user-confirmed in-game results.
- Keep volatile release facts in PROJECT_STATE.md and durable working rules here.
- Use local configuration/CLI options for machine-specific paths.
- Keep routine changes scoped. Add helpers, tests or documentation when the requested
  behavior, a concrete regression or the established release process requires them.

## Reusable command

Use tools/project.py for status, check and release operations. The release --install
action performs the established build/install/verification sequence. See
docs/REPOSITORY.md for setup and .agents/skills/halo-hud-release/SKILL.md for release use.
