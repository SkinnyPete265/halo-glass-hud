# Development notes

Halo Glass HUD for the 2025 and 2026 dials. Use the [repository guide](REPOSITORY.md)
for the current build and install workflow. Earlier release sections record the
implementation and verification at the time.

## Test build 0.7.0

Version 0.7.0 packages the approved refinements since v0.6.0.

- Four green DRS rails sit outside the upper and lower wing edges, with aligned
  starts, softer caps and about 10% longer travel along the curve.
- DRS opening takes 0.30 seconds. The travelling highlight follows the extension.
  Closing takes 0.075 seconds.
- DRS OPEN has a subtle black outline and a slightly darker bright-green core.
- Dark wing backing extends about 10% farther with the approved 32-pixel fade.
- The projected sector block sits 18 art pixels farther toward the left tip.
- The RPM bar has antialiased rounded endpoints and a soft moving fill edge.
- Live RPM digits use a wider, low-opacity blue halo. The unit keeps its icy glow.
- Idle gears are 2% larger and selected gears are 5% larger, with whiter tinted cores.

The build uses the installed SWOFTY 1.9.42. Position-only composer clips retain
16-byte animation-data alignment. The installed v0.6.0 package and runtime are
preserved under build/rollback-v0.6.0. Both native DLLs are reused from v0.6.0.

- Three sector rows follow the wing's slanted depth axis with 5% smaller type.
- White sector labels use icy-blue glow. Timings use a colour bloom and fine contrast edge.
- The centre rim uses coverage antialiasing and a 2x base texture.
- The enlarged selected gear fades from 30% to full alpha over 0.15 seconds.
- Fixed slot anchors and separate visibility gates preserve gear spacing and N/R handling.
- RPM uses native-font glow and a measured number/unit row for five-digit spacing.
- The red RPM warning begins at 83% of the bar and strengthens toward its end.
- The battery icon is 54 by 22 art pixels, with revised N/R clearance.
- Speed is centered in the circle and KPH sits higher above it.

The build includes the approved larger scale, taller shaded glass wings,
soft wing-edge lighting, wider pedal slats, curved glass accents and
BRAKE/THROTTLE captions. The warning follows the game's native revs fraction.

Brake and throttle use the earlier working native input components with the
shared slat geometry. The encoded pedal masks are generated from that same
geometry. The battery icon sits below speed and uses stored charge
for its fill and a uniform animated colour.

- Blue at 35% and above, fading into yellow from 35% to 30%.
- Yellow from 30% to 12.5%.
- Yellow fades into red from 12.5% to 10%.
- Red at 10% and below.

The same colour curve applies while charging and discharging. The white bolt
has its own layer.

DRS uses the game's existing distance, state and mapped-button widgets. Opening
reveals the four curved green rails with synchronized text and pulsing alpha.
Closing uses the faster native fade curve. Prompt positioning is centered below
the speedometer.

The entire component inherits the game's HUD positioning and scaling root.
Native speed, RPM and pedal captions use OSD_24_bold. Gear art uses bundled Saira. The preview
approximates native fonts and the mapped DRS button. The KPH caption currently
assumes kilometre-per-hour settings.

## Sector timing

Three sector rows sit near the left wing's outer side.
The rows share character columns aligned along the wing's slanted depth axis
and parallel curved baselines. Sector type is 5% smaller than the first draft.
Each glyph uses projected surface tangents for perspective scale and shear.
Each prefix and colon is permanently white, with a restrained icy-blue glow.
Timing text uses a matching colour bloom and a narrow dark contrast edge.
Native Alpha overrides cap effect opacity independently of the main text.
Pending times show white --.--- placeholders. Completed times use yellow,
green or purple according to the earlier split-event comparison rules.

On the two recognized executables, sector timing prefers SWOFTY Live table v6
when the player's `car_detail` has `SWOFTY_LIVE_HAVE_LAP_TIMES`. The current
record supplies S1/S2. The preceding record supplies S3 when the completed-lap
counter advances. S3 stays visible until the next observed player split.
First samples and discontinuities establish a baseline. Colour comparisons
learn personal and session bests from observed player and rival splits.
Typed HUD leaves publish the timing cells together and resynchronize after HUD
recreation. The HUD uses game-memory-backed state with UDP disabled.

The existing verified reader supplies splits on older cores or when its gate
arrives before live timing is available. After selecting Live, the comparison
reader only contributes diagnostics. In `loader.log`, search for
`[halo-v2-sectors]` to see the provider, player gates (one-based lap and
milliseconds), unmatched gates after two seconds, and paired times differing
by more than one millisecond. Live SDK headers are pinned in
`native/include/source.json`. The addon ABI remains 9.
[SWOFTY Live timing contract](https://f1.swofty.net/reference/std/live.html#car-detail)

The reader and focused state/publication tests compile and pass offline.
The user confirmed v0.4.0's in-game sector display and approved its appearance.
A further small outer-glow lift is approved. Decimal points use the v0.4.0
baseline position, DECIMAL_BASELINE_FRACTION = 0.40 in halo/sectors.py.
The offline previews approximate the game font.

## DRS travelling highlight

halo/drs_motion.py defines the one-second centre-out highlight and soft mask.
Both native eMaskTexture windows follow the same profile and path as the preview.
The game's default_curve_1 animates paired window/counter channels. A native
one-second timer restarts them through a current drs_pit_state query. Closing,
pit states and HUD hide/disable stop the sweep. Existing rail reveal and pulse
control the complete DRS group. The user approved the v0.5.0 changes after an in-game test.

## Battery interpolation

The battery fill and colour animation players use a
native timer and the game's generic_fade_on curve. Every 50 ms the players
receive a live fp32 ers_stored target in their signal attributes. The curve is
150 ms long and retargets from its current position. Opening the HUD initializes
the displayed charge directly. Hiding the HUD or losing ERS stops the timer.
The existing charge-colour keys apply during both discharge and regeneration.
A 0.9-art-pixel soft mask edge reduces visible pixel stepping in the small icon.
The user approved the v0.6.0 changes after testing.

## DRS edge rails in v0.7.0

Version 0.7.0 adds matching green rails to the top edges of both wings.
The top and bottom rails share the same reveal and travelling highlight.
Their starts align with the rounded wing corners. The upper rails sit above
the top wing edges and the lower rails sit below the bottom edges. Their glow
uses a soft horizontal fade at the wing starts and ends. Supersampled rounded
caps soften the tips and edges.
Rail extension and text fade use generic_fade_on_slow, the game's 0.30-second
ease-out curve. The travelling highlight begins after that opening completes.
The 0.075-second closing curve continues to control closure. The rails are
about 10% longer along the wing curve, with matching highlight travel.
These changes need an in-game test in v0.7.0.

## Wing-tip finish in v0.7.0

The dark backing extends 10% farther along each wing, within the existing
outer glass silhouette. The earlier 32-art-pixel smoothstep fade, original
tint and previous outline treatment are restored. These material changes
need an in-game test in v0.7.0.

## Sector placement in v0.7.0

The sector block moves 18 art pixels toward the left wing tip. All glyphs are
reprojected through the established surface basis. Row pitch, column advances,
font size, decimal baseline and live timing bindings use the existing values.
The new placement needs its first in-game test in v0.7.0.

## Installation and removal

The addon ID is `local.halo-hud-v2`. Use the [release guide](REPOSITORY.md#build-package-and-install-step-by-step)
to build, install and verify it in `Halo-HUD-Dev`. Disable it in SWOFTY to
remove its changes from the next launch of that profile.

## Source and rebuild

- halo/layout.py supplies shared geometry and the uniform coordinate conversion.
- halo/material.py and artwork.py render the glass and RPM warning artwork.
- halo/feature_assets.py supplies battery, DRS and native pedal-mask textures.
- halo/composition.py writes the native hud.element authoring record.
- tools/native_interop.py connects the captured native input/DRS components and
  adds the battery's DiffuseColour animation.
- tools/prepare_runtime.py repairs composer gauge packets and validates the
  resulting resources, native component references and UI signal targets.
- tools/package.py packages prepared overlays, the DLL and authoring sources.
- native/src/dial.hpp publishes gear-selection booleans and N/R/RPM strings.
- native/reference/native-controls.erpk and drs-template.bin are captured build
  inputs from the earlier working v0.31.0 project. Their provenance is recorded
  alongside them. Normal builds use these self-contained reference files.
- native/reference/sector_reader.cpp preserves the earlier reader source.
- halo/sectors.py supplies the shared sector character layout and bindings.
- native/src/sector_state.hpp supplies split classification and atomic publication.
- native/src/sector_times.cpp connects the Live frame callback and guarded split event.
- native/src/live_sectors.hpp tracks providers, lap transitions and comparison diagnostics.

Python 3.14, Pillow, SWOFTY and Zig are used locally. Run from this project folder.

```powershell
python -B tools/build.py --compose --ensure-native
python -B tools/package.py
```

`--ensure-native` compiles and tests both DLLs if their validation is missing or
stale. Use `--native` to force a rebuild. `--launcher` and `--data-dir` can
override the local executable and store paths.

The canonical manifest uses operations.hud. The installer uses precomposed
operations.erp overlays. Full authoring sources are included under source/.
Run developer commands from the repository root.

## Development workflow

Generated artwork is reused when its source, font, interpreter/library and output
hashes match build/artwork-cache.json. Missing or edited outputs trigger regeneration.
The option reuses the approved visual preview during release work.

New compositions record the artwork and native UI source fingerprint in their
validation metadata. Packaging checks that fingerprint, registry and runtime hashes,
then verifies a temporary archive before publishing it. Earlier validation records
continue to use their registry and runtime checks.

Run python -B tests/test_workflow.py when editing these workflow functions. Its
isolated checks cover cache reuse, invalidation, stale input rejection and atomic
publication. tools/verify_install.py performs the release installation checks.
AGENTS.md holds the development workflow. Share PROJECT_STATE.md when starting a
new chat. Use the game's HUD editor and gameplay for visual review.

## Historical validation through v0.7.0

The user confirmed that v0.1.1 loads a session successfully and its RPM bar
responds in game. The user confirmed that v0.2.0 DRS works in Time Trial.
Battery-charge progression still needs testing during energy consumption.

The user tested v0.3.0 and provided the feedback incorporated here.
The user approved v0.3.1 in-game and requested the circle-edge and RPM-glow
refinements included here. The user confirmed the v0.4.0 sector display and its appearance in game.

Version 0.4.0 composed successfully with the installed SWOFTY 1.9.27.
Its prepared resources include the projected sector rows, separately measured
lighting copies and native opacity caps. The timing reader's executable-build
guard and named split binding match the local game and launcher.

Offline checks cover the serialized scene and UI links, all twelve aligned
composer gauge clips, native text anchors, gear visibility gates and
show/hide animation signals. The native dial state test covers forward gear,
N/R and unavailable-data handling. The wider pedal masks retain the approved
geometry from v0.3.0.

The earlier crash was traced to redundant constant quaternion packets in a
composer gauge. SWOFTY 1.9.39 removes those packets upstream and 1.9.40 pads
animation buffers to 16 bytes. The preparer accepts the corrected output and
can normalize the older identity-only channels while preserving sample values.
Gauge expectations come from the authored registry. Native pedal endpoints
retain the approved shared geometry. Version 0.5.0 composed successfully with SWOFTY 1.9.40. Its twelve generated
clips are position-only and 16-byte padded upstream. The native UI graph has
1035 unique nodes with all signal targets and layout links resolved. Both BC7
soft-mask textures have a 0.37/255 RMS alpha error against their source masks.
Serialized sweep endpoints and counter-motion match the preview geometry.
Both native DLLs match the user-tested v0.4.0 package byte for byte.
The user approved v0.5.0 and v0.6.0 in game. Version 0.7.0 needs its first in-game test.

The general SWOFTY dev check warns that its optional Python SDK data validator
is unavailable. Its native composer parsed the registry and generated the
archives. Focused local validators check the prepared output separately.

## Licences

Project source follows AGPL-3.0-or-later. Bundled SDK and format helpers retain
their upstream notices and licences. Saira is distributed under the SIL Open
Font License in assets/fonts/Saira/OFL.txt.

## Shared instrument definitions

halo/instruments.py contains charge colours, the charge-domain interpolation,
gear artwork and measured RPM row positions. Authoring and native interop use
these definitions directly.

## Local configuration

Copy project.local.example.json to project.local.json and edit the tool paths.
CLI options override those defaults. The local file and PROJECT_STATE.md are
excluded from version control. Build commands use swofty from PATH when a
launcher path is omitted. SWOFTY selects its default store when --data-dir is
omitted during composition. Installation verification accepts --data-dir,
--profile and --cache for an explicit cache folder.

Reference capture accepts --legacy-addon and --stock-archive. It is a bootstrap
utility for the captured build inputs.

## Publication status

The active addon remains a development build. Its public name, author identity
and final addon ID can be selected when preparing the publication candidate.
THIRD_PARTY_NOTICES.md records the captured UI inputs and verified SDK notice.
Redistribution permission for the captured game-derived resources remains unverified.

## Release 0.8.0

This release packages the approved v0.7.0 HUD design with the shared instrument
module, portable developer configuration, explicit installation checks, refined
build workflow and corrected SDK licence notice. The source cleanup matched
three preview states pixel for pixel and all 236 prepared UI fragments against
the v0.7.0 baseline. The existing native source and DLLs passed the rollback
comparison. Release 0.8.0 requires its own in-game confirmation.

## DRS typography and battery fill after v0.8.0

DRS OPEN uses a native text core with the HUD's OSD_24_bold style. Native distance
and available captions receive the same type treatment with capped edge effects.
The shared pit caption follows that treatment. Distance formatting, visibility
and mapped controller/keyboard bindings use the existing game fields.

The battery fill's previous animation path included texture padding and filter
support outside the visible cavity. At 95% stored charge it rendered effectively
full. The corrected source uses the exact cavity bounds, BOX-filtered fill art
and a centered feather profile. Charge maps linearly to the visible fill edge
while the existing smooth retarget animation drives the native slider.

Run python -B tests/test_drs_battery.py after generating artwork for focused checks.
The native typography fixture uses existing composer output when available.
Full composition and in-game confirmation follow in the next approved build.
