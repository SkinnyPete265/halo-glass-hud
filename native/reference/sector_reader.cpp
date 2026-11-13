#include <swofty_api.h>
#include <windows.h>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <mutex>

namespace {
const SwoftyApi *api = nullptr;
const SwoftyCarOps *cars = nullptr;
const SwoftyHud *hud = nullptr;
using SplitFn = void (*)(void *, void *);
SplitFn original = nullptr;
std::mutex state_lock;
uint8_t lap_seen = 0xff;
float sectors[3]{};
float personal_best[3]{};
float session_best[3]{};
uint8_t quality[3]{}; // 0 pending, 1 yellow, 2 green, 3 purple
double publish_elapsed = 0;

template<class T> bool read_at(uintptr_t address, T &out) {
    SIZE_T got=0;
    return address && ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void *>(address),&out,sizeof out,&got) && got==sizeof out;
}
bool build_matches() {
    auto *base=reinterpret_cast<const uint8_t *>(GetModuleHandleW(nullptr));
    if (!base) return false;
    auto *dos=reinterpret_cast<const IMAGE_DOS_HEADER *>(base);
    if (dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 || dos->e_lfanew>0x1000) return false;
    auto *nt=reinterpret_cast<const IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
    return nt->Signature==IMAGE_NT_SIGNATURE && nt->FileHeader.TimeDateStamp==1789118616u && nt->OptionalHeader.SizeOfImage==0x193e6000u;
}
int human_vehicle() {
    if (!cars || !cars->available || !cars->available()) return -1;
    uint32_t count=0;
    if (cars->count(&count)!=SWOFTY_ASSET_OK || count>32) return -1;
    int selected=-1;
    for (uint32_t i=0;i<count;++i) {
        void *handle=nullptr; uint32_t ai=1;
        if (cars->car(i,&handle,&ai)==SWOFTY_ASSET_OK && handle && ai==0) {
            if (selected!=-1) return -1;
            selected=static_cast<int>(i);
        }
    }
    return selected;
}
void format(char *out,size_t cap,float s) {
    if (!(s>.5f && s<180.f) || !std::isfinite(s)) std::snprintf(out,cap,"--.---");
    else if (s>=60.f) {int m=static_cast<int>(s/60.f); std::snprintf(out,cap,"%d:%06.3f",m,s-60.f*m);}
    else std::snprintf(out,cap,"%.3f",s);
}
void format_cells(char *out,size_t cap,float s) {
    // Five digits plus the decimal point occupy fixed cells on the HUD.
    // Keep the original complete-string fields available for compatibility.
    if (!(s>.5f && s<180.f) || !std::isfinite(s)) std::snprintf(out,cap,"--.---");
    else {
        std::snprintf(out,cap,"%6.3f",s);
        if (std::strlen(out)>6) std::snprintf(out,cap,"--.---");
    }
}
void publish_text(const char *path,const char *complete,const char *cells) {
    hud->set(path,SWOFTY_HUD_TEXT,complete);
    const size_t count=std::strlen(cells);
    for (size_t j=0;j<6;++j) {
        char leaf[128],value[2]{};
        std::snprintf(leaf,sizeof leaf,"%s_c%u",path,static_cast<unsigned>(j));
        if (j<count && cells[j]!=' ') value[0]=cells[j];
        hud->set(leaf,SWOFTY_HUD_TEXT,value);
    }
}
void on_frame(double dt,void *) {
    if (!hud || !hud->available || !hud->available()) return;
    publish_elapsed+=dt;
    if (publish_elapsed<.5) return;
    publish_elapsed=0;
    float snapshot[3];
    uint8_t colors[3];
    {std::lock_guard<std::mutex> guard(state_lock); std::memcpy(snapshot,sectors,sizeof snapshot); std::memcpy(colors,quality,sizeof colors);}
    const char *paths[3][4]={
        {"view_model_data.hud_halo_sector_s1_time_white","view_model_data.hud_halo_sector_s1_time_yellow","view_model_data.hud_halo_sector_s1_time_green","view_model_data.hud_halo_sector_s1_time_purple"},
        {"view_model_data.hud_halo_sector_s2_time_white","view_model_data.hud_halo_sector_s2_time_yellow","view_model_data.hud_halo_sector_s2_time_green","view_model_data.hud_halo_sector_s2_time_purple"},
        {"view_model_data.hud_halo_sector_s3_time_white","view_model_data.hud_halo_sector_s3_time_yellow","view_model_data.hud_halo_sector_s3_time_green","view_model_data.hud_halo_sector_s3_time_purple"}};
    for (int i=0;i<3;++i) {
        char value[48],cells[16];
        format(value,sizeof value,snapshot[i]);
        format_cells(cells,sizeof cells,snapshot[i]);
        uint8_t active=(snapshot[i]>.5f && colors[i]<4)?colors[i]:0;
        // Clear inactive layers first. Pending sectors use the white layer.
        for (int c=0;c<4;++c) if (c!=active) publish_text(paths[i][c],"","");
        publish_text(paths[i][active],value,cells);
    }
}
void on_split(void *manager,void *event) {
    uint8_t vehicle=0xff;
    read_at(reinterpret_cast<uintptr_t>(event)+0x10,vehicle);
    original(manager,event);
    if (vehicle>=32) return;
    uintptr_t m=reinterpret_cast<uintptr_t>(manager),begin=0,end=0,entry=0;
    if (!read_at(m+0x58,begin) || !read_at(m+0x60,end) || !begin || end<begin || end-begin>32*sizeof(uintptr_t) ||
        vehicle>=(end-begin)/sizeof(uintptr_t) || !read_at(begin+vehicle*sizeof(uintptr_t),entry) || !entry) return;
    uint8_t lap=0xff,sector=0xff;
    if (!read_at(entry+0x38,lap) || !read_at(entry+0x39,sector) || lap>=199 || sector>=3) return;
    uintptr_t slot=entry+0x38+uintptr_t(lap)*0xc8+uintptr_t(sector)*0x10;
    uint32_t a=0,b=0;
    if (!read_at(slot+0x10,a) || !read_at(slot+0x18,b)) return;
    uint32_t bits=a^b; float seconds=0; std::memcpy(&seconds,&bits,sizeof seconds);
    if (!std::isfinite(seconds) || seconds<.5f || seconds>180.f) return;
    int player=human_vehicle();
    std::lock_guard<std::mutex> guard(state_lock);
    if (static_cast<int>(vehicle)==player) {
        if (lap!=lap_seen) {lap_seen=lap; std::memset(sectors,0,sizeof sectors); std::memset(quality,0,sizeof quality);}
        // Same three-tier ordering used by the game: session best, own best,
        // otherwise completed. Bests are learned from observed split events.
        quality[sector]=(session_best[sector]==0 || seconds<session_best[sector]-.0005f)?3:
                        (personal_best[sector]==0 || seconds<personal_best[sector]-.0005f)?2:1;
        sectors[sector]=seconds;
        if (personal_best[sector]==0 || seconds<personal_best[sector]) personal_best[sector]=seconds;
        if (api && api->log) api->log("[halo-sectors] vehicle=%u lap_slot=%u sector_slot=%u time=%.3f quality=%u",vehicle,lap,sector,seconds,quality[sector]);
    }
    if (session_best[sector]==0 || seconds<session_best[sector]) session_best[sector]=seconds;
}
}
extern "C" __declspec(dllexport) const uint32_t SwoftyAddonApi=SWOFTY_API_VERSION;
extern "C" __declspec(dllexport) int SwoftyAddonInit(const SwoftyApi *a) {
    if (!a || a->version<5 || !a->resolve || !a->register_mixins || !a->events || !a->events->on_frame ||
        !build_matches() || !a->resolve("Sess_LapTimes_ReportSplit")) return 0;
    api=a;
    HMODULE core=GetModuleHandleW(L"swofty_core.dll");
    auto get_cars=core?reinterpret_cast<SwoftyCoreCarOpsFn>(GetProcAddress(core,"SwoftyCoreCarOps")):nullptr;
    auto get_hud=core?reinterpret_cast<const SwoftyHud *(*)()>(GetProcAddress(core,"SwoftyCoreHud")):nullptr;
    cars=get_cars?get_cars():nullptr; hud=get_hud?get_hud():nullptr;
    if (!cars || !hud) return 0;
    uint32_t token=0;
    if (a->events->on_frame(on_frame,nullptr,&token)!=SWOFTY_ASSET_OK) return 0;
    const SwoftyMixin mixin{"Sess_LapTimes_ReportSplit",SWOFTY_MIXIN_WRAP,0,reinterpret_cast<void *>(&on_split),reinterpret_cast<void **>(&original)};
    return a->register_mixins(&mixin,1);
}
