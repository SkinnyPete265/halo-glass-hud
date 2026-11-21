// AGPL-3.0-or-later. Split classification and HUD publication from the earlier Halo project.
#pragma once
#include <array>
#include <cstdio>
#include <string>
#include <swofty/hud_leaves.hpp>

namespace halo {
struct SectorSnapshot {
    std::array<int, 3> milliseconds{};
    std::array<unsigned, 3> quality{};
    std::array<unsigned, 3> revision{};
};

class SectorState {
public:
    void reset()
    {
        const auto revisions = revisions_;
        *this = SectorState{};
        revisions_ = revisions; // A new context can receive a split before the next HUD flush.
    }

    void context(unsigned generation, int player)
    {
        if (!context_valid_ || generation != generation_ || player != player_) {
            reset();
            generation_ = generation;
            player_ = player;
            context_valid_ = true;
        }
    }

    bool observe(unsigned vehicle, int lap, unsigned sector, int milliseconds)
    {
        if (!context_valid_ || vehicle >= 32 || sector >= 3 || lap < 0 || lap >= 199 ||
            milliseconds < 500 || milliseconds > 180000)
            return false;
        auto &previous = seen_[vehicle][sector];
        if (previous.lap == lap && previous.milliseconds == milliseconds)
            return false;
        previous = {lap, milliseconds};
        if (static_cast<int>(vehicle) == player_) {
            if (lap != lap_seen_) {
                lap_seen_ = lap;
                current_ = {};
            }
            unsigned quality = 1;
            if (!session_best_[sector] || milliseconds < session_best_[sector])
                quality = 3;
            else if (!personal_best_[sector] || milliseconds < personal_best_[sector])
                quality = 2;
            current_.quality[sector] = quality;
            current_.milliseconds[sector] = milliseconds;
            current_.revision[sector] = ++revisions_[sector];
            if (!personal_best_[sector] || milliseconds < personal_best_[sector])
                personal_best_[sector] = milliseconds;
        }
        if (!session_best_[sector] || milliseconds < session_best_[sector])
            session_best_[sector] = milliseconds;
        return true;
    }

    SectorSnapshot snapshot() const { return current_; }

    bool observed(unsigned vehicle, int lap, unsigned sector) const
    {
        return vehicle < seen_.size() && sector < 3 && seen_[vehicle][sector].lap == lap;
    }

    void clear_display() { current_ = {}; }

private:
    struct Seen { int lap = -1; int milliseconds = 0; };
    bool context_valid_ = false;
    unsigned generation_ = 0;
    int player_ = -1, lap_seen_ = -1;
    SectorSnapshot current_{};
    std::array<int, 3> personal_best_{}, session_best_{};
    std::array<unsigned, 3> revisions_{};
    std::array<std::array<Seen, 3>, 32> seen_{};
};

class SectorHud {
public:
    SectorHud()
    {
        for (int sector = 0; sector < 3; ++sector) {
            const std::string key = "s" + std::to_string(sector + 1);
            ready_[sector] = leaves_.boolean(key + "_ready");
            pulses_[sector] = leaves_.boolean(key + "_pulse");
            for (int colour = 0; colour < 4; ++colour)
                for (int cell = 0; cell < 6; ++cell) {
                    std::string key = "s" + std::to_string(sector + 1) + "_" + colours_[colour] +
                                      "_c" + std::to_string(cell);
                    cells_[sector][colour][cell] = leaves_.text(key, 2);
                }
        }
    }

    void publish(const SectorSnapshot &state)
    {
        {
            swofty::hud::Leaves::Atomic update(leaves_);
            for (int sector = 0; sector < 3; ++sector) {
                char text[16] = "--.---";
                const int milliseconds = state.milliseconds[sector];
                const bool valid = milliseconds >= 500 && milliseconds <= 99999;
                if (!valid) {
                    last_revision_[sector] = 0;
                } else if (last_revision_[sector] != state.revision[sector]) {
                    phase_[sector] = !phase_[sector];
                    last_revision_[sector] = state.revision[sector];
                }
                leaves_.set(ready_[sector], valid);
                leaves_.set(pulses_[sector], phase_[sector]);
                if (valid)
                    std::snprintf(text, sizeof text, "%2d.%03d", milliseconds / 1000, milliseconds % 1000);
                const unsigned active = valid && state.quality[sector] < 4 ? state.quality[sector] : 0;
                for (unsigned colour = 0; colour < 4; ++colour)
                    for (int cell = 0; cell < 6; ++cell) {
                        char value[2]{};
                        if (colour == active && text[cell] != ' ')
                            value[0] = text[cell];
                        leaves_.set(cells_[sector][colour][cell], value);
                    }
            }
        }
        leaves_.flush();
    }

private:
    static constexpr const char *colours_[4] = {"white", "yellow", "green", "purple"};
    swofty::hud::Leaves leaves_{"view_model_data.hud_halo_v2_sector_"};
    swofty::hud::TextLeaf cells_[3][4][6]{};
    swofty::hud::BoolLeaf ready_[3]{}, pulses_[3]{};
    std::array<unsigned, 3> last_revision_{};
    std::array<bool, 3> phase_{};
};
}
