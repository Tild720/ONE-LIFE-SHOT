"""Read-only editor acceptance and graph inventory for audio/black sky."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

GRAPHS = {
    '/Game/Weapons/Pistol/BP_Pistol': ['Fire', 'ConfigureWeapon'],
    '/Game/Weapons/Pistol/BP_BulletProjectile': ['Detonate', 'BeginExplosionFeedback'],
    '/Game/Weapons/Pistol/BP_PistolPickup': ['TryAcquire'],
    '/Game/Enemies/BP_EnemyStraightRunner': ['Die', 'BeginChargeWarning', 'BeginBlastWarning', 'BeginSniperWarning'],
    '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter': ['EventGraph'],
}

def work():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    audio = [{'path': str(a.package_name), 'class': str(a.asset_class_path.asset_name)}
             for a in registry.get_assets_by_path('/Game', True)
             if 'Sound' in str(a.asset_class_path.asset_name)]
    graphs = {}
    for path, names in GRAPHS.items():
        bp = unreal.load_asset(path)
        available = {g.get_name() for g in unreal.BlueprintEditorLibrary.list_graphs(bp)}
        for name in names:
            if name not in available:
                continue
            ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, name)
            rows = []
            for i in BT.get_node_infos(list(ed.list_all_nodes())):
                rows.append({'node': i.node.get_name(), 'type': i.type_id,
                             'inputs': [(p.name, p.value) for p in i.input_pins],
                             'outputs': [(p.name, [str(x) for x in i.node.find_output_pin(p.name).list_connected_pins()]) for p in i.output_pins]})
            graphs[path + ':' + name] = rows
    actors = []
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if any(s in a.get_class().get_name().lower() + a.get_actor_label().lower()
               for s in ('sky', 'fog', 'cloud', 'audio', 'sound', 'atmosphere', 'light')):
            row = {'label': a.get_actor_label(), 'class': a.get_class().get_name(),
                   'hidden': a.get_editor_property('hidden')}
            c = a.get_component_by_class(unreal.AudioComponent)
            if c:
                sound = c.get_editor_property('sound')
                row.update(sound=sound.get_path_name() if sound else None,
                           auto_activate=c.get_editor_property('auto_activate'),
                           is_ui_sound=c.get_editor_property('is_ui_sound'))
            if isinstance(a, unreal.SkyLight):
                row['real_time_capture'] = a.get_component_by_class(unreal.SkyLightComponent).get_editor_property('real_time_capture')
            actors.append(row)
    bgm = [a for a in actors if a['label'] == 'BGM_BuildingTension']
    def feedback(path, graph):
        return sum('PlaySound' in n['type'].replace(' ', '') for n in graphs.get(path + ':' + graph, [])) == 1
    checks = {'bgm_present': len(bgm) == 1,
              'black_sky': not any(not a['hidden'] and any(s in (a['class'] + a['label']).lower() for s in ('skyatmosphere', 'volumetriccloud', 'exponentialheightfog', 'skysphere')) for a in actors),
              'weapon_sound': any('SetFireSound' in n['type'] for n in graphs.get('/Game/Weapons/Pistol/BP_Pistol:ConfigureWeapon', [])),
              'enemy_death_sound': feedback('/Game/Enemies/BP_EnemyStraightRunner', 'Die'),
              'pickup_sound_once': feedback('/Game/Weapons/Pistol/BP_PistolPickup', 'TryAcquire'),
              'player_death_sound_once': feedback('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter', 'EventGraph'),
              'explosion_sound_once': feedback('/Game/Weapons/Pistol/BP_BulletProjectile', 'BeginExplosionFeedback')}
    for graph in ('BeginChargeWarning', 'BeginBlastWarning', 'BeginSniperWarning'):
        checks[graph + '_sound_once'] = feedback('/Game/Enemies/BP_EnemyStraightRunner', graph)
    config = graphs['/Game/Weapons/Pistol/BP_Pistol:ConfigureWeapon']
    checks['four_weapon_sounds'] = sum('SetFireSound' in n['type'] for n in config) == 4
    if bgm and bgm[0].get('sound'):
        wave = unreal.load_asset(bgm[0]['sound'])
        checks['bgm_looping'] = bool(wave.get_editor_property('looping'))
        checks['bgm_auto_activate'] = bgm[0]['auto_activate']
        checks['bgm_plays_in_menus'] = bgm[0]['is_ui_sound']
        checks['no_atmosphere_capture_warning'] = all(not a.get('real_time_capture') for a in actors if a['class'] == 'SkyLight')
        bgm[0]['duration'] = wave.get_editor_property('duration')
    return {'passed': all(checks.values()), 'checks': checks, 'audio': audio, 'actors': actors, 'graphs': graphs}

def run_runtime():
    import time
    import builtins
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world
    unreal.SystemLibrary.execute_console_command(world, 'au.DisableAppVolume 1')
    report = {'checks': {}, 'max_playback_percent': 0.0, 'passed': False}
    output = Path(unreal.Paths.project_saved_dir()) / 'AudioSkyRuntimeTest.json'
    output.write_text(json.dumps(report, indent=2))
    checks = report['checks']
    sounds = [a.get_component_by_class(unreal.AudioComponent)
              for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.AmbientSound)]
    music = [c for c in sounds if c.get_editor_property('sound') and 'SW_BuildingTension' in c.get_editor_property('sound').get_path_name()]
    assert len(music) == 1, music
    component = music[0]
    checks['bgm_started_automatically'] = component.is_playing()
    checks['bgm_non_spatial'] = not component.get_editor_property('allow_spatialization')
    def percent(_wave, value):
        report['max_playback_percent'] = max(report['max_playback_percent'], float(value))
    component.on_audio_playback_percent.add_callable(percent)
    # Seek only this test instance near the end to verify a real loop cheaply.
    component.play(component.get_editor_property('sound').get_editor_property('duration') - .5)
    cls = unreal.load_asset('/Game/Weapons/Pistol/BP_Pistol').generated_class()
    statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
    maths = unreal.get_default_object(unreal.MathLibrary.static_class())
    transform = maths.call_method('MakeTransform', args=(unreal.Vector(20000, 20000, 20000), unreal.Rotator(), unreal.Vector(1, 1, 1)))
    fixture = statics.call_method('BeginDeferredActorSpawnFromClass', args=(world, cls, transform, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    statics.call_method('FinishSpawningActor', args=(fixture, transform, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    for kind, expected in enumerate(('SW_PistolShot', 'SW_ShotgunShot', 'SW_SniperShot', 'SW_RocketShot')):
        fixture.set_editor_property('WeaponKind', kind)
        fixture.call_method('ConfigureWeapon')
        checks[expected + '_selected'] = expected in fixture.get_editor_property('FireSound').get_path_name()
    fixture.destroy_actor()
    start = time.monotonic()
    state = {'handle': None}
    builtins._ols_audio_runtime_qa = state
    def tick(_dt):
        elapsed = time.monotonic() - start
        report['elapsed'] = elapsed
        if not unreal.SystemLibrary.is_valid(component):
            unreal.unregister_slate_post_tick_callback(state['handle'])
            state['handle'] = None
            report['complete'] = True
            report['error'] = 'PIE ended before the audio check completed'
            output.write_text(json.dumps(report, indent=2))
            return
        if report['max_playback_percent'] > 1.01 or elapsed > 15:
            checks['bgm_crossed_loop_boundary'] = report['max_playback_percent'] > 1.01
            checks['bgm_still_playing'] = component.is_playing()
            component.set_pitch_multiplier(1.0)
            component.play(0.0)
            unreal.SystemLibrary.execute_console_command(world, 'au.DisableAppVolume 0')
            component.on_audio_playback_percent.remove_callable(percent)
            unreal.unregister_slate_post_tick_callback(state['handle'])
            state['handle'] = None
            report['passed'] = all(checks.values())
            report['complete'] = True
        if report.get('complete'):
            output.write_text(json.dumps(report, indent=2))
    state['handle'] = unreal.register_slate_post_tick_callback(tick)

command = json.loads((Path(unreal.Paths.project_saved_dir()) / 'EditorCommand.json').read_text(encoding='utf-8'))
if command.get('audio_cleanup'):
    import builtins
    state = builtins.__dict__.pop('_ols_audio_runtime_qa', None)
    if state and state.get('handle'):
        unreal.unregister_slate_post_tick_callback(state['handle'])
    if hasattr(builtins, '_ols_old_background_throttle'):
        perf = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
        perf.set_editor_property('bThrottleCPUWhenNotForeground', builtins._ols_old_background_throttle)
        del builtins._ols_old_background_throttle
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    unreal.SystemLibrary.execute_console_command(world, 'au.DisableAppVolume 0')
    if command.get('start_game') and world:
        unreal.GameplayStatics.get_player_controller(world, 0).get_hud().call_method('StartGame')
    cls = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class()
    report = {'runtime_callback_stopped': True, 'enemies': len(unreal.GameplayStatics.get_all_actors_of_class(world, cls)) if world else None}
    (Path(unreal.Paths.project_saved_dir()) / 'AudioQACleanup.json').write_text(json.dumps(report))
elif unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
    run_runtime()
else:
    run_editor(work, 'AudioSkyTest.json')
