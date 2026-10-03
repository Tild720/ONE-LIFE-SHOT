"""UE 5.8 editor authoring for the existing one-shot weapon/projectile Blueprints.

Run through the editor Python console or a temporary MCP harness. The resulting
gameplay is Blueprint-only. This script saves only BP_Pistol/BP_BulletProjectile.
"""
import json
import traceback
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BT, ContainerType
from toolset_registry.helpers import compile_blueprint

GUN = '/Game/Weapons/Pistol/BP_Pistol'
BULLET = '/Game/Weapons/Pistol/BP_BulletProjectile'
ENEMY = '/Game/Enemies/BP_EnemyStraightRunner'
BITS = '/Game/Weapons/Pistol/BP_PistolImpactBits'
SYS = '/Script/Engine.KismetSystemLibrary.'
MATH = '/Script/Engine.KismetMathLibrary.'
GAME = '/Script/Engine.GameplayStatics.'
ACT = '/Script/Engine.Actor.'
SCENE = '/Script/Engine.SceneComponent.'
PRIM = '/Script/Engine.PrimitiveComponent.'
ARRAY = '/Script/Engine.KismetArrayLibrary.'
MESHES = ['/Game/Characters/KayKit/Assets/fbx/Gun_Pistol',
          '/Game/Characters/KayKit/Assets/fbx/Gun_Rifle',
          '/Game/Characters/KayKit/Assets/fbx/Gun_Sniper',
          '/Game/Characters/KayKit/Assets/fbx/Gun_Rifle']


def ip(node, name):
    pin = node.find_input_pin(name)
    assert pin.is_valid(), (node.get_name(), 'input', name)
    return pin


def op(node, name='ReturnValue'):
    pin = node.find_output_pin(name)
    assert pin.is_valid(), (node.get_name(), 'output', name)
    return pin


def link(source, dest):
    assert source.try_create_connection(dest), (str(source), str(dest))


def val(node, name, value):
    assert ip(node, name).set_pin_value(str(value)), (node.get_name(), name, value)


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
    for name, value in values.items():
        if ip(node, name).set_pin_value(str(value)):
            continue
        if isinstance(value, (float, int)):
            integer = '_IntInt' in path or path.endswith('.Clamp')
            literal = ed.add_call_function_node(SYS + ('MakeLiteralInt' if integer else 'MakeLiteralDouble'))
            val(literal, 'Value', value)
            link(op(literal), ip(node, name))
        elif str(value).startswith('(X='):
            literal = ed.add_call_function_node(MATH + 'MakeVector')
            for part in str(value).strip('()').split(','):
                key, number = part.split('=')
                val(literal, key, number)
            link(op(literal), ip(node, name))
        else:
            raise AssertionError((path, name, value))
    return node


def chain(first, second):
    link(first.find_then_pin(), second.find_execute_pin())


def get(ed, name, cls=''):
    node = ed.add_get_member_variable_node(name, cls)
    assert node, name
    return node


def setv(ed, name, value=None, cls=''):
    node = ed.add_set_member_variable_node(name, cls)
    assert node, name
    if value is not None:
        val(node, name, value)
    return node


def branch(ed, condition):
    node = ed.add_branch_node()
    link(condition, ip(node, 'Condition'))
    return node


def cmp_kind(ed, value):
    kind = get(ed, 'WeaponKind')
    eq = call(ed, MATH + 'EqualEqual_IntInt', B=value)
    link(op(kind, 'WeaponKind'), ip(eq, 'A'))
    return op(eq)


def selfpin(ed):
    ids = [i for i in ed.list_available_nodes([])
           if '셀프' in i or i.endswith('|Getareferencetoself')]
    assert ids, 'Self node not available'
    node = ed.create_node_from_name(ids[0], unreal.Vector2D(), [])
    assert node
    return op(node, 'self')


def cast(ed, name):
    node = ed.create_node_from_name('Utilities|Casting|CastTo' + name,
                                   unreal.Vector2D(), [])
    assert node, name
    return node


def func(bp, name):
    graphs = {g.get_name(): g for g in unreal.BlueprintEditorLibrary.list_graphs(bp)}
    graph = graphs.get(name) or BT.add_function_graph(bp, name)
    ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    ed.remove_nodes([n for n in ed.list_all_nodes() if not isinstance(n, unreal.K2Node_FunctionEntry)])
    return ed


def var(bp, name, kind, default, editable=False):
    names = [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)]
    if name not in names:
        BT.add_variable(bp, name, kind)
        compile_blueprint(bp)
        unreal.get_default_object(bp.generated_class()).set_editor_property(name, default)
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, editable)
    unreal.BlueprintEditorLibrary.set_blueprint_variable_category(bp, name, 'One Shot|Weapon Roles')


def objvar(bp, name, cls, array=False):
    names = [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)]
    if name not in names:
        BT.add_object_variable(bp, name, cls, container_type=ContainerType.ARRAY if array else None)


def timer(ed, name, timepin=None, time=0.02, looping=False):
    node = call(ed, SYS + 'K2_SetTimer', FunctionName=name, Time=time,
                bLooping='true' if looping else 'false', bMaxOncePerFrame='true')
    link(selfpin(ed), ip(node, 'Object'))
    if timepin is not None:
        link(timepin, ip(node, 'Time'))
    return node


def make_array(ed, sources):
    ids = [i for i in ed.list_available_nodes([])
           if i.endswith('|MakeArray') or i.endswith('|배열만들기')]
    assert ids, 'MakeArray not available'
    node = ed.create_node_from_name(ids[0], unreal.Vector2D(), [])
    assert node
    for _ in range(len(sources) - 1):
        assert ed.add_node_pin(node)
    for i, source in enumerate(sources):
        link(source, ip(node, '[' + str(i) + ']'))
    return op(node, 'Array')


def spawn(ed, asset, transform, tail, owner=None):
    """Native deferred spawning avoids assumptions about localized SpawnActor titles."""
    begin = call(ed, GAME + 'BeginDeferredActorSpawnFromClass',
                 ActorClass=unreal.load_asset(asset).generated_class().get_path_name(),
                 CollisionHandlingOverride='AlwaysSpawn', TransformScaleMethod='MultiplyWithRoot')
    link(transform, ip(begin, 'SpawnTransform'))
    if owner is not None:
        link(owner, ip(begin, 'Owner'))
    chain(tail, begin)
    finish = call(ed, GAME + 'FinishSpawningActor', TransformScaleMethod='MultiplyWithRoot')
    link(op(begin), ip(finish, 'Actor'))
    link(transform, ip(finish, 'SpawnTransform'))
    chain(begin, finish)
    return finish, op(finish)


def transform(ed, location, rotation=None, scale='(X=1,Y=1,Z=1)'):
    node = call(ed, MATH + 'MakeTransform', Scale=scale)
    link(location, ip(node, 'Location'))
    if rotation is not None:
        link(rotation, ip(node, 'Rotation'))
    return op(node)


def mesh(ed, tail, component, asset, scale=None):
    node = call(ed, '/Script/Engine.StaticMeshComponent.SetStaticMesh',
                NewMesh=asset + '.' + asset.rsplit('/', 1)[1])
    link(component, ip(node, 'self'))
    chain(tail, node)
    if scale is not None:
        size = call(ed, SCENE + 'SetRelativeScale3D', NewScale3D=scale)
        link(component, ip(size, 'self'))
        chain(node, size)
        node = size
    return node


def add_visual_component(ed, tail, variable, mesh_asset, scale, rotation, location, material=None):
    add = call(ed, ACT + 'AddComponentByClass', Class='/Script/Engine.StaticMeshComponent',
               bManualAttachment='false')
    transform = call(ed, MATH + 'MakeTransform', Scale='(X=1,Y=1,Z=1)')
    link(op(transform), ip(add, 'RelativeTransform'))
    chain(tail, add)
    convert = cast(ed, 'StaticMeshComponent')
    link(op(add), ip(convert, 'Object'))
    chain(add, convert)
    cast_info = BT.get_node_infos([convert])[0]
    component = op(convert, next(p.name for p in cast_info.output_pins if p.name.startswith('As')))
    remember = setv(ed, variable)
    link(component, ip(remember, variable))
    chain(convert, remember)
    collision = call(ed, PRIM + 'SetCollisionEnabled', NewType='NoCollision')
    link(component, ip(collision, 'self'))
    chain(remember, collision)
    tail = mesh(ed, collision, component, mesh_asset, scale)
    rotate = call(ed, SCENE + 'K2_SetRelativeRotation', NewRotation=rotation,
                  bSweep='false', bTeleport='true')
    link(component, ip(rotate, 'self'))
    chain(tail, rotate)
    move = call(ed, SCENE + 'K2_SetRelativeLocation', NewLocation=location,
                bSweep='false', bTeleport='true')
    link(component, ip(move, 'self'))
    chain(rotate, move)
    tail = move
    if material:
        mat = call(ed, '/Script/Engine.PrimitiveComponent.SetMaterial', ElementIndex=0,
                   Material=material + '.' + material.rsplit('/', 1)[1])
        link(component, ip(mat, 'self'))
        chain(tail, mat)
        tail = mat
    return tail, component


def configure_gun(gun):
    ed = func(gun, 'ConfigureWeapon')
    bounded = call(ed, MATH + 'Clamp', Min=0, Max=3)
    link(op(get(ed, 'WeaponKind'), 'WeaponKind'), ip(bounded, 'Value'))
    kind = setv(ed, 'WeaponKind')
    link(op(bounded), ip(kind, 'WeaponKind'))
    link(ed.find_graph_entry_pin(), kind.find_execute_pin())
    # Preserve the original mesh transform; scale relative to its inspected template.
    template = unreal.load_object(None, GUN + '.BP_Pistol_C:WeaponMesh_GEN_VARIABLE')
    assert isinstance(template, unreal.StaticMeshComponent)
    baseline = template.get_editor_property('relative_scale3d')
    tube = get(ed, 'RocketTube')
    valid = call(ed, SYS + 'IsValid')
    link(op(tube, 'RocketTube'), ip(valid, 'Object'))
    hide_guard = branch(ed, op(valid))
    chain(kind, hide_guard)
    hide = call(ed, SCENE + 'SetVisibility', bNewVisibility='false', bPropagateToChildren='false')
    link(op(tube, 'RocketTube'), ip(hide, 'self'))
    chain(hide_guard, hide)
    weapon = op(get(ed, 'WeaponMesh'), 'WeaponMesh')
    first = None
    previous_else = None
    for index, name in enumerate(['PISTOL', 'SHOTGUN', 'SNIPER', 'RPG']):
        guard = branch(ed, cmp_kind(ed, index))
        if first is None:
            first = guard
        if previous_else is not None:
            link(previous_else, guard.find_execute_pin())
        previous_else = op(guard, 'else')
        label = setv(ed, 'WeaponName', name)
        chain(guard, label)
        factors = [(1, 1, 1), (1.3, 0.78, 1.25), (1, 1, 1), (1.35, 1.05, 1.25)][index]
        scale = '(X=%s,Y=%s,Z=%s)' % (baseline.x * factors[0], baseline.y * factors[1], baseline.z * factors[2])
        tail = mesh(ed, label, weapon, MESHES[index], scale)
        if index == 3:
            tube_call = call(ed, 'ConfigureRocketTube')
            chain(tail, tube_call)
    chain(hide, first)
    link(op(hide_guard, 'else'), first.find_execute_pin())


def configure_rocket_tube(gun):
    ed = func(gun, 'ConfigureRocketTube')
    tube = get(ed, 'RocketTube')
    valid = call(ed, SYS + 'IsValid')
    link(op(tube, 'RocketTube'), ip(valid, 'Object'))
    guard = branch(ed, op(valid))
    link(ed.find_graph_entry_pin(), guard.find_execute_pin())
    show = call(ed, SCENE + 'SetVisibility', bNewVisibility='true', bPropagateToChildren='false')
    link(op(tube, 'RocketTube'), ip(show, 'self'))
    chain(guard, show)
    # A launcher tube assembled from an existing engine mesh; no new content asset.
    class ElseTail:
        def find_then_pin(self):
            return op(guard, 'else')
    tail, component = add_visual_component(ed, ElseTail(), 'RocketTube', '/Engine/BasicShapes/Cylinder',
                                          '(X=0.2,Y=0.2,Z=1.25)', '(Pitch=0,Yaw=0,Roll=90)',
                                          '(X=0,Y=45,Z=18)', '/Game/Weapons/Pistol/M_PistolCasing')
    attach = call(ed, SCENE + 'K2_AttachToComponent', SocketName='None',
                  LocationRule='KeepRelative', RotationRule='KeepRelative', ScaleRule='KeepRelative',
                  bWeldSimulatedBodies='false')
    link(component, ip(attach, 'self'))
    link(op(get(ed, 'WeaponMesh'), 'WeaponMesh'), ip(attach, 'Parent'))
    chain(tail, attach)


def copy_projectile_settings(ed, tail, projectile, gun, bullet):
    for name in ['WeaponKind', 'PistolRange', 'ShotgunRange', 'SniperRange', 'BlastRadius', 'RocketSpeed', 'RocketRange']:
        setting = get(ed, name)
        target = setv(ed, name, cls=bullet.generated_class().get_path_name())
        link(op(setting, name), ip(target, name))
        link(projectile, ip(target, 'self'))
        chain(tail, target)
        tail = target
    configure = call(ed, bullet.generated_class().get_path_name() + ':ConfigureProjectile')
    link(projectile, ip(configure, 'self'))
    chain(tail, configure)
    return configure


def shotgun(gun, bullet):
    ed = func(gun, 'ResolveShotgun')
    count = call(ed, MATH + 'Clamp', Min=3, Max=15)
    link(op(get(ed, 'ShotgunPelletCount'), 'ShotgunPelletCount'), ip(count, 'Value'))
    last = call(ed, MATH + 'Subtract_IntInt', B=1)
    link(op(count), ip(last, 'A'))
    middle = call(ed, MATH + 'Divide_IntInt', B=2)
    link(op(count), ip(middle, 'A'))
    loop = ed.add_macro_node('/Engine/EditorBlueprintResources/StandardMacros.StandardMacros.ForLoop')
    assert loop
    val(loop, 'FirstIndex', 0)
    link(op(last), ip(loop, 'LastIndex'))
    link(ed.find_graph_entry_pin(), ip(loop, 'execute'))
    extra = call(ed, MATH + 'NotEqual_IntInt')
    link(op(loop, 'Index'), ip(extra, 'A'))
    link(op(middle), ip(extra, 'B'))
    guard = branch(ed, op(extra))
    link(op(loop, 'LoopBody'), guard.find_execute_pin())
    # Existing primary bullet is the centre pellet; six additional pellets by default.
    index = call(ed, MATH + 'Conv_IntToDouble')
    link(op(loop, 'Index'), ip(index, 'InInt'))
    denom = call(ed, MATH + 'Conv_IntToDouble')
    link(op(last), ip(denom, 'InInt'))
    normalized = call(ed, MATH + 'Divide_DoubleDouble')
    link(op(index), ip(normalized, 'A'))
    link(op(denom), ip(normalized, 'B'))
    twice = call(ed, MATH + 'Multiply_DoubleDouble', B=2)
    link(op(normalized), ip(twice, 'A'))
    signed = call(ed, MATH + 'Subtract_DoubleDouble', B=1)
    link(op(twice), ip(signed, 'A'))
    angle = call(ed, MATH + 'Multiply_DoubleDouble')
    link(op(signed), ip(angle, 'A'))
    spread = call(ed, MATH + 'FClamp', Min=1, Max=40)
    link(op(get(ed, 'ShotgunSpread'), 'ShotgunSpread'), ip(spread, 'Value'))
    link(op(spread), ip(angle, 'B'))
    offset = call(ed, MATH + 'MakeRotator')
    link(op(angle), ip(offset, 'Yaw'))
    rotation = call(ed, MATH + 'ComposeRotators')
    link(op(get(ed, 'ShotRotation'), 'ShotRotation'), ip(rotation, 'A'))
    link(op(offset), ip(rotation, 'B'))
    trans = transform(ed, op(get(ed, 'ShotOrigin'), 'ShotOrigin'), op(rotation))
    finish, spawned = spawn(ed, BULLET, trans, guard, selfpin(ed))
    convert = cast(ed, 'BP_BulletProjectile')
    link(spawned, ip(convert, 'Object'))
    chain(finish, convert)
    copy_projectile_settings(ed, convert, op(convert, 'AsBP Bullet Projectile'), gun, bullet)


def sniper(gun, bullet):
    ed = func(gun, 'ResolveSniper')
    instigator = call(ed, ACT + 'GetInstigator')
    owner = call(ed, ACT + 'GetOwner')
    initial = make_array(ed, [op(owner), selfpin(ed), op(instigator)])
    ignored = setv(ed, 'SniperIgnored')
    link(initial, ip(ignored, 'SniperIgnored'))
    link(ed.find_graph_entry_pin(), ignored.find_execute_pin())
    origin = op(get(ed, 'ShotOrigin'), 'ShotOrigin')
    forward = call(ed, MATH + 'GetForwardVector')
    link(op(get(ed, 'ShotRotation'), 'ShotRotation'), ip(forward, 'InRot'))
    range_limit = call(ed, MATH + 'FClamp', Min=650, Max=12000)
    link(op(get(ed, 'SniperRange'), 'SniperRange'), ip(range_limit, 'Value'))
    vector = call(ed, MATH + 'Multiply_VectorFloat')
    link(op(forward), ip(vector, 'A'))
    link(op(range_limit), ip(vector, 'B'))
    end = call(ed, MATH + 'Add_VectorVector')
    link(origin, ip(end, 'A'))
    link(op(vector), ip(end, 'B'))
    visual_end = setv(ed, 'SniperVisualEnd')
    link(op(end), ip(visual_end, 'SniperVisualEnd'))
    chain(ignored, visual_end)
    count = call(ed, MATH + 'Clamp', Min=1, Max=32)
    link(op(get(ed, 'SniperMaxHits'), 'SniperMaxHits'), ip(count, 'Value'))
    last = call(ed, MATH + 'Subtract_IntInt', B=1)
    link(op(count), ip(last, 'A'))
    loop = ed.add_macro_node('/Engine/EditorBlueprintResources/StandardMacros.StandardMacros.ForLoopWithBreak')
    assert loop
    val(loop, 'FirstIndex', 0)
    link(op(last), ip(loop, 'LastIndex'))
    chain(visual_end, loop)
    trace = call(ed, SYS + 'LineTraceSingle', TraceChannel='TraceTypeQuery1', bTraceComplex='false',
                 DrawDebugType='None', bIgnoreSelf='true')
    link(origin, ip(trace, 'Start'))
    link(op(end), ip(trace, 'End'))
    link(op(get(ed, 'SniperIgnored'), 'SniperIgnored'), ip(trace, 'ActorsToIgnore'))
    link(op(loop, 'LoopBody'), trace.find_execute_pin())
    hit = branch(ed, op(trace))
    chain(trace, hit)
    link(op(hit, 'else'), ip(loop, 'Break'))
    result = call(ed, GAME + 'BreakHitResult')
    link(op(trace, 'OutHit'), ip(result, 'Hit'))
    enemy = cast(ed, 'BP_EnemyStraightRunner')
    link(op(result, 'HitActor'), ip(enemy, 'Object'))
    chain(hit, enemy)
    die = call(ed, unreal.load_asset(ENEMY).generated_class().get_path_name() + ':Die')
    link(op(enemy, 'AsBP Enemy Straight Runner'), ip(die, 'self'))
    chain(enemy, die)
    add = call(ed, ARRAY + 'Array_AddUnique')
    link(op(get(ed, 'SniperIgnored'), 'SniperIgnored'), ip(add, 'TargetArray'))
    link(op(result, 'HitActor'), ip(add, 'NewItem'))
    chain(die, add)
    impact_transform = transform(ed, op(result, 'ImpactPoint'))
    spawn(ed, BITS, impact_transform, add)
    wall = setv(ed, 'SniperVisualEnd')
    link(op(result, 'ImpactPoint'), ip(wall, 'SniperVisualEnd'))
    link(op(enemy, 'CastFailed'), wall.find_execute_pin())
    link(wall.find_then_pin(), ip(loop, 'Break'))
    # Stop the cosmetic tracer where the wall stopped the penetrating shot.
    distance = call(ed, MATH + 'Vector_Distance')
    link(origin, ip(distance, 'V1'))
    link(op(get(ed, 'SniperVisualEnd'), 'SniperVisualEnd'), ip(distance, 'V2'))
    travel = call(ed, MATH + 'Divide_DoubleDouble', B=14000)
    link(op(distance), ip(travel, 'A'))
    bounded = call(ed, MATH + 'FClamp', Min=0.02, Max=1)
    link(op(travel), ip(bounded, 'Value'))
    life = call(ed, ACT + 'SetLifeSpan')
    link(op(get(ed, 'ShotProjectile'), 'ShotProjectile'), ip(life, 'self'))
    link(op(bounded), ip(life, 'InLifespan'))
    link(op(loop, 'Completed'), life.find_execute_pin())


def resolve_gun(gun, bullet):
    ed = func(gun, 'ResolveWeaponShot')
    projectile = op(get(ed, 'ShotProjectile'), 'ShotProjectile')
    class Entry:
        def find_then_pin(self):
            return ed.find_graph_entry_pin()
    tail = copy_projectile_settings(ed, Entry(), projectile, gun, bullet)
    shotgun_guard = branch(ed, cmp_kind(ed, 1))
    chain(tail, shotgun_guard)
    sg = call(ed, 'ResolveShotgun')
    chain(shotgun_guard, sg)
    sniper_guard = branch(ed, cmp_kind(ed, 2))
    link(op(shotgun_guard, 'else'), sniper_guard.find_execute_pin())
    sn = call(ed, 'ResolveSniper')
    chain(sniper_guard, sn)


def configure_bullet(bullet):
    ed = func(bullet, 'ConfigureProjectile')
    ignore = call(ed, PRIM + 'IgnoreActorWhenMoving', bShouldIgnore='true')
    link(op(get(ed, 'Collision'), 'Collision'), ip(ignore, 'self'))
    link(op(call(ed, GAME + 'GetPlayerPawn', PlayerIndex=0)), ip(ignore, 'Actor'))
    link(ed.find_graph_entry_pin(), ignore.find_execute_pin())
    previous_else = None
    for index, range_name, speed in [(0, 'PistolRange', 2200), (1, 'ShotgunRange', 2200),
                                   (2, 'SniperRange', 14000), (3, 'RocketRange', None)]:
        guard = branch(ed, cmp_kind(ed, index))
        if previous_else is None:
            chain(ignore, guard)
        else:
            link(previous_else, guard.find_execute_pin())
        previous_else = op(guard, 'else')
        set_speed = setv(ed, 'ProjectileSpeed', speed if speed else None)
        if speed is None:
            clamp_speed = call(ed, MATH + 'FClamp', Min=400, Max=4000)
            link(op(get(ed, 'RocketSpeed'), 'RocketSpeed'), ip(clamp_speed, 'Value'))
            link(op(clamp_speed), ip(set_speed, 'ProjectileSpeed'))
        chain(guard, set_speed)
        movement = op(get(ed, 'ProjectileMovement'), 'ProjectileMovement')
        maximum = setv(ed, 'MaxSpeed', cls='/Script/Engine.ProjectileMovementComponent')
        link(movement, ip(maximum, 'self'))
        speed_get = op(get(ed, 'ProjectileSpeed'), 'ProjectileSpeed')
        link(speed_get, ip(maximum, 'MaxSpeed'))
        chain(set_speed, maximum)
        velocity = call(ed, MATH + 'MakeVector')
        link(speed_get, ip(velocity, 'X'))
        move = call(ed, '/Script/Engine.ProjectileMovementComponent.SetVelocityInLocalSpace')
        link(movement, ip(move, 'self'))
        link(op(velocity), ip(move, 'NewVelocity'))
        chain(maximum, move)
        tail = move
        if index == 2:
            no_collision = call(ed, ACT + 'SetActorEnableCollision', bNewActorEnableCollision='false')
            chain(tail, no_collision)
            tail = no_collision
        bounded_range = call(ed, MATH + 'FClamp', Min=100, Max=12000)
        link(op(get(ed, range_name), range_name), ip(bounded_range, 'Value'))
        duration = call(ed, MATH + 'Divide_DoubleDouble')
        link(op(bounded_range), ip(duration, 'A'))
        link(speed_get, ip(duration, 'B'))
        if index == 3:
            expiry = timer(ed, 'Detonate', op(duration))
            chain(tail, expiry)
            extra = call(ed, MATH + 'Subtract_DoubleDouble', B=-0.4)
            link(op(duration), ip(extra, 'A'))
            life_input = op(extra)
            tail = expiry
        else:
            life_input = op(duration)
        life = call(ed, ACT + 'SetLifeSpan')
        link(life_input, ip(life, 'InLifespan'))
        chain(tail, life)


def detonate(bullet):
    ed = func(bullet, 'Detonate')
    not_done = call(ed, MATH + 'Not_PreBool')
    link(op(get(ed, 'ExplosionDone'), 'ExplosionDone'), ip(not_done, 'A'))
    guard = branch(ed, op(not_done))
    link(ed.find_graph_entry_pin(), guard.find_execute_pin())
    done = setv(ed, 'ExplosionDone', 'true')
    chain(guard, done)
    no_collision = call(ed, ACT + 'SetActorEnableCollision', bNewActorEnableCollision='false')
    chain(done, no_collision)
    stop = call(ed, '/Script/Engine.MovementComponent.StopMovementImmediately')
    link(op(get(ed, 'ProjectileMovement'), 'ProjectileMovement'), ip(stop, 'self'))
    chain(no_collision, stop)
    # Engine radial damage handles unique actors and Visibility-channel cover.
    radius = call(ed, MATH + 'FClamp', Min=100, Max=1000)
    link(op(get(ed, 'BlastRadius'), 'BlastRadius'), ip(radius, 'Value'))
    origin = call(ed, ACT + 'K2_GetActorLocation')
    instigator = call(ed, ACT + 'GetInstigator')
    owner = call(ed, ACT + 'GetOwner')
    player = call(ed, GAME + 'GetPlayerPawn', PlayerIndex=0)
    ignored = make_array(ed, [op(owner), selfpin(ed), op(instigator), op(player)])
    damage = call(ed, GAME + 'ApplyRadialDamage', BaseDamage=100, bDoFullDamage='true',
                  DamagePreventionChannel='ECC_Visibility')
    link(op(origin), ip(damage, 'Origin'))
    link(op(radius), ip(damage, 'DamageRadius'))
    link(ignored, ip(damage, 'IgnoreActors'))
    link(selfpin(ed), ip(damage, 'DamageCauser'))
    controller = call(ed, ACT + 'GetInstigatorController')
    link(op(controller), ip(damage, 'InstigatedByController'))
    chain(stop, damage)
    trans = transform(ed, op(origin), scale='(X=3,Y=3,Z=3)')
    bits, _ = spawn(ed, BITS, trans, damage)
    stamp = setv(ed, 'ExplosionStartTime')
    link(op(call(ed, SYS + 'GetGameTimeInSeconds')), ip(stamp, 'ExplosionStartTime'))
    chain(bits, stamp)
    tail, component = add_visual_component(ed, stamp, 'ExplosionSphere', '/Engine/BasicShapes/Sphere',
                                          '(X=0.1,Y=0.1,Z=0.1)', '(Pitch=0,Yaw=0,Roll=0)',
                                          '(X=0,Y=0,Z=0)', '/Game/Weapons/Pistol/M_PistolCasing')
    update = timer(ed, 'UpdateExplosionVisual', time=0.02, looping=True)
    chain(tail, update)
    # Prevent inherited projectile lifespan from expiring before this short effect.
    life = call(ed, ACT + 'SetLifeSpan', InLifespan=0.22)
    chain(update, life)
    ed = func(bullet, 'UpdateExplosionVisual')
    now = call(ed, SYS + 'GetGameTimeInSeconds')
    elapsed = call(ed, MATH + 'Subtract_DoubleDouble')
    link(op(now), ip(elapsed, 'A'))
    link(op(get(ed, 'ExplosionStartTime'), 'ExplosionStartTime'), ip(elapsed, 'B'))
    duration = call(ed, MATH + 'Divide_DoubleDouble', B=0.18)
    link(op(elapsed), ip(duration, 'A'))
    alpha = call(ed, MATH + 'FClamp', Min=0.01, Max=1)
    link(op(duration), ip(alpha, 'Value'))
    size = call(ed, MATH + 'Multiply_DoubleDouble')
    link(op(alpha), ip(size, 'A'))
    world_scale = call(ed, MATH + 'Divide_DoubleDouble', B=50)
    link(op(get(ed, 'BlastRadius'), 'BlastRadius'), ip(world_scale, 'A'))
    link(op(world_scale), ip(size, 'B'))
    vector = call(ed, MATH + 'MakeVector')
    for name in ['X', 'Y', 'Z']:
        link(op(size), ip(vector, name))
    scale = call(ed, SCENE + 'SetRelativeScale3D')
    link(op(get(ed, 'ExplosionSphere'), 'ExplosionSphere'), ip(scale, 'self'))
    link(op(vector), ip(scale, 'NewScale3D'))
    link(ed.find_graph_entry_pin(), scale.find_execute_pin())


def hook_existing(gun, bullet):
    fire = unreal.BlueprintGraphEditor.get_graph_editor_by_name(gun, 'Fire')
    # Delete only previously generated integration nodes; rebuild owned functions.
    titles = {'|ConfigureWeapon', '|ResolveWeaponShot', '|SetShotProjectile', '|SetShotOrigin', '|SetShotRotation'}
    fire.remove_nodes([i.node for i in BT.get_node_infos(list(fire.list_all_nodes())) if i.type_id in titles])
    nodes = {n.get_name(): n for n in fire.list_all_nodes()}
    entry = fire.find_graph_entry_pin()
    entry.break_pin_links()
    configure = call(fire, 'ConfigureWeapon')
    link(entry, configure.find_execute_pin())
    chain(configure, nodes['K2Node_IfThenElse_0'])
    good_spawn = nodes['K2Node_IfThenElse_3']
    good_spawn.find_then_pin().break_pin_links()
    projectile = setv(fire, 'ShotProjectile')
    link(op(nodes['K2Node_SpawnActorFromClass_1']), ip(projectile, 'ShotProjectile'))
    chain(good_spawn, projectile)
    origin = setv(fire, 'ShotOrigin')
    link(op(nodes['K2Node_CallFunction_9']), ip(origin, 'ShotOrigin'))
    chain(projectile, origin)
    rotation = setv(fire, 'ShotRotation')
    link(op(nodes['K2Node_CallFunction_10']), ip(rotation, 'ShotRotation'))
    chain(origin, rotation)
    resolve = call(fire, 'ResolveWeaponShot')
    chain(rotation, resolve)
    chain(resolve, nodes['K2Node_VariableSet_0'])
    events = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bullet, 'EventGraph')
    # Named helper functions make these two original event gates idempotent.
    baseline_file = Path(unreal.Paths.project_saved_dir()) / 'WeaponEventsBaseline.json'
    if not baseline_file.exists():
        baseline_file.write_text(json.dumps([n.get_name() for n in events.list_all_nodes()]), encoding='utf-8')
    original_nodes = set(json.loads(baseline_file.read_text(encoding='utf-8')))
    events.remove_nodes([n for n in events.list_all_nodes() if n.get_name() not in original_nodes])
    before = {n.get_name() for n in events.list_all_nodes()}
    ns = {n.get_name(): n for n in events.list_all_nodes()}
    ns['K2Node_ComponentBoundEvent_0'].find_then_pin().break_pin_links()
    hit = call(events, 'HandleWeaponHit')
    chain(ns['K2Node_ComponentBoundEvent_0'], hit)
    # Original on-hit starts with ActorHasTag; retain every original feedback node.
    gate = branch(events, cmp_kind(events, 3))
    chain(hit, gate)
    boom = call(events, 'Detonate')
    chain(gate, boom)
    link(op(gate, 'else'), ns['K2Node_IfThenElse_0'].find_execute_pin())
    enemy_cast = ns['K2Node_DynamicCast_1']
    enemy_cast.find_then_pin().break_pin_links()
    overlap = call(events, 'HandleEnemyOverlap')
    chain(enemy_cast, overlap)
    overlap_gate = branch(events, cmp_kind(events, 3))
    chain(overlap, overlap_gate)
    overlap_boom = call(events, 'Detonate')
    chain(overlap_gate, overlap_boom)
    link(op(overlap_gate, 'else'), ns['K2Node_CallFunction_16'].find_execute_pin())


def inspect_muzzles():
    """Keep original sockets, author missing mesh sockets from verified mesh bounds."""
    source = unreal.load_asset(MESHES[0])
    pistol_muzzle = source.find_socket('Muzzle')
    assert pistol_muzzle, 'The inspected pistol must retain its existing Muzzle socket'
    reference = pistol_muzzle.get_editor_property('relative_location')
    axis = 'x' if abs(reference.x) > abs(reference.y) else 'y'
    direction = 1 if getattr(reference, axis) >= 0 else -1
    changed = []
    sockets = {}
    for path in sorted(set(MESHES)):
        asset = unreal.load_asset(path)
        socket = asset.find_socket('Muzzle')
        if socket is None:
            bounds = asset.get_bounding_box()
            minimum, maximum = bounds.min, bounds.max
            center = (minimum + maximum) * 0.5
            location = unreal.Vector(center.x, center.y, minimum.z + (maximum.z - minimum.z) * 0.78)
            setattr(location, axis, getattr(maximum if direction > 0 else minimum, axis) + direction)
            socket = unreal.new_object(unreal.StaticMeshSocket, outer=asset, name='Muzzle')
            socket.set_editor_property('socket_name', 'Muzzle')
            socket.set_editor_property('relative_location', location)
            socket.set_editor_property('relative_rotation', unreal.Rotator())
            socket.set_editor_property('relative_scale', unreal.Vector(1, 1, 1))
            asset.add_socket(socket)
            assert asset.find_socket('Muzzle')
            changed.append(asset)
        sockets[path] = str(socket.get_editor_property('relative_location'))
    return changed, sockets


def implement():
    checkpoint('load verified assets')
    gun = unreal.load_asset(GUN)
    bullet = unreal.load_asset(BULLET)
    assert gun and bullet and unreal.load_asset(ENEMY) and unreal.load_asset(BITS)
    for asset in MESHES + ['/Engine/BasicShapes/Cylinder', '/Engine/BasicShapes/Sphere']:
        assert unreal.load_asset(asset), asset
    checkpoint('inspect muzzle sockets')
    changed_meshes, muzzle_sockets = inspect_muzzles()
    checkpoint('declare weapon role variables')
    for bp in [gun, bullet]:
        for name, kind, default, editable in [
            ('WeaponKind', 'int', 0, True), ('PistolRange', 'float', 1800.0, True),
            ('ShotgunRange', 'float', 650.0, True),
            ('SniperRange', 'float', 4500.0, True), ('BlastRadius', 'float', 450.0, True),
            ('RocketSpeed', 'float', 1200.0, True), ('RocketRange', 'float', 3200.0, True)]:
            var(bp, name, kind, default, editable)
    for name, kind, default, editable in [
        ('WeaponName', 'string', 'PISTOL', False), ('ShotgunSpread', 'float', 20.0, True),
        ('ShotgunPelletCount', 'int', 7, True), ('SniperMaxHits', 'int', 8, True),
        ('ShotOrigin', 'Vector', unreal.Vector(), False),
        ('ShotRotation', 'Rotator', unreal.Rotator(), False),
        ('SniperVisualEnd', 'Vector', unreal.Vector(), False)]:
        var(gun, name, kind, default, editable)
    for name, kind, default in [('ExplosionDone', 'bool', False), ('ExplosionStartTime', 'float', 0.0)]:
        var(bullet, name, kind, default)
    objvar(gun, 'ShotProjectile', bullet.generated_class())
    objvar(gun, 'SniperIgnored', unreal.Actor.static_class(), True)
    objvar(gun, 'RocketTube', unreal.StaticMeshComponent.static_class())
    objvar(bullet, 'ExplosionSphere', unreal.StaticMeshComponent.static_class())
    # Declare all cross-called functions before compiling their call nodes.
    checkpoint('declare shared Blueprint functions')
    for bp, names in [(gun, ['ConfigureWeapon', 'ConfigureRocketTube', 'ResolveWeaponShot', 'ResolveShotgun', 'ResolveSniper']),
                      (bullet, ['ConfigureProjectile', 'Detonate', 'UpdateExplosionVisual', 'HandleWeaponHit', 'HandleEnemyOverlap'])]:
        for name in names:
            func(bp, name)
        compile_blueprint(bp, True)
    checkpoint('author launcher visual tube')
    configure_rocket_tube(gun)
    checkpoint('author weapon mesh configuration')
    configure_gun(gun)
    checkpoint('author projectile role configuration')
    configure_bullet(bullet)
    checkpoint('author radial blast and visible explosion')
    detonate(bullet)
    checkpoint('compile projectile functions')
    compile_blueprint(bullet, True)
    checkpoint('author shotgun pellet spread')
    shotgun(gun, bullet)
    checkpoint('author penetrating sniper trace')
    sniper(gun, bullet)
    checkpoint('author shared shot dispatch')
    resolve_gun(gun, bullet)
    checkpoint('compile weapon functions')
    compile_blueprint(gun, True)
    checkpoint('connect existing Fire and impact events')
    hook_existing(gun, bullet)
    checkpoint('compile connected projectile and weapon graphs')
    compile_blueprint(bullet, True)
    compile_blueprint(gun, True)
    checkpoint('save verified assets')
    for bp in [bullet, gun] + changed_meshes:
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False), bp.get_path_name()
    return {'saved': [bp.get_path_name() for bp in [bullet, gun] + changed_meshes],
            'verified_muzzles': muzzle_sockets,
            'roles': {'0': 'Pistol: existing single projectile, 1800 cm',
                      '1': 'Shotgun: 7 total pellets, +/-20 degrees, 650 cm',
                      '2': 'Sniper: 4500 cm penetrating trace, 8 enemies, wall stop',
                      '3': 'RPG: 450 cm blast, Visibility cover, unique radial damage'},
            'integration': 'Set WeaponKind then call ConfigureWeapon. Enemy AnyDamage must call Die.',
            'ammo': 'Fire() preserved; existing successful-shot path consumes Ammo exactly once.'}


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
handle = [None]


def checkpoint(stage):
    unreal.log('OLS_WEAPON_ROLE_STAGE ' + stage)
    (Path(unreal.Paths.project_saved_dir()) / 'WeaponRolesImplementation.json').write_text(
        json.dumps({'status': 'running', 'stage': stage}, indent=2), encoding='utf-8')


def after_pie(dt):
    if les.is_in_play_in_editor():
        return
    unreal.unregister_slate_post_tick_callback(handle[0])
    try:
        checkpoint('begin editor-only implementation')
        result = implement()
    except Exception:
        result = {'error': traceback.format_exc()}
        unreal.log_error(result['error'])
    (Path(unreal.Paths.project_saved_dir()) / 'WeaponRolesImplementation.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')


handle[0] = unreal.register_slate_post_tick_callback(after_pie)
les.editor_request_end_play()
