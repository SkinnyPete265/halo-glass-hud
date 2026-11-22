#include <cassert>
#include <cstdio>
#include <limits>
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

    car.have |= SWOFTY_LIVE_HAVE_ERS_STORE | SWOFTY_LIVE_HAVE_ERS_POWER;
    car.ers_store = 3e6f;
    car.ers_capacity = 4e6f;
    car.ers_deploy = 20000;
    dial.frame();
    assert(hud.text(prefix+"charge") == "75%" && hud.text(prefix+"flow") == "DEPLOYING");
    assert(hud.text(prefix+"deploy_kw") == "20" && hud.text(prefix+"harvest_kw") == "0");
    car.ers_harvest_k = 12500; car.ers_harvest_h = 9000;
    dial.frame();
    assert(hud.text(prefix+"flow") == "HARVESTING" && hud.text(prefix+"harvest_kw") == "22");
    car.ers_deploy = 22500; // exactly +1 kW
    car.ers_store = 0;
    dial.frame();
    assert(hud.text(prefix+"flow").empty() && hud.text(prefix+"charge") == "0%");
    car.ers_deploy = 22501; // display still rounds to 23
    car.ers_store = car.ers_capacity;
    dial.frame();
    assert(hud.text(prefix+"flow") == "DEPLOYING" && hud.text(prefix+"charge") == "100%");
    car.ers_deploy = std::numeric_limits<float>::quiet_NaN();
    car.ers_capacity = 0;
    dial.frame();
    assert(hud.text(prefix+"flow").empty() && hud.text(prefix+"charge") == "-");
    assert(hud.text(prefix+"deploy_kw") == "-" && hud.text(prefix+"harvest_kw") == "22");
    car.have &= ~SWOFTY_LIVE_HAVE_ERS_POWER;
    car.have |= SWOFTY_LIVE_HAVE_ERS_MODE | SWOFTY_LIVE_HAVE_SPEED;
    car.speed = 69.4444f;
    const char *modes[] = {"NONE", "MEDIUM", "OVERTAKE", "HOTLAP", "-"};
    for (int i=0; i<5; ++i) {
        car.ers_mode = i;
        dial.frame();
        assert(hud.text(prefix+"mode") == modes[i]);
        assert(hud.text(prefix+"mode26") == (i == 2 ? "-" : modes[i]));
    }
    assert(hud.text(prefix+"kph") == "250" && hud.text(prefix+"mph") == "155");
    assert(hud.text(prefix+"harvest_kw") == "-");
    car.speed = 0;
    car.have &= ~SWOFTY_LIVE_HAVE_ERS_MODE;
    dial.frame();
    assert(hud.text(prefix+"kph") == "0" && hud.text(prefix+"mode") == "-");
    assert(hud.number(prefix+"speed_valid") && hud.text(prefix+"mph") == "0");
    car.speed = std::numeric_limits<float>::infinity();
    dial.frame();
    assert(hud.text(prefix+"mph") == "-");

    assert(!hud.number(prefix+"speed_valid"));
    car.have &= ~SWOFTY_LIVE_HAVE_SPEED;
    car.speed = 20;
    dial.frame();
    assert(!hud.number(prefix+"speed_valid"));
    car.have |= SWOFTY_LIVE_HAVE_SPEED;
    dial.frame();
    assert(hud.number(prefix+"speed_valid") && hud.text(prefix+"kph") == "72"
           && hud.text(prefix+"mph") == "45");

    const auto pedals = [&](bool stepped, int brake, int throttle) {
        assert(hud.number(prefix+"pedals_stepped") == stepped);
        for (int i=1; i<=10; ++i) {
            std::string suffix = (i<10 ? "0" : "") + std::to_string(i);
            assert(hud.number(prefix+"brake"+suffix) == (i<=brake));
            assert(hud.number(prefix+"throttle"+suffix) == (i<=throttle));
        }
    };
    car.have |= SWOFTY_LIVE_HAVE_PEDALS;
    car.brake = .45f; car.throttle = .74f;
    dial.frame(); pedals(false,0,0);
    dial.use_stepped_pedals(true);
    dial.frame(); pedals(true,5,7);
    hud.rebuild(); pedals(true,5,7);
    car.brake = 0; car.throttle = 1;
    dial.frame(); pedals(true,0,10);
    car.brake = std::numeric_limits<float>::quiet_NaN();
    dial.frame(); pedals(false,0,0);
    car.brake = 1; car.throttle = 0;
    dial.frame(); pedals(true,10,0);
    car.have &= ~SWOFTY_LIVE_HAVE_PEDALS;
    dial.frame(); pedals(false,0,0);
    car.have |= SWOFTY_LIVE_HAVE_PEDALS;
    dial.frame(); pedals(true,10,0);
    dial.use_stepped_pedals(false);
    dial.frame(); pedals(false,0,0);

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
