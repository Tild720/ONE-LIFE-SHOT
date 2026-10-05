"""Declare the shared pickup/player fields before the role graphs are authored."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    character = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')
    for name, kind, default, editable in [
        ('NextWeaponKind', 'int', 0, False), ('Dodging', 'bool', False, False),
        ('DodgeCooling', 'bool', False, False), ('DodgeSpeed', 'float', 1100.0, True),
        ('DodgeDuration', 'float', 0.18, True), ('DodgeCooldown', 'float', 1.0, True)]:
        var(character, name, kind, default, editable)
    hud = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_AmmoHUD')
    var(hud, 'WeaponLabel', 'string', 'NO WEAPON', True)
    pickup = unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup')
    var(pickup, 'WeaponKind', 'int', 0, True)
    for bp in [character, hud, pickup]:
        compile_blueprint(bp, True)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    return {'prepared': [bp.get_path_name() for bp in [character, hud, pickup]]}

run_editor(work, 'CombatPreparation.json')
