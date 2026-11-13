# Halo Glass HUD v2

A glass-style Halo HUD addon for EA Sports F1 25 through SWOFTY Launcher.
The development build targets the stock 2025 F1 dial and the F1 26 DLC dial.

## Features

- Curved glass wings with subtle edge lighting and projected sector timings.
- Central speed display, stored-charge battery icon and separate N/R handling.
- Curved brake/throttle slats and an animated 1ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ8 gear row.
- RPM bar with a high-rev red warning and separately measured number/unit labels.
- DRS distance and mapped-button prompts, pulsing edge rails and travelling highlights.
- Native 2026 Straight Mode prompts/rails and temporary Overtake/Boost status readouts.
- Positioning and uniform scaling through the game's HUD controls.

## Install and remove

1. Import dist/local.halo-hud-v2.swoftyaddon into SWOFTY.
2. Enable Halo Glass HUD v2 in the profile used to launch the game.
3. Disable the earlier local.halo-hud addon if it is enabled.
4. Launch through SWOFTY and select a stock 2025 F1 car or an F1 26 DLC car.

Disable the addon in SWOFTY to remove its changes on the next launch.

## Compatibility and testing

Version 0.11.0 uses SWOFTY 1.9.42. It adds a rounded moving RPM cap that follows
the wing arc, a heavier GEARS caption and another 10% battery width increase.
The existing closing-rail retraction and sector-result fades are included.

Battery fill and colour follow the native normalized ers_stored charge value.
The stock battery gauge uses the same direct source. The custom icon now uses
the native geometric eWindow clip, with its rounded silhouette supplied by the
artwork. Actual charge response follows the game. The blue/yellow/red charge
thresholds apply during drain and refill.

Both dials use the shared 33-key RPM mask/counter motion. The artwork remains
stationary as the rounded cap travels along its curve. Offline checks verify
the exact samples, timing, counter-motion, native clipping and UI bindings.

The 2026 SM prompts use the native availability, distance and active-state fields.
Green rails carry across to SM. The small OVERTAKE ON/OFF caption exposes
om_active. BOOST READY/ACTIVE/UNAVAILABLE exposes the separate stock
ers_overtake_state decision. The 2026-specific battery-mode and per-lap energy
presentation remains future work.

Offline validation covers both namespaces, native data tags, animation buffers,
UI signal/layout links and installation. Sector publisher tests cover result
revision events, equal-time repeats, duplicate callbacks and lap/session reset.
In-game confirmation of the v0.11.0 visual changes is pending.

The sector reader checks the executable build before attaching its split hook.
Its recorded PE timestamp is 1789118616 and image size is 0x193e6000. A different
executable build needs verification of that reader. Sector colours are learned
from observed personal and session splits. The KPH caption assumes km/h settings.
Additional sector/session transitions remain part of ongoing in-game verification.

## Build from source

Use Python 3.14 and the dependencies in requirements.txt. A first native build
also uses Zig through SWOFTY's C++ toolchain. The pinned SDK headers are included.
Run these commands from the repository root.

```powershell
python -m pip install -r requirements.txt
python -B tools/build.py --native --compose --skip-preview --launcher "C:/path/to/SwoftyLauncher/bin/swofty.exe" --data-dir "C:/path/to/Swofty"
python -B tools/package.py
```

For subsequent artwork/UI iterations, reuse the compiled DLLs by omitting
--native. Copy project.local.example.json to project.local.json to save local
paths. Command-line options override the local settings.

Generated artwork uses a content-checked cache. Packaging verifies prepared
inputs and publishes the archive atomically. Full authoring sources are included
under source/ in the addon package.

## Development and provenance

[Development notes](docs/DEVELOPMENT.md) describe the shared geometry, native
controls, validation and iteration workflow.

[Third-party notices](THIRD_PARTY_NOTICES.md) record licences, upstream sources
and the captured game UI resources that need review for public distribution.
The project manifest declares AGPL-3.0-or-later and retains the bundled notices.

## Repository workflow

See [repository setup](docs/REPOSITORY.md) for local inputs, the reusable project
command, the release skill and automated source checks.
