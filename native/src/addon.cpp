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

SWOFTY_SETTING(std::string_view, pedal_fill, "gradual");

SWOFTY_ON_CHANGE(pedal_fill, std::string_view choice)
{
    dial.use_stepped_pedals(choice == "stepped");
}

SWOFTY_ON_LOAD
{
    dial.use_stepped_pedals(pedal_fill.get() == "stepped");
    const auto result = swofty::events::on_frame(on_frame);
    swofty::log("[halo-v2] frame registration: %s", swofty::events::name(result));
}
SWOFTY_ADDON()
