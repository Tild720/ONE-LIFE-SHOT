"""Editor-managed presentation pass for the existing one-shot HUD.

AmmoLabel, WeaponLabel and StatusLabel remain the gameplay-facing inputs.
This script changes presentation only: no inventory, weapon or dodge logic.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

HUD_PATH = '/Game/ThirdPerson/Blueprints/BP_AmmoHUD'
CHAR_PATH = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter'
# Verified in Engine/Content/EngineFonts and in the editor's QAFonts report.
FONT = '/Engine/EngineFonts/RobotoDistanceField.RobotoDistanceField'
HUD_FN = '/Script/Engine.HUD.'
STRING = '/Script/Engine.KismetStringLibrary.'
WHITE = '(R=0.94,G=0.93,B=0.88,A=1)'
MUTED = '(R=0.46,G=0.48,B=0.47,A=1)'
AMBER = '(R=1,G=0.48,B=0.12,A=1)'
BACKGROUND = '(R=0.005,G=0.008,B=0.009,A=0.62)'


def value(node, name, source):
    if hasattr(source, 'is_valid'):
        link(source, inp(node, name))
    else:
        val(node, name, source)


def number(ed, value):
    return out(call(ed, SYS + 'MakeLiteralDouble', Value=value))


def arithmetic(ed, operation, a, b):
    node = call(ed, MATH + operation)
    # Connect explicit scalar pins before wildcard arithmetic can promote.
    value(node, 'B', b if hasattr(b, 'is_valid') else number(ed, b))
    value(node, 'A', a if hasattr(a, 'is_valid') else number(ed, a))
    return out(node)


def choose_string(ed, condition, yes, no):
    node = call(ed, MATH + 'SelectString')
    value(node, 'A', yes)
    value(node, 'B', no)
    link(condition, inp(node, 'bPickA'))
    return out(node)


def choose_color(ed, condition, yes, no):
    node = call(ed, MATH + 'SelectColor', A=yes, B=no)
    link(condition, inp(node, 'bPickA'))
    return out(node)


def equal_string(ed, source, literal):
    node = call(ed, STRING + 'EqualEqual_StrStr', B=literal)
    link(source, inp(node, 'A'))
    return out(node)


def cast_output(node):
    info = BT.get_node_infos([node])[0]
    return out(node, next(pin.name for pin in info.output_pins
                         if pin.name.startswith('As')))


def author_canvas():
    bp = unreal.load_asset(HUD_PATH)
    character = unreal.load_asset(CHAR_PATH)
    font_asset = unreal.load_asset('/Engine/EngineFonts/RobotoDistanceField')
    assert bp and character and font_asset
    glyphs = font_asset.get_editor_property('characters')
    assert len(glyphs) > ord('1'), 'Distance-field font must contain the one-shot digit'
    font_height = float(glyphs[ord('1')].get_editor_property('v_size'))
    assert font_height > 0
    # Canvas uses this offline font's native 26-pixel glyphs. Normalize our
    # authored type scale to a 16-pixel base instead of enlarging a 10px atlas.
    font_normalization = 16.0 / font_height
    before = {name: str(unreal.get_default_object(bp.generated_class()).get_editor_property(name))
              for name in ['AmmoLabel', 'WeaponLabel', 'StatusLabel']}
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'EventGraph')
    infos = BT.get_node_infos(list(ed.list_all_nodes()))
    events = [info for info in infos if isinstance(info.node, unreal.K2Node_Event)]
    draw = next(info.node for info in events if
                {'SizeX', 'SizeY'}.issubset({pin.name for pin in info.output_pins}))
    # Preserve event entries. Abort if the HUD gained unrelated event behavior.
    for info in events:
        if info.node != draw:
            assert not info.node.find_then_pin().list_connected_pins(), \
                'Unexpected HUD event logic: ' + info.node.get_name()
    ed.remove_nodes([info.node for info in infos
                     if not isinstance(info.node, unreal.K2Node_Event)])
    draw.find_then_pin().break_pin_links()

    height = out(draw, 'SizeY')
    width = out(draw, 'SizeX')
    factor = arithmetic(ed, 'Divide_DoubleDouble', height, 900.0)
    bounded = call(ed, MATH + 'FClamp', Min=0.7, Max=1.35)
    link(factor, inp(bounded, 'Value'))
    ui_scale = out(bounded)

    def units(value):
        return arithmetic(ed, 'Multiply_DoubleDouble', ui_scale, value)

    safe_margin = call(ed, MATH + 'FClamp', Min=12, Max=96)
    link(out(get(ed, 'HUDMargin'), 'HUDMargin'), inp(safe_margin, 'Value'))
    margin = arithmetic(ed, 'Multiply_DoubleDouble', ui_scale, out(safe_margin))
    inset = arithmetic(ed, 'Add_DoubleDouble', margin, units(110))
    bottom = arithmetic(ed, 'Subtract_DoubleDouble', height, inset)

    def position(base, offset):
        return arithmetic(ed, 'Add_DoubleDouble', base, units(offset))

    def rectangle(tail, x, y, w, h, color):
        node = call(ed, HUD_FN + 'DrawRect')
        for key, source in [('ScreenX', x), ('ScreenY', y),
                            ('ScreenW', units(w)), ('ScreenH', units(h)),
                            ('RectColor', color)]:
            value(node, key, source)
        chain(tail, node)
        return node

    def text(tail, label, x, y, scale=1.0, color=WHITE):
        node = call(ed, HUD_FN + 'DrawText', Font=FONT, bScalePosition='false')
        for key, source in [('Text', label), ('ScreenX', x), ('ScreenY', y),
                            ('Scale', units(scale * font_normalization)), ('TextColor', color)]:
            value(node, key, source)
        chain(tail, node)
        return node

    pawn = call(ed, GAME + 'GetPlayerPawn', PlayerIndex=0)
    cast = ed.create_node_from_name('Utilities|Casting|CastToBP_ThirdPersonCharacter',
                                   unreal.Vector2D(), [])
    assert cast
    link(out(pawn), inp(cast, 'Object'))
    chain(draw, cast)
    player = cast_output(cast)
    cls = character.generated_class().get_path_name()
    dead = get(ed, 'Dead', cls)
    link(player, inp(dead, 'self'))
    death = branch(ed, out(dead, 'Dead'))
    chain(cast, death)

    # A single prominent digit conveys the only available shot. No clip count.
    loaded = equal_string(ed, out(get(ed, 'AmmoLabel'), 'AmmoLabel'), '1/1')
    ink = choose_color(ed, loaded, WHITE, AMBER)
    digit = choose_string(ed, loaded, '1', '0')
    shot = choose_string(ed, loaded, 'shot', 'spent')
    hint = choose_string(ed, loaded, 'Left click  Fire', 'Bait a charge')
    weapon_input = out(get(ed, 'WeaponLabel'), 'WeaponLabel')
    weapon = choose_string(ed, equal_string(ed, weapon_input, 'NO WEAPON'),
                           'No weapon', weapon_input)
    normal = rectangle(death, margin, bottom, 190, 110, BACKGROUND)
    # Route the card only through the alive branch; dead has a separate cue.
    inp(normal, 'execute').break_pin_links()
    link(out(death, 'else'), normal.find_execute_pin())
    normal = text(normal, weapon, position(margin, 48), position(bottom, 10), 1.25)
    normal = text(normal, digit, position(margin, 45), position(bottom, 29), 3.15, ink)
    normal = text(normal, shot, position(margin, 100), position(bottom, 58), 0.9, ink)
    normal = text(normal, hint, position(margin, 48), position(bottom, 88), 0.9, MUTED)

    # One cartridge, filled when loaded and an empty silhouette after firing.
    bx = position(margin, 19)
    by = position(bottom, 49)
    normal = rectangle(normal, bx, by, 12, 28, ink)
    normal = rectangle(normal, position(bx, 3), position(by, -5), 6, 5, ink)
    normal = rectangle(normal, position(bx, -2), position(by, 27), 16, 3, ink)
    empty = branch(ed, loaded)
    chain(normal, empty)
    hollow = rectangle(empty, position(bx, 2), position(by, 2), 8, 23, BACKGROUND)
    inp(hollow, 'execute').break_pin_links()
    link(out(empty, 'else'), hollow.find_execute_pin())

    # Show the existing dodge's real cooldown; no new timers or input actions.
    cooling = get(ed, 'DodgeCooling', cls)
    link(player, inp(cooling, 'self'))
    dodge_ink = choose_color(ed, out(cooling, 'DodgeCooling'), MUTED, WHITE)
    dodge_label = choose_string(ed, out(cooling, 'DodgeCooling'), 'Recovering', 'Evade')
    right_x = arithmetic(ed, 'Subtract_DoubleDouble', width,
                         arithmetic(ed, 'Add_DoubleDouble', margin, units(188)))
    right_y = arithmetic(ed, 'Subtract_DoubleDouble', height,
                         arithmetic(ed, 'Add_DoubleDouble', margin, units(31)))
    key = rectangle(empty, right_x, right_y, 48, 23, BACKGROUND)
    chain(hollow, key)
    key = text(key, 'Space', position(right_x, 6), position(right_y, 3), 0.9, MUTED)
    key = text(key, dodge_label, position(right_x, 60), position(right_y, 2), 1.0, dodge_ink)

    # Mouse aiming is the core input. GetMousePosition returns raw viewport
    # pixels, the same coordinates as Canvas; do not apply UMG DPI conversion.
    owner_pc = call(ed, HUD_FN + 'GetOwningPlayerController')
    pointer = call(ed, '/Script/Engine.PlayerController.GetMousePosition')
    link(out(owner_pc), inp(pointer, 'self'))
    pointer_valid = branch(ed, out(pointer))
    chain(key, pointer_valid)
    cursor_x, cursor_y = out(pointer, 'LocationX'), out(pointer, 'LocationY')
    opening = call(ed, MATH + 'SelectFloat', A=3, B=5)
    link(loaded, inp(opening, 'bPickA'))
    gap = arithmetic(ed, 'Multiply_DoubleDouble', ui_scale, out(opening))
    reach = arithmetic(ed, 'Add_DoubleDouble', gap, units(5))
    left_x = arithmetic(ed, 'Subtract_DoubleDouble', cursor_x, reach)
    right_x = arithmetic(ed, 'Add_DoubleDouble', cursor_x, gap)
    top_y = arithmetic(ed, 'Subtract_DoubleDouble', cursor_y, reach)
    bottom_y = arithmetic(ed, 'Add_DoubleDouble', cursor_y, gap)
    horizontal_y = position(cursor_y, -.5)
    vertical_x = position(cursor_x, -.5)
    shadow = '(R=0.002,G=0.003,B=0.003,A=0.9)'
    reticle = pointer_valid
    for x, y, w, h in [(left_x, horizontal_y, 5, 1),
                        (right_x, horizontal_y, 5, 1),
                        (vertical_x, top_y, 1, 5),
                        (vertical_x, bottom_y, 1, 5)]:
        reticle = rectangle(reticle, position(x, -1), position(y, -1), w + 2, h + 2, shadow)
        reticle = rectangle(reticle, x, y, w, h, ink)
    live_dot = branch(ed, loaded)
    chain(reticle, live_dot)
    rectangle(live_dot, position(cursor_x, -1), position(cursor_y, -1), 2, 2, ink)

    # The existing FailRun/restart owns timing and camera fading.
    center_x = arithmetic(ed, 'Multiply_DoubleDouble', width, 0.5)
    center_y = arithmetic(ed, 'Multiply_DoubleDouble', height, 0.42)
    cue = text(death, 'Run ended', position(center_x, -86), center_y, 1.8, WHITE)
    cue = text(cue, 'Restarting', position(center_x, -43), position(center_y, 48), 0.9, MUTED)

    compile_blueprint(bp, True)
    after = {name: str(unreal.get_default_object(bp.generated_class()).get_editor_property(name))
             for name in before}
    assert before == after, {'before': before, 'after': after}
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    return {'asset': bp.get_path_name(), 'public_inputs_preserved': after,
            'canvas_layout': 'Bottom-left shot/weapon, bottom-right real dodge state',
            'crosshair': 'Raw mouse viewport position; white compact loaded, amber open spent, hidden while dead',
            'typography': {'font': FONT, 'native_digit_height': font_height,
                           'normalized_base_height': 16, 'card_width': 190},
            'scale': 'Height / 900 clamped to 0.7–1.35'}


def work():
    return {'canvas': author_canvas(), 'progress': author_progress()}


def author_progress():
    """Restyle the existing widget; its source manager and lifetime stay intact."""
    path = '/Game/UI/WBP_RunnerProgress'
    bp = unreal.load_asset(path)
    assert bp
    tool_class = unreal.load_class(None, '/Script/UMGToolSet.UMGToolSet')
    assert tool_class
    tree_info = unreal.get_default_object(tool_class).call_method('GetWidgets', args=(bp,))
    widgets = {str(info.get_editor_property('widget_name')): info.get_editor_property('widget')
               for info in tree_info.get_editor_property('widgets')}
    required = {'Root', 'PanelBackground', 'Title', 'TrackProgress', 'RunnerIcon',
                'Head', 'PercentText', 'Body', 'Visor', 'ArmFront', 'ArmBack',
                'LegFront', 'LegBack', 'FinishPole'}
    required.update('Checkpoint' + str(index) for index in range(5))
    required.update('Flag' + str(index) for index in range(6))
    assert required.issubset(widgets), sorted(required - set(widgets))

    def color(r, g, b, a=1):
        return unreal.LinearColor(r, g, b, a)

    def slot(name, x, y, width, height):
        existing = widgets[name].get_editor_property('slot')
        assert isinstance(existing, unreal.CanvasPanelSlot), name
        existing.set_position(unreal.Vector2D(x, y))
        existing.set_size(unreal.Vector2D(width, height))

    def tint_struct(existing, ink):
        existing.set_editor_property('specified_color', ink)
        return existing

    def solid_brush(existing, ink):
        existing.set_editor_property('draw_as', unreal.SlateBrushDrawType.BOX)
        existing.set_editor_property('resource_object', None)
        existing.set_editor_property('margin', unreal.Margin(0, 0, 0, 0))
        tint = existing.get_editor_property('tint_color')
        existing.set_editor_property('tint_color', tint_struct(tint, ink))
        return existing

    def font(name, size, weight='Regular'):
        widget = widgets[name]
        current = widget.get_editor_property('font')
        current.set_editor_property('size', size)
        current.set_editor_property('typeface_font_name', weight)
        current.set_editor_property('letter_spacing', 0)
        widget.set_font(current)
        ink = widget.get_editor_property('color_and_opacity')
        widget.set_color_and_opacity(tint_struct(ink, color(.78, .8, .77)))

    # Keep all names referenced by Blueprint graphs. Remove visual clutter only.
    hidden = ['PanelBackground', 'Body', 'Visor', 'ArmFront', 'ArmBack',
              'LegFront', 'LegBack', 'FinishPole'] + ['Flag' + str(index) for index in range(6)]
    for name in hidden:
        widgets[name].set_visibility(unreal.SlateVisibility.COLLAPSED)
    widgets['Root'].set_visibility(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    widgets['Title'].set_text('Escape route')
    font('Title', 14)
    font('PercentText', 14)
    slot('Title', -160, 26, 180, 20)
    slot('PercentText', 106, 25, 54, 20)
    slot('TrackProgress', -160, 50, 320, 3)
    bar = widgets['TrackProgress']
    style = bar.get_editor_property('widget_style')
    for brush_name, ink in [('background_image', color(.065, .075, .075, .86)),
                            ('fill_image', color(.8, .82, .77))]:
        brush = style.get_editor_property(brush_name)
        style.set_editor_property(brush_name, solid_brush(brush, ink))
    # UE 5.8's style/padding setters are C++ accessors without UFUNCTION.
    # Use the reflected editor properties for these two template settings.
    bar.set_editor_property('widget_style', style)
    bar.set_fill_color_and_opacity(color(1, 1, 1))
    bar.set_editor_property('border_padding', unreal.Vector2D(0, 0))

    # Existing Head becomes a clean position marker instead of a stick figure.
    slot('RunnerIcon', -163, 47, 6, 9)
    slot('Head', 0, 0, 6, 9)
    head = widgets['Head']
    head.set_brush(solid_brush(head.get_editor_property('brush'), color(1, .48, .12)))
    for index in range(5):
        name = 'Checkpoint' + str(index)
        slot(name, -160.75 + index * 80, 47, 1.5, 9)
        marker = widgets[name]
        marker.set_brush(solid_brush(marker.get_editor_property('brush'), color(.22, .25, .24)))

    # Progress still interpolates from the real manager. Match its visual travel
    # to the shorter rail and end the obsolete hidden-limb animation chain.
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'UpdateHUD')
    nodes = {node.get_name(): node for node in ed.list_all_nodes()}
    travel = nodes['K2Node_CallFunction_11']
    assert str(inp(travel, 'Value').get_pin_value()) in ['544.0', '544', '320.0', '320']
    val(travel, 'Value', 320.0)
    val(nodes['K2Node_CallFunction_12'], 'Value', 0.0)
    nodes['K2Node_CallFunction_14'].find_then_pin().break_pin_links()
    compile_blueprint(bp, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    return {'asset': bp.get_path_name(), 'rail_width': 320,
            'visuals': 'Thin neutral rail, amber marker, percentage; no oversized panel or stick figure',
            'preserved': 'Widget names, progress source, smoothing, hit-test invisibility and construct/destruct timer'}


run_editor(work, 'CombatUIPolish.json')
