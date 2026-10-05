"""Use native input events, including while paused, for Canvas menu controls."""
import runpy
from pathlib import Path
api=runpy.run_path(str(Path(__file__).with_name('Implement-CourseMenus.py')),run_name='menu_library')
globals().update({k:v for k,v in api.items() if not k.startswith('__')})

def work():
    bp=unreal.load_asset(HUD)
    # Reuse the same click hit boxes without polling/edge state.
    ed=func(bp,'PollMenuInput')
    allowed=branch(ed,negate(ed,eq(ed,v(ed,'MenuState'),1)))
    link(ed.find_graph_entry_pin(),allowed.find_execute_pin())
    mouse=call(ed,PC+'GetMousePosition');link(player(ed),inp(mouse,'self'))
    x=out(mouse,'LocationX');y=out(mouse,'LocationY');width=v(ed,'MenuWidth');height=v(ed,'MenuHeight')
    previous=None
    for index in range(4):
        row=math(ed,'Multiply_DoubleDouble',height,.56+.075*index)
        xmin=math(ed,'Multiply_DoubleDouble',width,.31);xmax=math(ed,'Multiply_DoubleDouble',width,.69)
        ymax=math(ed,'Add_DoubleDouble',row,math(ed,'Multiply_DoubleDouble',height,.06))
        hit=both(ed,both(ed,math(ed,'GreaterEqual_DoubleDouble',x,xmin),math(ed,'LessEqual_DoubleDouble',x,xmax)),both(ed,math(ed,'GreaterEqual_DoubleDouble',y,row),math(ed,'LessEqual_DoubleDouble',y,ymax)))
        b=branch(ed,both(ed,out(mouse),hit))
        if previous:link(out(previous,'else'),b.find_execute_pin())
        else:chain(allowed,b)
        selected=setv(ed,'MenuSelection',index);chain(b,selected);chain(selected,own(ed,bp,'MenuAction'));previous=b
    graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EventGraph')
    for info in BT.get_node_infos(list(graph.list_all_nodes())):
        if info.type_id=='|PollMenuInput':
            previous=list(info.node.find_execute_pin().list_connected_pins());next_pins=list(info.node.find_then_pin().list_connected_pins())
            graph.remove_nodes([info.node])
            for a in previous:
                for b in next_pins:link(a,b)
    for name in ['ShowStart','ShowPause']:
        graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,name)
        tail=next(i.node for i in BT.get_node_infos(list(graph.list_all_nodes())) if i.type_id.endswith('SetGamePaused'))
        mode=call(graph,'/Script/UMG.WidgetBlueprintLibrary.SetInputMode_GameOnly',bFlushInput='true')
        link(player(graph),inp(mode,'PlayerController'));insert_after(graph,tail,mode)
    compile_blueprint(bp,True);assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    controller=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller,'EventGraph')
    for key,node_id,action in [('Escape','Input|KeyboardEvents|Escape','TogglePause'),('Enter','Input|KeyboardEvents|Enter','MenuAction'),('LeftMouseButton','Input|MouseEvents|LeftMouseButton','PollMenuInput')]:
        node=graph.create_node_from_name(node_id,unreal.Vector2D(),[]);assert node
        node.set_editor_property('bExecuteWhenPaused',True)
        node.set_editor_property('bConsumeInput',False)
        hud=call(graph,PC+'GetHUD')
        cast=graph.create_node_from_name('Utilities|Casting|CastToBP_AmmoHUD',unreal.Vector2D(),[]);assert cast
        link(out(hud),inp(cast,'Object'));link(out(node,'Pressed'),cast.find_execute_pin())
        obj=out(cast,next(p.name for p in BT.get_node_infos([cast])[0].output_pins if p.name.startswith('As')))
        tail=cast
        if key=='Enter':
            selected=setv(graph,'MenuSelection',0,bp.generated_class().get_path_name());link(obj,inp(selected,'self'));chain(cast,selected);tail=selected
        invoke=own(graph,bp,action);link(obj,inp(invoke,'self'));chain(tail,invoke)
    compile_blueprint(controller,True);assert unreal.EditorAssetLibrary.save_loaded_asset(controller,False)
    return {'saved':[bp.get_path_name(),controller.get_path_name()],'raw_keys':['Escape','Enter','LeftMouseButton'],'execute_while_paused':True}

run_editor(work,'CourseMenuKeysConnected.json')
