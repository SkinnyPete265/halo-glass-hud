# Halo Glass HUD changelog

Development and beta builds use the same versioned notes intended for future releases.

## 0.16.0-dev2

### New/Added

- Test

## 0.16.0-dev1

### New/Added

- Added a left-wing battery display with charge, mode, deployment, harvesting, and power readings.
- Added simultaneous KPH and MPH readouts to both dials.
- Added a per-profile choice between gradual and stepped brake and throttle slats.

### Fixes

- Kept F1 26 Boost and Overtake indicators independent.
- Restored stock primary speed when the native Live speed is unavailable.

## 0.16.0

### New/Added

- Added Live v6 sector timing for supported builds, with the verified native split reader as fallback.
- Added a prototype battery charge percentage and net deploy/harvest readout.

### Fixes

- Restored the full glow above the speedometer ring.
- Smoothed the decorative wing edges through the tips and matched them more closely to the ring's blue.
- Corrected the 2026 Boost element IDs for HUD schema validation.

### Miscellaneous

- Added hosted source checks and GitHub-triggered local packaging and installation.
- Added release evidence and exact-cache checks. In-game testing starts with a manual launch.

### Test status

- The owner approved the wing-edge changes in `0.15.0-dev2`. A dedicated UDP-off Time Trial remains pending.

## 0.15.0-dev2

### Fixes

- Smoothed the upper and lower decorative wing edges through their tip fades.
- Matched the decorative wing edges more closely to the speedometer ring's blue.

### Miscellaneous

- Release installation ends after cache verification. Launch F1 25 when ready to test.

## 0.15.0-dev1

### New/Added

- Added native sector timing through SWOFTY on supported Steam builds, with UDP off.
- Added a SWOFTY boot smoke test.
- Added native tests to CI with a pinned Zig version.
- Added a prototype battery percentage and net deploy/harvest readout.

### Fixes

- Fixed the flat cutoff above the speedometer glow.
- Smoothed the decorative wing extensions.
- Normalized the 2026 Boost element IDs for SWOFTY schema validation.

### Miscellaneous

- Matched the decorative wing extensions to the speedometer ring's blue.
- Kept the verified split reader as a fallback and diagnostic comparison.
- Added per-build release records.
- Restricted packages to the intended source files and sprites.
- Retired the browser previewer in favour of the game's HUD editor.
- Added pinned HUD schema validation and checks for the active game copy.
- Save the profile conflict report when cache verification fails.
- Added a repeatable Time Trial check using Halo's split logs.
- Added GitHub-triggered local packaging, installation, and optional boot verification.

### Test status

- Timing and artwork passed offline checks. The UDP-off Steam Time Trial check is pending.

## 0.14.2

### Fixes

- Restored native sector timing support for Steam F1 25 v1.27.
- Smoothed the edges of the active brake and throttle slats.

### Miscellaneous

- Extended the green DRS rails to the wing tips.
- Strengthened the blue glow around the wings and speedometer.

## 0.14.1

### Fixes

- Smoothed the long blue wing edges.
- Smoothed the speedometer ring, inner arc, battery outline, and idle pedal slats.

## 0.14.0

### Fixes

- Restored the full fade of the decorative wing extensions in-game.

### Miscellaneous

- Increased the resolution of the shared HUD texture.
