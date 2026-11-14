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

## Commands

```powershell
python -B tools/project.py status
python -B tools/project.py check
python -B tools/project.py release
python -B tools/project.py release --install
```

Add --native to release when rebuilding the native publishers. Release logs and
rollback packages stay under build/. In-game testing remains a separate verification.
The repository-local halo-hud-release skill records these entry points.

GitHub Actions runs Python/workflow checks and generated-art checks. Full native
composition and in-game checks use the local game inputs and toolchain.

Keep current local release feedback in PROJECT_STATE.md. The installed baseline at
repository creation is v0.11.0, with its latest visual refinements awaiting testing.
Open this folder as the primary project when starting another Codex chat.

## Developer iteration

The shared style.json controls battery geometry and colours, speed text, the GEARS
caption and RPM thickness. Both car generations consume the same validated values.
For the interactive editor, run

```powershell
python -B tools/project.py tune
```

Open http://127.0.0.1:8766 in a browser. The editor supports draft sliders, colour
pickers, simulated inputs and light/dark backgrounds. Export draft downloads JSON.
Apply settings explicitly saves style.json. Reload before applying if another editor
has changed the file. The server binds to loopback and checks the request origin.
Use --port to select another port. Stop the foreground server with Ctrl+C.

The preview uses the shared 2025 renderer. Native font rendering and live animations
still need in-game confirmation. Preview edits apply to shared settings for both
2025 and 2026, while their native mode bindings remain generation-specific.

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
python -B tools/project.py logs build/compose-v0.11.0.log
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

Installation compares the package against the complete installed addon tree and reads
the selected profile. Matching files skip reinstallation, and an enabled addon skips
the enable command. SWOFTY handles cache freshness for game/profile changes, followed
by verification of the resulting exact cache.

Timing reports are build/build-timings.json for artwork/native composition and
build/release-timings.json for preparation, packaging, installation, SWOFTY cache and
installation verification. Failures also record the elapsed stage. Raw logs remain
available alongside their compact summaries.
