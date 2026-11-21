#include <cassert>
#include <cstdio>
#include <cstdarg>
#include <string>
#include <vector>
#include <halo/sector_builds.hpp>
#include <swofty/fake_hud.hpp>
#include <swofty/fake_live.hpp>
#include "../src/live_sectors.hpp"

std::string time(const swofty::fake::Hud &hud, int sector, const char *colour)
{
    const std::string prefix = "view_model_data.hud_halo_v2_sector_s" + std::to_string(sector) + "_" + colour + "_c";
    std::string text;
    for (int cell = 0; cell < 6; ++cell)
        text += hud.text(prefix + std::to_string(cell));
    return text;
}

namespace {
std::vector<std::string> messages;
void capture(const char *format, ...)
{
    char buffer[256];
    va_list args;
    va_start(args, format);
    std::vsnprintf(buffer, sizeof buffer, format, args);
    va_end(args);
    messages.emplace_back(buffer);
}

void live_transitions()
{
    swofty::fake::Live live;
    live.add_car(7);
    live.add_car(2);
    live.set_player(7);
    live.install();
    auto &me = live.detail(7);
    auto &rival = live.detail(2);
    me.have = rival.have = SWOFTY_LIVE_HAVE_LAP_TIMES;
    halo::SectorTiming timing(capture);
    timing.legacy_available = true;
    swofty::fake::Hud hud;
    halo::SectorHud publisher;
    auto frame = [&] { timing.frame(); publisher.publish(timing.snapshot()); };
    const char *s3_ready = "view_model_data.hud_halo_v2_sector_s3_ready";
    const char *s3_pulse = "view_model_data.hud_halo_v2_sector_s3_pulse";
    frame();
    assert(timing.provider() == halo::SectorProvider::live);
    rival.current_sector_ms[0] = 21000;
    me.current_sector_ms[0] = 22000;
    timing.legacy_split(7, 0, 0, 22002);
    assert(!timing.snapshot().milliseconds[0]); // comparison only
    frame();
    assert(time(hud, 1, "green") == "22.000");
    assert(messages.back().find("disagreement lap=1 S1 live=22000 reader=22002") != std::string::npos);
    const auto log_count = messages.size();
    hud.clear();
    frame();
    assert(hud.writes().empty() && messages.size() == log_count);

    me.have = 0;
    timing.legacy_split(7, 0, 1, 23000);
    frame();
    assert(timing.provider() == halo::SectorProvider::live && !timing.snapshot().milliseconds[1]);
    me.have = SWOFTY_LIVE_HAVE_LAP_TIMES;
    me.current_sector_ms[1] = 23000;
    frame();
    assert(time(hud, 2, "purple") == "23.000");
    me.laps_completed++;
    me.current_sector_ms[0] = me.current_sector_ms[1] = 0;
    frame(); // The completed record can be zero on the first read.
    assert(!hud.number(s3_ready));
    me.last_sector_ms[2] = 24000;
    frame();
    assert(time(hud, 3, "purple") == "24.000" && hud.number(s3_ready));
    const auto pulse = hud.number(s3_pulse);
    frame();
    assert(hud.number(s3_pulse) == pulse && hud.number(s3_ready));
    me.current_sector_ms[0] = 22000;
    frame();
    assert(time(hud, 1, "yellow") == "22.000" && !hud.number(s3_ready));
    assert(timing.snapshot().revision[0] == 2);

    // A stalled render loop sees the finish and the next S1 together.
    me.laps_completed++;
    frame();
    assert(time(hud, 3, "yellow") == "24.000" && hud.number(s3_pulse) != pulse);
    frame();
    assert(time(hud, 1, "yellow") == "22.000" && !hud.number(s3_ready));
    assert(timing.snapshot().revision[0] == 3);
    me.current_sector_ms[0] = 0;
    frame();
    me.current_sector_ms[0] = 22000;
    frame();
    assert(timing.snapshot().revision[0] == 3);

    me.laps_completed = 0;
    frame();
    assert(!timing.snapshot().milliseconds[0] && !hud.number(s3_ready));
    me.current_lap_ms = 48000;
    me.current_sector_ms[1] = 26000;
    frame();
    assert(time(hud, 2, "purple") == "26.000");
    me.current_lap_ms = 1000; // Restart before the first finish.
    me.current_sector_ms[0] = me.current_sector_ms[1] = 0;
    frame();
    assert(!timing.snapshot().milliseconds[1]);
    me.current_sector_ms[0] = 19000;
    frame();
    assert(time(hud, 1, "purple") == "19.000");
    ++live.session().generation;
    frame();
    frame();
    assert(!timing.snapshot().milliseconds[0]);
    live.set_player(2);
    frame();
    assert(!timing.snapshot().milliseconds[0]);
    rival.current_sector_ms[1] = 18500;
    frame();
    assert(time(hud, 2, "purple") == "18.500");
    live.set_available(false);
    frame();
    assert(!timing.snapshot().milliseconds[1]);
    live.set_available(true);
    frame();
    assert(!timing.snapshot().milliseconds[1]);
}

void fallback_selection()
{
    swofty::fake::Live live;
    live.add_car(4);
    live.set_player(4);
    auto &d = live.detail(4);
    d.have = SWOFTY_LIVE_HAVE_LAP_TIMES;
    d.laps_completed = 9;
    d.current_sector_ms[0] = d.last_sector_ms[2] = 21000;
    live.set_table_version(5);
    live.install();
    halo::SectorTiming timing;
    timing.frame();
    assert(timing.provider() == halo::SectorProvider::waiting);
    timing.legacy_available = true;
    timing.frame();
    assert(timing.provider() == halo::SectorProvider::legacy);
    timing.legacy_split(4, 9, 0, 21000);
    assert(timing.snapshot().revision[0] == 1);
    live.set_table_version(6);
    d.have = SWOFTY_LIVE_HAVE_GRID;
    halo::SectorTiming missing;
    missing.legacy_available = true;
    missing.frame();
    assert(missing.provider() == halo::SectorProvider::waiting);
    missing.legacy_split(4, 9, 0, 21000);
    assert(missing.provider() == halo::SectorProvider::legacy && missing.snapshot().revision[0] == 1);
    d.current_sector_ms[0] = 0; // Live initially trails the already published fallback gate.
    d.have |= SWOFTY_LIVE_HAVE_LAP_TIMES;
    missing.frame();
    assert(missing.provider() == halo::SectorProvider::live && missing.snapshot().revision[0] == 1);
    assert(!missing.snapshot().milliseconds[2]); // No previous-lap replay.
    d.current_sector_ms[0] = 21002;
    missing.frame();
    assert(missing.snapshot().milliseconds[0] == 21000 && missing.snapshot().revision[0] == 1);
    missing.legacy_split(4, 9, 1, 20000);
    assert(!missing.snapshot().milliseconds[1]);
    d.current_sector_ms[1] = 20000;
    missing.frame();
    assert(missing.snapshot().revision[1] == 1);
    d.laps_completed += 3; // Old HUD rows expire across a gap of multiple laps.
    missing.frame();
    assert(!missing.snapshot().milliseconds[0] && !missing.snapshot().milliseconds[1]);
    assert(!missing.snapshot().milliseconds[2]);
}
}

int main()
{
    live_transitions();
    fallback_selection();
    assert(halo::supports_sector_reader(1789118616u, 0x193e6000u));
    assert(halo::supports_sector_reader(1794312636u, 0x18434000u));
    assert(!halo::supports_sector_reader(1794312636u, 0x193e6000u));
    assert(!halo::supports_sector_reader(1789118616u, 0x18434000u));
    assert(!halo::supports_sector_reader(1794312635u, 0x18434000u));
    assert(!halo::supports_sector_reader(0u, 0u));

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
    std::puts("Live v6 timing, fallback selection, comparison, colours, lap/session reset and HUD pulses: passed");
}
