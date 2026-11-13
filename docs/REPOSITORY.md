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
