#pragma once
#include <atomic>
#include <chrono>
#include <tuple>
#include <cmath>
#include <cstdio>
#include <swofty/hud_leaves.hpp>
#include <swofty/live.hpp>

namespace halo {
class Dial {
public:
    void use_stepped_pedals(bool enabled) { stepped_preference_.store(enabled); }

    using Clock = std::chrono::steady_clock;
    void frame(Clock::time_point now = Clock::now())
    {
        const auto car = swofty::live::available() ? swofty::live::subject() : std::nullopt;
        int selected = -1;
        const char *special = "";
        char rpm[12]{};
        char charge[8] = "-", deploy[8] = "-", harvest[8] = "-";
        char kph[8] = "-", mph[8] = "-";
        const char *mode = "-";
        std::optional<int> flow;
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
        const bool speed_valid = car && swofty::live::has(*car, SWOFTY_LIVE_HAVE_SPEED) &&
            std::isfinite(car->speed) && car->speed >= 0;
        const char *mode26 = "-";
        if (car) {
            const auto fraction = swofty::live::ers_fraction(*car);
            if (fraction && std::isfinite(car->ers_store) && std::isfinite(car->ers_capacity) &&
                std::isfinite(*fraction))
                std::snprintf(charge, sizeof charge, "%ld%%", std::lround(*fraction * 100.0f));
            if (swofty::live::has(*car, SWOFTY_LIVE_HAVE_ERS_MODE) &&
                car->ers_mode >= 0 && car->ers_mode <= 3) {
                constexpr const char *modes[] = {"NONE", "MEDIUM", "OVERTAKE", "HOTLAP"};
                mode = modes[car->ers_mode];
                // Mode 2 has no verified ordinary 2026 label. Boost is a native dial event.
                if (car->ers_mode != 2) mode26 = mode;
            }
            if (swofty::live::has(*car, SWOFTY_LIVE_HAVE_ERS_POWER)) {
                const double deployed = car->ers_deploy / 1000.;
                const double recovered = (double(car->ers_harvest_k) + car->ers_harvest_h) / 1000.;
                format_number(deploy, deployed);
                format_number(harvest, recovered);
                if (std::isfinite(deployed) && std::isfinite(recovered)) {
                    const double net = deployed - recovered;
                    flow = (net > 1.) - (net < -1.);
                }
            }
            if (speed_valid) {
                format_number(kph, car->speed * 3.6);
                format_number(mph, car->speed * 2.236936292);
            }
        }
        const auto session = flow ? swofty::live::session() : std::nullopt;
        if (!session) {
            flow_subject_.reset();
            pending_flow_ = visible_flow_ = 0;
        } else {
            const auto subject = std::make_tuple(session->generation, session->subject_generation, car->vehicle);
            if (flow_subject_ != subject) {
                flow_subject_ = subject;
                pending_flow_ = visible_flow_ = 0;
            }
            if (*flow != pending_flow_) {
                pending_flow_ = *flow;
                flow_since_ = now;
            } else if (now - flow_since_ >= std::chrono::milliseconds(200)) {
                visible_flow_ = pending_flow_;
            }
        }
        const bool stepped = stepped_preference_.load() && car &&
            swofty::live::has(*car, SWOFTY_LIVE_HAVE_PEDALS) &&
            valid_pedal(car->throttle) && valid_pedal(car->brake);
        {
            swofty::hud::Leaves::Atomic update(leaves_);
            leaves_.set(stepped_, stepped);
            leaves_.set(brake_, stepped ? int(std::lround(car->brake * 10)) : 0);
            leaves_.set(throttle_, stepped ? int(std::lround(car->throttle * 10)) : 0);
            leaves_.set(gears_, selected);
            leaves_.set(special_, special);
            leaves_.set(rpm_, rpm);
            leaves_.set(charge_, charge);
            leaves_.set(mode_, mode);
            leaves_.set(mode26_, mode26);
            leaves_.set(speed_valid_, speed_valid);
            leaves_.set(flow_, visible_flow_ > 0 ? "DEPLOYING" : visible_flow_ < 0 ? "HARVESTING" : "");
            leaves_.set(deploy_kw_, deploy);
            leaves_.set(harvest_kw_, harvest);
            leaves_.set(kph_, kph);
            leaves_.set(mph_, mph);
        }
        leaves_.flush();
    }

private:
    std::optional<std::tuple<uint32_t,uint32_t,uint32_t>> flow_subject_;
    Clock::time_point flow_since_{};
    int pending_flow_ = 0, visible_flow_ = 0;
    std::atomic<bool> stepped_preference_{false};
    static bool valid_pedal(float value) { return value >= 0 && value <= 1; }

    static void format_number(char (&out)[8], double value)
    {
        if (std::isfinite(value)) {
            if (std::abs(value) >= 999.5)
                std::snprintf(out, sizeof out, "%s", value < 0 ? "<-999" : ">999");
            else
                std::snprintf(out, sizeof out, "%ld", std::lround(value));
        }
    }

    swofty::hud::Leaves leaves_{"view_model_data.hud_halo_v2_"};
    swofty::hud::BoolLeaf stepped_ = leaves_.boolean("pedals_stepped");
    swofty::hud::Level brake_ = leaves_.level("brake", 10);
    swofty::hud::Level throttle_ = leaves_.level("throttle", 10);
    swofty::hud::OneHot gears_ = leaves_.one_hot("gear", 8, 0, 1);
    swofty::hud::TextLeaf special_ = leaves_.text("special_gear", 2);
    swofty::hud::TextLeaf rpm_ = leaves_.text("rpm", 6);
    swofty::hud::TextLeaf charge_ = leaves_.text("charge", 8);
    swofty::hud::BoolLeaf speed_valid_ = leaves_.boolean("speed_valid");
    swofty::hud::TextLeaf mode26_ = leaves_.text("mode26", 12);
    swofty::hud::TextLeaf mode_ = leaves_.text("mode", 12);
    swofty::hud::TextLeaf flow_ = leaves_.text("flow", 12);
    swofty::hud::TextLeaf deploy_kw_ = leaves_.text("deploy_kw", 8);
    swofty::hud::TextLeaf harvest_kw_ = leaves_.text("harvest_kw", 8);
    swofty::hud::TextLeaf kph_ = leaves_.text("kph", 8);
    swofty::hud::TextLeaf mph_ = leaves_.text("mph", 8);
};
}
