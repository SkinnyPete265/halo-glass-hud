// AGPL-3.0-or-later. Exact executable identities verified for the split reader.
#pragma once
#include <array>
#include <cstdint>

namespace halo {
struct ExecutableIdentity {
    uint32_t pe_timestamp;
    uint32_t size_of_image;
};

inline constexpr std::array<ExecutableIdentity, 2> sector_reader_builds{{
    {1789118616u, 0x193e6000u},
    {1794312636u, 0x18434000u},
}};

inline constexpr bool supports_sector_reader(uint32_t pe_timestamp, uint32_t size_of_image)
{
    for (const auto &identity : sector_reader_builds)
        if (identity.pe_timestamp == pe_timestamp && identity.size_of_image == size_of_image)
            return true;
    return false;
}
} // namespace halo
