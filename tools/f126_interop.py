"""Straight Mode effects and separate 2026 Overtake/Boost diagnostics.

Bindings are taken from the installed dial_om_xm template. The game owns
zone distance, availability and Overtake eligibility. No lap/gap rules are copied.
"""
import copy
import uuid
from formats import pkg, idf, uinode as N, uiops as U
from halo import layout, drs_motion
from halo.tuning import rgb
from halo.f126 import BOOST_STATES
from native_interop import walk, soft_mask, text_opacity, remove_signals


def straight_mode(archive, reference, scene, dial_child, controls, ctx):
    prefix = ctx.path + '.' + ctx.prefix + '_ctl.'
    root = scene.scenes[0].root
    removed = prefix + 'v_drs_open'
    controls.items[N.CHILDREN].items = [n for n in N.children(controls)
                                         if N.name(n) != 'v_drs_open']
    remove_signals(dial_child, [removed])
    controls.items[N.CHILDREN].items.append(U.hidden('sm_open',ctx.prefix+'_drs_open'))

    reveal = [N.child(controls,f'x_drs_{side}_{part}')
              for side in ('left','right') for part in ('win','ctr')]
    sweep = [N.child(controls,f'x_drs_sweep_{side}_{part}')
             for side in ('left','right') for part in ('win','ctr')]
    for channel in reveal+sweep:
        N.drop_key(channel.items[N.PROPS],'fraction')
    for side in ('left','right'):
        soft_mask(archive,reference,scene,ctx.prefix+'_drs_sweep_'+side+'_win',
            'eaid://ui_package/art/osd/textures/hud/'+ctx.prefix+'_drs_sweep_'+side+'_mask.tif')

    def animation(channels,pin,event,value,curve=None):
        attrs={'value':float(value)}
        if curve:
            attrs['curveName']=N.djb2(curve)
        return [U.sig(prefix+N.name(c),pin,event,attrs) for c in channels]

    def actor(name,target,start,value,curve,events=()):
        return U.node(name,'UIMO',props=[
            ('ParameterName',U.prop('stri','Alpha')),
            ('Value',U.prop('fp32',value)),('StartingValue',U.prop('fp32',start)),
            ('Cascade',U.prop('bool',True)),
            ('BlendType',U.prop('stri','Multiplicative')),
            ('AnimationCurve',U.prop('stri',curve)),
        ],layout=(ctx.prefix+'_'+target,),events=events,
           behav=('NBEL','NBMG','NBOS','NBXA'))

    def deactivate(event):
        return [U.sig(prefix+name,'deactivateOverride',event)
                for name in ('sm_enter','sm_leave','sm_pulse_up','sm_pulse_down')]

    def stop_motion(event):
        return [U.sig(prefix+name,'stop',event)
                for name in ('sm_sweep_timer','sm_opening_timer','sm_close_timer')]

    def close(event):
        return (stop_motion(event)+deactivate(event)+
            [U.sig(prefix+'sm_leave','activateOverride',event),
             U.sig(prefix+'sm_close_timer','reset',event,{'duration':layout.DRS_CLOSE_DURATION})]+
            animation(reveal,'playToFraction',event,0.,layout.DRS_CLOSE_CURVE)+
            animation(sweep,'goToFraction',event,0.))

    def opened(event):
        return (stop_motion(event)+deactivate(event)+
            [U.sig(prefix+'sm_open','show',event),
             U.sig(prefix+'sm_enter','activateOverride',event),
             U.sig(prefix+'sm_opening_timer','reset',event,{'duration':layout.DRS_OPEN_DURATION})]+
            animation(reveal,'goToFraction',event,0.)+
            animation(reveal,'playToFraction',event,1.,layout.DRS_OPEN_CURVE))

    enter=actor('sm_enter','drs_open',0.,1.,layout.DRS_OPEN_CURVE,[U.event('overrideComplete',[
        U.sig(prefix+'sm_enter','deactivateOverride','overrideComplete'),
        U.sig(prefix+'sm_pulse_down','activateOverride','overrideComplete')])])
    leave=actor('sm_leave','drs_open_label_n',1.,0.,layout.DRS_CLOSE_CURVE)
    pulses=[]
    for name,other,start,end in (('sm_pulse_down','sm_pulse_up',1.,.74),
                                  ('sm_pulse_up','sm_pulse_down',.74,1.)):
        pulses.append(actor(name,'drs_pulse',start,end,'dial_drs_pulse_ready',[
            U.event('overrideComplete',[U.sig(prefix+name,'deactivateOverride','overrideComplete'),
                                       U.sig(prefix+other,'activateOverride','overrideComplete')])]))
    active=U.node('sm_active','SVCD',props=[('value',U.prop('bool',True)),
                    ('dbEntry',U.prop('stri','is_xm_active'))],events=[
                    U.event('yes',opened('yes')),U.event('no',close('no'))])
    cycle=(animation(sweep,'goToFraction','yes',0.)+
           animation(sweep,'playToFraction','yes',1.,drs_motion.CURVE)+
           [U.sig(prefix+'sm_sweep_timer','reset','yes',{'duration':drs_motion.PERIOD})])
    cycle_gate=U.node('sm_sweep_gate','SVCD',props=[('value',U.prop('bool',True)),
                    ('dbEntry',U.prop('stri','is_xm_active'))],events=[
                    U.event('yes',cycle),U.event('no',stop_motion('no'))])
    close_gate=U.node('sm_close_gate','SVCD',props=[('value',U.prop('bool',True)),
                    ('dbEntry',U.prop('stri','is_xm_active'))],events=[
                    U.event('no',[U.sig(prefix+'sm_open','hide','no')])])
    timers=[]
    for name,gate in (('sm_opening_timer','sm_sweep_gate'),('sm_sweep_timer','sm_sweep_gate'),
                       ('sm_close_timer','sm_close_gate')):
        timers.append(U.node(name,'TIME',props=[('enabled',U.prop('bool',False)),
            ('visible',U.prop('bool',False))],events=[U.event('time_out_expired',[
                U.sig(prefix+gate,'query','time_out_expired')])]))
    controls.items[N.CHILDREN].items.extend([active,cycle_gate,close_gate,enter,leave,*pulses,*timers])

    # Preserve the native enum decision, including its exact event names and type.
    stock=next(n for n in walk(dial_child)
        if n.items[N.PROPS].get('dbEntry') is not None
        and n.items[N.PROPS]['dbEntry']['value'].value=='ers_overtake_state')
    boost=copy.deepcopy(stock)
    boost.items[N.PROPS]['name'].value='boost_state'
    boost.items[N.COMMANDS].items=[]
    boost.items[N.CHILDREN].items=[]
    boost.items[N.LAYOUT].items=[]
    boost.items[N.EVENTS].items=[]
    for state in BOOST_STATES:
        gate='boost_'+state
        controls.items[N.CHILDREN].items.append(U.hidden(gate,ctx.prefix+'_'+gate))
        boost.items[N.EVENTS].items.append(U.event(state,[
            U.sig(prefix+'boost_'+other,'show' if other==state else 'hide',state)
            for other in BOOST_STATES]))
    controls.items[N.CHILDREN].items.append(boost)

    # Crisp native text with a restrained four-sample glow around SM OPEN.
    label=N.child(controls,'t_drs_open_label')
    text_colour = rgb(layout.STYLE['text_colour']) if layout.STYLE['text_colour'] != '#ffffff' else (154,247,199)
    label.items[N.PROPS].set('colourOverride',U.prop('rgba','#'+''.join(f'{v:02x}' for v in text_colour)+( 'ff' if len(text_colour)==3 else '')))
    glyph=root.find(ctx.prefix+'_drs_open_label').obj
    parent=root.find(ctx.prefix+'_drs_open_label_n').obj
    pixel=layout.HUD_SCALE*.018/parent['scale'].value[0]
    for index,(x,y) in enumerate(((-.7,0.),(.7,0.),(0.,-.7),(0.,.7))):
        name=ctx.prefix+'_sm_open_glow_'+str(index)
        glow=copy.deepcopy(glyph)
        glow['name'].value=name
        idf.set_param(glow,'guid',str(uuid.uuid5(uuid.NAMESPACE_URL,'halo-v2/'+name)))
        glow.set('position',pkg.Val('vec3',[x*pixel*layout.STYLE['text_glow'],y*pixel*layout.STYLE['text_glow'],0.,0.]))
        idf.set_param(glow,'eLayer.layer',39,'si32')
        parent['children'].items.insert(0,glow)
        binding=copy.deepcopy(label)
        binding.items[N.PROPS]['name'].value='sm_open_glow_'+str(index)
        binding.items[N.LAYOUT]=U.layout_path(name)
        controls.items[N.CHILDREN].items.append(binding)
        text_opacity(controls,dial_child,binding,'sm_glow_alpha_'+str(index),name,
                     8/255.*layout.STYLE['text_glow_strength']/100.,ctx=ctx)
    for name in ('sm_distance_caption','sm_distance_value','sm_button','sm_keyboard','sm_prompt_caption'):
        colour = rgb(layout.STYLE['text_colour']) if layout.STYLE['text_colour'] != '#ffffff' else layout.DRS_PROMPT_COLOUR
        N.child(controls,'t_'+name).items[N.PROPS].set('colourOverride',U.prop('rgba','#'+''.join(f'{v:02x}' for v in colour)))
    if layout.STYLE['text_colour'] != '#ffffff':
        colour = '#' + layout.STYLE['text_colour'][1:] + 'ff'
        for name in ('overtake_on', 'overtake_off', *(f'boost_text_{state}' for state in BOOST_STATES)):
            N.child(controls, 't_' + name).items[N.PROPS].set('colourOverride', U.prop('rgba', colour))
    idf.set_param(root.find(ctx.prefix+'_sm_button').obj,'style','icons_tool_tips')
    N.child(controls,'t_sm_keyboard').items[N.PROPS].set('localise',
        U.prop('bool',False,'x_mode_overtake_tooltip_localise'))

    # Composer path bindings are absolute (#). These verified stock fields are
    # local to the dial VM context, so preserve the stock unqualified scope.
    for name,prop,field in (
        ('t_sm_distance_value','text','distance_to_xm'),
        ('v_sm_distance','visible','show_xm_distance'),
        ('v_sm_available','visible','is_xm_available'),
        ('v_sm_ready','visible','x_mode_show_tooltip'),
        ('t_sm_button','text','x_mode_overtake_tooltip_icon_path'),
        ('t_sm_keyboard','text','x_mode_overtake_tooltip_text'),
    ):
        N.child(controls,name).items[N.PROPS][prop]['dbentry'].value=field

    # Both decisions register once per context and query immediately on entry.
    for command in dial_child.items[N.COMMANDS].items:
        event=command['commandName'].value
        if event in ('command_vmContextValid','use_dial','show'):
            command['signals'].items.extend([U.sig(prefix+name,pin,event)
                for name in ('sm_active','boost_state') for pin in ('register','query')])
        elif event in ('hide','disable'):
            command['signals'].items.extend(stop_motion(event)+deactivate(event)+[
                U.sig(prefix+name,'unregister',event) for name in ('sm_active','boost_state')]+[
                U.sig(prefix+'sm_open','hide',event)])
    return {'selector':'is_xm_active','availability':'x_mode_show_tooltip',
            'distance':'distance_to_xm','distance_visible':'show_xm_distance',
            'eligibility':'native game rules','opening_seconds':layout.DRS_OPEN_DURATION,
            'closing_seconds':layout.DRS_CLOSE_DURATION,'overtake':'om_active',
            'boost':'ers_overtake_state','boost_events':list(BOOST_STATES),
            'temporary_status':True,'rail_colour':'existing green'}
