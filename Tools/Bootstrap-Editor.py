"""Attach a temporary unsaved console node through MCP, then start PIE once."""
import json
import runpy
from pathlib import Path
api = runpy.run_path(str(Path(__file__).with_name('Editor-Mcp.py')))
call = api['call']
BT = 'editor_toolset.toolsets.blueprint.BlueprintTools'
bp = {'refPath':'/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController.BP_ThirdPersonPlayerController'}
def invoke(tool, args):
    result = call(BT, tool, args)
    if result.get('result',{}).get('isError'):
        raise RuntimeError(result)
    return json.loads(result['result']['content'][0]['text'])['returnValue']
graph = invoke('get_graph', {'blueprint':bp,'graph_name':'EventGraph'})
origin = {'refPath':graph['refPath']+':K2Node_CallFunction_11'}
nodes = invoke('get_connected_subgraph', {'node':origin})
node = invoke('create_node', {'graph':graph,'type_id':'개발|ExecuteConsoleCommand','pos':{'x':1400,'y':0},'declaring_class':{'refPath':'/Script/Engine.KismetSystemLibrary'}})
def pin(node, index, direction):
    return {'node':node,'index_id':index,'direction':'EGPD_'+direction}
invoke('set_pin_value', {'pin':pin(node,1,'Input'),'value':'py "C:/Users/sobin/Documents/Unreal/ONE-LIFE-SHOT/Tools/Editor-Queue.py"'})
invoke('connect_pins', {'output_pin':pin(origin,0,'Output'),'input_pin':pin(node,0,'Input')})
invoke('compile_blueprint', {'blueprint':bp})
print(call('EditorToolset.EditorAppToolset','StartPIE',{'options':{'bSimulate':False,'playMode':'PlayMode_InEditorFloating','warmupSeconds':0}}))
