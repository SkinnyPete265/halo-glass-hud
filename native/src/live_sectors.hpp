// AGPL-3.0-or-later. Convert sampled lap records to split events for the existing HUD.
#pragma once
#include "sector_state.hpp"
#include <swofty/live.hpp>
#include <chrono>
#include <cstdlib>

namespace halo {
enum class SectorProvider { waiting, live, legacy };

class LapCursor {
public:
    bool initialized() const { return lap_ >= 0; }

    bool rewound(const SwoftyLiveCarDetail &d) const
    {
        return lap_ >= 0 && (int(d.laps_completed) < lap_ ||
            (int(d.laps_completed) == lap_ && d.current_lap_ms && d.current_lap_ms < elapsed_));
    }

    bool skipped(const SwoftyLiveCarDetail &d) const
    {
        return lap_ >= 0 && int(d.laps_completed) > lap_ + 1;
    }

    template<class Observe>
    void sample(const SwoftyLiveCarDetail &d, Observe observe)
    {
        const int lap = static_cast<int>(d.laps_completed);
        if (lap_ < 0 || rewound(d) || skipped(d)) {
            // First contact, restart or skipped laps. Adopt the record without replaying it.
            lap_ = lap;
            elapsed_ = d.current_lap_ms;
            for (unsigned i = 0; i < 2; ++i)
                seen_[i] = valid(d.current_sector_ms[i]);
            finish_pending_ = false;
            return;
        }
        if (lap != lap_) {
            lap_ = lap;
            seen_ = {};
            elapsed_ = 0;
            finish_pending_ = true;
        }
        if (d.current_lap_ms)
            elapsed_ = d.current_lap_ms;
        if (finish_pending_ && valid(d.last_sector_ms[2])) {
            finish_pending_ = false;
            observe(lap - 1, 2, d.last_sector_ms[2]);
            // Keep S3 ready for this HUD publication, even after a long gap between frames.
            // Current-lap records persist and are picked up on the following frame.
            return;
        }
        for (unsigned i = 0; i < 2; ++i) {
            if (!seen_[i] && valid(d.current_sector_ms[i])) {
                seen_[i] = true;
                finish_pending_ = false; // A late previous-lap record must never rewind the HUD.
                observe(lap, i, d.current_sector_ms[i]);
            }
        }
    }

private:
    static bool valid(uint32_t ms) { return ms >= 500 && ms <= 180000; }
    int lap_ = -1;
    uint32_t elapsed_ = 0;
    std::array<bool, 2> seen_{};
    bool finish_pending_ = false;
};

class SectorTiming {
public:
    using Log = void (*)(const char *, ...);
    explicit SectorTiming(Log log = nullptr) : log_(log) {}

    void frame()
    {
        if (!context())
            return;
        const auto table = swofty::live::detail::table();
        if (!table || table->version < 6 || !table->car_detail) {
            if (legacy_available && provider_ == SectorProvider::waiting)
                select(SectorProvider::legacy);
            return;
        }
        const auto me = detail(player_);
        if (me)
            select(SectorProvider::live);
        if (provider_ != SectorProvider::live)
            return;
        if (me && cursors_[player_].rewound(*me)) {
            clear_observations();
            state_.context(generation_, player_);
            if (log_)
                log_("[halo-v2-sectors] player lap counter or clock rewound; rebaselined");
        } else if (me && cursors_[player_].skipped(*me)) {
            state_.clear_display();
            comparisons_ = {};
            if (log_)
                log_("[halo-v2-sectors] missed multiple player laps; rebaselined");
        }
        // Within the same sample use observed rivals as the session-best reference.
        for (unsigned id = 0; id < cursors_.size(); ++id)
            if (id != unsigned(player_))
                if (const auto rival = detail(id))
                    sample(*rival);
        if (me)
            sample(*me);
        if (legacy_available)
            check_comparisons();
    }

    void legacy_split(unsigned id, int lap, unsigned sector, int ms)
    {
        if (!context())
            return;
        if (provider_ == SectorProvider::waiting) {
            // A verified real gate is evidence the fallback is usable. Prefer v6
            // even if this callback arrives before our first frame callback.
            if (detail(player_))
                select(SectorProvider::live);
            else
                select(SectorProvider::legacy);
        }
        if (provider_ == SectorProvider::legacy) {
            accept(id, lap, sector, ms);
            if (id == unsigned(player_) && sector < 3)
                comparisons_[sector][0] = {lap, ms, false, {}};
        } else if (id == unsigned(player_) && sector < 3 && cursors_[id].initialized())
            compare(false, lap, sector, ms);
    }

    SectorSnapshot snapshot() const { return state_.snapshot(); }
    SectorProvider provider() const { return provider_; }
    bool legacy_available = false;

private:
    using Clock = std::chrono::steady_clock;
    struct Reading {
        int lap = -1, ms = 0;
        bool pending = false;
        Clock::time_point received{};
    };
    std::array<std::array<Reading, 2>, 3> comparisons_{};
    std::array<LapCursor, SWOFTY_LIVE_MAX_CARS> cursors_{};
    SectorState state_;
    SectorProvider provider_ = SectorProvider::waiting;
    Log log_;
    int player_ = -1;
    unsigned generation_ = 0;
    bool active_ = false;

    static std::optional<SwoftyLiveCarDetail> detail(unsigned id)
    {
        auto d = swofty::live::car_detail(id);
        if (d && d->vehicle == id && swofty::live::has(*d, SWOFTY_LIVE_HAVE_LAP_TIMES)
            && d->laps_completed < 199)
            return d;
        return std::nullopt;
    }

    void clear_observations()
    {
        state_.reset();
        cursors_ = {};
        comparisons_ = {};
    }

    bool context()
    {
        const auto session = swofty::live::session();
        if (!session || session->player < 0 || session->player >= int(cursors_.size())) {
            if (active_) {
                clear_observations();
                active_ = false;
            }
            return false;
        }
        if (session->player != player_ || session->generation != generation_) {
            clear_observations();
            player_ = session->player;
            generation_ = session->generation;
            provider_ = SectorProvider::waiting;
        }
        state_.context(generation_, player_);
        active_ = true;
        return true;
    }

    void select(SectorProvider provider)
    {
        if (provider_ == provider)
            return;
        provider_ = provider;
        if (log_)
            log_("[halo-v2-sectors] generation=%u player=%d provider=%s", generation_, player_,
                 provider == SectorProvider::live ? "live.car_detail" : "verified split reader");
    }

    void sample(const SwoftyLiveCarDetail &d)
    {
        cursors_[d.vehicle].sample(d, [&](int lap, unsigned sector, int ms) {
            // A fallback gate can lead the first available v6 record by a refresh.
            // The identity survives a one-millisecond difference between readers.
            if (!state_.observed(d.vehicle, lap, sector))
                accept(d.vehicle, lap, sector, ms);
            if (legacy_available && d.vehicle == unsigned(player_))
                compare(true, lap, sector, ms);
        });
    }

    void accept(unsigned id, int lap, unsigned sector, int ms)
    {
        if (state_.observe(id, lap, sector, ms) && id == unsigned(player_) && log_)
            log_("[halo-v2-sectors] accepted lap=%d S%u=%d ms", lap + 1, sector + 1, ms);
    }

    void unmatched(Reading &reading, bool live, unsigned sector)
    {
        if (log_)
            log_("[halo-v2-sectors] unmatched %s lap=%d S%u=%d ms",
                 live ? "live" : "reader", reading.lap + 1, sector + 1, reading.ms);
        reading.pending = false;
    }

    void check_comparisons()
    {
        const auto now = Clock::now();
        for (unsigned sector = 0; sector < 3; ++sector)
            for (unsigned live = 0; live < 2; ++live) {
                auto &reading = comparisons_[sector][live];
                if (reading.pending && now - reading.received > std::chrono::seconds(2))
                    unmatched(reading, live, sector);
            }
    }

    void compare(bool live, int lap, unsigned sector, int ms)
    {
        auto &pair = comparisons_[sector];
        auto &mine = pair[live];
        if (mine.lap == lap && mine.ms == ms)
            return;
        if (mine.pending && mine.lap != lap)
            unmatched(mine, live, sector);
        mine = {lap, ms, true, Clock::now()};
        if (pair[!live].lap != lap)
            return;
        pair[0].pending = pair[1].pending = false;
        if (log_ && std::abs(pair[0].ms - pair[1].ms) > 1)
            log_("[halo-v2-sectors] disagreement lap=%d S%u live=%d reader=%d ms",
                 lap + 1, sector + 1, pair[1].ms, pair[0].ms);
    }
};
}
