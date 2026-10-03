"""Use existing enemy animations/telegraphs to show commitment and recovery."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
BASE='/Game/Enemies/BP_EnemyStraightRunner'
SC='/Script/Engine.SceneComponent.'
SK='/Script/Engine.SkeletalMeshComponent.'
def v(ed,name):return out(get(ed,name),name)
def binary(ed,fn,a,b,ap='A',bp='B'):
    n=call(ed,MATH+fn)
    for key,value in [(ap,a),(bp,b)]:
        if hasattr(value,'is_valid'):link(value,inp(n,key))
        elif fn=='Multiply_VectorFloat' and key==bp:
            # A vector connection promotes both wildcard operands to Vector.
            # Connect a typed scalar instead of accepting an invalid vector default.
            literal=call(ed,SYS+'MakeLiteralDouble',Value=value)
            link(out(literal),inp(n,key))
        elif not inp(n,key).set_pin_value(str(value)):
            literal=call(ed,SYS+('MakeLiteralInt' if '_IntInt' in fn else 'MakeLiteralDouble'),Value=value)
            link(out(literal),inp(n,key))
    return out(n)
def unary(ed,fn,p,pin='A'):
    n=call(ed,MATH+fn);link(p,inp(n,pin));return out(n)
def own(ed,bp,name):return call(ed,bp.generated_class().get_path_name()+':'+name)
def meshcall(ed,path,component='Mesh',**values):
    n=call(ed,path,**values);link(v(ed,component),inp(n,'self'));return n
def time(ed):return out(call(ed,SYS+'GetGameTimeInSeconds'))
def color(ed,p):
    n=meshcall(ed,'/Script/Engine.MeshComponent.SetVectorParameterValueOnMaterials',component='TelegraphMesh',ParameterName='TracerColor')
    link(p,inp(n,'ParameterValue'));return n
def clamp(ed,p,lo,hi):
    n=call(ed,MATH+'FClamp',Min=lo,Max=hi);link(p,inp(n,'Value'));return out(n)
def warning_ground_position(ed,xy):
    coordinates=call(ed,MATH+'BreakVector');link(xy,inp(coordinates,'InVec'))
    target=call(ed,MATH+'BreakVector');link(v(ed,'AttackTarget'),inp(target,'InVec'))
    player=call(ed,GAME+'GetPlayerCharacter',PlayerIndex=0)
    capsule=call(ed,ACT+'GetComponentByClass',ComponentClass='/Script/Engine.CapsuleComponent')
    link(out(player),inp(capsule,'self'))
    height=call(ed,'/Script/Engine.CapsuleComponent.GetScaledCapsuleHalfHeight')
    link(out(capsule),inp(height,'self'))
    floor=binary(ed,'Add_DoubleDouble',binary(ed,'Subtract_DoubleDouble',out(target,'Z'),out(height)),v(ed,'TelegraphFloorLift'))
    position=call(ed,MATH+'MakeVector')
    link(out(coordinates,'X'),inp(position,'X'));link(out(coordinates,'Y'),inp(position,'Y'));link(floor,inp(position,'Z'))
    return out(position)
def build_pose(bp):
    ed=func(bp,'UpdateEnemyPose')
    alive=branch(ed,unary(ed,'Not_PreBool',v(ed,'Dead')))
    link(ed.find_graph_entry_pin(),alive.find_execute_pin())
    moving=branch(ed,binary(ed,'Greater_DoubleDouble',v(ed,'MoveSpeed'),1.0));chain(alive,moving)
    heavy=branch(ed,binary(ed,'EqualEqual_IntInt',v(ed,'WeaponKind'),3));chain(moving,heavy)
    def pose(start,output,mode,anim,reference=None):
        gate=branch(ed,binary(ed,'NotEqual_IntInt',v(ed,'EnemyPoseMode'),mode))
        link(out(start,output),gate.find_execute_pin())
        play=meshcall(ed,SK+'PlayAnimation',NewAnimToPlay='/Game/Characters/KayKit/Anims/'+anim,bLooping='true')
        chain(gate,play)
        cache=setv(ed,'EnemyPoseMode',mode);chain(play,cache)
        rate=meshcall(ed,SK+'SetPlayRate')
        if reference:
            link(clamp(ed,binary(ed,'Divide_DoubleDouble',v(ed,'MoveSpeed'),v(ed,reference)),.6,2.2),inp(rate,'Rate'))
        else:val(rate,'Rate',1.0)
        chain(cache,rate);link(out(gate,'else'),rate.find_execute_pin())
    pose(moving,'else',0,'A_Dummy_Idle')
    pose(heavy,'then',1,'A_Dummy_Walk','WalkAnimationSpeed')
    pose(heavy,'else',2,'A_Dummy_Run','RunAnimationSpeed')
def build_warning(bp):
    ed=func(bp,'UpdateAttackWarning')
    gate=branch(ed,binary(ed,'EqualEqual_IntInt',v(ed,'AIState'),1))
    link(ed.find_graph_entry_pin(),gate.find_execute_pin())
    # Track early, then leave a guaranteed visible commitment window.
    previous=gate
    for role,duration in [(1,'ChargeWindup'),(2,'SniperWindup'),(3,'BlastWindup')]:
        select=branch(ed,binary(ed,'EqualEqual_IntInt',v(ed,'WeaponKind'),role))
        if previous is gate:chain(previous,select)
        else:link(out(previous,'else'),select.find_execute_pin())
        remaining=binary(ed,'Subtract_DoubleDouble',v(ed,'StateEndTime'),time(ed))
        tracking=branch(ed,binary(ed,'Greater_DoubleDouble',remaining,v(ed,'WarningLockLeadTime')));chain(select,tracking)
        refresh=own(ed,bp,'RefreshAttackAim');chain(tracking,refresh)
        progress=clamp(ed,binary(ed,'Subtract_DoubleDouble',1.0,binary(ed,'Divide_DoubleDouble',remaining,v(ed,duration))),0.0,1.0)
        tint=color(ed,binary(ed,'Multiply_VectorFloat',v(ed,'BodyTint'),binary(ed,'Add_DoubleDouble',1.0,progress)));chain(refresh,tint)
        committed=color(ed,binary(ed,'Multiply_VectorFloat',v(ed,'BodyTint'),4.0));link(out(tracking,'else'),committed.find_execute_pin())
        previous=select
def build_tracking(bp):
    ed=func(bp,'RefreshAttackAim')
    player=call(ed,GAME+'GetPlayerPawn',PlayerIndex=0)
    location=call(ed,ACT+'K2_GetActorLocation');link(out(player),inp(location,'self'))
    target=setv(ed,'AttackTarget');link(out(location),inp(target,'AttackTarget'))
    link(ed.find_graph_entry_pin(),target.find_execute_pin())
    direction=setv(ed,'AttackDirection')
    link(unary(ed,'Vector_Normal2D',binary(ed,'Subtract_VectorVector',v(ed,'AttackTarget'),v(ed,'AttackOrigin'))),inp(direction,'AttackDirection'));chain(target,direction)
    facing=call(ed,ACT+'K2_SetActorRotation',bTeleportPhysics='true')
    link(unary(ed,'MakeRotFromX',v(ed,'AttackDirection'),'X'),inp(facing,'NewRotation'));chain(direction,facing)
    heavy=branch(ed,binary(ed,'EqualEqual_IntInt',v(ed,'WeaponKind'),3));chain(facing,heavy)
    blast=own(ed,bp,'ShowBlastZone');chain(heavy,blast)
    line=own(ed,bp,'ShowAttackLine');link(out(heavy,'else'),line.find_execute_pin())
def build_discharge(bp):
    ed=func(bp,'ShowAttackDischarge')
    tint=color(ed,binary(ed,'Multiply_VectorFloat',v(ed,'BodyTint'),8.0))
    link(ed.find_graph_entry_pin(),tint.find_execute_pin())
    sniper=branch(ed,binary(ed,'EqualEqual_IntInt',v(ed,'WeaponKind'),2));chain(tint,sniper)
    # A narrow beam at body height distinguishes the shot from its ground warning.
    midpoint=binary(ed,'Add_VectorVector',v(ed,'AttackOrigin'),binary(ed,'Multiply_VectorFloat',v(ed,'AttackDirection'),binary(ed,'Multiply_DoubleDouble',v(ed,'AttackLength'),.5)))
    pos=meshcall(ed,SC+'K2_SetWorldLocation',component='TelegraphMesh',bSweep='false',bTeleport='true')
    link(midpoint,inp(pos,'NewLocation'));chain(sniper,pos)
    size=call(ed,MATH+'MakeVector',X=.08,Y=.08)
    link(binary(ed,'Divide_DoubleDouble',v(ed,'AttackLength'),100.0),inp(size,'Z'))
    narrow=meshcall(ed,SC+'SetWorldScale3D',component='TelegraphMesh');link(out(size),inp(narrow,'NewScale'));chain(pos,narrow)
    # Keep the blast footprint at exactly the damage radius; thicken its flash.
    diameter=binary(ed,'Divide_DoubleDouble',v(ed,'BlastRadius'),50.0)
    blastsize=call(ed,MATH+'MakeVector',Z=.16)
    link(diameter,inp(blastsize,'X'));link(diameter,inp(blastsize,'Y'))
    blast=meshcall(ed,SC+'SetWorldScale3D',component='TelegraphMesh');link(out(blastsize),inp(blast,'NewScale'))
    link(out(sniper,'else'),blast.find_execute_pin())
    end=timer(ed,'HideTelegraph',v(ed,'AttackFlashDuration'))
    chain(narrow,end);chain(blast,end)
def work():
    bp=unreal.load_asset(BASE);assert bp
    for name in ['A_Dummy_Idle','A_Dummy_Walk','A_Dummy_Run']:
        assert unreal.load_asset('/Game/Characters/KayKit/Anims/'+name)
    for name,kind,default,editable in [('EnemyPoseMode','int',-1,False),('RunAnimationSpeed','float',300.0,True),('WalkAnimationSpeed','float',140.0,True),('AttackFlashDuration','float',.16,True),('WarningLockLeadTime','float',.4,True),('TelegraphFloorLift','float',3.0,True)]:
        var(bp,name,kind,default,editable)
        unreal.BlueprintEditorLibrary.set_blueprint_variable_category(bp,name,'Enemy Presentation')
    for name in ['UpdateEnemyPose','UpdateAttackWarning','ShowAttackDischarge','RefreshAttackAim']:
        if name not in [g.get_name() for g in unreal.BlueprintEditorLibrary.list_graphs(bp)]:BT.add_function_graph(bp,name)
    compile_blueprint(bp,True)
    build_pose(bp);build_tracking(bp);build_warning(bp);build_discharge(bp)
    compile_blueprint(bp,True)
    for name in ['ShowAttackLine','ShowBlastZone']:
        ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,name)
        position=next(i.node for i in BT.get_node_infos(list(ed.list_all_nodes())) if i.type_id.endswith('|SetWorldLocation'))
        pin=inp(position,'NewLocation')
        original=list(pin.list_connected_pins())[0]
        # Detect our own floor-lift path so repeat runs don't add another wrapper.
        if any(i.type_id=='|GetTelegraphFloorLift' for i in BT.get_node_infos(list(ed.list_all_nodes()))):continue
        grounded=warning_ground_position(ed,original)
        pin.break_pin_links();link(grounded,pin)
    # Small insertions preserve the existing movement, damage, and drop graphs.
    for name in ['BeginChargeWarning','BeginBlastWarning','BeginSniperWarning','AssaultPulse','HeavyPulse','SniperPulse']:
        ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,name)
        for info in BT.get_node_infos(list(ed.list_all_nodes())):
            if info.type_id=='|SetMoveSpeed':
                following=list(info.node.find_then_pin().list_connected_pins())
                if not any(p.get_owning_node().get_name() in [i.node.get_name() for i in BT.get_node_infos(list(ed.list_all_nodes())) if i.type_id=='|UpdateEnemyPose'] for p in following):
                    insert_after(ed,info.node,own(ed,bp,'UpdateEnemyPose'))
        if name in ['HeavyPulse','SniperPulse']:
            for info in BT.get_node_infos(list(ed.list_all_nodes())):
                if info.type_id=='|HideTelegraph':
                    before=list(info.node.find_execute_pin().list_connected_pins())
                    after=list(info.node.find_then_pin().list_connected_pins())
                    replacement=own(ed,bp,'ShowAttackDischarge')
                    info.node.find_execute_pin().break_pin_links();info.node.find_then_pin().break_pin_links()
                    for p in before:link(p,replacement.find_execute_pin())
                    for p in after:link(replacement.find_then_pin(),p)
                    ed.remove_nodes([info.node])
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EventGraph')
    original=next(n for n in ed.list_all_nodes() if n.get_name()=='K2Node_CallFunction_52')
    if not original.find_then_pin().list_connected_pins():insert_after(ed,original,own(ed,bp,'UpdateEnemyPose'))
    # Pulse after role state transitions so windup brightness follows commitment.
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EnemyRolePulse')
    alive=ed.find_graph_entry_pin().list_connected_pins()[0].get_owning_node()
    if not any(p.get_owning_node().get_name() in [i.node.get_name() for i in BT.get_node_infos(list(ed.list_all_nodes())) if i.type_id=='|UpdateEnemyPose'] for p in alive.find_then_pin().list_connected_pins()):
        insert_after(ed,alive,own(ed,bp,'UpdateEnemyPose'))
    for info in BT.get_node_infos(list(ed.list_all_nodes())):
        if info.type_id in ['|AssaultPulse','|HeavyPulse','|SniperPulse']:
            if not info.node.find_then_pin().list_connected_pins():insert_after(ed,info.node,own(ed,bp,'UpdateAttackWarning'))
    # Chasing movement should turn the robot with its path, rather than slide
    # sideways while keeping only its BeginPlay facing. Charge stays committed.
    for name in ['EnemyRolePulse','AssaultPulse','HeavyPulse']:
        ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,name)
        infos=BT.get_node_infos(list(ed.list_all_nodes()))
        rotations={i.node.get_name() for i in infos if i.type_id.endswith('|SetActorRotation')}
        for info in infos:
            if info.type_id=='|SetTravelDirection' and not any(p.get_owning_node().get_name() in rotations for p in info.node.find_then_pin().list_connected_pins()):
                facing=call(ed,ACT+'K2_SetActorRotation',bTeleportPhysics='true')
                link(unary(ed,'MakeRotFromX',v(ed,'TravelDirection'),'X'),inp(facing,'NewRotation'))
                insert_after(ed,info.node,facing)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'ConfigureEnemyAppearance')
    for info in BT.get_node_infos(list(ed.list_all_nodes())):
        if info.type_id.endswith('|SetVectorParameterValueOnMaterials') and any(p.name=='ParameterName' and p.value=='TracerColor' for p in info.input_pins):
            inp(info.node,'ParameterValue').break_pin_links();link(v(ed,'BodyTint'),inp(info.node,'ParameterValue'))
    # Death animation must run at its own normal speed, even after a fast charge.
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'Die')
    play=next(i.node for i in BT.get_node_infos(list(ed.list_all_nodes())) if i.type_id.endswith('|PlayAnimation'))
    rates={i.node.get_name() for i in BT.get_node_infos(list(ed.list_all_nodes())) if i.type_id.endswith('|SetPlayRate')}
    if not any(p.get_owning_node().get_name() in rates for p in play.find_then_pin().list_connected_pins()):
        insert_after(ed,play,meshcall(ed,SK+'SetPlayRate',Rate=1.0))
    saved=[]
    for path in [BASE,'/Game/Enemies/BP_EnemyRunnerFast','/Game/Enemies/BP_EnemyRunnerSlow','/Game/Enemies/BP_EnemySniper']:
        child=unreal.load_asset(path);compile_blueprint(child,True)
        unreal.get_default_object(child.generated_class()).set_editor_property('WarningLockLeadTime',.55 if path.endswith('BP_EnemyRunnerSlow') else .4)
        assert unreal.EditorAssetLibrary.save_loaded_asset(child,False);saved.append(path)
    # Strip the temporary MCP console hook before any project save or restart.
    controller=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller,'EventGraph')
    ed.remove_nodes([i.node for i in BT.get_node_infos(list(ed.list_all_nodes())) if any(p.name=='Command' and 'Tools/Editor-Queue.py' in p.value for p in i.input_pins)])
    compile_blueprint(controller,True)
    return {'saved':saved,'reused_animations':['Idle','Walk','Run'],'flash_seconds':.16,'return_duration':.55,'final_aim_lock_seconds':{'Assault':.4,'Sniper':.4,'Heavy':.55},'damage_and_attack_durations':'preserved'}
run_editor(work,'EnemyPresentationPolish.json')
