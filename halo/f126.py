"""2026 native state bindings on the shared Halo artwork."""
import copy
from . import layout as geo
from .dials import F126

BOOST_STATES = {
    'eAvailable': 'BOOST READY',
    'eActive': 'BOOST ACTIVE',
    'eUnavailable': 'BOOST UNAVAILABLE',
    'eInvalid': 'BOOST --',
    'eHidden': 'BOOST --',
}

def record_for_2026(shared):
    record = copy.deepcopy(shared)
    record.update(prefix=F126.prefix, dial=F126.dial)
    opened = next(e for e in record['elements'] if e['id'] == 'drs_open')
    opened['visible'] = {'game': 'is_xm_active'}
    label = opened['children'][0]['children'][0]['children'][-1]
    assert label['id'] == 'drs_open_label'
    label['literal'] = 'SM OPEN'

    def text(name, literal=None, value=None, size=17.5, style='OSD_24_bold'):
        result = {'kind':'text', 'id':name, 'style':style, 'align':'centre',
                  'cap_height':round(size*.672*geo.HUD_SCALE,6), 'layer':27}
        result['literal' if literal is not None else 'value'] = literal if literal is not None else value
        return result

    def row(name, children, visible):
        return {'kind':'centre', 'id':name, 'at':geo.hud_point(*geo.DRS_CENTRE),
                'visible':visible, 'children':[{'kind':'stack', 'id':name+'_row',
                'dir':'right', 'gap':geo.DRS_DISTANCE_GAP*geo.HUD_SCALE,
                'children':children}]}

    record['elements'].append(row('sm_distance', [text('sm_distance_caption','SM'),
        text('sm_distance_value',value={'path':'distance_to_xm','ty':'text'})],
        {'path':'show_xm_distance','ty':'bool'}))
    # The native tooltip glyph and keyboard caption remain game supplied.
    ready = row('sm_ready', [
        text('sm_button',value={'path':'x_mode_overtake_tooltip_icon_path','ty':'text'},
             style='OSD_24_bold'),
        text('sm_keyboard',value={'path':'x_mode_overtake_tooltip_text','ty':'text'}),
        text('sm_prompt_caption','SM')], {'path':'x_mode_show_tooltip','ty':'bool'})
    record['elements'].append({'kind':'group','id':'sm_prompt_closed',
        'visible':{'game':'is_xm_active','not':True}, 'children':[
            {'kind':'group','id':'sm_available',
             'visible':{'path':'is_xm_available','ty':'bool'},'children':[ready]}]})

    # Temporary, intentionally compact state checks in the unused inner left wing.
    x=335.
    for active in (False,True):
        item=text('overtake_'+('on' if active else 'off'),
                  'OVERTAKE ON' if active else 'OVERTAKE OFF',size=13.)
        item.update(at=geo.hud_point(x,geo.top(x)+50.),rot=-16.,
                    visible={'game':'om_active','not':not active})
        record['elements'].append(item)
    for state,caption in BOOST_STATES.items():
        item=text('boost_text_'+state,caption,size=13.)
        record['elements'].append({'kind':'group','id':'boost_'+state,
            'at':geo.hud_point(x,geo.top(x)+76.),'rot':-16.,'children':[item]})
    return record
