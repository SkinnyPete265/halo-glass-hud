#include <cassert>
#include <cstdio>
#include <string>
#include <swofty/fake_hud.hpp>
#include "../src/sector_state.hpp"

std::string time(const swofty::fake::Hud &hud, int sector, const char *colour)
{
    const std::string prefix = "view_model_data.hud_halo_v2_sector_s" + std::to_string(sector) + "_" + colour + "_c";
    std::string text;
    for (int cell = 0; cell < 6; ++cell)
        text += hud.text(prefix + std::to_string(cell));
    return text;
}

int main()
{
    swofty::fake::Hud hud;
    halo::SectorState state;
    halo::SectorHud publisher;
    state.context(1, 0);
    publisher.publish(state.snapshot());
    assert(time(hud, 1, "white") == "--.---");
    assert(hud.number("view_model_data.hud_halo_v2_sector_s1_ready") == 0);
    assert(time(hud, 1, "purple").empty());
    assert(state.observe(1, 0, 0, 26000));
    assert(state.observe(0, 0, 0, 27628));
    assert(state.snapshot().quality[0] == 2);
    publisher.publish(state.snapshot());
    assert(time(hud, 1, "green") == "27.628");
    assert(hud.number("view_model_data.hud_halo_v2_sector_s1_ready") == 1);
    assert(hud.number("view_model_data.hud_halo_v2_sector_s1_pulse") == 1);
    assert(time(hud, 1, "white").empty());
    assert(time(hud, 1, "purple").empty());
    assert(!state.observe(0, 0, 0, 27628));
    assert(state.snapshot().quality[0] == 2);
    assert(state.observe(0, 0, 1, 18159));
    assert(state.snapshot().quality[1] == 3);
    assert(state.observe(0, 0, 2, 33366));
    assert(state.observe(0, 1, 0, 28000));
    assert(state.snapshot().quality[0] == 1);
    assert(state.snapshot().milliseconds[1] == 0);
    assert(state.snapshot().milliseconds[2] == 0);
    publisher.publish(state.snapshot());
    assert(time(hud, 1, "yellow") == "28.000");
    assert(hud.number("view_model_data.hud_halo_v2_sector_s1_pulse") == 0);
    assert(hud.number("view_model_data.hud_halo_v2_sector_s2_ready") == 0);
    assert(time(hud, 1, "green").empty());
    assert(time(hud, 2, "white") == "--.---");
    assert(state.observe(0, 2, 0, 25000));
    publisher.publish(state.snapshot());
    assert(time(hud, 1, "purple") == "25.000");
    assert(time(hud, 1, "yellow").empty());
    assert(!state.observe(32, 2, 0, 25000));
    assert(!state.observe(0, 2, 3, 25000));
    const int prior_pulse = hud.number("view_model_data.hud_halo_v2_sector_s1_pulse");
    assert(state.observe(0, 3, 0, 25000));
    publisher.publish(state.snapshot());
    assert(hud.number("view_model_data.hud_halo_v2_sector_s1_pulse") != prior_pulse);
    hud.clear();
    publisher.publish(state.snapshot());
    assert(hud.writes().empty());
    state.context(2, 0);
    publisher.publish(state.snapshot());
    assert(time(hud, 1, "white") == "--.---");
    assert(time(hud, 1, "purple").empty());
    hud.rebuild();
    assert(time(hud, 1, "white") == "--.---");
    hud.clear();
    publisher.publish(state.snapshot());
    assert(hud.writes().empty());
    assert(hud.refused() == 0);
    std::puts("sector defaults, colours, lap/session reset, per-result pulses and duplicate suppression: passed");
}
