"""Normalize enemy query bodies without changing combat damage or timing.

Author through Unreal Editor only. The shared appearance initialization also
repairs inherited and placed component overrides in every gameplay spawn.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

PATHS = [
    '/Game/Enemies/BP_EnemyStraightRunner',
    '/Game/Enemies/BP_EnemyRunnerFast',
    '/Game/Enemies/BP_EnemyRunnerSlow',
    '/Game/Enemies/BP_EnemySniper',
]
PRIMITIVE = '/Script/Engine.PrimitiveComponent.'


def normalization_prefix(editor):
    """Match the four setters at the entry, including their actual targets."""
    infos = BT.get_node_infos(list(editor.list_all_nodes()))
    by_path = {info.node.get_path_name(): info for info in infos}
    entry = next(info for info in infos if isinstance(info.node, unreal.K2Node_FunctionEntry))
    successors = next(pin.connected_pins for pin in entry.output_pins if pin.name == 'then')
    expected = [
        ('SetCollisionResponseToChannel', 'CapsuleComponent', {'Channel': 'ECC_Visibility', 'NewResponse': 'ECR_Block'}),
        ('SetCollisionResponseToChannel', 'CapsuleComponent', {'Channel': 'ECC_Camera', 'NewResponse': 'ECR_Ignore'}),
        ('SetCollisionEnabled', 'Mesh', {'NewType': 'NoCollision'}),
        ('SetCollisionEnabled', 'TelegraphMesh', {'NewType': 'NoCollision'}),
    ]
    for function, target, values in expected:
        if len(successors) != 1:
            return False
        info = by_path.get(successors[0].node.get_path_name())
        if info is None or info.type_id.rsplit('|', 1)[-1] != function:
            return False
        inputs = {pin.name: pin for pin in info.input_pins}
        if any(name not in inputs or inputs[name].value != value for name, value in values.items()):
            return False
        target_links = inputs['self'].connected_pins
        if len(target_links) != 1:
            return False
        source = by_path.get(target_links[0].node.get_path_name())
        if source is None or not any(pin.name == target for pin in source.output_pins):
            return False
        successors = next(pin.connected_pins for pin in info.output_pins if pin.name == 'then')
    return True


def install_runtime_normalization(blueprint):
    graph = BT.get_graph(blueprint, 'ConfigureEnemyAppearance')
    assert graph, 'Existing shared appearance function is required'
    editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    if normalization_prefix(editor):
        return False
    entry = editor.find_graph_entry_pin()
    following = list(entry.list_connected_pins())
    assert following, 'Appearance function must retain its existing implementation'

    # These native/inherited members are already used by the existing Blueprint.
    capsule = get(editor, 'CapsuleComponent')
    mesh = get(editor, 'Mesh')
    telegraph = get(editor, 'TelegraphMesh')
    visibility = call(editor, PRIMITIVE + 'SetCollisionResponseToChannel',
                      Channel='ECC_Visibility', NewResponse='ECR_Block')
    camera = call(editor, PRIMITIVE + 'SetCollisionResponseToChannel',
                  Channel='ECC_Camera', NewResponse='ECR_Ignore')
    mesh_off = call(editor, PRIMITIVE + 'SetCollisionEnabled', NewType='NoCollision')
    telegraph_off = call(editor, PRIMITIVE + 'SetCollisionEnabled', NewType='NoCollision')
    for node in [visibility, camera]:
        link(out(capsule, 'CapsuleComponent'), inp(node, 'self'))
    link(out(mesh, 'Mesh'), inp(mesh_off, 'self'))
    link(out(telegraph, 'TelegraphMesh'), inp(telegraph_off, 'self'))
    chain(visibility, camera)
    chain(camera, mesh_off)
    chain(mesh_off, telegraph_off)
    # Splice once, preserving every original appearance node and outgoing link.
    entry.break_pin_links()
    link(entry, visibility.find_execute_pin())
    for pin in following:
        link(telegraph_off.find_then_pin(), pin)
    return True


def snapshot(capsule, mesh, telegraph=None):
    result = {
        'visibility': str(capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)),
        'camera': str(capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA)),
        'bullet': str(capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_BULLET)),
        'capsule_enabled': str(capsule.get_collision_enabled()),
        'mesh_enabled': str(mesh.get_collision_enabled()),
    }
    if telegraph is not None:
        result['telegraph_enabled'] = str(telegraph.get_collision_enabled())
    return result


def normalize_actor(actor):
    capsule = actor.get_component_by_class(unreal.CapsuleComponent)
    mesh = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    assert capsule and mesh, actor.get_path_name()
    before_bullet = capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_BULLET)
    before_enabled = capsule.get_collision_enabled()
    capsule.modify()
    mesh.modify()
    capsule.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,
                                              unreal.CollisionResponseType.ECR_BLOCK)
    capsule.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA,
                                              unreal.CollisionResponseType.ECR_IGNORE)
    mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    telegraphs = [component for component in actor.get_components_by_class(unreal.StaticMeshComponent)
                 if component.get_name().split('_GEN_VARIABLE', 1)[0] == 'TelegraphMesh']
    for component in telegraphs:
        component.modify()
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    assert capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY) == unreal.CollisionResponseType.ECR_BLOCK
    assert capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA) == unreal.CollisionResponseType.ECR_IGNORE
    assert capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_BULLET) == before_bullet, 'Bullet response changed'
    assert capsule.get_collision_enabled() == before_enabled, 'Capsule physics mode changed'
    assert mesh.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
    assert all(component.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION for component in telegraphs)
    return snapshot(capsule, mesh, telegraphs[0] if telegraphs else None)


def work():
    assets = [unreal.load_asset(path) for path in PATHS]
    assert all(assets), 'All four existing enemy Blueprints are required'
    base = assets[0]
    inserted = install_runtime_normalization(base)
    # Compile the entire inheritance family first. Obtain fresh native CDO
    # components afterwards so re-instancing cannot discard the written values.
    for blueprint in assets:
        compile_blueprint(blueprint, True)
    editor = unreal.BlueprintGraphEditor.get_graph_editor(BT.get_graph(base, 'ConfigureEnemyAppearance'))
    assert normalization_prefix(editor), 'Shared runtime normalization was not compiled'

    defaults = {}
    template_paths = []
    for blueprint in assets:
        blueprint.modify()
        cdo = unreal.get_default_object(blueprint.generated_class())
        defaults[blueprint.get_path_name()] = normalize_actor(cdo)
        # SCS components are absent from native CDO component enumeration. Use
        # the inspected generated template path; inherited children may have no
        # local template, which is covered by their parent's shared template.
        path = blueprint.generated_class().get_path_name() + ':TelegraphMesh_GEN_VARIABLE'
        template = unreal.load_object(None, path)
        if blueprint == base:
            assert template, 'Existing shared TelegraphMesh template is required'
        if template is not None:
            template.modify()
            template.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            assert template.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
            template_paths.append(template.get_path_name())
        assert unreal.EditorAssetLibrary.save_loaded_asset(blueprint, False)

    placed = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if not unreal.MathLibrary.class_is_child_of(actor.get_class(), base.generated_class()):
            continue
        actor.modify()
        state = normalize_actor(actor)
        placed.append({'actor': actor.get_path_name(), 'label': actor.get_actor_label(), 'collision': state})
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    return {
        'saved': PATHS,
        'runtime_prefix_inserted': inserted,
        'defaults_after_compile': defaults,
        'telegraph_templates': template_paths,
        'placed_enemies': placed,
        'preserved': ['Capsule Bullet response', 'Capsule collision mode', 'Damage and HP',
                      'Weapon math', 'AI timing', 'Existing appearance nodes', 'Telegraph geometry and materials'],
    }


if __name__ == '__main__':
    run_editor(work, 'EnemyQueryCollisionFix.json')
