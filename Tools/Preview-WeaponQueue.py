"""Disposable frozen visual preview, using real pickup/Fire to fill the HUD."""
import builtins
import json
import runpy
import time
from pathlib import Path
import unreal

root = Path(__file__).resolve().parents[1]
builtins._ols_facility_preview_y = 1320
runpy.run_path(str(root / 'Tools/Preview-Facility.py'), run_name='__main__')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
controller = unreal.GameplayStatics.get_player_controller(world, 0)
system = unreal.get_default_object(unreal.SystemLibrary.static_class())
statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
maths = unreal.get_default_object(unreal.MathLibrary.static_class())
pickup_class = unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup').generated_class()
start = time.monotonic()
stage = [0]
handle = [None]
snapshots = []

def aim():
    point = unreal.GameplayStatics.project_world_to_screen(controller, pawn.get_actor_location() + unreal.Vector(0, 500, -92.25))
    assert point
    controller.set_mouse_location(round(point.x), round(point.y))

def pickup(kind):
    transform = maths.call_method('MakeTransform', args=(pawn.get_actor_location(), unreal.Rotator(), unreal.Vector(1, 1, 1)))
    scale = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
    actor = statics.call_method('BeginDeferredActorSpawnFromClass', args=(world, pickup_class, transform,
        unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, scale))
    actor.set_editor_property('WeaponKind', kind)
    statics.call_method('FinishSpawningActor', args=(actor, transform, scale))
    actor.call_method('TryAcquire')

def frame(name):
    builtins._ols_frame_name = name
    runpy.run_path(str(root / 'Tools/Capture-FacilityFrame.py'), run_name='__main__')
    gun = pawn.get_editor_property('EquippedPistol')
    snapshots.append({'frame': name, 'current': int(gun.get_editor_property('WeaponKind')) if gun and unreal.SystemLibrary.is_valid(gun) else None,
                      'reserve': int(pawn.get_editor_property('QueuedWeaponKind'))})

def sample(_dt):
    age = time.monotonic() - start
    if stage[0] == 0 and age > .35:
        aim()
        stage[0] = 1
    elif stage[0] == 1 and age > .60:
        # Spend startup weapons through Fire; never manufacture ammo/queue state.
        for _ in range(2):
            gun = pawn.get_editor_property('EquippedPistol')
            if gun and unreal.SystemLibrary.is_valid(gun):
                gun.call_method('Fire')
        pickup(1)
        pickup(2)
        stage[0] = 2
    elif stage[0] == 2 and age > 1.0:
        frame('WeaponQueueLoaded')
        aim()
        stage[0] = 3
    elif stage[0] == 3 and age > 1.6:
        pawn.get_editor_property('EquippedPistol').call_method('Fire')
        stage[0] = 4
    elif stage[0] == 4 and age > 2.2:
        frame('WeaponQueuePromoted')
        aim()
        stage[0] = 5
    elif stage[0] == 5 and age > 2.8:
        pawn.get_editor_property('EquippedPistol').call_method('Fire')
        stage[0] = 6
    elif stage[0] == 6 and age > 3.4:
        frame('WeaponQueueEmpty')
        unreal.unregister_slate_post_tick_callback(handle[0])
        hud = controller.get_hud()
        report = {'preview_only': True, 'runtime_threats_frozen': True,
                  'inventory_source': 'Production TryAcquire and Fire',
                  'captures': ['WeaponQueueLoaded.png', 'WeaponQueuePromoted.png', 'WeaponQueueEmpty.png'],
                  'slots_per_capture': snapshots,
                  'final_reserve': int(pawn.get_editor_property('QueuedWeaponKind')),
                  'hud': {n: str(hud.get_editor_property(n)) for n in ['WeaponLabel', 'AmmoLabel', 'ReserveWeaponLabel']}}
        (Path(unreal.Paths.project_saved_dir()) / 'WeaponQueuePreview.json').write_text(json.dumps(report, indent=2))

handle[0] = unreal.register_slate_post_tick_callback(sample)
