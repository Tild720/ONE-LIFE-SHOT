"""Editor-only short dodge and readable weapon/empty-state HUD."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    bp = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')
    ed = func(bp, 'TryDodge')
    dead = get(ed, 'Dead'); cooling = get(ed, 'DodgeCooling')
    busy = call(ed, MATH+'BooleanOR')
    link(out(dead, 'Dead'), inp(busy, 'A')); link(out(cooling, 'DodgeCooling'), inp(busy, 'B'))
    ready = call(ed, MATH+'Not_PreBool'); link(out(busy), inp(ready, 'A'))
    gate = branch(ed, out(ready)); link(ed.find_graph_entry_pin(), gate.find_execute_pin())
    dodging = setv(ed, 'Dodging', 'true'); chain(gate, dodging)
    cooldown = setv(ed, 'DodgeCooling', 'true'); chain(dodging, cooldown)
    last = call(ed, '/Script/Engine.Pawn.GetLastMovementInputVector')
    length = call(ed, MATH+'VSizeSquared'); link(out(last), inp(length, 'A'))
    active = call(ed, MATH+'Greater_DoubleDouble', B=0.01); link(out(length), inp(active, 'A'))
    forward = call(ed, ACT+'GetActorForwardVector')
    select = call(ed, MATH+'SelectVector')
    link(out(last), inp(select, 'A')); link(out(forward), inp(select, 'B')); link(out(active), inp(select, 'bPickA'))
    normal = call(ed, MATH+'Vector_Normal2D'); link(out(select), inp(normal, 'A'))
    speed = get(ed, 'DodgeSpeed')
    velocity = call(ed, MATH+'Multiply_VectorFloat')
    link(out(normal), inp(velocity, 'A')); link(out(speed, 'DodgeSpeed'), inp(velocity, 'B'))
    launch = call(ed, '/Script/Engine.Character.LaunchCharacter', bXYOverride='true', bZOverride='false')
    link(out(velocity), inp(launch, 'LaunchVelocity')); chain(cooldown, launch)
    duration = get(ed, 'DodgeDuration'); bounded = call(ed, MATH+'FClamp', Min=0.08, Max=0.3)
    link(out(duration, 'DodgeDuration'), inp(bounded, 'Value'))
    end = timer(ed, 'EndDodge', out(bounded)); chain(launch, end)
    delay = get(ed, 'DodgeCooldown'); bound_delay = call(ed, MATH+'FClamp', Min=0.4, Max=3.0)
    link(out(delay, 'DodgeCooldown'), inp(bound_delay, 'Value'))
    reset = timer(ed, 'DodgeReady', out(bound_delay)); chain(end, reset)
    compile_blueprint(bp, True)
    end_ed = func(bp, 'EndDodge')
    end_flag = setv(end_ed, 'Dodging', 'false'); link(end_ed.find_graph_entry_pin(), end_flag.find_execute_pin())
    move = get(end_ed, 'CharacterMovement')
    stop = call(end_ed, '/Script/Engine.MovementComponent.StopMovementImmediately')
    link(out(move, 'CharacterMovement'), inp(stop, 'self')); chain(end_flag, stop)
    reset_ed = func(bp, 'DodgeReady')
    reset_flag = setv(reset_ed, 'DodgeCooling', 'false'); link(reset_ed.find_graph_entry_pin(), reset_flag.find_execute_pin())
    compile_blueprint(bp, True)
    event = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'EventGraph')
    nodes = {n.get_name(): n for n in event.list_all_nodes()}
    action = nodes['K2Node_EnhancedInputAction_6']
    out(action, 'Started').break_pin_links()
    dodge = call(event, 'TryDodge'); link(out(action, 'Started'), dodge.find_execute_pin())
    out(action, 'Completed').break_pin_links()
    # Mouse aiming and WASD are unchanged. Space reuses the existing IA_Jump mapping.
    compile_blueprint(bp, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)

    hud = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_AmmoHUD')
    hed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(hud, 'EventGraph')
    for info in BT.get_node_infos(list(hed.list_all_nodes())):
        if not info.type_id.endswith('|DrawText'):
            continue
        text_pin = inp(info.node, 'Text')
        if text_pin.get_pin_value() == 'PISTOL':
            label = get(hed, 'WeaponLabel'); link(out(label, 'WeaponLabel'), text_pin)
        if 'WASD MOVE' in str(text_pin.get_pin_value()):
            val(info.node, 'Text', 'WASD MOVE   MOUSE AIM   LMB FIRE   SPACE DODGE   R RETRY')
            val(info.node, 'Scale', 0.7)
    compile_blueprint(hud, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(hud, False)
    return {'saved': [bp.get_path_name(), hud.get_path_name()], 'dodge_duration': 0.18, 'dodge_cooldown': 1.0}

run_editor(work, 'DodgeImplementation.json')
