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
- Every development handoff asks the implementing agent for a verification
  handoff. Request the exact branch and commit, a summary mapped to the requested
  changes, the SWOFTY version verified, checks and their results, links to relevant
  logs or screenshots, and any gaps, warnings, or decisions that need review.
  Include the package and install status and the remaining in-game checks.

## Git history

- Do all development and release preparation on `main`. Use versioned packages
  and their recorded commits as release checkpoints. Commit each meaningful
  change once its focused checks pass,
  even when several changes belong to one candidate. Use a short, descriptive
  commit message, such as “Smooth active brake and throttle slats.”
- For longer experiments, make a clearly labelled checkpoint when it gives us
  a useful rollback point. Leave unrelated working-tree edits out of the commit.
- Build test candidates from their exact approved SHA on `main` and record the
  owner's in-game result against it. In release reviews, include a `Commits`
  section with one bullet per included commit, its short SHA and a brief
  description of what changed.
- Use the changelog to summarize each version. After in-game approval, track the
  version and changelog in a separate release metadata commit. When publishing,
  tag the exact commit that produced the verified package.

## Release

- Keep the manifest version, package name and CHANGELOG.md entry aligned.
  Bump the minor version when starting a new development cycle and use `-devN`
  for its approved test builds. Owner approval after in-game testing authorizes
  packaging and installing the same version with the `-devN` suffix removed.
  Follow the numbering examples and release-note format in docs/REPOSITORY.md.

- For a requested build and install, use
  `python -B tools/project.py release --install`. Add `--native` for C++
  changes. Omit `--install` when the request is for offline packaging.
- For a GitHub candidate, dispatch Local release from main with the exact
  approved commit. Use `install` mode for every approved test build and
  release checkpoint, unless the owner explicitly requests package-only.
  A design or code review approval accepts the changes only. Report the
  result after exact-cache verification. The owner starts F1 25 manually.
- For the owner's local installs, always target the `Halo-HUD-Dev` SWOFTY
  profile through `project.local.json`, regardless of which profile is active.
- The release helper handles composition, validation, package reuse, rollback,
  the profile snapshot and exact-cache verification. If F1 25 is open, finish
  preparation, then resume with the same command after normal game closure.
- Use `python -B tools/project.py status` and `check` for local checks. Use
  `logs LOGFILE` for warning and failure details.
- Report the actual SWOFTY version, package/install checks and in-game results.
  Whenever you recommend a candidate for in-game testing or confirm it is ready,
  give the owner a bullet checklist with one item per distinct check. Include
  where to test it and what should happen when that matters.
  The release tool refreshes generated facts in PROJECT_STATE.md. Update its
  handoff notes in place when owner feedback or the next test changes.
