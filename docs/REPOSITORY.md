# Halo Glass HUD build and release guide

Development and release commits live on `main`. The usual workflow is
**make a change → review and select a commit → package and install a dev build → test in-game → prepare the stable release**.

Use [the GitHub steps](#build-package-and-install-step-by-step) for the normal
release. Use [the PowerShell steps](#build-on-the-pc-without-github) if you want
to run a release directly on the PC. Choose one route per build.

## What each stage does

| Stage | What it does |
| --- | --- |
| Commit and push | A commit saves a snapshot of the source with an ID called a SHA. Pushing sends that snapshot to GitHub so the release can use it. A tag is a separate label you can give a verified release commit after building. |
| Source checks | Python tests check the build tools, HUD geometry and generated HUD records. Native fixtures test the C++ publishers that feed values such as gear and energy flow to the HUD. These checks run without launching F1 25. |
| Build and compose | The Windows PC generates the artwork and compiles any DLLs that need rebuilding. SWOFTY combines the HUD records and textures with stock game resources to produce game-ready archives for both dials and the shared editor. |
| Package | Bundles the validated archives, DLLs, manifest and changelog into a `.swoftyaddon` file. `package` mode ends here. |
| Install and verify | Adds or updates the package in SWOFTY, enables Halo in `Halo-HUD-Dev`, builds the profile's game-ready cache, and checks its files and resources against the package and composed outputs. `install` mode includes packaging. |
| In-game test | You manually launch F1 25 through SWOFTY and check the changes. This is where we verify real gameplay behaviour and appearance. |

**Who does what?** GitHub runs the source checks and queues the request. A
scheduled Windows task picks it up and does the build and install using the
game files on your PC. The green GitHub check tells you the request reached the
queue. The Windows worker's `cache_verified` result tells you when to launch.

## Build, package and install step by step

1. **Start on `main`.** This is the only working branch. From the repo in
   PowerShell, run `git status --short --branch` and sync with
   `git pull --ff-only` when ready. `git status` shows local edits and whether
   your branch is ahead of or behind GitHub. The fast-forward-only pull updates
   your branch without creating a merge commit.
2. **Set the version.** In `swofty.json`, set the version to build. Add a
   nonempty `##` section for the exact same version in `CHANGELOG.md`. Run
   `python -B tools/project.py notes` to see the entry that will be packaged.
   If the candidate already has the right version and notes, use its existing
   commit. Otherwise stage the two files with `git add -- swofty.json CHANGELOG.md`
   and commit them with `git commit -m "Prepare dev test release"`. Push `main` with
   `git push origin main`. `git rev-parse HEAD` prints the exact SHA to review
   or rebuild later.
3. **Dispatch one build.** Close F1 25 and other SWOFTY Launcher windows to
   avoid file locks, and leave the release PC signed in. In GitHub, open
   **Actions → Local release → Run workflow**. Select `main`. If the approved
   commit is the latest on `main`, leave **commit** blank. Otherwise paste its
   full 40-character SHA from `main` history without angle brackets. Keep **mode**
   at `install` for a playable build, or choose `package` to create the file only. Click
   **Run workflow** once. The CLI equivalent for current `main` is
   `gh workflow run local-release.yml --ref main -f mode=install`.
4. **Wait for the Windows result.** GitHub's green check means the request passed
   source checks and is queued. Use `python -B tools/local_release.py status RUN_ID`
   on the release PC, replacing `RUN_ID` with the number at the end of the GitHub
   run URL. For example, `python -B tools/local_release.py status 45087449907`
   looks up that specific historical run. Wait for `cache_verified` for install
   or `packaged` for package-only. The result gives the versioned `.swoftyaddon`
   and the evidence directory. For installs it also records the cache and any
   rollback package. `project.local.json` selects `Halo-HUD-Dev` regardless of
   which profile is active in SWOFTY.
5. **Test manually.** After `cache_verified`, open SWOFTY, select `Halo-HUD-Dev`
   and launch F1 25. Use the candidate's gameplay checklist. Keep packages local
   until public distribution is approved.
6. **Finish the cycle.** Record the in-game result against the tested commit in
   `PROJECT_STATE.md`. If a fix needs another test, increment the dev suffix.
   If the test is approved, remove the suffix for the stable release and use
   the same build and install process. See [version examples](#versions-and-changelogs).

### Build on the PC without GitHub

Use this route from the approved checkout when GitHub or the worker is
unavailable. Check the version with `python -B tools/project.py notes`, then
run one command in PowerShell:

| Goal | Command |
| --- | --- |
| Package and install | `python -B tools/project.py release --install` |
| Package only | `python -B tools/project.py release` |

The release helper automatically rebuilds and tests the DLLs when their sources,
headers, fixtures or binary contents change. It reuses verified DLLs for artwork-only
changes. Add `--native` to force a rebuild. The helper prints the release
evidence path under `build/releases/`. For an install, look for
`installation verification passed`. Run local and GitHub installs one at a time.
If the helper warns about local tracked edits, the recorded commit may be
insufficient to reproduce the package. Commit the intended changes before
building a checkpoint you want to reproduce from GitHub.

### Read the result

| Result | Meaning |
| --- | --- |
| `running` | The Windows worker is building, packaging, installing or verifying. |
| `packaged` | The `.swoftyaddon` is ready to keep or share as approved. |
| `cache_verified` | The addon is installed and enabled, and the target profile's cache passed verification. Launch the game manually when ready. |
| `waiting_for_game_close` | The package is ready. For a GitHub job, the worker resumes after the game closes. For a direct PowerShell build, repeat the command after closing the game. |
| `failed` or `interrupted` | Read the worker log or local release evidence, resolve the issue, then retry the same candidate. |

Keep the versioned package listed in the release record. `dist/` holds the
latest working package and is overwritten by later builds. The rollback is a
separate copy of the addon payload that was installed before an update.

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
  log at `local/release-worker/jobs/RUN_ID/release.log`. A scheduled poll can
  take about three minutes. `python -B tools/local_release.py poll` starts the
  same worker immediately on the release PC.
- **Local build or cache error.** Open the evidence folder printed by the release
  helper. `compose-vVERSION.log` covers the HUD build. `swofty-build-vVERSION.log`
  covers cache creation. If cache verification fails, look for `conflicts.log`.

## First-time setup on the release PC

This section is for a fresh checkout or a replacement PC. An existing working
release PC can proceed directly to the release steps.

1. Install Python 3.14 and run `python -m pip install -r requirements.txt`
   from the repository. The Python tools generate artwork and orchestrate the
   build. Zig compiles and tests the native DLLs. Hosted checks pin Zig 0.17.0.
2. Use `project.local.example.json` as the template for `project.local.json`.
   The `launcher` is the path to `swofty.exe`, `data_dir` holds SWOFTY's addons,
   profiles and cache, `profile` selects `Halo-HUD-Dev`, and `game` is the F1 25
   installation folder. Set `zig` to the executable path if Zig is unavailable on
   `PATH`. The local configuration stays off GitHub.
3. Keep a local copy of `native/reference/native-controls.erpk` and
   `native/reference/drs-template.bin`. Composition uses these captured inputs
   to preserve native game bindings. Fresh source clones need them before
   composition. `tools/extract_native_reference.py` can capture them from the
   legacy addon and stock archive.
4. Run `python -B tools/project.py status` and check the profile and both native
   inputs. Make sure SWOFTY's active game points to the same F1 25 installation
   as `project.local.json` so composition reads the correct stock archives.

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
Inspect `local/release-worker/jobs/RUN_ID.json` for the result and evidence
paths. For a failed or interrupted job, inspect its log and dispatch again
after fixing the problem. Avoid running a manual install concurrently.

The worker reads GitHub over HTTPS. Local inputs, packages and logs stay on the
PC. To pause polling, disable **Halo HUD local release worker** in Task Scheduler.

## Optional commands for checks and debugging

| Command | When to use it |
| --- | --- |
| `python -B tools/project.py status` | Before a local build or when in doubt about the installed version, target profile, local inputs or whether F1 25 is running. |
| `python -B tools/project.py notes` | After editing the manifest or changelog. Prints the entry that matches the manifest version. |
| `python -B tools/project.py check` | To run the project's Python checks and HUD schema validation locally. GitHub runs these checks for you when you dispatch a release. |
| `python -B tools/build.py --native-tests` | To run just the C++ fixtures after editing native code. |
| `python -B tools/project.py logs LOGFILE` | To summarize warnings and errors from one raw release log. Replace `LOGFILE` with its actual path. |
| `python -B tools/project.py state` | To refresh the generated facts in `PROJECT_STATE.md` before sharing it with a new chat. |

The source checks use a checksum-pinned HUD schema validator. The first run
downloads it and later runs reuse `build/sdk-validation/`. Full composition
also runs SWOFTY's HUD checks on the release PC.

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

Every release attempt refreshes the generated facts block in `PROJECT_STATE.md`
in the checkout it ran from. Run `python -B tools/project.py state` in your
working checkout when preparing a handoff after a worker run. Use the worker's
result for that run's exact install evidence.

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
`native-validation.json` records the tested native inputs and both DLL hashes.
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
