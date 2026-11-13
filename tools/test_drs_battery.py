"""Regression checks for DRS typography and the complete battery charge range."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
import uuid
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import prepare_runtime
import native_interop as native
from formats import erpw,idf,pkg,uinode as N,uiops as U
from halo import layout as geo


class InstrumentRefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record=json.loads((ROOT/'registry/hud.json').read_text())['hud.element']['glass_dial']
        battery=next(item for item in cls.record['elements'] if item['id']=='battery')
        cls.fill=next(item for item in battery['children'] if item['id']=='battery_charge')

    def edge(self,charge):
        start,end=self.fill['path']
        centre=start[0]+(end[0]-start[0])*charge
        return (centre+self.fill['window'][0]/2)/geo.HUD_SCALE+geo.CX

    def test_battery_geometry_excludes_texture_padding(self):
        sprite=self.record['sprites']['battery_fill']
        left,top,right,bottom=geo.battery_fill_bounds()
        actual=[value/geo.HUD_SCALE+origin for value,origin in
                zip(sprite['bounds'],(geo.CX,geo.CY,geo.CX,geo.CY))]
        resolution=geo.BATTERY_TEXTURE_RESOLUTION
        self.assertLessEqual(abs(actual[0]-left),1/resolution)
        self.assertLessEqual(abs(actual[1]-top),1/resolution)
        self.assertLessEqual(abs(actual[2]-right),4/resolution)
        self.assertLessEqual(abs(actual[3]-bottom),4/resolution)
        with Image.open(ROOT/sprite['png']) as image:
            self.assertEqual(image.width%4,0)
            self.assertEqual(image.height%4,0)
            self.assertAlmostEqual(image.width,(actual[2]-actual[0])*resolution,places=4)
            self.assertAlmostEqual(image.height,(actual[3]-actual[1])*resolution,places=4)
        for value in (0.,.5,.92,.95,.99,1.):
            self.assertAlmostEqual(self.edge(value),geo.battery_fill_edge(value),places=4)

    def test_last_fill_pixel_tracks_the_full_charge_range(self):
        left,top,right,bottom=geo.battery_fill_bounds()
        def coverage(charge,x):
            return float(x<self.edge(charge))
        self.assertEqual(coverage(0.,left+.5),0.)
        self.assertEqual(coverage(1.,right-.5),1.)
        self.assertEqual(coverage(.95,right-.5),0.)
        self.assertEqual(coverage(.99,right-.5),0.)
        self.assertEqual(coverage(.995,right-.5),1.)
        values=[coverage(charge/1000,right-.5) for charge in range(1001)]
        self.assertTrue(all(first<=second for first,second in zip(values,values[1:])))
        self.assertEqual(values,list(reversed([coverage(charge/1000,right-.5) for charge in range(1000,-1,-1)])))

    def test_drs_open_is_authored_as_native_text(self):
        def elements(items):
            for item in items:
                yield item
                yield from elements(item.get('children',[]))
        label=next(item for item in elements(self.record['elements']) if item['id']=='drs_open_label')
        self.assertEqual(label['kind'],'text')
        self.assertEqual(label['literal'],'DRS OPEN')
        self.assertEqual(label['style'],geo.DRS_TEXT_STYLE)
        self.assertEqual(label['at'],geo.hud_point(*geo.DRS_CENTRE))

    def test_direct_battery_binding_is_shared_and_timer_free(self):
        from halo.dials import DIALS
        for ctx in DIALS:
            names=['x_battery_charge_win','x_battery_charge_ctr',
                   'x_'+ctx.prefix+'_battery_frame_colour',
                   'x_'+ctx.prefix+'_battery_charge_fill_colour']
            controls=U.node(ctx.prefix+'_ctl','UIGP',kids=[
                U.node(name,'UAXA',props=[('fraction',U.prop('fp32',.5))]) for name in names])
            report=native.battery_binding(controls,ctx=ctx)
            self.assertEqual(report['method'],'direct native fraction')
            self.assertEqual(len(N.children(controls)),4)
            for name in names:
                value=N.child(controls,name).items[N.PROPS]['fraction']
                self.assertEqual(value['value'].type,'fp32')
                self.assertEqual(value['dbentry'].value,'ers_stored')

    def test_battery_dimensions_and_bolt_resolution(self):
        self.assertAlmostEqual(geo.BATTERY_WIDTH,54.*1.06*1.10)
        self.assertAlmostEqual(geo.BATTERY_HEIGHT,22.*1.02)
        self.assertGreater(geo.BATTERY_CORNER_RADIUS/geo.BATTERY_HEIGHT,.25)
        with Image.open(ROOT/self.record['sprites']['battery_bolt']['png']) as image:
            self.assertGreaterEqual(image.height,geo.BATTERY_TEXTURE_RESOLUTION*9)

    def test_rpm_tip_profile_is_rounded_and_follows_the_arc(self):
        from halo import rpm_mask
        self.assertEqual(len(rpm_mask.path()),rpm_mask.KEY_COUNT)
        # The circle extends the core ahead of the moving cut and tapers at its sides.
        self.assertGreater(rpm_mask.coverage(1.,0.),.95)
        self.assertLess(rpm_mask.coverage(3.,0.),.2)
        self.assertLess(rpm_mask.coverage(1.8,1.8),.2)
        for fraction in (0.,.25,.5,.75,1.):
            x,y=rpm_mask.tip(fraction)
            self.assertAlmostEqual(y,geo.top(x)+geo.RPM_BAR_OFFSET)
        self.assertEqual(geo.BATTERY_FILL_FEATHER,0.)

    @unittest.skipUnless((ROOT/'build/composed/hud_scene.erp').exists(),'Needs a local composer fixture')
    def test_native_drs_styles_keep_live_bindings_and_scoped_effects(self):
        archive=erpw.Erp(ROOT/'build/composed/hud_scene.erp')
        scene=idf.Idf(archive.frag_data(archive.find(native.MAIN),0))
        template_archive=erpw.Erp(ROOT/'build/composed/hud_template.erp')
        template=pkg.Pkg(template_archive.frag_data(template_archive.find(native.TEMPLATE),0))
        f1=next(node for node in native.walk(template.root) if N.name(node)=='hud_f1_dial')
        dial=N.child(N.child(f1,'osd_visibility_option'),'f1_dial_child')
        controls=N.child(dial,'halo_v2_ctl')
        tree=scene.scenes[0].root
        # Older composer output supplies the same native text prototype for this focused fixture.
        if tree.find('halo_v2_drs_open_label_n') is None:
            holder=copy.deepcopy(tree.find('halo_v2_rpm_unit_n').obj)
            glyph=copy.deepcopy(tree.find('halo_v2_rpm_unit').obj)
            holder['name'].value='halo_v2_drs_open_label_n'
            glyph['name'].value='halo_v2_drs_open_label'
            holder.set('children',pkg.Arr([glyph]))
            scale=holder['scale'].value[0]*geo.DRS_STATUS_TEXT_SIZE/geo.UNIT_LABEL_SIZE
            holder.set('scale',pkg.Val('vec3',[scale,scale,1.,0.]))
            for obj in (holder,glyph):
                idf.set_param(obj,'guid',str(uuid.uuid5(uuid.NAMESPACE_URL,obj['name'].value)))
            for parent,_ in tree.walk():
                for index,child in enumerate(parent.children):
                    if child.name=='halo_v2_drs_open_label':
                        parent.obj['children'].items[index]=holder
                        break
            label=copy.deepcopy(N.child(controls,'t_rpm_unit'))
            label.items[N.PROPS]['name'].value='t_drs_open_label'
            label.items[N.PROPS].set('text',U.prop('stri','DRS OPEN'))
            label.items[N.LAYOUT]=U.layout_path('halo_v2_drs_open_label')
            controls.items[N.CHILDREN].items.append(label)
            native.refresh_scene(scene)
            scene=idf.Idf(scene.to_bytes())
        reference=erpw.Erp(ROOT/'native/reference/native-controls.erpk')
        native.centre_text_readouts(scene,reference)
        prompt=idf.Idf(reference.frag_data(reference.find('eaid://ui_package/art/osd/local_halo/status.idf'),0))
        ui=pkg.Pkg((ROOT/'native/reference/drs-template.bin').read_bytes()).root
        old=N.child(dial,'drs_and_pit_distance')
        dial.items[N.CHILDREN].items[dial.items[N.CHILDREN].items.index(old)]=ui
        report=native.drs_typography(scene,prompt,ui,controls,dial)
        native.refresh_scene(scene)
        native.refresh_scene(prompt)
        N.fix_ids(f1)
        scene=idf.Idf(scene.to_bytes())
        prompt=idf.Idf(prompt.to_bytes())
        self.assertEqual(sum(item['effect_layers'] for item in report['labels']),32)
        self.assertFalse(idf.xref_mismatches(scene))
        self.assertFalse(idf.xref_mismatches(prompt))
        for name in ('text','distance_text','halo_drs_prompt_text','halo_pit_prompt_text','drs_activate_tooltip_as_label'):
            self.assertEqual(prompt.scenes[0].root.find(name).params['style'],geo.DRS_TEXT_STYLE)
        for name,binding in (('distance','distance_formatted'),('bar_status','bar_state_text')):
            self.assertEqual(N.child(ui,name).items[N.PROPS]['text']['dbentry'].value,binding)
        for name in ('distance','bar_status'):
            self.assertEqual(N.child(ui,name).items[N.PROPS]['colourOverride']['value'].value,'#ffffffff')
        tooltip=N.child(ui,'tooltip_drs_button')
        for name,binding in (('icon','icon'),('icon_as_text','action.axis_0.display_text')):
            self.assertEqual(N.child(tooltip,name).items[N.PROPS]['text']['dbentry'].value,binding)
        def paths(node,parent=''):
            path=parent+'.'+N.name(node) if parent else N.name(node)
            yield path,node
            for child in N.children(node):
                yield from paths(child,path)
        nodes=dict(paths(f1))
        for path,node in nodes.items():
            if '.halo_drs_type_' in path and path.endswith('_alpha'):
                expected=geo.DRS_PROMPT_OUTLINE_ALPHA/255
                if '_open_' in path:
                    expected=30/255 if '_outline_' in path else geo.DRS_LABEL_GLOW_ALPHA/255
                self.assertAlmostEqual(node.items[N.PROPS]['Value']['value'].value,expected,places=6)
                for event in ('show','use_dial','command_vmContextValid'):
                    command=next(item for item in dial.items[N.COMMANDS].items if item['commandName'].value==event)
                    self.assertTrue(any(signal['to_object_name'].value==path for signal in command['signals'].items),path)
        # Exercise the serialized metadata used by the game loader.
        idf.Idf(scene.to_bytes())
        idf.Idf(prompt.to_bytes())
        pkg.Pkg(template.to_bytes())


if __name__=='__main__':
    unittest.main()
