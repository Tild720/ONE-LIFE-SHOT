"""Editor-only authoring of the four design-brief enemy roles.

The resulting gameplay is Blueprint-native. Run through the temporary editor
MCP harness, then remove that harness. Binary assets are saved by Unreal only.
"""
import json
import traceback
from pathlib import Path

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BT
from editor_toolset.toolsets.actor import ActorTools as AT
from toolset_registry.helpers import compile_blueprint

BASE = '/Game/Enemies/BP_EnemyStraightRunner'
FAST = '/Game/Enemies/BP_EnemyRunnerFast'
HEAVY = '/Game/Enemies/BP_EnemyRunnerSlow'
SNIPER = '/Game/Enemies/BP_EnemySniper'
CHAR = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter'
MAT = '/Game/Enemies/Materials/M_EnemyRed'
GUN = '/Game/Characters/KayKit/Assets/fbx/'
CYL = '/Engine/BasicShapes/Cylinder'
M = '/Script/Engine.KismetMathLibrary.'
S = '/Script/Engine.KismetSystemLibrary.'
A = '/Script/Engine.Actor.'
SC = '/Script/Engine.SceneComponent.'
GAME = '/Script/Engine.GameplayStatics.'


def ip(node, name):
    pin = node.find_input_pin(name)
    assert pin.is_valid(), (node.get_name(), name)
    return pin


def op(node, name='ReturnValue'):
    pin = node.find_output_pin(name)
    assert pin.is_valid(), (node.get_name(), name)
    return pin


def link(a, b):
    assert a.try_create_connection(b), (str(a), str(b))


def chain(a, b, output=None):
    link(op(a, output) if output else a.find_then_pin(), b.find_execute_pin())


def call(ed, path, **values):
    operator = {'Add_DoubleDouble':'Add', 'Subtract_DoubleDouble':'Subtract',
                'Multiply_DoubleDouble':'Multiply', 'Divide_DoubleDouble':'Divide',
                'Subtract_IntInt':'Subtract', 'Multiply_IntInt':'Multiply', 'Divide_IntInt':'Divide'}.get(path.rsplit('.',1)[-1])
    stem = path.rsplit('.',1)[-1].split('_',1)[0]
    if stem in ('Add','Subtract','Multiply','Divide'):
        operator = stem
    localized = {'Add':'추가','Subtract':'빼기','Multiply':'곱하기','Divide':'나누기'}
    compare = {'EqualEqual_IntInt':'같음(==)','EqualEqual_ObjectObject':'같음(==)',
               'NotEqual_IntInt':'같지않음(!=)','LessEqual_DoubleDouble':'작거나같음(<=)',
               'GreaterEqual_DoubleDouble':'크거나같음(>=)','Less_DoubleDouble':'작음(<)',
               'Greater_DoubleDouble':'보다큼(>)'}.get(path.rsplit('.',1)[-1])
    type_name = localized[operator] if operator else compare
    node = ed.create_node_from_name('유틸리티|연산자|'+type_name, unreal.Vector2D(), []) if type_name else ed.add_call_function_node(path)
    assert node, path
    for key, value in values.items():
        if ip(node, key).set_pin_value(str(value)):
            continue
        if isinstance(value, (int, float)):
            literal = ed.add_call_function_node(S + ('MakeLiteralInt' if 'IntInt' in path else 'MakeLiteralDouble'))
            assert ip(literal, 'Value').set_pin_value(str(value))
            link(op(literal), ip(node, key))
        elif str(value).startswith('(X='):
            literal = ed.add_call_function_node(M + 'MakeVector')
            for component in str(value).strip('()').split(','):
                axis, number = component.split('=')
                assert ip(literal, axis).set_pin_value(number)
            link(op(literal), ip(node, key))
        else:
            raise AssertionError((path, key, value))
    return node


def get(ed, name, cls=''):
    node = ed.add_get_member_variable_node(name, cls)
    assert node, name
    pin = op(node, name)
    return pin


def setv(ed, name, value=None, cls=''):
    node = ed.add_set_member_variable_node(name, cls)
    assert node, name
    if value is not None:
        if isinstance(value, unreal.BlueprintGraphPin):
            link(value, ip(node, name))
        else:
            assert ip(node, name).set_pin_value(str(value)), (name, value)
    return node


def branch(ed, condition):
    node = ed.add_branch_node()
    link(condition, ip(node, 'Condition'))
    return node


def unary(ed, fn, value, pin='A'):
    node = call(ed, M + fn)
    link(value, ip(node, pin))
    return op(node)


def binary(ed, fn, lhs, rhs, ap='A', bp='B'):
    unreal.log('ENEMY_BINARY create ' + fn)
    node = call(ed, M + fn)
    unreal.log('ENEMY_BINARY created ' + fn)
    for key, value in [(ap, lhs), (bp, rhs)]:
        if isinstance(value, unreal.BlueprintGraphPin):
            unreal.log('ENEMY_BINARY link ' + fn + ' ' + key)
            link(value, ip(node, key))
            unreal.log('ENEMY_BINARY linked ' + fn + ' ' + key)
        elif not ip(node, key).set_pin_value(str(value)):
            literal = call(ed, S + ('MakeLiteralInt' if 'IntInt' in fn else 'MakeLiteralDouble'), Value=value)
            link(op(literal), ip(node, key))
    return op(node)


def eq(ed, name, value):
    return binary(ed, 'EqualEqual_IntInt', get(ed, name), value)


def allof(ed, *pins):
    result = pins[0]
    for pin in pins[1:]:
        result = binary(ed, 'BooleanAND', result, pin)
    return result


def current_time(ed):
    return op(call(ed, S + 'GetGameTimeInSeconds'))


def location(ed, actor=None):
    node = call(ed, A + 'K2_GetActorLocation')
    if actor is not None:
        link(actor, ip(node, 'self'))
    return op(node)


def player(ed):
    return op(call(ed, GAME + 'GetPlayerPawn', PlayerIndex=0))


def vector_dist(ed, lhs, rhs):
    return binary(ed, 'Vector_Distance2D', lhs, rhs, 'V1', 'V2')


def toward_player(ed):
    return unary(ed, 'Vector_Normal2D', binary(ed, 'Subtract_VectorVector', location(ed, player(ed)), location(ed)))


def selfpin(ed):
    ids = [s for s in ed.list_available_nodes([]) if s == 'Variables|셀프레퍼런스가져오기' or s.endswith('|Getareferencetoself')]
    assert ids, 'Self node unavailable'
    return op(ed.create_node_from_name(ids[0], unreal.Vector2D(0, 400), []), 'self')


def function_call(ed, bp, name):
    return call(ed, bp.generated_class().get_path_name() + ':' + name)


def func(bp, name):
    graph = next((g for g in unreal.BlueprintEditorLibrary.list_graphs(bp) if g.get_name() == name), None)
    if graph is None:
        graph = BT.add_function_graph(bp, name)
    ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    ed.remove_nodes([n for n in ed.list_all_nodes() if not isinstance(n, unreal.K2Node_FunctionEntry)])
    return ed


def variables(bp):
    specs = [
        ('WeaponKind', 'int', 0, True),
        ('BodyTint', 'Vector', unreal.Vector(0.75, 0.055, 0.025), True),
        ('BodyScale', 'Vector', unreal.Vector(1, 1, 1), True),
        ('CruiseSpeed', 'float', 220.0, True),
        ('ContactRadius', 'float', 78.0, True),
        ('ChargeTriggerDistance', 'float', 700.0, True),
        ('ChargeWindup', 'float', 0.45, True),
        ('ChargeSpeed', 'float', 850.0, True),
        ('ChargeDuration', 'float', 0.55, True),
        ('RecoveryDuration', 'float', 1.0, True),
        ('BlastRadius', 'float', 300.0, True),
        ('BlastWindup', 'float', 1.0, True),
        ('BlastCooldown', 'float', 2.0, True),
        ('SniperRange', 'float', 2200.0, True),
        ('SniperWidth', 'float', 60.0, True),
        ('SniperWindup', 'float', 0.9, True),
        ('SniperCooldown', 'float', 1.8, True),
        ('AIState', 'int', 0, False),
        ('ChargeActive', 'bool', False, False),
        ('NextAttackTime', 'float', 0.0, False),
        ('StateEndTime', 'float', 0.0, False),
        ('AttackOrigin', 'Vector', unreal.Vector(), False),
        ('AttackTarget', 'Vector', unreal.Vector(), False),
        ('AttackDirection', 'Vector', unreal.Vector(), False),
        ('AttackLength', 'float', 2200.0, False),
        ('AttackWidth', 'float', 60.0, False),
    ]
    names = [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)]
    added = []
    for name, kind, default, editable in specs:
        if name not in names:
            BT.add_variable(bp, name, kind)
            added.append(name)
        unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, editable)
        unreal.BlueprintEditorLibrary.set_blueprint_variable_category(bp, name, 'Enemy Role')
    compile_blueprint(bp)
    cdo = unreal.get_default_object(bp.generated_class())
    for name, kind, default, editable in specs:
        if name in added:
            cdo.set_editor_property(name, default)
    cdo.set_editor_property('MoveSpeed', 220.0)


def timer(ed, name, seconds):
    node = call(ed, S + 'K2_SetTimer', FunctionName=name, Time=seconds, bLooping='true', bMaxOncePerFrame='true')
    link(selfpin(ed), ip(node, 'Object'))
    return node


def set_component(ed, name, fn, **values):
    node = call(ed, SC + fn, **values)
    link(get(ed, name), ip(node, 'self'))
    return node


def set_deadline(ed, name, duration):
    unreal.log('ENEMY_ROLES deadline: clock')
    clock = current_time(ed)
    unreal.log('ENEMY_ROLES deadline: duration')
    seconds = get(ed, duration)
    unreal.log('ENEMY_ROLES deadline: add')
    total = binary(ed, 'Add_DoubleDouble', clock, seconds)
    unreal.log('ENEMY_ROLES deadline: setter')
    return setv(ed, name, total)


def expired(ed, name='StateEndTime'):
    return binary(ed, 'GreaterEqual_DoubleDouble', current_time(ed), get(ed, name))


def face(ed, direction):
    node = call(ed, A + 'K2_SetActorRotation', bTeleportPhysics='true')
    link(unary(ed, 'MakeRotFromX', direction, 'X'), ip(node, 'NewRotation'))
    return node


def player_cast(ed, start):
    node = ed.create_node_from_name('Utilities|Casting|CastToBP_ThirdPersonCharacter', unreal.Vector2D(300, 100), [])
    assert node
    link(player(ed), ip(node, 'Object'))
    chain(start, node)
    return node


def player_safe(ed, actor):
    cls = unreal.load_asset(CHAR).generated_class().get_path_name()
    dead = ed.add_get_member_variable_node('Dead', cls)
    dodge = ed.add_get_member_variable_node('Dodging', cls)
    link(actor, ip(dead, 'self'))
    link(actor, ip(dodge, 'self'))
    return allof(ed, unary(ed, 'Not_PreBool', op(dead, 'Dead')), unary(ed, 'Not_PreBool', op(dodge, 'Dodging')))


def fail_player(ed, start, condition):
    c = player_cast(ed, start)
    pawn = op(c, 'AsBP Third Person Character')
    gate = branch(ed, allof(ed, condition, player_safe(ed, pawn)))
    chain(c, gate)
    fail = function_call(ed, unreal.load_asset(CHAR), 'FailRun')
    link(pawn, ip(fail, 'self'))
    # A locked warning can be escaped by moving behind actual level cover.
    trace = call(ed, S + 'LineTraceSingle', TraceChannel='TraceTypeQuery1',
                 bTraceComplex='false', DrawDebugType='None', bIgnoreSelf='true')
    link(get(ed, 'AttackOrigin'), ip(trace, 'Start'))
    link(location(ed, pawn), ip(trace, 'End'))
    chain(gate, trace)
    blocking = branch(ed, op(trace))
    chain(trace, blocking)
    # No blocking geometry before the endpoint means the corridor is clear,
    # including player collision configurations which ignore Visibility.
    chain(blocking, fail, 'else')
    hit = call(ed, GAME + 'BreakHitResult')
    link(op(trace, 'OutHit'), ip(hit, 'Hit'))
    hit_player = branch(ed, binary(ed, 'EqualEqual_ObjectObject', op(hit, 'HitActor'), pawn))
    chain(blocking, hit_player)
    chain(hit_player, fail)
    return gate


def build_appearance(bp):
    ed = func(bp, 'ConfigureEnemyAppearance')
    tint = call(ed, '/Script/Engine.MeshComponent.SetVectorParameterValueOnMaterials', ParameterName='EnemyTint')
    link(get(ed, 'Mesh'), ip(tint, 'self'))
    link(get(ed, 'BodyTint'), ip(tint, 'ParameterValue'))
    link(ed.find_graph_entry_pin(), tint.find_execute_pin())
    scale = call(ed, A + 'SetActorScale3D')
    link(get(ed, 'BodyScale'), ip(scale, 'NewScale3D'))
    chain(tint, scale)
    warning_color = call(ed, '/Script/Engine.MeshComponent.SetVectorParameterValueOnMaterials', ParameterName='TracerColor', ParameterValue='(X=1,Y=0.13,Z=0.015)')
    link(get(ed, 'TelegraphMesh'), ip(warning_color, 'self'))
    chain(scale, warning_color)
    tail = warning_color
    roles = [(0, GUN + 'Gun_Pistol', '(X=1,Y=1,Z=1)', '(Pitch=0,Yaw=0,Roll=0)'),
             (1, GUN + 'Gun_Rifle', '(X=0.75,Y=0.75,Z=0.75)', '(Pitch=0,Yaw=0,Roll=0)'),
             (2, GUN + 'Gun_Sniper', '(X=0.8,Y=0.8,Z=0.8)', '(Pitch=0,Yaw=0,Roll=0)'),
             (3, CYL, '(X=0.18,Y=0.18,Z=0.8)', '(Pitch=90,Yaw=0,Roll=0)')]
    previous = None
    for role, meshpath, size, rotation in roles:
        gate = branch(ed, eq(ed, 'WeaponKind', role))
        if previous is None:
            chain(tail, gate)
        else:
            chain(previous, gate, 'else')
        sm = call(ed, '/Script/Engine.StaticMeshComponent.SetStaticMesh', NewMesh=meshpath)
        link(get(ed, 'WeaponMesh'), ip(sm, 'self'))
        chain(gate, sm)
        ss = set_component(ed, 'WeaponMesh', 'SetRelativeScale3D', NewScale3D=size)
        chain(sm, ss)
        sr = set_component(ed, 'WeaponMesh', 'K2_SetRelativeRotation', NewRotation=rotation, bSweep='false', bTeleport='true')
        chain(ss, sr)
        previous = gate
    compile_blueprint(bp)


def build_telegraphs(bp):
    hide = func(bp, 'HideTelegraph')
    node = set_component(hide, 'TelegraphMesh', 'SetVisibility', bNewVisibility='false', bPropagateToChildren='false')
    link(hide.find_graph_entry_pin(), node.find_execute_pin())

    beam = func(bp, 'ShowAttackLine')
    midpoint = binary(beam, 'Add_VectorVector', get(beam, 'AttackOrigin'),
                      binary(beam, 'Multiply_VectorFloat', get(beam, 'AttackDirection'),
                             binary(beam, 'Multiply_DoubleDouble', get(beam, 'AttackLength'), 0.5)))
    floor = call(beam, M + 'MakeVector', X=0, Y=0, Z=-85)
    pos = set_component(beam, 'TelegraphMesh', 'K2_SetWorldLocation', bSweep='false', bTeleport='true')
    link(binary(beam, 'Add_VectorVector', midpoint, op(floor)), ip(pos, 'NewLocation'))
    link(beam.find_graph_entry_pin(), pos.find_execute_pin())
    rot = set_component(beam, 'TelegraphMesh', 'K2_SetWorldRotation', bSweep='false', bTeleport='true')
    beam_rotation = call(beam, M + 'MakeRotFromZX', X='(X=0,Y=0,Z=1)')
    link(get(beam, 'AttackDirection'), ip(beam_rotation, 'Z'))
    link(op(beam_rotation), ip(rot, 'NewRotation'))
    chain(pos, rot)
    size = call(beam, M + 'MakeVector', X=0.025)
    link(binary(beam, 'Divide_DoubleDouble', get(beam, 'AttackWidth'), 50.0), ip(size, 'Y'))
    link(binary(beam, 'Divide_DoubleDouble', get(beam, 'AttackLength'), 100.0), ip(size, 'Z'))
    scale = set_component(beam, 'TelegraphMesh', 'SetWorldScale3D')
    link(op(size), ip(scale, 'NewScale'))
    chain(rot, scale)
    visible = set_component(beam, 'TelegraphMesh', 'SetVisibility', bNewVisibility='true', bPropagateToChildren='false')
    chain(scale, visible)

    ring = func(bp, 'ShowBlastZone')
    offset = call(ring, M + 'MakeVector', X=0, Y=0, Z=-92)
    pos = set_component(ring, 'TelegraphMesh', 'K2_SetWorldLocation', bSweep='false', bTeleport='true')
    link(binary(ring, 'Add_VectorVector', get(ring, 'AttackTarget'), op(offset)), ip(pos, 'NewLocation'))
    link(ring.find_graph_entry_pin(), pos.find_execute_pin())
    rot = set_component(ring, 'TelegraphMesh', 'K2_SetWorldRotation', NewRotation='(Pitch=0,Yaw=0,Roll=0)', bSweep='false', bTeleport='true')
    chain(pos, rot)
    diameter = binary(ring, 'Divide_DoubleDouble', get(ring, 'BlastRadius'), 50.0)
    size = call(ring, M + 'MakeVector', Z=0.025)
    link(diameter, ip(size, 'X'))
    link(diameter, ip(size, 'Y'))
    scale = set_component(ring, 'TelegraphMesh', 'SetWorldScale3D')
    link(op(size), ip(scale, 'NewScale'))
    chain(rot, scale)
    visible = set_component(ring, 'TelegraphMesh', 'SetVisibility', bNewVisibility='true', bPropagateToChildren='false')
    chain(scale, visible)
    compile_blueprint(bp)


def start_attack(bp, name, windup, visual):
    unreal.log('ENEMY_ROLES warning: get graph ' + name)
    ed = func(bp, name)
    unreal.log('ENEMY_ROLES warning: set state')
    state = setv(ed, 'AIState', 1)
    link(ed.find_graph_entry_pin(), state.find_execute_pin())
    stop = setv(ed, 'MoveSpeed', 0.0)
    chain(state, stop)
    origin = setv(ed, 'AttackOrigin', location(ed))
    unreal.log('ENEMY_ROLES warning: origin')
    chain(stop, origin)
    target = setv(ed, 'AttackTarget', location(ed, player(ed)))
    unreal.log('ENEMY_ROLES warning: target')
    chain(origin, target)
    direction = setv(ed, 'AttackDirection', toward_player(ed))
    unreal.log('ENEMY_ROLES warning: direction')
    chain(target, direction)
    facing = face(ed, get(ed, 'AttackDirection'))
    unreal.log('ENEMY_ROLES warning: facing')
    chain(direction, facing)
    deadline = set_deadline(ed, 'StateEndTime', windup)
    unreal.log('ENEMY_ROLES warning: deadline')
    chain(facing, deadline)
    if visual == 'ShowAttackLine':
        length = binary(ed, 'Multiply_DoubleDouble', get(ed, 'ChargeSpeed'), get(ed, 'ChargeDuration')) if name == 'BeginChargeWarning' else get(ed, 'SniperRange')
        attack_length = setv(ed, 'AttackLength', length)
        chain(deadline, attack_length)
        attack_width = setv(ed, 'AttackWidth', get(ed, 'ContactRadius') if name == 'BeginChargeWarning' else get(ed, 'SniperWidth'))
        chain(attack_length, attack_width)
        deadline = attack_width
    show = function_call(ed, bp, visual)
    unreal.log('ENEMY_ROLES warning: show')
    chain(deadline, show)
    return ed


def build_assault(bp):
    unreal.log('ENEMY_ROLES assault: warning graph')
    start_attack(bp, 'BeginChargeWarning', 'ChargeWindup', 'ShowAttackLine')
    unreal.log('ENEMY_ROLES assault: pulse graph')
    ed = func(bp, 'AssaultPulse')
    ready = branch(ed, eq(ed, 'AIState', 0))
    link(ed.find_graph_entry_pin(), ready.find_execute_pin())
    cruise = setv(ed, 'MoveSpeed', get(ed, 'CruiseSpeed'))
    chain(ready, cruise)
    direction = setv(ed, 'TravelDirection', toward_player(ed))
    chain(cruise, direction)
    attack = branch(ed, allof(ed, expired(ed, 'NextAttackTime'),
                             binary(ed, 'LessEqual_DoubleDouble', vector_dist(ed, location(ed), location(ed, player(ed))), get(ed, 'ChargeTriggerDistance'))))
    chain(direction, attack)
    warning = function_call(ed, bp, 'BeginChargeWarning')
    chain(attack, warning)
    phase1 = branch(ed, eq(ed, 'AIState', 1))
    chain(ready, phase1, 'else')
    expires1 = branch(ed, expired(ed))
    chain(phase1, expires1)
    active = setv(ed, 'ChargeActive', 'true')
    chain(expires1, active)
    state = setv(ed, 'AIState', 2)
    chain(active, state)
    speed = setv(ed, 'MoveSpeed', get(ed, 'ChargeSpeed'))
    chain(state, speed)
    travel = setv(ed, 'TravelDirection', get(ed, 'AttackDirection'))
    chain(speed, travel)
    deadline = set_deadline(ed, 'StateEndTime', 'ChargeDuration')
    chain(travel, deadline)
    hide = function_call(ed, bp, 'HideTelegraph')
    chain(deadline, hide)
    phase2 = branch(ed, eq(ed, 'AIState', 2))
    chain(phase1, phase2, 'else')
    expires2 = branch(ed, expired(ed))
    chain(phase2, expires2)
    inactive = setv(ed, 'ChargeActive', 'false')
    chain(expires2, inactive)
    state = setv(ed, 'AIState', 3)
    chain(inactive, state)
    stop = setv(ed, 'MoveSpeed', 0.0)
    chain(state, stop)
    deadline = set_deadline(ed, 'StateEndTime', 'RecoveryDuration')
    chain(stop, deadline)
    phase3 = branch(ed, allof(ed, eq(ed, 'AIState', 3), expired(ed)))
    chain(phase2, phase3, 'else')
    reset = setv(ed, 'AIState', 0)
    chain(phase3, reset)
    next_time = setv(ed, 'NextAttackTime', binary(ed, 'Add_DoubleDouble', current_time(ed), 0.5))
    chain(reset, next_time)
    compile_blueprint(bp)
    unreal.log('ENEMY_ROLES assault: compiled')


def build_heavy(bp):
    start_attack(bp, 'BeginBlastWarning', 'BlastWindup', 'ShowBlastZone')
    ed = func(bp, 'HeavyPulse')
    ready = branch(ed, eq(ed, 'AIState', 0))
    link(ed.find_graph_entry_pin(), ready.find_execute_pin())
    cruise = setv(ed, 'MoveSpeed', get(ed, 'CruiseSpeed'))
    chain(ready, cruise)
    direction = setv(ed, 'TravelDirection', toward_player(ed))
    chain(cruise, direction)
    attack = branch(ed, allof(ed, expired(ed, 'NextAttackTime'),
                             binary(ed, 'LessEqual_DoubleDouble', vector_dist(ed, location(ed), location(ed, player(ed))), 1100.0)))
    chain(direction, attack)
    warning = function_call(ed, bp, 'BeginBlastWarning')
    chain(attack, warning)
    phase1 = branch(ed, allof(ed, eq(ed, 'AIState', 1), expired(ed)))
    chain(ready, phase1, 'else')
    hide = function_call(ed, bp, 'HideTelegraph')
    chain(phase1, hide)
    state = setv(ed, 'AIState', 2)
    chain(hide, state)
    deadline = set_deadline(ed, 'StateEndTime', 'BlastCooldown')
    chain(state, deadline)
    hit = binary(ed, 'LessEqual_DoubleDouble', vector_dist(ed, location(ed, player(ed)), get(ed, 'AttackTarget')), get(ed, 'BlastRadius'))
    fail_player(ed, deadline, hit)
    phase2 = branch(ed, allof(ed, eq(ed, 'AIState', 2), expired(ed)))
    chain(phase1, phase2, 'else')
    state = setv(ed, 'AIState', 0)
    chain(phase2, state)
    compile_blueprint(bp)


def build_sniper(bp):
    start_attack(bp, 'BeginSniperWarning', 'SniperWindup', 'ShowAttackLine')
    ed = func(bp, 'SniperPulse')
    ready = branch(ed, eq(ed, 'AIState', 0))
    link(ed.find_graph_entry_pin(), ready.find_execute_pin())
    stop = setv(ed, 'MoveSpeed', 0.0)
    chain(ready, stop)
    facing = face(ed, toward_player(ed))
    chain(stop, facing)
    attack = branch(ed, allof(ed, expired(ed, 'NextAttackTime'),
                             binary(ed, 'LessEqual_DoubleDouble', vector_dist(ed, location(ed), location(ed, player(ed))), get(ed, 'SniperRange'))))
    chain(facing, attack)
    warning = function_call(ed, bp, 'BeginSniperWarning')
    chain(attack, warning)
    phase1 = branch(ed, allof(ed, eq(ed, 'AIState', 1), expired(ed)))
    chain(ready, phase1, 'else')
    hide = function_call(ed, bp, 'HideTelegraph')
    chain(phase1, hide)
    state = setv(ed, 'AIState', 2)
    chain(hide, state)
    deadline = set_deadline(ed, 'StateEndTime', 'SniperCooldown')
    chain(state, deadline)
    delta = binary(ed, 'Subtract_VectorVector', location(ed, player(ed)), get(ed, 'AttackOrigin'))
    projection = binary(ed, 'Dot_VectorVector', delta, get(ed, 'AttackDirection'))
    projected = binary(ed, 'Add_VectorVector', get(ed, 'AttackOrigin'), binary(ed, 'Multiply_VectorFloat', get(ed, 'AttackDirection'), projection))
    hit = allof(ed, binary(ed, 'GreaterEqual_DoubleDouble', projection, 0.0),
                binary(ed, 'LessEqual_DoubleDouble', projection, get(ed, 'SniperRange')),
                binary(ed, 'LessEqual_DoubleDouble', vector_dist(ed, location(ed, player(ed)), projected), get(ed, 'SniperWidth')))
    fail_player(ed, deadline, hit)
    phase2 = branch(ed, allof(ed, eq(ed, 'AIState', 2), expired(ed)))
    chain(phase1, phase2, 'else')
    state = setv(ed, 'AIState', 0)
    chain(phase2, state)
    compile_blueprint(bp)


def build_role_pulse(bp):
    ed = func(bp, 'EnemyRolePulse')
    alive = branch(ed, unary(ed, 'Not_PreBool', get(ed, 'Dead')))
    link(ed.find_graph_entry_pin(), alive.find_execute_pin())
    hide = function_call(ed, bp, 'HideTelegraph')
    chain(alive, hide, 'else')
    clear = call(ed, S + 'K2_ClearTimer', FunctionName='EnemyRolePulse')
    link(selfpin(ed), ip(clear, 'Object'))
    chain(hide, clear)
    valid = call(ed, S + 'IsValid')
    link(player(ed), ip(valid, 'Object'))
    player_valid = branch(ed, op(valid))
    chain(alive, player_valid)
    c = player_cast(ed, player_valid)
    pawn = op(c, 'AsBP Third Person Character')
    contact = branch(ed, allof(ed, player_safe(ed, pawn), binary(ed, 'LessEqual_DoubleDouble', vector_dist(ed, location(ed), location(ed, pawn)), get(ed, 'ContactRadius'))))
    chain(c, contact)
    fail = function_call(ed, unreal.load_asset(CHAR), 'FailRun')
    link(pawn, ip(fail, 'self'))
    chain(contact, fail)
    previous = contact
    for role, name in [(1, 'AssaultPulse'), (3, 'HeavyPulse'), (2, 'SniperPulse')]:
        gate = branch(ed, eq(ed, 'WeaponKind', role))
        chain(previous, gate, 'else')
        fn = function_call(ed, bp, name)
        chain(gate, fn)
        previous = gate
    # The original movement Tick remains; only its direction is updated here.
    basic = setv(ed, 'TravelDirection', toward_player(ed))
    chain(previous, basic, 'else')
    compile_blueprint(bp)


def install_events(bp):
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'EventGraph')
    infos = BT.get_node_infos(list(ed.list_all_nodes()))
    # Own additions can be rebuilt without touching existing collision/death nodes.
    own_calls = {'|ConfigureEnemyAppearance', '|EnemyRolePulse', '|HideTelegraph'}
    ed.remove_nodes([i.node for i in infos if i.type_id in own_calls or
                     any(p.name == 'FunctionName' and p.value == 'EnemyRolePulse' for p in i.input_pins)])
    ns = {n.get_name(): n for n in ed.list_all_nodes()}
    terminal = ns['K2Node_CallFunction_52']
    terminal.find_then_pin().break_pin_links()
    configure = function_call(ed, bp, 'ConfigureEnemyAppearance')
    chain(terminal, configure)
    reset = setv(ed, 'AIState', 0)
    chain(configure, reset)
    deadline = setv(ed, 'NextAttackTime', binary(ed, 'Add_DoubleDouble', current_time(ed), 1.0))
    chain(reset, deadline)
    pulse = timer(ed, 'EnemyRolePulse', 0.1)
    chain(deadline, pulse)

    # Contact death also applies to overlap-only capsule configurations.
    completed = op(ns['K2Node_MacroInstance_29'], 'Completed')
    completed.break_pin_links()
    cast = ed.create_node_from_name('Utilities|Casting|CastToBP_ThirdPersonCharacter', unreal.Vector2D(1800, 1300), [])
    link(op(ns['K2Node_Event_6'], 'OtherActor'), ip(cast, 'Object'))
    link(completed, cast.find_execute_pin())
    pawn = op(cast, 'AsBP Third Person Character')
    safe = branch(ed, allof(ed, player_safe(ed, pawn), unary(ed, 'Not_PreBool', get(ed, 'Dead'))))
    chain(cast, safe)
    fail = function_call(ed, unreal.load_asset(CHAR), 'FailRun')
    link(pawn, ip(fail, 'self'))
    chain(safe, fail)

    # Existing hit path: preserve KillVolume death and protect player dodges.
    contact_cast = ns['K2Node_DynamicCast_0']
    contact_cast.find_then_pin().break_pin_links()
    contact_pawn = op(contact_cast, 'AsBP Third Person Character')
    safe = branch(ed, allof(ed, player_safe(ed, contact_pawn), unary(ed, 'Not_PreBool', get(ed, 'Dead'))))
    chain(contact_cast, safe)
    fail = ns['K2Node_CallFunction_0']
    chain(safe, fail)

    # Empty-state recovery requires a real committed charge against a vertical
    # WorldStatic wall. Floors, ordinary walking hits, and dead bodies cannot drop.
    contact_cast.find_output_pin('CastFailed').break_pin_links()
    normal = call(ed, M + 'BreakVector')
    link(op(ns['K2Node_Event_7'], 'HitNormal'), ip(normal, 'InVec'))
    vertical = binary(ed, 'Less_DoubleDouble', unary(ed, 'Abs', op(normal, 'Z')), 0.35)
    static_channel = call(ed, '/Script/Engine.PrimitiveComponent.GetCollisionObjectType')
    link(op(ns['K2Node_Event_7'], 'OtherComp'), ip(static_channel, 'self'))
    enum_eq = ed.create_node_from_name('Utilities|Enum|Equal(Enum)', unreal.Vector2D(2200, 1300), [])
    assert enum_eq
    link(op(static_channel), ip(enum_eq, 'A'))
    assert ip(enum_eq, 'B').set_pin_value('ECC_WorldStatic')
    charged = branch(ed, allof(ed, get(ed, 'ChargeActive'), vertical, op(enum_eq), unary(ed, 'Not_PreBool', get(ed, 'Dead'))))
    chain(contact_cast, charged, 'CastFailed')
    die = function_call(ed, bp, 'Die')
    chain(charged, die)
    # RPG blast damage reaches the same idempotent existing death function.
    damage = BT.add_event(bp, 'ReceiveAnyDamage', unreal.IntPoint(2000, 2100))
    damage.find_then_pin().break_pin_links()
    positive = branch(ed, binary(ed, 'Greater_DoubleDouble', op(damage, 'Damage'), 0.0))
    chain(damage, positive)
    die = function_call(ed, bp, 'Die')
    chain(positive, die)
    # Hidden warning meshes must not linger during the death animation.
    # Do not modify Die itself: the root owns weapon-kind propagation there.
    ended = BT.add_event(bp, 'ReceiveEndPlay', unreal.IntPoint(2000, 2300))
    ended.find_then_pin().break_pin_links()
    clear = call(ed, S + 'K2_ClearTimer', FunctionName='EnemyRolePulse')
    link(selfpin(ed), ip(clear, 'Object'))
    chain(ended, clear)
    construction = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'UserConstructionScript')
    construction.find_graph_entry_pin().break_pin_links()
    configure = function_call(construction, bp, 'ConfigureEnemyAppearance')
    link(construction.find_graph_entry_pin(), configure.find_execute_pin())
    compile_blueprint(bp, True)


def edit():
    # Verify actual asset availability before creating or choosing any content.
    bp = unreal.load_asset(BASE)
    assert bp
    char = unreal.load_asset(CHAR)
    assert 'Dodging' in [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(char, False)], 'Character dodge must be compiled first'
    tracer = '/Game/Weapons/Pistol/M_BulletTracer'
    for path in [FAST, HEAVY, MAT, tracer, CYL, GUN + 'Gun_Pistol', GUN + 'Gun_Rifle', GUN + 'Gun_Sniper']:
        assert unreal.load_asset(path), 'Missing inspected asset: ' + path
    unreal.log('ENEMY_ROLES stage variables')
    variables(bp)
    unreal.log('ENEMY_ROLES stage warning component')
    components = AT.get_components(unreal.get_default_object(bp.generated_class()))
    warning = next((c for c in components if c.get_name().startswith('TelegraphMesh')), None)
    if warning is None:
        warning = AT.add_component(bp, unreal.StaticMeshComponent.static_class(), 'TelegraphMesh')
    warning.set_editor_property('static_mesh', unreal.load_asset(CYL))
    warning.set_editor_property('override_materials', [unreal.load_asset(tracer)])
    warning.set_editor_property('visible', False)
    warning.set_editor_property('cast_shadow', False)
    warning.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    # Keep world-space locked telegraphs still while their owning robot turns.
    warning.set_editor_property('absolute_location', True)
    warning.set_editor_property('absolute_rotation', True)
    warning.set_editor_property('absolute_scale', True)
    names = ['ConfigureEnemyAppearance', 'HideTelegraph', 'ShowAttackLine', 'ShowBlastZone',
             'BeginChargeWarning', 'AssaultPulse', 'BeginBlastWarning', 'HeavyPulse',
             'BeginSniperWarning', 'SniperPulse', 'EnemyRolePulse']
    for name in names:
        BT.add_function_graph(bp, name)
    compile_blueprint(bp)
    for label, action in [('appearance', build_appearance), ('telegraphs', build_telegraphs),
                          ('assault', build_assault), ('heavy', build_heavy),
                          ('sniper', build_sniper), ('role pulse', build_role_pulse),
                          ('events', install_events)]:
        unreal.log('ENEMY_ROLES stage ' + label)
        action(bp)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
        (Path(unreal.Paths.project_saved_dir()) / 'EnemyRolesImplementation.json').write_text(
            json.dumps({'status':'running','completed_stage':label}), encoding='utf-8')
    unreal.log('ENEMY_ROLES stage sniper child')
    sniper = unreal.load_asset(SNIPER)
    created_sniper = sniper is None
    if created_sniper:
        sniper = BT.create('/Game/Enemies', 'BP_EnemySniper', bp.generated_class())
    assert BT.get_parent(sniper) == bp.generated_class(), 'Existing Sniper has a different parent'
    role_defaults = [(bp, 0, unreal.Vector(0.75, 0.055, 0.025), unreal.Vector(1, 1, 1), 220.0),
                     (unreal.load_asset(FAST), 1, unreal.Vector(1.0, 0.32, 0.02), unreal.Vector(0.88, 0.88, 0.92), 240.0),
                     (sniper, 2, unreal.Vector(0.015, 0.8, 0.85), unreal.Vector(0.82, 0.82, 1.17), 0.0),
                     (unreal.load_asset(HEAVY), 3, unreal.Vector(0.55, 0.04, 0.8), unreal.Vector(1.3, 1.3, 1.2), 140.0)]
    result = {'saved': [], 'roles': [], 'new_blueprints': [SNIPER] if created_sniper else []}
    for asset, kind, color, scale, speed in role_defaults:
        unreal.log('ENEMY_ROLES stage defaults/save ' + asset.get_path_name())
        compile_blueprint(asset, True)
        cdo = unreal.get_default_object(asset.generated_class())
        for prop, value in [('WeaponKind', kind), ('BodyTint', color), ('BodyScale', scale),
                            ('CruiseSpeed', speed), ('MoveSpeed', speed)]:
            cdo.set_editor_property(prop, value)
        assert unreal.EditorAssetLibrary.save_loaded_asset(asset, False)
        result['saved'].append(asset.get_path_name())
        result['roles'].append({'asset': asset.get_path_name(), 'weapon_kind': kind, 'speed': speed,
                                'color': str(color), 'scale': str(scale)})
    result['mechanics'] = ['Assault charge: warning .45 / committed charge .55 / recovery 1.0 seconds',
                           'Assault charging vertical WorldStatic wall dies and yields its weapon',
                           'Heavy: locked ground blast radius300 after 1.0 seconds',
                           'Sniper: locked lane range2200 half-width60 after .9 seconds',
                           'Heavy/Sniper Visibility trace preserves level cover; warning strips match attack width',
                           'Player contact respects Dead and Dodging; fallback distance pulse .1 seconds',
                           'RPG AnyDamage uses existing guarded Die; ordinary walking/floor cannot cause wall death']
    return result


les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
handle = [None]


def after_pie(dt):
    if les.is_in_play_in_editor():
        return
    unreal.unregister_slate_post_tick_callback(handle[0])
    try:
        result = edit()
    except Exception:
        result = {'error': traceback.format_exc()}
        unreal.log_error(result['error'])
    (Path(unreal.Paths.project_saved_dir()) / 'EnemyRolesImplementation.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')


handle[0] = unreal.register_slate_post_tick_callback(after_pie)
les.editor_request_end_play()
