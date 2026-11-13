#include <swofty/events.hpp>
#include <swofty/mixin.hpp>
#include "dial.hpp"

namespace {
halo::Dial dial;
void on_frame(double, void *)
{
    dial.frame();
}
}

SWOFTY_ON_LOAD
{
    const auto result = swofty::events::on_frame(on_frame);
    swofty::log("[halo-v2] frame registration: %s", swofty::events::name(result));
}
SWOFTY_ADDON()
