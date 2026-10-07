"""Check the viewport path that routes every uncaptured mouse press to gameplay."""
import json
import sys
from pathlib import Path
import unreal
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import BT

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world, 'Start PIE before checking production mouse capture'
controller = unreal.GameplayStatics.get_player_controller(world, 0)
hud = controller.get_hud()
expected = unreal.MouseCaptureMode.CAPTURE_PERMANENTLY_INCLUDING_INITIAL_MOUSE_DOWN
checks = {}
states = {}
bp = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')
ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'EventGraph')
infos = BT.get_node_infos(list(ed.list_all_nodes()))
fire = [i.node for i in infos if i.type_id.endswith('EnhancedInputActionIA_Fire')]
assert len(fire) == 1
checks['one_press_dispatches_once'] = len(fire[0].find_output_pin('Started').list_connected_pins()) == 1
checks['held_button_does_not_spend_the_reserve'] = not fire[0].find_output_pin('Triggered').list_connected_pins()
for name in ('ShowStart', 'StartGame', 'ShowPause', 'StartGame'):
    hud.call_method(name)
    mode = unreal.GameplayStatics.get_viewport_mouse_capture_mode(world)
    key = name + '_' + str(len(states))
    states[key] = str(mode)
    checks[key + '_routes_first_mouse_down'] = mode == expected
pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
gun = pawn.get_editor_property('EquippedPistol')
report = {'passed': all(checks.values()), 'checks': checks, 'capture_modes': states,
          'cursor_visible': controller.get_editor_property('bShowMouseCursor'),
          'ammo': gun.get_editor_property('Ammo') if gun else None,
          'weapon': gun.get_path_name() if gun else None}
(Path(unreal.Paths.project_saved_dir()) / 'ClickCaptureTest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
assert report['passed'], 'GameOnly must not discard each uncaptured single mouse press'
