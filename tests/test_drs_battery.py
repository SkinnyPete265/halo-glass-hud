"""Regression checks for DRS typography and the complete battery charge range."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
import prepare_runtime
import native_interop as native
from formats import erpw,idf,pkg,uinode as N,uiops as U
from halo import artwork as art, feature_assets, layout as geo, material as mat


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

    def test_filtered_battery_frame_keeps_the_original_terminal_gap(self):
        cx,cy=geo.BATTERY_CENTRE
        left,right=cx-geo.BATTERY_WIDTH/2,cx+geo.BATTERY_WIDTH/2
        top,bottom=cy-geo.BATTERY_HEIGHT/2,cy+geo.BATTERY_HEIGHT/2
        box=(round(left*art.S),round(top*art.S),
             round(right*art.S),round(bottom*art.S))
        frame_source=Image.new('L',(geo.WIDTH*art.S,geo.HEIGHT*art.S))
        ImageDraw.Draw(frame_source).rounded_rectangle(
            box,radius=geo.BATTERY_CORNER_RADIUS*art.S,outline=225,width=art.S)
        terminal_source=Image.new('L',frame_source.size)
        ImageDraw.Draw(terminal_source).rounded_rectangle(
            ((right+1)*art.S,(cy-3)*art.S,(right+4)*art.S,(cy+3)*art.S),
            radius=2*art.S,fill=180)
        centre_y=round(cy*art.S)
        frame_x=[x for x in range(round(right*art.S)-art.S*2,
                                  round(right*art.S)+art.S*2+1)
                 if frame_source.getpixel((x,centre_y))]
        terminal_x=[x for x in range(round(right*art.S)-art.S*2,
                                     round((right+4)*art.S)+1)
                    if terminal_source.getpixel((x,centre_y))]
        gap=range(max(frame_x)+1,min(terminal_x))
        self.assertEqual(len(gap),2)

        filtered=feature_assets.battery_layers()['frame'].getchannel('A')
        top,bottom=terminal_source.getbbox()[1::2]
        for y in range(top,bottom):
            for x in gap:
                self.assertEqual(filtered.getpixel((x,y)),0,(x,y))
        self.assertGreater(filtered.getpixel((gap.start-1,centre_y)),0)
        self.assertGreater(filtered.getpixel((gap.stop,centre_y)),0)

    def test_idle_slats_keep_ten_distinct_filtered_lines_per_bank(self):
        layer=art._idle_slats_layer()
        alpha=layer.getchannel('A')
        self.assertEqual(alpha.getextrema(),(0,55))
        self.assertEqual(layer.size,(geo.WIDTH*art.S,geo.HEIGHT*art.S))
        for side in (-1,1):
            centres=[]
            for index in range(10):
                points=geo.slat_points(side,index)
                x=round(sum(point[0] for point in points)/len(points)*art.S)
                y=round(sum(point[1] for point in points)/len(points)*art.S)
                centres.append((x,y))
                self.assertEqual(layer.getpixel((x,y)),(126,176,187,55))
            for first,second in zip(centres,centres[1:]):
                x=round((first[0]+second[0])/2)
                y=round((first[1]+second[1])/2)
                self.assertEqual(alpha.crop((x-1,y-1,x+2,y+2)).getextrema(),(0,0))

    def test_filtered_circle_and_arc_keep_core_coverage_at_endpoints(self):
        captured=[]
        compose=mat._compose_stroke_mask
        def capture(image,mask,offset,color,glow,prefilter_core=False):
            if prefilter_core:
                captured.append((mask.copy(),offset))
            return compose(image,mask,offset,color,glow,prefilter_core)
        blank=Image.new('RGBA',(geo.WIDTH*art.S,geo.HEIGHT*art.S))
        with patch.object(mat,'_compose_stroke_mask',side_effect=capture):
            mat.circle_stroke(blank,(geo.CX,geo.CY),89.,(150,210,238,170),.8,0.,
                              prefilter_core=True)
            mat.arc_stroke(blank,(geo.CX,geo.CY),61.,140.,400.,mat.WHITE+(230,),
                           1.6,0.,prefilter_core=True)
        self.assertEqual(len(captured),2)
        for mask,_ in captured:
            bounds=mask.getbbox()
            self.assertIsNotNone(bounds)
            self.assertGreaterEqual(bounds[0],1)
            self.assertGreaterEqual(bounds[1],1)
            self.assertGreaterEqual(mask.width-bounds[2],1)
            self.assertGreaterEqual(mask.height-bounds[3],1)
            self.assertGreater(max(mat._box_filter_alpha_3x3(mask).getdata()),0)
        arc,offset=captured[1]
        for angle in (140.,400.):
            radians=math.radians(angle)
            endpoint=(geo.CX+61.*math.cos(radians),geo.CY+61.*math.sin(radians))
            found=False
            for y in range(arc.height):
                for x in range(arc.width):
                    px=(offset[0]+x+.5)/art.S
                    py=(offset[1]+y+.5)/art.S
                    if math.hypot(px-endpoint[0],py-endpoint[1])<=1.2 and arc.getpixel((x,y))>0:
                        found=True
                        break
                if found:
                    break
            self.assertTrue(found,f'Arc endpoint at {angle:g} degrees was clipped')

    def test_b_and_b_plus_change_only_glow_layer_count(self):
        core_keys=('outline_width','outline_alpha','reflection_alpha','reflection_sigma',
                   'tail_alpha','tail_radius','tail_sigma')
        self.assertEqual({key:mat.RACE_EDGE_VARIANTS['B'][key] for key in core_keys},
                         {key:mat.RACE_EDGE_VARIANTS['B+'][key] for key in core_keys})
        for key in ('edge_glow_layers','outline_glow_layers','circle_glow_layers'):
            self.assertEqual(mat.RACE_EDGE_VARIANTS['B'][key],1)
            self.assertEqual(mat.RACE_EDGE_VARIANTS['B+'][key],2)
            self.assertEqual(mat.RACE_EDGE_VARIANTS['B+3'][key],3)
            self.assertEqual(mat.RACE_EDGE_VARIANTS['B+4'][key],4)
        for name in ('B+3','B+4'):
            self.assertEqual({key:mat.RACE_EDGE_VARIANTS['B+'][key]
                              for key in core_keys},
                             {key:mat.RACE_EDGE_VARIANTS[name][key]
                              for key in core_keys})
            for key in ('edge_glow_alpha','edge_glow_sigma','outline_glow_alpha',
                        'outline_glow_sigma','circle_glow_alpha','circle_glow_sigma'):
                self.assertEqual(mat.RACE_EDGE_VARIANTS['B+'][key],
                                 mat.RACE_EDGE_VARIANTS[name][key])
        self.assertEqual(mat.DEFAULT_RACE_EDGE_VARIANT,'B+4')

    def test_drs_rails_and_fade_end_at_the_wing_face_tip(self):
        from halo import drs_motion
        self.assertEqual(geo.DRS_RAIL_END,geo.WING_FACE_END)
        for edge in geo.DRS_RAIL_EDGES:
            points=geo.drs_rail_points(edge)
            self.assertEqual(points[-1][0],round(geo.WING_FACE_END))
        feature_assets.drs_clip_mask.cache_clear()
        fade=feature_assets.drs_clip_mask()
        before=round((geo.WING_FACE_END-16.)*art.S)
        tip=round(geo.WING_FACE_END*art.S)
        after=round((geo.WING_FACE_END+1.)*art.S)
        self.assertGreater(fade.getpixel((before,round(geo.CY*art.S))),0)
        self.assertEqual(fade.getpixel((tip,round(geo.CY*art.S))),0)
        self.assertEqual(fade.getpixel((after,round(geo.CY*art.S))),0)
        self.assertEqual(drs_motion.rail_limits(),(geo.DRS_RAIL_START,geo.WING_FACE_END))
        self.assertGreater(drs_motion.window_centre(1.),
                           geo.WING_FACE_END-geo.CX)
        rails=feature_assets.drs_rails().getchannel('A')
        for side in (-1,1):
            face_tip=round((geo.CX+side*(geo.WING_FACE_END-geo.CX))*art.S)
            near_tip=round((geo.CX+side*(geo.WING_FACE_END-8.-geo.CX))*art.S)
            self.assertGreater(rails.crop((near_tip,0,near_tip+1,rails.height)).getextrema()[1],0)
            beyond=min(rails.width-1,face_tip+side)
            self.assertEqual(rails.crop((beyond,0,beyond+1,rails.height)).getextrema(),(0,0))

    def test_drs_sweep_uses_and_invalidates_live_wing_geometry(self):
        from halo import drs_motion
        original=dict(geo.STYLE)
        original_end=geo.WING_FACE_END
        previous_side=drs_motion.side_surface('right').tobytes()
        try:
            geo.refresh_style(dict(original,wing_extension=original['wing_extension']+12))
            mat.sync_layout()
            feature_assets.drs_clip_mask.cache_clear()
            feature_assets.drs_rails.cache_clear()
            drs_motion.invalidate()
            self.assertEqual(drs_motion.rail_limits(),
                             (geo.DRS_RAIL_START,geo.WING_FACE_END))
            self.assertAlmostEqual(geo.WING_FACE_END-original_end,12.)
            self.assertAlmostEqual(drs_motion.window_centre(1.)-
                                   drs_motion.window_centre(0.),
                                   geo.WING_FACE_END-geo.DRS_RAIL_START+
                                   2*drs_motion.END_MARGIN+drs_motion.WINDOW_WIDTH)
            self.assertEqual(drs_motion.surface().size,
                             (geo.WIDTH*art.S,geo.HEIGHT*art.S))
            self.assertEqual(drs_motion.side_surface('right').size,
                             (geo.WIDTH*art.S,geo.HEIGHT*art.S))
            self.assertNotEqual(drs_motion.side_surface('right').tobytes(),previous_side)
        finally:
            geo.refresh_style(original)
            mat.sync_layout()
            feature_assets.drs_clip_mask.cache_clear()
            feature_assets.drs_rails.cache_clear()
            drs_motion.invalidate()

    def test_both_dial_drs_crops_reveal_and_sweep_reach_face_tip(self):
        from halo import drs_motion
        registry=json.loads((ROOT/'registry/hud.json').read_text())['hud.element']
        expected=(geo.WING_FACE_END-geo.CX)*geo.HUD_SCALE

        def descendants(items):
            for item in items:
                yield item
                yield from descendants(item.get('children',[]))

        for dial_name in ('glass_dial','glass_dial_26'):
            with self.subTest(dial=dial_name):
                record=registry[dial_name]
                bounds={name:record['sprites'][name]['bounds']
                        for name in ('drs_left','drs_right')}
                self.assertLessEqual(abs(bounds['drs_right'][2]-expected),
                                     geo.HUD_SCALE+1e-4)
                self.assertLessEqual(abs(bounds['drs_left'][0]+expected),
                                     geo.HUD_SCALE+1e-4)
                group=next(item for item in descendants(record['elements'])
                           if item.get('id')=='drs_open')
                elements={item['id']:item for item in descendants(group.get('children',[]))}
                right=elements['drs_right']
                right_half=right['window'][0]/2
                self.assertAlmostEqual(right['path'][0][0]+right_half,
                                       bounds['drs_right'][0],places=5)
                self.assertLessEqual(abs(right['path'][1][0]+right_half-expected),
                                     geo.HUD_SCALE+1e-4)
                left=elements['drs_left']
                left_half=left['window'][0]/2
                self.assertAlmostEqual(left['path'][0][0]-left_half,
                                       bounds['drs_left'][2],places=5)
                self.assertLessEqual(abs(left['path'][1][0]-left_half+expected),
                                     geo.HUD_SCALE+1e-4)
                for side,sign in (('right',1),('left',-1)):
                    sweep=elements['drs_sweep_'+side]
                    for phase,point in zip((0.,1.),sweep['path']):
                        wanted=geo.hud_point(
                            geo.CX+sign*drs_motion.window_centre(phase),0.
                        )[0]
                        self.assertAlmostEqual(point[0],wanted,places=5)
                    face_tip=geo.CX+sign*(geo.WING_FACE_END-geo.CX)
                    sweep_end=geo.CX+sign*drs_motion.window_centre(1.)
                    self.assertGreater(sign*(sweep_end-face_tip),0.)

    def test_active_pedal_masks_keep_slat_interiors_and_clear_gaps(self):
        idle = art._idle_slats_layer().getchannel('A')
        runtime_masks={side:feature_assets.pedal_mask(side).getchannel('A')
                       for side in (-1,1)}
        self.assertEqual(runtime_masks[-1].tobytes(),
                         runtime_masks[1].transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes())
        for side in (-1,1):
            runtime=runtime_masks[side]
            centres=[]
            for index in range(10):
                points=geo.slat_points(side,index)
                x=sum(point[0] for point in points)/len(points)
                y=sum(point[1] for point in points)/len(points)
                px=round((.5+(x-geo.CX)/geo.PEDAL_MASK_SPAN)*runtime.width-.5)
                py=round((.5+(y-geo.CY)/geo.PEDAL_MASK_SPAN)*runtime.height-.5)
                self.assertGreaterEqual(runtime.getpixel((px,py)),250)
                self.assertEqual(idle.getpixel((round(x*art.S),round(y*art.S))),55)
                centres.append((x,y))
            for first,second in zip(centres,centres[1:]):
                x=(first[0]+second[0])/2
                y=(first[1]+second[1])/2
                px=round((.5+(x-geo.CX)/geo.PEDAL_MASK_SPAN)*runtime.width-.5)
                py=round((.5+(y-geo.CY)/geo.PEDAL_MASK_SPAN)*runtime.height-.5)
                # The native UV frame is only 1.64 mask texels per art pixel;
                # its Lanczos footprint can leave a faint antialias fringe.
                # Keep the centre of every inter-slat gap effectively clear.
                self.assertLessEqual(runtime.getpixel((px,py)),16)
                idle_x,idle_y=round(x*art.S),round(y*art.S)
                self.assertEqual(idle.crop((idle_x-1,idle_y-1,
                                            idle_x+2,idle_y+2)).getextrema(),(0,0))

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
