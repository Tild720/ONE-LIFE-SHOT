"""Editor acceptance for course length, reusable scenery and tuning."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
from editor_toolset.toolsets.actor import ActorTools as AT

def work():
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    labels={a.get_actor_label():a for a in actors}
    checks=[]
    def check(name,passed,actual=None): checks.append({'name':name,'passed':bool(passed),'actual':actual})
    distance=(labels['Runner_EndPoint'].get_actor_location()-labels['Runner_StartPoint'].get_actor_location()).length()
    check('Playable course is 15 times the original 3850 cm',abs(distance-57750)<1,distance)
    check('A single finish platform is placed',sum(a.get_class().get_name()=='BP_ClearPad_C' for a in actors)==1)
    extensions=[a for a in actors if a.get_actor_label()=='Facility_Extension']
    check('Extension uses instanced scenery',bool(extensions) and len(extensions[0].get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent))>0)
    hud=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_AmmoHUD')
    names=[g.get_name() for g in unreal.BlueprintEditorLibrary.list_graphs(hud)]
    check('Start, pause, clear and input paths exist',all(n in names for n in ['StartGame','ShowStart','TogglePause','ClearGame','PollMenuInput','DrawMenus']))
    char=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')
    arm=next(c for c in AT.get_components(unreal.get_default_object(char.generated_class())) if isinstance(c,unreal.SpringArmComponent))
    check('Camera is 1.5 times closer',abs(arm.target_arm_length-1400/1.5)<.1,arm.target_arm_length)
    gun=unreal.get_default_object(unreal.load_asset('/Game/Weapons/Pistol/BP_Pistol').generated_class())
    check('Shot feedback is stronger',gun.get_editor_property('FireShakeScale')>1,gun.get_editor_property('FireShakeScale'))
    spawn=unreal.load_asset('/Game/Enemies/BP_EnemySpawnPoint')
    variables=[str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(spawn,False)]
    check('Forward spawn distance is Editor tunable','SpawnAheadDistance' in variables)
    return {'passed':all(c['passed'] for c in checks),'checks':checks}

run_editor(work,'CourseExpansionTest.json')
