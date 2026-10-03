"""Polish the existing RPG impact without rebuilding its damage/impact flow.

This source is safe to import. Root runs work() serially inside Unreal Editor
after authoring the inspected shared M_AttackTelegraph material.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

BULLET = '/Game/Weapons/Pistol/BP_BulletProjectile'
FIELD = '/Game/Enemies/Materials/M_AttackTelegraph'
TRACER = '/Game/Weapons/Pistol/M_BulletTracer'
PLANE = '/Engine/BasicShapes/Plane'
SCENE = '/Script/Engine.SceneComponent.'
PRIMITIVE = '/Script/Engine.PrimitiveComponent.'
MESH = '/Script/Engine.MeshComponent.'


def v(ed, name):
    return out(get(ed, name), name)


def binary(ed, function, a, b):
    node = call(ed, MATH + function)
    for name, source in [('A', a), ('B', b)]:
        if hasattr(source, 'is_valid'):
            link(source, inp(node, name))
        else:
            # Connecting a typed scalar also avoids VectorFloat wildcard
            # promotion treating a numeric default as a vector.
            literal = call(ed, SYS + 'MakeLiteralDouble', Value=source)
            link(out(literal), inp(node, name))
    return out(node)


def bounded(ed, value, minimum, maximum):
    node = call(ed, MATH + 'FClamp', Min=minimum, Max=maximum)
    link(value, inp(node, 'Value'))
    return out(node)


def component_call(ed, path, component, **values):
    node = call(ed, path, **values)
    link(v(ed, component), inp(node, 'self'))
    return node


def visibility(ed, component, visible):
    return component_call(ed, SCENE + 'SetVisibility', component,
                          bNewVisibility='true' if visible else 'false',
                          bPropagateToChildren='false')


def scalar(ed, component, name, value):
    node = component_call(ed, MESH + 'SetScalarParameterValueOnMaterials',
                          component, ParameterName=name)
    if hasattr(value, 'is_valid'):
        link(value, inp(node, 'ParameterValue'))
    else:
        val(node, 'ParameterValue', value)
    return node


def vector_scale(ed, component, xy, z=None):
    vector = call(ed, MATH + 'MakeVector')
    for axis, source in [('X', xy), ('Y', xy), ('Z', xy if z is None else z)]:
        if hasattr(source, 'is_valid'):
            link(source, inp(vector, axis))
        else:
            val(vector, axis, source)
    node = component_call(ed, SCENE + 'SetWorldScale3D', component)
    link(out(vector), inp(node, 'NewScale'))
    return node


def ground_position(ed):
    """Use impact XY and the current player's foot plane, not projectile Z."""
    impact = call(ed, ACT + 'K2_GetActorLocation')
    xy = call(ed, MATH + 'BreakVector')
    link(out(impact), inp(xy, 'InVec'))
    player = call(ed, GAME + 'GetPlayerCharacter', PlayerIndex=0)
    location = call(ed, ACT + 'K2_GetActorLocation')
    link(out(player), inp(location, 'self'))
    coordinates = call(ed, MATH + 'BreakVector')
    link(out(location), inp(coordinates, 'InVec'))
    capsule = call(ed, ACT + 'GetComponentByClass',
                   ComponentClass='/Script/Engine.CapsuleComponent')
    link(out(player), inp(capsule, 'self'))
    height = call(ed, '/Script/Engine.CapsuleComponent.GetScaledCapsuleHalfHeight')
    link(out(capsule), inp(height, 'self'))
    floor = binary(ed, 'Add_DoubleDouble',
                   binary(ed, 'Subtract_DoubleDouble', out(coordinates, 'Z'), out(height)),
                   3.0)
    position = call(ed, MATH + 'MakeVector')
    link(out(xy, 'X'), inp(position, 'X'))
    link(out(xy, 'Y'), inp(position, 'Y'))
    link(floor, inp(position, 'Z'))
    return out(position)


def append_flare(ed, tail):
    """Add a collision-free impact plane facing the actual fixed game camera."""
    add = call(ed, ACT + 'AddComponentByClass',
               Class='/Script/Engine.StaticMeshComponent', bManualAttachment='true')
    transform = call(ed, MATH + 'MakeTransform',
                     Scale='(X=1,Y=1,Z=1)', Rotation='0, 0, 0')
    link(out(transform), inp(add, 'RelativeTransform'))
    chain(tail, add)
    convert = ed.create_node_from_name('Utilities|Casting|CastToStaticMeshComponent',
                                      unreal.Vector2D(), [])
    assert convert, 'StaticMeshComponent flare cast is unavailable'
    link(out(add), inp(convert, 'Object'))
    chain(add, convert)
    info = BT.get_node_infos([convert])[0]
    component = out(convert, next(p.name for p in info.output_pins if p.name.startswith('As')))
    remember = setv(ed, 'ExplosionFlare')
    link(component, inp(remember, 'ExplosionFlare'))
    chain(convert, remember)
    collision = component_call(ed, PRIMITIVE + 'SetCollisionEnabled',
                               'ExplosionFlare', NewType='NoCollision')
    chain(remember, collision)
    mesh = component_call(ed, '/Script/Engine.StaticMeshComponent.SetStaticMesh',
                          'ExplosionFlare', NewMesh=PLANE + '.Plane')
    chain(collision, mesh)
    material = component_call(ed, PRIMITIVE + 'SetMaterial', 'ExplosionFlare',
                              ElementIndex=0, Material=FIELD + '.M_AttackTelegraph')
    chain(mesh, material)
    absolute = component_call(ed, SCENE + 'SetAbsolute', 'ExplosionFlare',
                              bNewAbsoluteLocation='true', bNewAbsoluteRotation='true',
                              bNewAbsoluteScale='true')
    chain(material, absolute)
    impact = out(call(ed, ACT + 'K2_GetActorLocation'))
    position = component_call(ed, SCENE + 'K2_SetWorldLocation', 'ExplosionFlare',
                              bSweep='false', bTeleport='true')
    link(impact, inp(position, 'NewLocation'))
    chain(absolute, position)
    camera = call(ed, GAME + 'GetPlayerCameraManager', PlayerIndex=0)
    camera_location = call(ed, '/Script/Engine.PlayerCameraManager.GetCameraLocation')
    link(out(camera), inp(camera_location, 'self'))
    camera_rotation = call(ed, '/Script/Engine.PlayerCameraManager.GetCameraRotation')
    link(out(camera), inp(camera_rotation, 'self'))
    right = call(ed, MATH + 'GetRightVector')
    link(out(camera_rotation), inp(right, 'InRot'))
    facing = call(ed, MATH + 'MakeRotFromZX')
    link(binary(ed, 'Subtract_VectorVector', out(camera_location), impact), inp(facing, 'Z'))
    link(out(right), inp(facing, 'X'))
    rotation = component_call(ed, SCENE + 'K2_SetWorldRotation', 'ExplosionFlare',
                              bSweep='false', bTeleport='true')
    link(out(facing), inp(rotation, 'NewRotation'))
    chain(position, rotation)
    scale = vector_scale(ed, 'ExplosionFlare',
                         binary(ed, 'Divide_DoubleDouble', v(ed, 'ExplosionFlareRadius'), 50.0), 1.0)
    chain(rotation, scale)
    shadow = component_call(ed, PRIMITIVE + 'SetCastShadow', 'ExplosionFlare',
                            NewCastShadow='false')
    chain(scale, shadow)
    color = component_call(ed, MESH + 'SetVectorParameterValueOnMaterials',
                           'ExplosionFlare', ParameterName='TracerColor',
                           ParameterValue='(X=1,Y=0.30,Z=0.03)')
    chain(shadow, color)
    mode = scalar(ed, 'ExplosionFlare', 'ShapeMode', 3.0)
    chain(color, mode)
    progress = scalar(ed, 'ExplosionFlare', 'EffectProgress', 0.0)
    chain(mode, progress)
    opacity = scalar(ed, 'ExplosionFlare', 'Opacity', 0.95)
    chain(progress, opacity)
    show = visibility(ed, 'ExplosionFlare', True)
    chain(opacity, show)
    return show


def build_begin(bp):
    ed = func(bp, 'BeginExplosionFeedback')
    hide_tracer = visibility(ed, 'Tracer', False)
    link(ed.find_graph_entry_pin(), hide_tracer.find_execute_pin())
    core_color = component_call(ed, MESH + 'SetVectorParameterValueOnMaterials',
                                'ExplosionSphere', ParameterName='TracerColor',
                                ParameterValue='(X=3,Y=0.9,Z=0.08)')
    chain(hide_tracer, core_color)
    core_scale = vector_scale(ed, 'ExplosionSphere',
                              binary(ed, 'Divide_DoubleDouble', v(ed, 'ExplosionCoreRadius'), 50.0))
    chain(core_color, core_scale)
    core_shadow = component_call(ed, PRIMITIVE + 'SetCastShadow',
                                 'ExplosionSphere', NewCastShadow='false')
    chain(core_scale, core_shadow)

    add = call(ed, ACT + 'AddComponentByClass',
               Class='/Script/Engine.StaticMeshComponent', bManualAttachment='true')
    transform = call(ed, MATH + 'MakeTransform',
                     Scale='(X=1,Y=1,Z=1)', Rotation='0, 0, 0')
    link(out(transform), inp(add, 'RelativeTransform'))
    chain(core_shadow, add)
    convert = ed.create_node_from_name('Utilities|Casting|CastToStaticMeshComponent',
                                      unreal.Vector2D(), [])
    assert convert, 'StaticMeshComponent cast is unavailable'
    link(out(add), inp(convert, 'Object'))
    chain(add, convert)
    info = BT.get_node_infos([convert])[0]
    component = out(convert, next(p.name for p in info.output_pins if p.name.startswith('As')))
    remember = setv(ed, 'ExplosionRing')
    link(component, inp(remember, 'ExplosionRing'))
    chain(convert, remember)
    collision = component_call(ed, PRIMITIVE + 'SetCollisionEnabled',
                               'ExplosionRing', NewType='NoCollision')
    chain(remember, collision)
    mesh = component_call(ed, '/Script/Engine.StaticMeshComponent.SetStaticMesh',
                          'ExplosionRing', NewMesh=PLANE + '.Plane')
    chain(collision, mesh)
    material = component_call(ed, PRIMITIVE + 'SetMaterial', 'ExplosionRing',
                              ElementIndex=0, Material=FIELD + '.M_AttackTelegraph')
    chain(mesh, material)
    absolute = component_call(ed, SCENE + 'SetAbsolute', 'ExplosionRing',
                              bNewAbsoluteLocation='true', bNewAbsoluteRotation='true',
                              bNewAbsoluteScale='true')
    chain(material, absolute)
    position = component_call(ed, SCENE + 'K2_SetWorldLocation', 'ExplosionRing',
                              bSweep='false', bTeleport='true')
    link(ground_position(ed), inp(position, 'NewLocation'))
    chain(absolute, position)
    rotation = component_call(ed, SCENE + 'K2_SetWorldRotation', 'ExplosionRing',
                              NewRotation='0, 0, 0', bSweep='false', bTeleport='true')
    chain(position, rotation)
    # Match ApplyRadialDamage's existing safety clamp exactly.
    radius = bounded(ed, v(ed, 'BlastRadius'), 100.0, 1000.0)
    scale = vector_scale(ed, 'ExplosionRing', binary(ed, 'Divide_DoubleDouble', radius, 50.0), 1.0)
    chain(rotation, scale)
    shadow = component_call(ed, PRIMITIVE + 'SetCastShadow', 'ExplosionRing',
                            NewCastShadow='false')
    chain(scale, shadow)
    color = component_call(ed, MESH + 'SetVectorParameterValueOnMaterials',
                           'ExplosionRing', ParameterName='TracerColor',
                           ParameterValue='(X=1,Y=0.36,Z=0.045)')
    chain(shadow, color)
    mode = scalar(ed, 'ExplosionRing', 'ShapeMode', 2.0)
    chain(color, mode)
    progress = scalar(ed, 'ExplosionRing', 'EffectProgress', 0.0)
    chain(mode, progress)
    opacity = scalar(ed, 'ExplosionRing', 'Opacity', 0.95)
    chain(progress, opacity)
    show = visibility(ed, 'ExplosionRing', True)
    chain(opacity, show)
    append_flare(ed, show)


def build_update(bp):
    ed = func(bp, 'UpdateExplosionVisual')
    now = out(call(ed, SYS + 'GetGameTimeInSeconds'))
    elapsed = binary(ed, 'Subtract_DoubleDouble', now, v(ed, 'ExplosionStartTime'))
    duration = bounded(ed, v(ed, 'ExplosionVisualDuration'), 0.08, 1.0)
    progress = bounded(ed, binary(ed, 'Divide_DoubleDouble', elapsed, duration), 0.0, 1.0)
    ring = scalar(ed, 'ExplosionRing', 'EffectProgress', progress)
    link(ed.find_graph_entry_pin(), ring.find_execute_pin())
    flare = scalar(ed, 'ExplosionFlare', 'EffectProgress', progress)
    chain(ring, flare)
    core_time = bounded(ed, v(ed, 'ExplosionCoreDuration'), 0.01, 0.15)
    core_expired = branch(ed, binary(ed, 'GreaterEqual_DoubleDouble', elapsed, core_time))
    chain(flare, core_expired)
    hide = visibility(ed, 'ExplosionSphere', False)
    chain(core_expired, hide)
    core_progress = bounded(ed, binary(ed, 'Divide_DoubleDouble', elapsed, core_time), 0.0, 1.0)
    core_factor = binary(ed, 'Subtract_DoubleDouble', 1.0,
                         binary(ed, 'Multiply_DoubleDouble', core_progress, 0.3))
    core_scale = vector_scale(ed, 'ExplosionSphere',
                              binary(ed, 'Multiply_DoubleDouble',
                                     binary(ed, 'Divide_DoubleDouble', v(ed, 'ExplosionCoreRadius'), 50.0),
                                     core_factor))
    link(out(core_expired, 'else'), core_scale.find_execute_pin())
    done = branch(ed, binary(ed, 'GreaterEqual_DoubleDouble', elapsed, duration))
    chain(hide, done)
    chain(core_scale, done)
    hide_ring = visibility(ed, 'ExplosionRing', False)
    chain(done, hide_ring)
    hide_core = visibility(ed, 'ExplosionSphere', False)
    chain(hide_ring, hide_core)
    hide_flare = visibility(ed, 'ExplosionFlare', False)
    chain(hide_core, hide_flare)
    clear = call(ed, SYS + 'K2_ClearTimer', FunctionName='UpdateExplosionVisual')
    link(selfpin(ed), inp(clear, 'Object'))
    chain(hide_flare, clear)


def damage_snapshot(ed):
    """Assert the damage node/pins survive this cosmetic-only authoring."""
    nodes = [i for i in BT.get_node_infos(list(ed.list_all_nodes()))
             if i.type_id.endswith('|ApplyRadialDamage')]
    assert len(nodes) == 1, 'Expected one existing RPG radial damage node'
    info = nodes[0]
    return {'node': info.node.get_name(),
            'pins': [(p.name, p.value,
                      [(q.get_owning_node().get_name(), str(q.get_pin_name()))
                       for q in inp(info.node, p.name).list_connected_pins()])
                     for p in info.input_pins]}


def work():
    bp = unreal.load_asset(BULLET)
    assert bp and unreal.load_asset(FIELD) and unreal.load_asset(TRACER) and unreal.load_asset(PLANE)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'Detonate')
    original_damage = damage_snapshot(ed)
    names = {str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)}
    for name in ['ExplosionRing', 'ExplosionFlare']:
        if name not in names:
            BT.add_object_variable(bp, name, unreal.StaticMeshComponent.static_class())
    for name, value in [('ExplosionVisualDuration', 0.35), ('ExplosionCoreDuration', 0.07),
                        ('ExplosionCoreRadius', 70.0), ('ExplosionFlareRadius', 160.0)]:
        var(bp, name, 'float', value, editable=True)
        unreal.BlueprintEditorLibrary.set_blueprint_variable_category(bp, name, 'RPG Feedback')
    if 'BeginExplosionFeedback' not in [g.get_name() for g in unreal.BlueprintEditorLibrary.list_graphs(bp)]:
        BT.add_function_graph(bp, 'BeginExplosionFeedback')
    compile_blueprint(bp, True)
    build_begin(bp)
    build_update(bp)
    compile_blueprint(bp, True)

    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'Detonate')
    nodes = {n.get_name(): n for n in ed.list_all_nodes()}
    material = nodes['K2Node_CallFunction_93']
    val(material, 'Material', TRACER + '.M_BulletTracer')
    if not any(i.type_id == '|BeginExplosionFeedback' for i in BT.get_node_infos(list(ed.list_all_nodes()))):
        begin = call(ed, bp.generated_class().get_path_name() + ':BeginExplosionFeedback')
        insert_after(ed, material, begin)
    # Tuned default lifespan is 0.42s; keep cleanup valid when duration changes.
    life = nodes['K2Node_CallFunction_95']
    inp(life, 'InLifespan').break_pin_links()
    duration = bounded(ed, v(ed, 'ExplosionVisualDuration'), 0.08, 1.0)
    link(binary(ed, 'Add_DoubleDouble', duration, 0.07), inp(life, 'InLifespan'))
    assert damage_snapshot(ed) == original_damage, 'RPG damage changed during cosmetic authoring'
    compile_blueprint(bp, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False), BULLET
    return {'saved': [BULLET], 'damage_preserved': True,
            'visual_duration': 0.35, 'core_duration': 0.07, 'core_radius': 70.0,
            'flare_radius': 160.0, 'flare_shape_mode': 3.0,
            'flare_orientation': 'Impact plane normal faces actual game camera; local X follows camera right',
            'flare_timing': 'Shared EffectProgress drives shader fade; all components hide at visual duration',
            'lifespan_default': 0.42, 'shared_material': FIELD,
            'collision': 'unchanged damage; collision-free core/ring/flare; hidden tracer'}


if __name__ == '__main__':
    run_editor(work, 'RPGFeedbackAuthoring.json')
