// AGPL-3.0-or-later. Uses the previously verified F1 25 split-event layout.
#include <swofty_api.h>
#include <swofty/live.hpp>
#include <windows.h>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <mutex>
#include "sector_state.hpp"

namespace {
using SplitFn = void (*)(void *, void *);
SplitFn original = nullptr;
std::mutex state_lock;
halo::SectorState state;
halo::SectorHud publisher;

template<class T> bool read_at(uintptr_t address, T &out)
{
    SIZE_T got = 0;
    return address && ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<const void *>(address),
                                       &out, sizeof out, &got) && got == sizeof out;
}

bool build_matches()
{
    auto *base = reinterpret_cast<const uint8_t *>(GetModuleHandleW(nullptr));
    if (!base)
        return false;
    auto *dos = reinterpret_cast<const IMAGE_DOS_HEADER *>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 || dos->e_lfanew > 0x1000)
        return false;
    auto *nt = reinterpret_cast<const IMAGE_NT_HEADERS64 *>(base + dos->e_lfanew);
    return nt->Signature == IMAGE_NT_SIGNATURE && nt->FileHeader.TimeDateStamp == 1789118616u &&
           nt->OptionalHeader.SizeOfImage == 0x193e6000u;
}

bool context()
{
    const auto session = swofty::live::available() ? swofty::live::session() : std::nullopt;
    if (!session || session->player < 0 || session->player >= 32) {
        state.reset();
        return false;
    }
    state.context(session->generation, session->player);
    return true;
}

void on_frame(double, void *)
{
    halo::SectorSnapshot snapshot;
    {
        std::lock_guard<std::mutex> guard(state_lock);
        context();
        snapshot = state.snapshot();
    }
    publisher.publish(snapshot);
}

void on_split(void *manager, void *event)
{
    uint8_t vehicle = 0xff;
    read_at(reinterpret_cast<uintptr_t>(event) + 0x10, vehicle);
    original(manager, event);
    if (vehicle >= 32)
        return;
    const uintptr_t address = reinterpret_cast<uintptr_t>(manager);
    uintptr_t begin = 0, end = 0, entry = 0;
    if (!read_at(address + 0x58, begin) || !read_at(address + 0x60, end) || !begin ||
        end < begin || end - begin > 32 * sizeof(uintptr_t) ||
        vehicle >= (end - begin) / sizeof(uintptr_t) ||
        !read_at(begin + vehicle * sizeof(uintptr_t), entry) || !entry)
        return;
    uint8_t lap = 0xff, sector = 0xff;
    if (!read_at(entry + 0x38, lap) || !read_at(entry + 0x39, sector) || lap >= 199 || sector >= 3)
        return;
    const uintptr_t slot = entry + 0x38 + uintptr_t(lap) * 0xc8 + uintptr_t(sector) * 0x10;
    uint32_t first = 0, second = 0;
    if (!read_at(slot + 0x10, first) || !read_at(slot + 0x18, second))
        return;
    const uint32_t bits = first ^ second;
    float seconds = 0;
    std::memcpy(&seconds, &bits, sizeof seconds);
    if (!std::isfinite(seconds) || seconds < .5f || seconds > 180.f)
        return;
    std::lock_guard<std::mutex> guard(state_lock);
    if (context())
        state.observe(vehicle, lap, sector, static_cast<int>(std::lround(seconds * 1000.f)));
}
}

extern "C" __declspec(dllexport) const uint32_t SwoftyAddonApi = SWOFTY_API_VERSION;
extern "C" __declspec(dllexport) int SwoftyAddonInit(const SwoftyApi *a)
{
    if (!a || a->version < 5 || !a->resolve || !a->register_mixins || !a->events || !a->events->on_frame)
        return 0;
    uint32_t token = 0;
    if (a->events->on_frame(on_frame, nullptr, &token) != SWOFTY_ASSET_OK)
        return 0;
    if (!build_matches() || !a->resolve("Sess_LapTimes_ReportSplit")) {
        a->log("[halo-v2-sectors] split reader unavailable for this game build");
        return 1;
    }
    const SwoftyMixin mixin{"Sess_LapTimes_ReportSplit", SWOFTY_MIXIN_WRAP, 0,
                            reinterpret_cast<void *>(&on_split), reinterpret_cast<void **>(&original)};
    const int installed = a->register_mixins(&mixin, 1);
    a->log("[halo-v2-sectors] split reader registration: %s", installed ? "ok" : "unavailable");
    return 1;
}
