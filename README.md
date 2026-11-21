# Halo Glass HUD v2

A glass-style racing HUD for EA Sports F1 25, including the F1 26 season
expansion. Halo Glass HUD v2 is currently in beta.

[Read the changelog](CHANGELOG.md). This repository contains the addon source.
Build setup and local game inputs are documented in the
[repository guide](docs/REPOSITORY.md).

## Features

- Curved glass wings with subtle edge lighting and projected sector timings.
- Central speed display, stored-charge battery icon and separate N/R handling.
- Curved brake/throttle slats and an animated 1–8 gear row.
- RPM bar with a high-rev red warning and separately measured number/unit labels.
- DRS distance and mapped-button prompts, pulsing edge rails and travelling highlights.
- Native 2026 Straight Mode prompts/rails and temporary Overtake/Boost status readouts.
- Positioning and uniform scaling through the game's HUD controls.

## Install and remove

1. Import the Halo Glass HUD `.swoftyaddon` file into SWOFTY Launcher.
2. Enable Halo Glass HUD v2 in the profile used to launch the game.
3. Disable Project Halo or any other addon that replaces the same dial.
4. Launch through SWOFTY and select a stock 2025 F1 car or an F1 26 DLC car.

Disable the addon in SWOFTY to remove its changes on the next launch.

## Compatibility

Halo shares artwork and layout across the 2025 and 2026 dials while keeping
their respective native controls. Charge follows the game's stored-energy
reading. The 2026 dial also shows Straight Mode and temporary Overtake/Boost
readouts.

The HUD works with UDP switched off. Beta development currently targets
the Steam copy of F1 25. Sector timing depends on the game build and the
native data available through SWOFTY. Check the changelog for the current
beta's test status.

## Development and provenance

[Repository setup](docs/REPOSITORY.md) covers building from source and preparing
releases. [Development notes](docs/DEVELOPMENT.md) explain the implementation.

[Third-party notices](THIRD_PARTY_NOTICES.md) record licences, upstream sources
and the captured game UI resources that need review for public distribution.
The project manifest declares AGPL-3.0-or-later and retains the bundled notices.
