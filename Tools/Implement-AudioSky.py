"""Import requested audio and patch existing Blueprint feedback in UE 5.8."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

PACK = Path('C:/Users/user/Downloads/FREE FPS SFX Pack')
BGM_SOURCE = Path('C:/Users/user/Downloads/freesound_community-014815_building-tension-56926.mp3')
GUN = '/Game/Weapons/Pistol/BP_Pistol'
ENEMY = '/Game/Enemies/BP_EnemyStraightRunner'
BULLET = '/Game/Weapons/Pistol/BP_BulletProjectile'
PICKUP = '/Game/Weapons/Pistol/BP_PistolPickup'
CHAR = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter'
SFX_DIR = '/Game/Weapons/Pistol/Audio'
BGM_PATH = '/Game/ThirdPerson/Audio/SW_BuildingTension'
SOURCES = {
    'SW_PistolShot': ('GrapplingHook_Shot-001.wav', .6, 1.5),
    'SW_ShotgunShot': ('Shotgun_Shot-001.wav', .7, 1.0),
    'SW_SniperShot': ('Sniper_Shot-001.wav', .65, 1.0),
    'SW_RocketShot': ('Rocket_Shot-001.wav', .65, 1.0),
    'SW_RocketExplosion': ('Rocket_Explosion-001.wav', .7, 1.0),
    'SW_WeaponPickup': ('Rocket_Equip.wav', .5, 1.0),
    'SW_RobotDeath': ('Enemy_Robot_Death-001.wav', .45, 1.0),
    'SW_AttackWarning': ('Player_Warning.wav', .35, 1.0),
    'SW_PlayerDeath': ('Computer Crashing.wav', .55, 1.0),
}

def editor(bp, name):
    return unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, name)

def sound_path(name):
    return f'{SFX_DIR}/{name}.{name}'

def import_wave(source, path, volume, pitch=1.0, loop=False):
    assert source.is_file(), source
    wave = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if wave is None:
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', str(source))
        task.set_editor_property('destination_path', path.rsplit('/', 1)[0])
        task.set_editor_property('destination_name', path.rsplit('/', 1)[1])
        task.set_editor_property('automated', True)
        task.set_editor_property('save', True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        wave = unreal.load_asset(path)
    assert isinstance(wave, unreal.SoundWave), path
    wave.modify()
    wave.set_editor_property('looping', loop)
    wave.set_editor_property('volume', volume)
    wave.set_editor_property('pitch', pitch)
    assert wave.get_editor_property('duration') > 0, path
    assert unreal.EditorAssetLibrary.save_loaded_asset(wave, False)
    return wave

def add_feedback(bp, graph, anchor, name):
    ed = editor(bp, graph)
    path = sound_path(name)
    infos = BT.get_node_infos(list(ed.list_all_nodes()))
    if any(any(p.name == 'Sound' and path in p.value for p in i.input_pins) for i in infos):
        return
    targets = [i.node for i in infos if anchor(i)]
    assert len(targets) == 1, (bp.get_name(), graph, len(targets))
    sound = call(ed, GAME + 'PlaySound2D', Sound=path, bIsUISound='false')
    insert_after(ed, targets[0], sound)

def set_true(name):
    return lambda i: any(p.name == name and p.value == 'true' for p in i.input_pins) and 'Set' in i.type_id

def work():
    assets = [unreal.load_asset(p) for p in (GUN, ENEMY, BULLET, PICKUP, CHAR)]
    assert all(assets)
    # Inspect registered content and reveal the existing owners before importing.
    unreal.EditorAssetLibrary.sync_browser_to_objects([a.get_path_name() for a in assets])
    bgm = import_wave(BGM_SOURCE, BGM_PATH, .22, loop=True)
    for name, (source, volume, pitch) in SOURCES.items():
        import_wave(PACK / source, f'{SFX_DIR}/{name}', volume, pitch)
    gun, enemy, bullet, pickup, char = assets
    ed = editor(gun, 'ConfigureWeapon')
    infos = BT.get_node_infos(list(ed.list_all_nodes()))
    for weapon, name in zip(('PISTOL', 'SHOTGUN', 'SNIPER', 'RPG'),
                            ('SW_PistolShot', 'SW_ShotgunShot', 'SW_SniperShot', 'SW_RocketShot')):
        # Reuse FireSound and the existing successful-shot sound node.
        matches = [i.node for i in infos if any(p.name == 'WeaponName' and p.value == weapon for p in i.input_pins)]
        assert len(matches) == 1, weapon
        if not any(any(p.name == 'FireSound' and sound_path(name) in p.value for p in i.input_pins) for i in infos):
            insert_after(ed, matches[0], setv(ed, 'FireSound', sound_path(name)))
    unreal.get_default_object(gun.generated_class()).set_editor_property('FireSound', unreal.load_asset(sound_path('SW_PistolShot')))
    add_feedback(enemy, 'Die', set_true('Dead'), 'SW_RobotDeath')
    add_feedback(pickup, 'TryAcquire', set_true('Consumed'), 'SW_WeaponPickup')
    add_feedback(char, 'EventGraph', set_true('Dead'), 'SW_PlayerDeath')
    add_feedback(bullet, 'BeginExplosionFeedback', lambda i: any(p.name == 'bNewVisibility' and p.value == 'false' for p in i.input_pins), 'SW_RocketExplosion')
    for graph, show in [('BeginChargeWarning', 'ShowAttackLine'), ('BeginBlastWarning', 'ShowBlastZone'), ('BeginSniperWarning', 'ShowAttackLine')]:
        add_feedback(enemy, graph, lambda i, show=show: show in i.type_id, 'SW_AttackWarning')
    for bp in assets:
        compile_blueprint(bp, True)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    for path in ('/Game/Enemies/BP_EnemyRunnerFast', '/Game/Enemies/BP_EnemyRunnerSlow', '/Game/Enemies/BP_EnemySniper'):
        compile_blueprint(unreal.load_asset(path), True)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(subsystem.get_all_level_actors())
    background = [a for a in actors if a.get_actor_label() == 'SM_SkySphere' or isinstance(a, (unreal.SkyAtmosphere, unreal.VolumetricCloud, unreal.ExponentialHeightFog))]
    assert background
    for actor in background:
        actor.modify()
        actor.set_actor_hidden_in_game(True)
        actor.set_editor_property('hidden', True)
        for component in actor.get_components_by_class(unreal.SceneComponent):
            component.modify()
            component.set_visibility(False, True)
            component.set_hidden_in_game(True, True)
    # Real-time sky capture requires an atmosphere; keep the existing light
    # using its fixed capture when the visible atmosphere is disabled.
    for actor in actors:
        if isinstance(actor, unreal.SkyLight):
            actor.modify()
            light = actor.get_component_by_class(unreal.SkyLightComponent)
            light.modify()
            light.set_editor_property('real_time_capture', False)
    matches = [a for a in actors if a.get_actor_label() == 'BGM_BuildingTension']
    assert len(matches) <= 1
    music = matches[0] if matches else subsystem.spawn_actor_from_class(unreal.AmbientSound, unreal.Vector())
    music.modify()
    music.set_actor_label('BGM_BuildingTension')
    music.set_folder_path('Audio')
    component = music.get_component_by_class(unreal.AudioComponent)
    component.modify()
    component.set_sound(bgm)
    component.set_editor_property('auto_activate', True)
    component.set_editor_property('allow_spatialization', False)
    component.set_editor_property('is_ui_sound', True)
    component.set_editor_property('override_attenuation', False)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    return {'assets': [a.get_path_name() for a in assets], 'sounds': list(SOURCES) + [BGM_PATH],
            'hidden_background': [a.get_actor_label() for a in background],
            'bgm': music.get_path_name(), 'saved': True,
            'pistol_source': 'Pack has no pistol shot; pitched grappling shot reused as sci-fi pistol'}

run_editor(work, 'AudioSkyImplementation.json')
