#include <cassert>
#include <cstdio>
#include <string>
#include <swofty/fake_hud.hpp>
#include <swofty/fake_live.hpp>
#include "../src/dial.hpp"

const std::string prefix = "view_model_data.hud_halo_v2_";

void check_gears(const swofty::fake::Hud &hud, int selected)
{
    for (int gear = 1; gear <= 8; ++gear)
        assert(hud.number(prefix + "gear" + std::to_string(gear)) == (gear == selected));
}

int main()
{
    swofty::fake::Hud hud;
    swofty::fake::Live live;
    halo::Dial dial;
    auto &car = live.add_car(0, 1);
    live.set_player(0);
    live.install();
    car.have |= SWOFTY_LIVE_HAVE_GEAR | SWOFTY_LIVE_HAVE_RPM;
    car.gear = 6;
    car.rpm = 11585.0f;
    dial.frame();
    check_gears(hud, 6);
    assert(hud.text(prefix + "rpm") == "11585");

    hud.clear();
    dial.frame();
    assert(hud.writes().empty());

    for (int gear = 1; gear <= 8; ++gear) {
        car.gear = gear;
        dial.frame();
        check_gears(hud, gear);
    }
    car.gear = 0;
    dial.frame();
    check_gears(hud, -1);
    assert(hud.text(prefix + "special_gear") == "N");
    car.gear = -1;
    dial.frame();
    check_gears(hud, -1);
    assert(hud.text(prefix + "special_gear") == "R");

    car.have &= ~(SWOFTY_LIVE_HAVE_GEAR | SWOFTY_LIVE_HAVE_RPM);
    dial.frame();
    check_gears(hud, -1);
    assert(hud.text(prefix + "rpm").empty());
    assert(hud.text(prefix + "special_gear").empty());

    car.have |= SWOFTY_LIVE_HAVE_GEAR | SWOFTY_LIVE_HAVE_RPM;
    car.gear = 3;
    dial.frame();
    check_gears(hud, 3);
    live.set_available(false);
    dial.frame();
    check_gears(hud, -1);
    assert(hud.text(prefix + "rpm").empty());

    live.set_available(true);
    dial.frame();
    hud.clear();
    hud.rebuild();
    check_gears(hud, 3);
    assert(hud.refused() == 0);
    std::puts("core dial states: passed");
}
