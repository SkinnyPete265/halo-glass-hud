# Halo Glass HUD v2

Use this directory as the project root. Read [PROJECT_STATE.md](PROJECT_STATE.md)
for the current candidate, owner feedback, and next test. It is the file to
share with a new chat. This file holds durable workflow rules. Local machine
paths come from the ignored `project.local.json`.

## Code map

- `style.json` and `halo/tuning.py` define the shared styling controls.
- `halo/layout.py`, `artwork.py`, `material.py`, `feature_assets.py` and
  `instruments.py` define geometry and generate the HUD assets.
- `halo/composition.py` authors both dial records. `halo/dials.py` defines
  their namespaces and `halo/f126.py` adds the 2026-specific records.
- `tools/native_interop.py` and `tools/f126_interop.py` connect native controls.
  `tools/prepare_runtime.py` assembles and validates both dials and their
  in-game editor preview. `native/src/` contains the live publishers.
- [Repository setup](docs/REPOSITORY.md) covers dependencies and setup.
  [Development notes](docs/DEVELOPMENT.md) hold implementation details.

## Development

- Share artwork and layout across both dials. Preserve their generation-specific
  native bindings and keep the HUD free of UDP dependencies.
- Preserve existing working-tree edits. Keep native, artwork and tooling changes
  separately reviewable when practical.
- Halo is a hobby addon. Keep files, release notes and rollback points tidy,
  and feel free to experiment. Proceed with reasonable, reversible changes even
  when they might temporarily break something. Use checkpoints and focused
  checks so we can iterate or roll back.
- Surface worthwhile improvements as you find them, including during feature
  work. Use your judgment on reversible implementation details. Ask when the
  answer changes the design direction or the action is hard to undo.
- Judge appearance in F1 25 using the HUD editor and gameplay at the owner's usual
  HUD scale. Use source and decoded assets for offline diagnostics.
- Run focused checks for the change. Recompile affected DLLs and run native tests
  for C++ edits. Reuse validated assets and DLLs for unrelated changes.

## Release

- Keep the manifest version and CHANGELOG.md entry aligned. Use the beta
  numbering and release-note format in docs/REPOSITORY.md.

- For a requested build and install, use
  `python -B tools/project.py release --install`. Add `--native` for C++
  changes. Omit `--install` when the request is for offline packaging.
- For a GitHub candidate, dispatch Local release from main with the exact
  approved commit and requested mode. An approval during an install review
  authorizes that install. A design or code review approval accepts the
  changes only. Use install-and-smoke when a boot test is also requested.
  Report the local result after hosted checks pass.
- The release helper handles composition, validation, package reuse, rollback,
  the profile snapshot and exact-cache verification. If F1 25 is open, finish
  preparation, then resume with the same command after normal game closure.
- Use `python -B tools/project.py status` and `check` for local checks. Use
  `logs LOGFILE` for warning and failure details.
- Report the actual SWOFTY version, package/install checks and in-game results.
  The release tool refreshes generated facts in PROJECT_STATE.md. Update its
  handoff notes in place when owner feedback or the next test changes.
