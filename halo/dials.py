"""Native scene and controller namespaces for the supported car generations."""
from dataclasses import dataclass

@dataclass(frozen=True)
class DialSpec:
    registry: str
    dial: str
    prefix: str
    scene_name: str
    template: str
    child: str
    namespace: str

    @property
    def main(self):
        return 'eaid://ui_package/art/osd/components/dial/' + self.scene_name + '.idf'

    @property
    def path(self):
        return self.template + '.osd_visibility_option.' + self.child

    @property
    def own(self):
        return 'eaid://ui_package/art/osd/' + self.namespace + '/'

F125 = DialSpec('glass_dial', 'f1_25', 'halo_v2', 'dial_complete',
               'hud_f1_dial', 'f1_dial_child', 'halo_hud_v2')
F126 = DialSpec('glass_dial_26', 'f1_26', 'halo_v2_26', 'dial_om_xm',
               'hud_f1_dial_om_xm', 'f1_om_xm_dial_child', 'halo_hud_v2_26')
DIALS = (F125, F126)
