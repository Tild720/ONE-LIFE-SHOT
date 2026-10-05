"""Add the one-shot reserve card to the existing HUD through Unreal Editor.

The gameplay-facing input is ReserveWeaponLabel: EMPTY (or an empty string),
PISTOL, SHOTGUN, SNIPER, or RPG. This script does not implement inventory logic.
The current card, reticle, death cue, dodge state and progress widget stay intact.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

HUD_PATH = '/Game/ThirdPerson/Blueprints/BP_AmmoHUD'
FONT = '/Engine/EngineFonts/RobotoDistanceField.RobotoDistanceField'
HUD_FN = '/Script/Engine.HUD.'
STRING = '/Script/Engine.KismetStringLibrary.'
FUNCTION = 'DrawReserveSlot'
WHITE = '(R=0.94,G=0.93,B=0.88,A=1)'
MUTED = '(R=0.46,G=0.48,B=0.47,A=1)'
BACKGROUND = '(R=0.005,G=0.008,B=0.009,A=0.62)'
# Match the established red, orange, cyan and purple enemy/weapon roles.
ROLE_COLORS = {
    'PISTOL': '(R=0.75,G=0.055,B=0.025,A=1)',
    'SHOTGUN': '(R=1,G=0.32,B=0.02,A=1)',
    'SNIPER': '(R=0.015,G=0.8,B=0.85,A=1)',
    'RPG': '(R=0.55,G=0.04,B=0.8,A=1)',
}


def value(node, name, source):
    if hasattr(source, 'is_valid'):
        link(source, inp(node, name))
    else:
        val(node, name, source)


def number(ed, scalar):
    return out(call(ed, SYS + 'MakeLiteralDouble', Value=scalar))


def arithmetic(ed, operation, a, b):
    node = call(ed, MATH + operation)
    # Connecting the typed scalar first prevents wildcard vector promotion.
    value(node, 'B', b if hasattr(b, 'is_valid') else number(ed, b))
    value(node, 'A', a if hasattr(a, 'is_valid') else number(ed, a))
    return out(node)


def choose(ed, function, condition, yes, no):
    node = call(ed, MATH + function)
    value(node, 'A', yes)
    value(node, 'B', no)
    link(condition, inp(node, 'bPickA'))
    return out(node)


def reserve_function(bp, font_normalization):
    ed = func(bp, FUNCTION)
    graph = BT.get_graph(bp, FUNCTION)
    entry = next(node for node in ed.list_all_nodes()
                 if isinstance(node, unreal.K2Node_FunctionEntry))
    for name in ['CurrentX', 'CurrentY', 'UIScale']:
        if not entry.find_output_pin(name).is_valid():
            BT.add_function_param(graph, name, 'float', True)
    entry = next(node for node in ed.list_all_nodes()
                 if isinstance(node, unreal.K2Node_FunctionEntry))
    scale = out(entry, 'UIScale')

    def units(scalar):
        return arithmetic(ed, 'Multiply_DoubleDouble', scale, scalar)

    def position(base, offset):
        return arithmetic(ed, 'Add_DoubleDouble', base, units(offset))

    # Raise the smaller reserve card slightly beside the larger current slot.
    # The twelve-pixel gap keeps both weapon labels and shot counts unobscured.
    x = position(out(entry, 'CurrentX'), 202)
    y = position(out(entry, 'CurrentY'), -16)

    def rectangle(tail, px, py, w, h, color):
        node = call(ed, HUD_FN + 'DrawRect')
        for key, source in [('ScreenX', px), ('ScreenY', py),
                            ('ScreenW', units(w)), ('ScreenH', units(h)),
                            ('RectColor', color)]:
            value(node, key, source)
        chain(tail, node)
        return node

    def text(tail, label, px, py, size=1.0, color=WHITE):
        node = call(ed, HUD_FN + 'DrawText', Font=FONT, bScalePosition='false')
        for key, source in [('Text', label), ('ScreenX', px), ('ScreenY', py),
                            ('Scale', units(size * font_normalization)),
                            ('TextColor', color)]:
            value(node, key, source)
        chain(tail, node)
        return node

    label = out(get(ed, 'ReserveWeaponLabel'), 'ReserveWeaponLabel')
    tests = {}
    role_ink = MUTED
    for weapon, color in ROLE_COLORS.items():
        test = call(ed, STRING + 'EqualEqual_StrStr', B=weapon)
        link(label, inp(test, 'A'))
        tests[weapon] = out(test)
        role_ink = choose(ed, 'SelectColor', tests[weapon], color, role_ink)
    ready = tests['PISTOL']
    for weapon in ['SHOTGUN', 'SNIPER', 'RPG']:
        either = call(ed, MATH + 'BooleanOR')
        link(ready, inp(either, 'A'))
        link(tests[weapon], inp(either, 'B'))
        ready = out(either)
    weapon_text = choose(ed, 'SelectString', ready, label, 'EMPTY')
    digit = choose(ed, 'SelectString', ready, '1', '-')
    shot = choose(ed, 'SelectString', ready, 'shot', '')
    count_ink = choose(ed, 'SelectColor', ready, WHITE, MUTED)
    cartridge_fill = choose(ed, 'SelectColor', ready, role_ink, BACKGROUND)

    tail = rectangle(entry, x, y, 128, 78, BACKGROUND)
    tail = rectangle(tail, x, y, 128, 2, role_ink)
    tail = text(tail, 'NEXT', position(x, 13), position(y, 9), .7, MUTED)
    tail = text(tail, weapon_text, position(x, 13), position(y, 25), 1.0,
                count_ink)
    tail = text(tail, digit, position(x, 12), position(y, 43), 1.65, count_ink)
    tail = text(tail, shot, position(x, 38), position(y, 55), .8, MUTED)
    bx, by = position(x, 102), position(y, 48)
    tail = rectangle(tail, bx, by, 8, 19, role_ink)
    tail = rectangle(tail, position(bx, 2), position(by, -4), 4, 4, role_ink)
    tail = rectangle(tail, position(bx, -1.5), position(by, 18), 11, 2, role_ink)
    rectangle(tail, position(bx, 2), position(by, 2), 4, 14, cartridge_fill)
    return {'name': FUNCTION, 'card_size': [128, 78], 'offset': [202, -16],
            'inputs': ['CurrentX', 'CurrentY', 'UIScale']}


def only_source(node, pin_name):
    pins = list(inp(node, pin_name).list_connected_pins())
    assert len(pins) == 1, (node.get_name(), pin_name, len(pins))
    return pins[0]


def locate_alive_card(ed):
    """Locate the current card structurally, without assuming generated names."""
    infos = BT.get_node_infos(list(ed.list_all_nodes()))
    candidates = []
    for info in infos:
        condition = info.node.find_input_pin('Condition')
        if condition.is_valid() and any(str(pin.get_pin_name()) == 'Dead'
                                        for pin in condition.list_connected_pins()):
            candidates.append(info.node)
    assert len(candidates) == 1, 'Expected the existing HUD Dead branch'
    alive = out(candidates[0], 'else')
    continuation = list(alive.list_connected_pins())
    assert len(continuation) == 1, 'Expected one alive HUD execution chain'
    first = continuation[0].get_owning_node()
    info = BT.get_node_infos([first])[0]
    hook = first if info.type_id == '|' + FUNCTION else None
    if hook:
        following = list(hook.find_then_pin().list_connected_pins())
        assert len(following) == 1
        first = following[0].get_owning_node()
    assert BT.get_node_infos([first])[0].type_id == 'HUD|DrawRect', \
        'Expected the current slot background after the alive branch'
    assert str(inp(first, 'RectColor').get_pin_value()) == BACKGROUND
    return alive, first, hook


def work():
    bp = unreal.load_asset(HUD_PATH)
    font_asset = unreal.load_asset('/Engine/EngineFonts/RobotoDistanceField')
    assert bp and font_asset, 'Reuse the inspected HUD and engine font'
    glyphs = font_asset.get_editor_property('characters')
    font_height = float(glyphs[ord('1')].get_editor_property('v_size'))
    assert font_height > 0
    public_names = ['AmmoLabel', 'WeaponLabel', 'StatusLabel', 'HUDMargin']
    before = {name: str(unreal.get_default_object(bp.generated_class())
                        .get_editor_property(name)) for name in public_names}
    names = {str(name) for name in
             unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)}
    if 'ReserveWeaponLabel' not in names:
        var(bp, 'ReserveWeaponLabel', 'string', 'EMPTY')

    # Rebuild only this script's helper; never replace the live HUD EventGraph.
    layout = reserve_function(bp, 16.0 / font_height)
    compile_blueprint(bp, True)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'EventGraph')
    original_nodes = {node.get_name() for node in ed.list_all_nodes()}
    alive, card, hook = locate_alive_card(ed)
    current_x = only_source(card, 'ScreenX')
    current_y = only_source(card, 'ScreenY')
    width_scale = only_source(card, 'ScreenW').get_owning_node()
    # The native inspection confirmed ScreenW = UIScale * literal 190.
    width_literal = only_source(width_scale, 'B').get_owning_node()
    assert float(inp(width_literal, 'Value').get_pin_value()) == 190.0, \
        'Current-slot dimensions changed; inspect before authoring'
    ui_scale = only_source(width_scale, 'A')
    created = hook is None
    if created:
        hook = call(ed, bp.generated_class().get_path_name() + ':' + FUNCTION)
        alive.break_pin_links()
        link(alive, hook.find_execute_pin())
        chain(hook, card)
    for name, source in [('CurrentX', current_x), ('CurrentY', current_y),
                         ('UIScale', ui_scale)]:
        target = inp(hook, name)
        target.break_pin_links()
        link(source, target)

    assert original_nodes.issubset({node.get_name() for node in ed.list_all_nodes()})
    compile_blueprint(bp, True)
    after = {name: str(unreal.get_default_object(bp.generated_class())
                       .get_editor_property(name)) for name in public_names}
    assert before == after, {'before': before, 'after': after}
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    return {'asset': bp.get_path_name(), 'saved': True,
            'public_inputs_preserved': after,
            'reserve_input': 'ReserveWeaponLabel: EMPTY, PISTOL, SHOTGUN, SNIPER, RPG',
            'helper': layout, 'new_draw_call': created,
            'existing_event_nodes_preserved': len(original_nodes),
            'font': FONT, 'native_digit_height': font_height,
            'preserved': ['Current slot', 'Reticle', 'Death cue', 'Dodge cooldown',
                          'WBP_RunnerProgress'],
            'verification': 'PIE: empty reserve, four roles, queue promotion, death, and UI scale'}


if __name__ == '__main__':
    run_editor(work, 'WeaponQueueHUDPolish.json')
