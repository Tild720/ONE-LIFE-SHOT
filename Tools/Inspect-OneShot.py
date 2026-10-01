"""Temporary MCP-triggered editor inspection; never part of gameplay."""
import json
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools


def inspect_editor():
    paths = ['/Game/Weapons/Pistol/BP_PistolPickup',
             '/Game/Enemies/BP_EnemyStraightRunner',
             '/Game/Enemies/BP_EnemySpawnPoint',
             '/Game/Runner/BP_RunnerProgress',
             '/Game/ThirdPerson/Blueprints/BP_AmmoHUD',
             '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter']
    result = {}
    for path in paths:
        bp = unreal.load_asset(path)
        if not bp:
            continue
        graphs = {}
        for graph in unreal.BlueprintEditorLibrary.list_graphs(bp):
            ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
            nodes = []
            for info in BlueprintTools.get_node_infos(list(ed.list_all_nodes())):
                def pin(p):
                    return {'name': p.name, 'value': p.value, 'type': p.type_id,
                            'links': [str(x.node.get_name()) + ':' + str(x.index_id)
                                      for x in p.connected_pins]}
                nodes.append({'name': info.node.get_name(), 'title': info.type_id,
                              'in': [pin(p) for p in info.input_pins],
                              'out': [pin(p) for p in info.output_pins]})
            graphs[graph.get_name()] = nodes
        cdo = unreal.get_default_object(bp.generated_class())
        result[path] = {'graphs': graphs, 'defaults': {
            str(n): str(cdo.get_editor_property(str(n))) for n in
            unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)}}
    result['actors'] = [{'label': a.get_actor_label(), 'path': a.get_path_name(),
                         'class': a.get_class().get_path_name(),
                         'pos': str(a.get_actor_location())}
                        for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()]
    dest = Path(unreal.Paths.project_saved_dir()) / 'OneShotInspection.json'
    dest.write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('ONE LIFE SHOT inspection complete')


les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
handle = [None]


def tick(dt):
    if les.is_in_play_in_editor():
        return
    unreal.unregister_slate_post_tick_callback(handle[0])
    try:
        inspect_editor()
    except Exception as error:
        unreal.log_error(str(error))


handle[0] = unreal.register_slate_post_tick_callback(tick)
les.editor_request_end_play()
