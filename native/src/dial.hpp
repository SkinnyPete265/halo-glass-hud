#pragma once
#include <cmath>
#include <cstdio>
#include <swofty/hud_leaves.hpp>
#include <swofty/live.hpp>

namespace halo {
class Dial {
public:
    void frame()
    {
        const auto car = swofty::live::available() ? swofty::live::subject() : std::nullopt;
        int selected = -1;
        const char *special = "";
        char rpm[12]{};
        if (car && swofty::live::has(*car, SWOFTY_LIVE_HAVE_GEAR)) {
            if (car->gear >= 1 && car->gear <= 8)
                selected = car->gear - 1;
            if (car->gear == 0)
                special = "N";
            if (car->gear == -1)
                special = "R";
        }
        if (car && swofty::live::has(*car, SWOFTY_LIVE_HAVE_RPM) &&
            std::isfinite(car->rpm) && car->rpm >= 0 && car->rpm <= 30000) {
            std::snprintf(rpm, sizeof rpm, "%ld", std::lround(car->rpm));
        }
        {
            swofty::hud::Leaves::Atomic update(leaves_);
            leaves_.set(gears_, selected);
            leaves_.set(special_, special);
            leaves_.set(rpm_, rpm);
        }
        leaves_.flush();
    }

private:
    swofty::hud::Leaves leaves_{"view_model_data.hud_halo_v2_"};
    swofty::hud::OneHot gears_ = leaves_.one_hot("gear", 8, 0, 1);
    swofty::hud::TextLeaf special_ = leaves_.text("special_gear", 2);
    swofty::hud::TextLeaf rpm_ = leaves_.text("rpm", 6);
};
}
