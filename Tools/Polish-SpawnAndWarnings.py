"""Scoped editor authoring: forward spawn windows and readable ground threats."""
import sys
import runpy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

SC = '/Script/Engine.SceneComponent.'
MESH = '/Script/Engine.MeshComponent.'
SPAWNER = '/Game/Enemies/BP_EnemySpawnPoint'
ENEMY = '/Game/Enemies/BP_EnemyStraightRunner'

def v(ed, name): return out(get(ed, name), name)
def binary(ed, fn, a, b):
    n = call(ed, MATH + fn)
    for key, value in [('A', a), ('B', b)]:
        if hasattr(value, 'is_valid'): link(value, inp(n, key))
        elif fn == 'Multiply_VectorFloat' and key == 'B':
            link(out(call(ed, SYS+'MakeLiteralDouble', Value=value)), inp(n, key))
        elif not inp(n, key).set_pin_value(str(value)):
            link(out(call(ed, SYS+'MakeLiteralDouble', Value=value)), inp(n, key))
    return out(n)
def unary(ed, fn, p, name='A'):
    n = call(ed, MATH+fn); link(p, inp(n, name)); return out(n)
def component(ed, path, **values):
    n = call(ed, path, **values); link(v(ed, 'TelegraphMesh'), inp(n, 'self')); return n
def own(ed, bp, name): return call(ed, bp.generated_class().get_path_name()+':'+name)
def location(ed, actor):
    n = call(ed, ACT+'K2_GetActorLocation'); link(actor, inp(n, 'self')); return out(n)
def ground(ed, xy):
    player = out(call(ed, GAME+'GetPlayerCharacter', PlayerIndex=0))
    capsule = call(ed, ACT+'GetComponentByClass', ComponentClass='/Script/Engine.CapsuleComponent')
    link(player, inp(capsule, 'self'))
    height = call(ed, '/Script/Engine.CapsuleComponent.GetScaledCapsuleHalfHeight')
    link(out(capsule), inp(height, 'self'))
    p = call(ed, MATH+'BreakVector'); link(location(ed, player), inp(p, 'InVec'))
    q = call(ed, MATH+'BreakVector'); link(xy, inp(q, 'InVec'))
    z = binary(ed, 'Add_DoubleDouble', binary(ed, 'Subtract_DoubleDouble', out(p,'Z'), out(height)), v(ed,'TelegraphFloorLift'))
    result = call(ed, MATH+'MakeVector')
    for axis, pin in [('X',out(q,'X')),('Y',out(q,'Y')),('Z',z)]: link(pin, inp(result,axis))
    return out(result)

def build_spawn_window(bp):
    for name, kind, default, editable in [
        ('SpawnWindowOpen','bool',False,False), ('SpawnRetired','bool',False,False),
        ('SpawnActivationDistance','float',2200.0,True), ('SpawnMinimumAhead','float',250.0,True)]:
        var(bp,name,kind,default,editable)
        unreal.BlueprintEditorLibrary.set_blueprint_variable_category(bp,name,'Spawn Window')
    ed = func(bp,'UpdateSpawnWindow')
    reset = setv(ed,'SpawnWindowOpen','false'); link(ed.find_graph_entry_pin(),reset.find_execute_pin())
    active = branch(ed,unary(ed,'Not_PreBool',v(ed,'SpawnRetired'))); chain(reset,active)
    player = out(call(ed,GAME+'GetPlayerPawn',PlayerIndex=0))
    # Project along the actual course rather than assuming a world Y direction.
    progress = unreal.load_asset('/Game/Runner/BP_RunnerProgress')
    points=[]
    for name in ['StartPoint','EndPoint']:
        point=get(ed,name,progress.generated_class().get_path_name())
        link(v(ed,'ProgressManager'),inp(point,'self')); points.append(location(ed,out(point,name)))
    direction=unary(ed,'Vector_Normal2D',binary(ed,'Subtract_VectorVector',points[1],points[0]))
    own_location=out(call(ed,ACT+'K2_GetActorLocation'))
    distance=binary(ed,'Dot_VectorVector',binary(ed,'Subtract_VectorVector',own_location,location(ed,player)),direction)
    passed=branch(ed,binary(ed,'LessEqual_DoubleDouble',distance,v(ed,'SpawnMinimumAhead'))); chain(active,passed)
    retire=setv(ed,'SpawnRetired','true'); chain(passed,retire)
    stop=call(ed,SYS+'K2_ClearTimer',FunctionName='SpawnNext'); link(selfpin(ed),inp(stop,'Object')); chain(retire,stop)
    near=branch(ed,binary(ed,'LessEqual_DoubleDouble',distance,v(ed,'SpawnActivationDistance')))
    link(out(passed,'else'),near.find_execute_pin())
    opened=setv(ed,'SpawnWindowOpen','true'); chain(near,opened)
    compile_blueprint(bp,True)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'SpawnNext')
    infos=BT.get_node_infos(list(ed.list_all_nodes()))
    if not any(i.type_id=='|UpdateSpawnWindow' for i in infos):
        source=next(i.node for i in infos if i.node.get_name()=='K2Node_MacroInstance_4')
        pin=out(source,'Is Valid'); following=list(pin.list_connected_pins()); assert following
        pin.break_pin_links()
        update=own(ed,bp,'UpdateSpawnWindow'); link(pin,update.find_execute_pin())
        allowed=branch(ed,v(ed,'SpawnWindowOpen')); chain(update,allowed)
        for p in following: link(allowed.find_then_pin(),p)
    compile_blueprint(bp,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)

def build_field(bp, name, mode):
    ed=func(bp,name)
    scalar=component(ed,MESH+'SetScalarParameterValueOnMaterials',ParameterName='ShapeMode',ParameterValue=mode)
    link(ed.find_graph_entry_pin(),scalar.find_execute_pin())
    alpha=component(ed,MESH+'SetScalarParameterValueOnMaterials',ParameterName='Opacity',ParameterValue=.85); chain(scalar,alpha)
    tint=component(ed,MESH+'SetVectorParameterValueOnMaterials',ParameterName='TracerColor')
    link(v(ed,'BodyTint'),inp(tint,'ParameterValue')); chain(alpha,tint)
    if mode==0:
        half=binary(ed,'Multiply_DoubleDouble',v(ed,'AttackLength'),.5)
        xy=binary(ed,'Add_VectorVector',v(ed,'AttackOrigin'),binary(ed,'Multiply_VectorFloat',v(ed,'AttackDirection'),half))
    else: xy=v(ed,'AttackTarget')
    pos=component(ed,SC+'K2_SetWorldLocation',bSweep='false',bTeleport='true'); link(ground(ed,xy),inp(pos,'NewLocation')); chain(tint,pos)
    rotation=component(ed,SC+'K2_SetWorldRotation',NewRotation='0, 0, 0',bSweep='false',bTeleport='true')
    if mode==0: link(unary(ed,'MakeRotFromX',v(ed,'AttackDirection'),'X'),inp(rotation,'NewRotation'))
    chain(pos,rotation)
    size=call(ed,MATH+'MakeVector',Z=1.0)
    if mode==0:
        link(binary(ed,'Divide_DoubleDouble',v(ed,'AttackLength'),100.0),inp(size,'X'))
        link(binary(ed,'Divide_DoubleDouble',v(ed,'AttackWidth'),50.0),inp(size,'Y'))
    else:
        scale=binary(ed,'Divide_DoubleDouble',v(ed,'BlastRadius'),50.0)
        link(scale,inp(size,'X')); link(scale,inp(size,'Y'))
    scale=component(ed,SC+'SetWorldScale3D'); link(out(size),inp(scale,'NewScale')); chain(rotation,scale)
    show=component(ed,SC+'SetVisibility',bNewVisibility='true',bPropagateToChildren='false'); chain(scale,show)

def build_discharge(bp):
    # Flash the same accurate footprint. A ground plane must never be rotated
    # upright or turned into the old opaque body-height cylinder.
    ed=func(bp,'ShowAttackDischarge')
    tint=component(ed,MESH+'SetVectorParameterValueOnMaterials',ParameterName='TracerColor')
    link(binary(ed,'Multiply_VectorFloat',v(ed,'BodyTint'),8.0),inp(tint,'ParameterValue'))
    link(ed.find_graph_entry_pin(),tint.find_execute_pin())
    alpha=component(ed,MESH+'SetScalarParameterValueOnMaterials',ParameterName='Opacity',ParameterValue=1.0); chain(tint,alpha)
    chain(alpha,timer(ed,'HideTelegraph',v(ed,'AttackFlashDuration')))

def work():
    material=runpy.run_path(str(Path(__file__).with_name('Author-CombatFieldMaterial.py')))['author_field_material'](allow_create=True)
    bp=unreal.load_asset(ENEMY); assert bp
    template=unreal.load_object(None,bp.generated_class().get_path_name()+':TelegraphMesh_GEN_VARIABLE'); assert template
    template.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
    template.set_material(0,material)
    template.set_editor_property('cast_shadow',False)
    template.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    build_field(bp,'ShowAttackLine',0.0); build_field(bp,'ShowBlastZone',1.0); build_discharge(bp)
    saved=[]
    for path in [ENEMY,'/Game/Enemies/BP_EnemyRunnerFast','/Game/Enemies/BP_EnemyRunnerSlow','/Game/Enemies/BP_EnemySniper']:
        asset=unreal.load_asset(path); compile_blueprint(asset,True)
        assert unreal.EditorAssetLibrary.save_loaded_asset(asset,False); saved.append(path)
    spawner=unreal.load_asset(SPAWNER); build_spawn_window(spawner); saved.append(SPAWNER)
    # Existing Heavy/Sniper points become visible when approached, rather than
    # relying on a long level-start delay that can expire after passing them.
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    updates={'Runner_EndSpawn_3':(1300.0,1.0),'Runner_EndSpawn_4':(1500.0,1.0)}
    tuned=[]
    for actor in actors:
        if actor.get_actor_label() in updates and actor.get_class()==spawner.generated_class():
            distance,delay=updates[actor.get_actor_label()]
            actor.set_editor_property('SpawnActivationDistance',distance)
            actor.set_editor_property('SpawnDelay',delay)
            tuned.append(actor.get_actor_label())
    assert len(tuned)==2,tuned
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    controller=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller,'EventGraph')
    ed.remove_nodes([i.node for i in BT.get_node_infos(list(ed.list_all_nodes())) if any(p.name=='Command' and 'Tools/Editor-Queue.py' in p.value for p in i.input_pins)])
    compile_blueprint(controller,True)
    return {'saved':saved+[material.get_path_name()], 'map_tuned_spawners':tuned,'retire_distance':250,'return_seconds':.55,'damage_and_AI':'preserved'}

if __name__=='__main__':run_editor(work,'SpawnAndWarningsPolish.json')
