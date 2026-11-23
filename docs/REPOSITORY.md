# Repository setup

The repository tracks authored source, SDK/font notices, agent instructions and
release helpers. Local settings, game-derived binary inputs, generated textures,
previews, composed archives and installed packages are excluded.

## Local setup

Use Python 3.14 and install requirements.txt. Copy project.local.example.json to
project.local.json and set the launcher, data directory, profile and game paths.
Native builds use Zig. The required local inputs are
native/reference/native-controls.erpk and native/reference/drs-template.bin.
Keep an existing local copy of those inputs. tools/extract_native_reference.py can
capture them from the legacy addon and stock archive using its documented flags.
Fresh source clones require those local inputs before full composition.

## Optional local checks

- `python -B tools/project.py status` shows the source and installed versions,
  whether the target profile exists and has Halo enabled, local inputs and
  whether F1 25 is running.
- `python -B tools/project.py check` runs the project's source checks locally.
  The GitHub workflow runs these checks for you when you dispatch a build.

The release steps start at [Build, package and install step by step](#build-package-and-install-step-by-step).

GitHub Actions runs the Python checks and native fixtures in separate Windows jobs.
The native job pins Zig 0.17.0 and uses the vendored SDK. Run the same fixtures
locally with `python -B tools/build.py --native-tests`. Composition and live
checks use the local game inputs.
If the Zig executable on PATH is inaccessible, set the optional `zig` path
in project.local.json or pass `--zig` to tools/build.py.

The source checks validate the generated HUD registry against SWOFTY's HUD
schema 1.4. The first run downloads the checksum-pinned validator and schema
from the 1.10.21 source revision. Later runs reuse build/sdk-validation/.
Composition checks SWOFTY's active stock game against project.local.json
before using its archives. A full compose also logs `swofty hud check`.

## Build, package and install step by step

1. **Start on `main`.** This is the only working branch. From the repo in
   PowerShell, run `git status --short --branch` and sync with
   `git pull --ff-only` when ready. A versioned package and its recorded commit
   are the rollback checkpoint.
2. **Set the version.** In `swofty.json`, set the version to build. Add a
   nonempty `##` section for the exact same version in `CHANGELOG.md`. Run
   `python -B tools/project.py notes` to see the entry that will be packaged.
   Commit the version and changelog together and push `main`. You can record
   the commit with `git rev-parse HEAD`. A Git tag can be added after verification.
3. **Dispatch one build.** Close F1 25 and other SWOFTY Launcher windows to
   avoid file locks, and leave the release PC signed in. In GitHub, open
   **Actions → Local release → Run workflow**. Select `main`. If the approved
   commit is the latest on `main`, leave **commit** blank. Otherwise paste its
   full 40-character SHA from `main` history without angle brackets. Keep **mode** at `install`
   for a playable build, or choose `package` to create the file only. Click
   **Run workflow** once. The CLI equivalent for current `main` is
   `gh workflow run local-release.yml --ref main -f mode=install`.
4. **Wait for the Windows result.** GitHub's green check means the request passed
   source checks and is queued. Use `python -B tools/local_release.py status RUN_ID`
   on the release PC, replacing `RUN_ID` with the number at the end of the GitHub
   run URL. Wait for `cache_verified`
   for install or `packaged` for package-only. The result gives the versioned
   `.swoftyaddon`, evidence directory and rollback location. Approved installs
   target `Halo-HUD-Dev` through `project.local.json`.
5. **Test manually.** After `cache_verified`, open SWOFTY, select `Halo-HUD-Dev`
   and launch F1 25. Use the candidate's gameplay checklist. Keep packages local
   until public distribution is approved.

### Build on the PC without GitHub

Use this route from the approved checkout when GitHub or the worker is
unavailable. Check the version with `python -B tools/project.py notes`, then
run one command in PowerShell:

| Goal | Command |
| --- | --- |
| Package and install | `python -B tools/project.py release --install --native` |
| Package only | `python -B tools/project.py release --native` |

`--native` rebuilds and tests the DLLs. Omit it only when the required DLLs
are already built and verified for the candidate. The helper prints the release
evidence path under `build/releases/`. For an install, look for
`installation verification passed`. Run local and GitHub installs one at a time.

### If a build stops

- **Changelog error.** Fix the version heading, run `python -B tools/project.py notes`,
  then commit and push the fix before dispatching again.
- **Profile missing.** Run `python -B tools/project.py status` and check the
  SWOFTY store and profile in `project.local.json`.
- **Files in use.** Close other SWOFTY windows and F1 25 normally. For a failed
  GitHub install, dispatch the same SHA again. For a manual install, repeat the
  same command. A worker waiting specifically for game closure resumes on its
  own. Keep the same version for a retry of the same candidate.
- **Green on GitHub, no install yet.** Check the matching job record and worker
  log at `local/release-worker/jobs/<run-id>/release.log`. A scheduled poll can
  take about three minutes. `python -B tools/local_release.py poll` starts the
  same worker immediately on the release PC.

### Windows worker setup

On the Windows release PC, check the local setup above and register the worker
once from the development checkout:

```powershell
.\tools\Register-HaloReleaseWorker.ps1
python -B tools/local_release.py status
```

While the owner is signed in, Task Scheduler checks for requests every three
minutes. The worker uses an isolated checkout under `local/release-worker/`,
rebuilds the DLLs for the requested commit, and reuses the project's release
command. If F1 25 is running, the worker resumes installation when it closes.
Inspect `local/release-worker/jobs/<run-id>.json` for the result and evidence
paths. For a failed or interrupted job, inspect its log and dispatch again
after fixing the problem. Avoid running a manual install concurrently.

The worker reads GitHub over HTTPS. Local inputs, packages and logs stay on the
PC. To pause polling, disable **Halo HUD local release worker** in Task Scheduler.

## Versions and changelogs

Use the manifest's SemVer version for the addon, package, Git tag, and changelog
heading. Start a new development cycle at the next minor version with `-dev1`.
Increment the suffix for revised test candidates and reuse it for retries of
the same commit.

Owner approval after in-game testing authorizes packaging and installing the
tested changes as the stable release for that cycle. Drop the `-devN` suffix
and keep the base version. For example, `0.17.0-dev1` → `0.17.0-dev2` →
`0.17.0` → `0.18.0-dev1`. Record the tested commit, then update the manifest
and changelog on a release commit containing just release metadata. Dispatch
`install` for that commit. Public uploading requires a separate request.

Each release record points to the verified, versioned deliverable
(`local.halo-hud-v2-0.15.0-dev1.swoftyaddon`, for example). The release command
uses the canonical filename in `dist/` internally for installation and cache checks.

Add one `## <version>` section to CHANGELOG.md per version. Use `New/Added`,
`Fixes` and `Miscellaneous` as the default headings. Omit empty sections and
add a heading when it helps, such as `Test status`. Use one concise Markdown
bullet per distinct change. Internal notes are welcome in beta. Keep machine
paths, checkpoints and raw validation evidence in PROJECT_STATE.md or the
release record. Packaging checks
that the manifest version has a matching entry and embeds the changelog.

For an approved public upload, use tag `v<version>` and attach the verified
package to the matching GitHub release. Mark development builds as prereleases.
Run `python -B tools/project.py notes` to print the current entry for GitHub or
SWOFTY's separate changelog field. Review the selected notes before submitting
to the Addon Browser. SWOFTY locks approved version changelogs.

Before a public upload, confirm the creator namespace and display author,
the redistribution status of game-derived inputs, and the compatibility
claims for tested platforms, game builds and seasons. A public source link
can be added when the repository is public.
[SWOFTY publishing documentation](https://f1.swofty.net/reference/addons/publishing.html)

## Folder layout

- `halo/` holds shared HUD sources, `native/` the C++ publishers, SDK and
  captured build inputs, and `tools/` the build and release commands.
- `tests/` holds the Python checks. C++ fixtures live
  under `native/test/`.
- `art/`, `registry/hud.json`, `runtime/` and `dist/` are generated.
- `build/` holds working outputs and release evidence. New recovery packages
  and source checkpoints belong in the ignored `local/archive/`. Existing
  archives under build/ still back older reports and handoffs. Preserve those
  and any release evidence you need when cleaning generated files.
- Keep reference captures under `design/reference/`. Retired preview renders
  are stored locally under `local/archive/design/retired-previews/`.

## Developer iteration

The shared style.json controls HUD scale, wing width and content positioning, text
appearance, battery geometry and colours, GEARS placement and RPM thickness. Both
car generations consume the same validated values. HUD scale applies uniformly around
the centre. Wing extension grows both sides; the optional wing-content link moves
wing-mounted elements outward along the curved layout while keeping the centre
instruments anchored.
Use the game's HUD editor and gameplay to review appearance.

Artwork is cached per asset using input and output hashes. An unchanged asset is
reused. A missing or modified output is regenerated. Source changes invalidate the
cache conservatively. The expensive backing layer is also cached across processes.

GEARS caption size, weight and colour changes can use a texture-only native refresh.
This path requires unchanged registry, source structure and compiled/runtime archive
hashes. It checks resource metadata, replaces matching pixel fragments and runs both
native validators. Other changes use full SWOFTY composition automatically. Cached
outputs and game-derived resources remain local under ignored folders.

Every release attempt refreshes the generated facts block in PROJECT_STATE.md while
preserving owner notes. Refresh it manually or inspect a compact log summary with

```powershell
python -B tools/project.py state
python -B tools/project.py logs build/releases/<run>/compose-v<version>.log
```

Raw logs remain available. Summaries show warning totals, newly introduced warnings
and errors. Successful release/cache verification advances the relevant warning
baseline. Reused composition preserves the previous warning baseline. Baselines stay
local under build/log-baselines.

The repository-local halo-hud-styling skill covers focused visual iterations.

### Repeating a release

Repeat the same release command after closing the game. Matching source/output hashes
reuse the previously validated native composition and package. Missing, changed or
corrupted outputs trigger regeneration. Native source or registry changes invalidate
composition reuse. Packaging still checks runtime freshness before accepting reuse.

Installation compares the package against the installed addon payload and reads
the selected profile. Matching files skip reinstallation, and an enabled addon skips
the enable command. The release warns before building if Project Halo is also
enabled in the profile. SWOFTY handles cache freshness for game/profile changes,
followed by exact-cache verification.

The packager includes build tools from its source list and includes generated
sprites referenced by either dial. Keep experiments and local scripts under
build/ and add new distributable build tools to the list in tools/package.py.

Each release attempt has a directory under build/releases/. Its release.json
records the source commit and tracked edit count, game and launcher identities,
package hash, outcome and cache or
rollback if available. The directory holds the logs, validation and timings,
and the install report after verification. The top-level timing files remain
available for inspecting the most recent run.
If the exact-cache check fails, the release also saves SWOFTY's profile report
as conflicts.log. This reads the last build without rebuilding the profile.

## Manual in-game verification

Launch F1 25 through SWOFTY after the exact-cache check passes. Use that same
session to check boot, split timing, and visual changes.

For the Time Trial check, confirm UDP is off, drive one full flying lap,
restart, then drive another. Compare splits with the game results and check
the display at each gate. Run:

```powershell
python -B tools/check_time_trial.py path/to/loader.log --restart
```

This checks the selected provider, split order, and complete laps across a
logged reset. It reads Halo's own logs. The direct SWOFTY Time Trial start
still needs live verification on the target build, so use the game's normal
Time Trial menu for the repeatable baseline.

For a clipping or editor issue, inspect the relevant IDF in Swofty UI and
compare the archive copies. Use a one-shot Game Assets read if the archive
texture itself is in question. Check actual placement, scaling, and fades in
gameplay and in the HUD editor.
[Swofty UI](https://f1.swofty.net/reference/ui/swofty-ui.html) ·
[Game assets](https://f1.swofty.net/reference/std/game-assets.html)

## Continuing in a fresh chat

Open the project folder and share PROJECT_STATE.md with the next request and any
screenshots. The agent reads AGENTS.md for durable rules and consults skills as
needed. PROJECT_STATE.md is local and ignored by Git. Keep its notes current and
let tools/project.py state refresh the generated facts.
