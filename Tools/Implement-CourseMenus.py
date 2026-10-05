"""Author native Blueprint Canvas menus in the existing HUD; no runtime Python."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import importlib, CombatAuthoring
importlib.reload(CombatAuthoring)
from CombatAuthoring import *
HUD='/Game/ThirdPerson/Blueprints/BP_AmmoHUD'
PC='/Script/Engine.PlayerController.'
HF='/Script/Engine.HUD.'
FONT='/Engine/EngineFonts/RobotoDistanceField.RobotoDistanceField'

def v(ed,name):return out(get(ed,name),name)
def number(ed,x):return out(call(ed,SYS+'MakeLiteralDouble',Value=x))
def put(node,key,value):
    if hasattr(value,'is_valid'):link(value,inp(node,key))
    else:val(node,key,value)
def math(ed,fn,a,b):
    node=call(ed,MATH+fn)
    put(node,'B',b if hasattr(b,'is_valid') else number(ed,b))
    put(node,'A',a if hasattr(a,'is_valid') else number(ed,a))
    return out(node)
def eq(ed,p,n):
    node=call(ed,MATH+'EqualEqual_IntInt',B=n);link(p,inp(node,'A'));return out(node)
def both(ed,a,b):
    node=call(ed,MATH+'BooleanAND');link(a,inp(node,'A'));link(b,inp(node,'B'));return out(node)
def negate(ed,p):
    node=call(ed,MATH+'Not_PreBool');link(p,inp(node,'A'));return out(node)
def player(ed):return out(call(ed,GAME+'GetPlayerController',PlayerIndex=0))
def own(ed,bp,name):return call(ed,bp.generated_class().get_path_name()+':'+name)
def pause(ed,tail,paused):
    node=call(ed,GAME+'SetGamePaused',bPaused=str(paused).lower());chain(tail,node);return node

def state_function(bp,name,state):
    ed=func(bp,name)
    set_state=setv(ed,'MenuState',state);link(ed.find_graph_entry_pin(),set_state.find_execute_pin())
    tail=pause(ed,set_state,state!=1)
    # Flushing the activation click prevents it from spending the first shot.
    if state==1:
        mode=call(ed,'/Script/UMG.WidgetBlueprintLibrary.SetInputMode_GameOnly',bFlushInput='true')
        link(player(ed),inp(mode,'PlayerController'));chain(tail,mode)

def build_actions(bp):
    for name,state in [('ShowStart',0),('StartGame',1),('ShowPause',2)]:state_function(bp,name,state)
    ed=func(bp,'TogglePause');b=branch(ed,eq(ed,v(ed,'MenuState'),1));link(ed.find_graph_entry_pin(),b.find_execute_pin())
    show=own(ed,bp,'ShowPause');chain(b,show)
    paused=branch(ed,eq(ed,v(ed,'MenuState'),2));link(out(b,'else'),paused.find_execute_pin())
    resume=own(ed,bp,'StartGame');chain(paused,resume)
    ed=func(bp,'ClearGame');b=branch(ed,eq(ed,v(ed,'MenuState'),1));link(ed.find_graph_entry_pin(),b.find_execute_pin())
    stamp=setv(ed,'MenuFadeStart');link(out(call(ed,GAME+'GetRealTimeSeconds')),inp(stamp,'MenuFadeStart'));chain(b,stamp)
    state=setv(ed,'MenuState',3);chain(stamp,state);pause(ed,state,True)
    ed=func(bp,'RestartGame');unpause=call(ed,GAME+'SetGamePaused',bPaused='false');link(ed.find_graph_entry_pin(),unpause.find_execute_pin())
    level=call(ed,GAME+'GetCurrentLevelName',bRemovePrefixString='true')
    asname=call(ed,'/Script/Engine.KismetStringLibrary.Conv_StringToName');link(out(level),inp(asname,'InString'))
    reopen=call(ed,GAME+'OpenLevel',bAbsolute='true');link(out(asname),inp(reopen,'LevelName'));chain(unpause,level);chain(level,reopen)
    ed=func(bp,'ReturnToStart');restart=own(ed,bp,'RestartGame');link(ed.find_graph_entry_pin(),restart.find_execute_pin())
    ed=func(bp,'QuitFromMenu');quit=call(ed,SYS+'QuitGame',QuitPreference='Quit',bIgnorePlatformRestrictions='false')
    link(player(ed),inp(quit,'SpecificPlayer'));link(ed.find_graph_entry_pin(),quit.find_execute_pin())
    compile_blueprint(bp,True)
    ed=func(bp,'MenuAction')
    previous=None
    for state,actions in [(0,['StartGame','QuitFromMenu']),(2,['StartGame','RestartGame','ReturnToStart','QuitFromMenu']),(3,['RestartGame','ReturnToStart','QuitFromMenu'])]:
        b=branch(ed,eq(ed,v(ed,'MenuState'),state))
        if previous:link(out(previous,'else'),b.find_execute_pin())
        else:link(ed.find_graph_entry_pin(),b.find_execute_pin())
        previous=b;index_previous=None
        for index,action in enumerate(actions):
            selected=branch(ed,eq(ed,v(ed,'MenuSelection'),index))
            if index_previous:link(out(index_previous,'else'),selected.find_execute_pin())
            else:chain(b,selected)
            chain(selected,own(ed,bp,action));index_previous=selected

def edge(ed,tail,key,name):
    down=call(ed,PC+'IsInputKeyDown',Key='(KeyName='+key+')');link(player(ed),inp(down,'self'))
    hit=setv(ed,name+'Edge');link(both(ed,out(down),negate(ed,v(ed,name+'Held'))),inp(hit,name+'Edge'))
    if tail:chain(tail,hit)
    else:link(ed.find_graph_entry_pin(),hit.find_execute_pin())
    remember=setv(ed,name+'Held');link(out(down),inp(remember,name+'Held'));chain(hit,remember)
    return remember

def build_input(bp):
    ed=func(bp,'PollMenuInput')
    tail=edge(ed,None,'Escape','MenuEsc');tail=edge(ed,tail,'Enter','MenuEnter');tail=edge(ed,tail,'LeftMouseButton','MenuClick')
    # Sequence preserves all key snapshots even when one branch takes no action.
    sequence=ed.create_node_from_name('Utilities|FlowControl|Sequence',unreal.Vector2D(),[]);assert sequence;chain(tail,sequence)
    esc=branch(ed,v(ed,'MenuEscEdge'));link(out(sequence,'then_0'),esc.find_execute_pin());chain(esc,own(ed,bp,'TogglePause'))
    other=branch(ed,negate(ed,eq(ed,v(ed,'MenuState'),1)));link(out(sequence,'then_1'),other.find_execute_pin())
    s=ed.create_node_from_name('Utilities|FlowControl|Sequence',unreal.Vector2D(),[]);assert s;chain(other,s)
    enter=branch(ed,v(ed,'MenuEnterEdge'));link(out(s,'then_0'),enter.find_execute_pin())
    first=setv(ed,'MenuSelection',0);chain(enter,first);chain(first,own(ed,bp,'MenuAction'))
    click=branch(ed,v(ed,'MenuClickEdge'));link(out(s,'then_1'),click.find_execute_pin())
    mouse=call(ed,PC+'GetMousePosition');link(player(ed),inp(mouse,'self'))
    x=out(mouse,'LocationX');y=out(mouse,'LocationY');width=v(ed,'MenuWidth');height=v(ed,'MenuHeight')
    previous=None
    for index in range(4):
        row=math(ed,'Multiply_DoubleDouble',height,.56+.075*index)
        xmin=math(ed,'Multiply_DoubleDouble',width,.31);xmax=math(ed,'Multiply_DoubleDouble',width,.69)
        ymin=row;ymax=math(ed,'Add_DoubleDouble',row,math(ed,'Multiply_DoubleDouble',height,.06))
        hit=both(ed,both(ed,math(ed,'GreaterEqual_DoubleDouble',x,xmin),math(ed,'LessEqual_DoubleDouble',x,xmax)),both(ed,math(ed,'GreaterEqual_DoubleDouble',y,ymin),math(ed,'LessEqual_DoubleDouble',y,ymax)))
        b=branch(ed,both(ed,out(mouse),hit))
        if previous:link(out(previous,'else'),b.find_execute_pin())
        else:chain(click,b)
        selected=setv(ed,'MenuSelection',index);chain(b,selected);chain(selected,own(ed,bp,'MenuAction'));previous=b

def draw_menus(bp):
    ed=func(bp,'DrawMenus');width=v(ed,'MenuWidth');height=v(ed,'MenuHeight')
    scale=math(ed,'Divide_DoubleDouble',height,720)
    since=math(ed,'Subtract_DoubleDouble',out(call(ed,GAME+'GetRealTimeSeconds')),v(ed,'MenuFadeStart'))
    f=call(ed,MATH+'FClamp',Min=0,Max=1);link(math(ed,'Divide_DoubleDouble',since,1.2),inp(f,'Value'))
    choose=call(ed,MATH+'SelectFloat',B=1);link(eq(ed,v(ed,'MenuState'),3),inp(choose,'bPickA'));link(out(f),inp(choose,'A'))
    fade=setv(ed,'MenuFade');link(out(choose),inp(fade,'MenuFade'));link(ed.find_graph_entry_pin(),fade.find_execute_pin())
    ink=call(ed,MATH+'MakeColor',R=.88,G=.98,B=1);link(v(ed,'MenuFade'),inp(ink,'A'))
    dim=call(ed,MATH+'MakeColor',R=.004,G=.009,B=.016);link(math(ed,'Multiply_DoubleDouble',v(ed,'MenuFade'),.76),inp(dim,'A'))
    bg=call(ed,HF+'DrawRect',ScreenX=0,ScreenY=0);link(out(dim),inp(bg,'RectColor'));link(width,inp(bg,'ScreenW'));link(height,inp(bg,'ScreenH'));chain(fade,bg)
    font=unreal.load_asset(FONT);glyphs=font.get_editor_property('characters');normalization=16/float(glyphs[ord('1')].get_editor_property('v_size'))
    def centered(tail,text,y,size,color):
        sizepin=math(ed,'Multiply_DoubleDouble',scale,size*normalization)
        measure=call(ed,HF+'GetTextSize',Text=text,Font=FONT);link(sizepin,inp(measure,'Scale'))
        node=call(ed,HF+'DrawText',Text=text,Font=FONT,bScalePosition='false')
        link(math(ed,'Multiply_DoubleDouble',math(ed,'Subtract_DoubleDouble',width,out(measure,'OutWidth')),.5),inp(node,'ScreenX'))
        link(math(ed,'Multiply_DoubleDouble',height,y),inp(node,'ScreenY'));link(sizepin,inp(node,'Scale'));put(node,'TextColor',color);chain(tail,node);return node
    def button(tail,text,index):
        row=.56+.075*index
        box=call(ed,HF+'DrawRect',RectColor='(R=0.015,G=0.09,B=0.12,A=0.92)')
        for key,factor,base in [('ScreenX',.31,width),('ScreenY',row,height),('ScreenW',.38,width),('ScreenH',.06,height)]:link(math(ed,'Multiply_DoubleDouble',base,factor),inp(box,key))
        chain(tail,box);return centered(box,text,row+.016,1.15,out(ink))
    previous=None
    for state,title,subtitle,buttons in [(0,'ONE LIFE SHOT','ONE SHOT. TAKE THEIR WEAPON. ESCAPE.',['START RUN  [ENTER]','QUIT']),(2,'PAUSED','ESC TO RESUME',['RESUME  [ENTER]','RESTART','MAIN MENU','QUIT']),(3,'YOU CLEARED!','RESEARCH FACILITY / ESCAPE COMPLETE',['PLAY AGAIN  [ENTER]','MAIN MENU','QUIT'])]:
        b=branch(ed,eq(ed,v(ed,'MenuState'),state))
        if previous:link(out(previous,'else'),b.find_execute_pin())
        else:chain(bg,b)
        previous=b
        tail=centered(b,title,.34,4.0 if state==3 else 3.6,out(ink))
        tail=centered(tail,subtitle,.445,.9,out(ink))
        for i,label in enumerate(buttons):tail=button(tail,label,i)
        centered(tail,'WASD MOVE / MOUSE AIM / LMB FIRE / SPACE DODGE / ESC MENU',.94,.72,out(ink))

def work():
    bp=unreal.load_asset(HUD);assert bp
    for name,kind,default in [('MenuState','int',0),('MenuSelection','int',0),('MenuWidth','float',1280),('MenuHeight','float',720),('MenuFadeStart','float',0),('MenuFade','float',0)]:var(bp,name,kind,default)
    for name in ['MenuEsc','MenuEnter','MenuClick']:
        for suffix in ['Held','Edge']:var(bp,name+suffix,'bool',False)
    for name in ['ShowStart','StartGame','ShowPause','TogglePause','ClearGame','RestartGame','ReturnToStart','QuitFromMenu','MenuAction','PollMenuInput','DrawMenus']:BT.add_function_graph(bp,name)
    compile_blueprint(bp)
    build_actions(bp);compile_blueprint(bp,True)
    build_input(bp);compile_blueprint(bp,True)
    draw_menus(bp);compile_blueprint(bp,True)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EventGraph')
    draw=next(i.node for i in BT.get_node_infos(list(ed.list_all_nodes())) if i.type_id.endswith('EventReceiveDrawHUD'))
    following=list(draw.find_then_pin().list_connected_pins());assert following
    draw.find_then_pin().break_pin_links()
    w=setv(ed,'MenuWidth');link(out(draw,'SizeX'),inp(w,'MenuWidth'));chain(draw,w)
    h=setv(ed,'MenuHeight');link(out(draw,'SizeY'),inp(h,'MenuHeight'));chain(w,h)
    poll=own(ed,bp,'PollMenuInput');chain(h,poll)
    playing=branch(ed,eq(ed,v(ed,'MenuState'),1));chain(poll,playing)
    for target in following:link(playing.find_then_pin(),target)
    menu=own(ed,bp,'DrawMenus');link(out(playing,'else'),menu.find_execute_pin())
    begin=BT.add_event(bp,'ReceiveBeginPlay');start=timer(ed,'ShowStart',.08)
    insert_after(ed,begin,start)
    compile_blueprint(bp,True);assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    return {'saved':bp.get_path_name(),'states':{'start':0,'play':1,'pause':2,'clear':3},'clear_fade_seconds':1.2,'background':'Production map, paused','controls':['Escape','Enter','LeftMouseButton']}

if __name__=='__main__':run_editor(work,'CourseMenusAuthored.json')
