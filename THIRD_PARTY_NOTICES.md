# Third-party notices and asset provenance

## Authored project source

The project manifest declares AGPL-3.0-or-later. The repository retains the
upstream SWOFTY notice and licence text in LICENSE. The public release author
and final project attribution are still to be selected by the project owner.

## SWOFTY format helpers

The format helpers under tools/formats derive from SWOFTY. Their bundled
licence text is tools/formats/SWOFTY-LICENSE, which carries the SWOFTY copyright
notice and GNU AGPL terms. That notice is preserved with the source.

## SWOFTY SDK

native/include/source.json records the SWOFTY v1.9.0 repository tag and SHA-256
hashes for the included headers. The SDK is MIT-licensed. Its SDK-specific notice
is bundled in native/include/LICENSE, with its source URL and hash in source.json.
The SDK fetch helper retrieves that same package-level notice.
[Upstream SDK licence](https://github.com/Swofty-Developments/SwoftyLauncher/blob/v1.9.0/packages/sdk/LICENSE).

## Saira

The bundled font is Saira. Its notice names Copyright 2020 The Saira Project
Authors. The SIL Open Font License text is assets/fonts/Saira/OFL.txt.

## Captured game UI inputs

native/reference/native-controls.erpk and drs-template.bin were captured from
the earlier local.halo-hud v0.31.0 addon and a stock F1 25 UI archive.
native/reference/native-controls-source.json lists the component resources and
records the stock archive hash. These inputs include game-derived component
layouts, animation data and rendering resources alongside locally generated
materials and pedal textures. Prepared runtime overlays also carry modified
game UI resources.

Redistribution permissions for the captured game-derived resources have not
been established in this project. Their presence in development packages is
recorded here for the public-release provenance review.

## Local reference media

The local design/reference folder contains visual reference captures used by
preview recipes. The addon packager excludes that folder. Its media provenance
and permission records are separate from the authored HUD artwork.
