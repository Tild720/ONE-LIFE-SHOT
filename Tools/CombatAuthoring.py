"""Small helpers for editor-managed Blueprint authoring. Never loaded by gameplay."""
import json
import traceback
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BT
from toolset_registry.helpers import compile_blueprint

SYS = '/Script/Engine.KismetSystemLibrary.'
MATH = '/Script/Engine.KismetMathLibrary.'
ACT = '/Script/Engine.Actor.'
GAME = '/Script/Engine.GameplayStatics.'

def inp(n, name):
    p = n.find_input_pin(name)
    assert p.is_valid(), (n.get_name(), name)
    return p

def out(n, name='ReturnValue'):
    p = n.find_output_pin(name)
    assert p.is_valid(), (n.get_name(), name)
    return p

def link(a, b):
    assert a.try_create_connection(b), (str(a), str(b))

def val(n, name, value):
    assert inp(n, name).set_pin_value(str(value)), (n.get_name(), name, value)

def call(ed, path, **values):
    function = path.rsplit('.',1)[-1]
    operator = {'Add':'추가','Subtract':'빼기','Multiply':'곱하기','Divide':'나누기'}.get(function.split('_',1)[0])
    compare = {'EqualEqual_IntInt':'같음(==)','EqualEqual_ObjectObject':'같음(==)',
               'NotEqual_IntInt':'같지않음(!=)','LessEqual_DoubleDouble':'작거나같음(<=)',
               'GreaterEqual_DoubleDouble':'크거나같음(>=)','Less_DoubleDouble':'작음(<)',
               'Greater_DoubleDouble':'보다큼(>)'}.get(function)
    type_name = operator or compare
    n = ed.create_node_from_name('유틸리티|연산자|'+type_name, unreal.Vector2D(), []) if type_name else ed.add_call_function_node(path)
    assert n, path
    for k, v in values.items():
        if not inp(n, k).set_pin_value(str(v)):
            if isinstance(v, (float, int)):
                literal = ed.add_call_function_node(SYS + ('MakeLiteralInt' if '_IntInt' in path else 'MakeLiteralDouble'))
                val(literal, 'Value', v)
                link(out(literal), inp(n, k))
            else:
                raise AssertionError((path, k, v))
    return n

def chain(a, b):
    link(a.find_then_pin(), b.find_execute_pin())

def get(ed, name, cls=''):
    n = ed.add_get_member_variable_node(name, cls)
    assert n, name
    return n

def setv(ed, name, value=None, cls=''):
    n = ed.add_set_member_variable_node(name, cls)
    assert n, name
    if value is not None:
        val(n, name, value)
    return n

def branch(ed, source):
    n = ed.add_branch_node()
    link(source, inp(n, 'Condition'))
    return n

def var(bp, name, kind, default, editable=False):
    names = [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)]
    if name not in names:
        BT.add_variable(bp, name, kind)
        unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, editable)
        unreal.BlueprintEditorLibrary.set_blueprint_variable_category(bp, name, 'One Shot')
        compile_blueprint(bp)
    unreal.get_default_object(bp.generated_class()).set_editor_property(name, default)

def func(bp, name):
    names = [g.get_name() for g in unreal.BlueprintEditorLibrary.list_graphs(bp)]
    graph = BT.get_graph(bp, name) if name in names else BT.add_function_graph(bp, name)
    ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    ed.remove_nodes([n for n in ed.list_all_nodes() if not isinstance(n, unreal.K2Node_FunctionEntry)])
    return ed

def selfpin(ed):
    ids = [s for s in ed.list_available_nodes([]) if s.endswith('|셀프레퍼런스가져오기') or s.endswith('|Getareferencetoself')]
    assert ids, 'Self node type not found'
    return out(ed.create_node_from_name(ids[0], unreal.Vector2D(), []), 'self')

def timer(ed, name, interval, looping=False):
    n = call(ed, SYS+'K2_SetTimer', FunctionName=name, bLooping='true' if looping else 'false', bMaxOncePerFrame='true')
    if hasattr(interval, 'is_valid'):
        link(interval, inp(n, 'Time'))
    else:
        val(n, 'Time', interval)
    link(selfpin(ed), inp(n, 'Object'))
    return n

def insert_after(ed, node, first, last=None):
    next_pins = list(node.find_then_pin().list_connected_pins())
    node.find_then_pin().break_pin_links()
    chain(node, first)
    for p in next_pins:
        link((last or first).find_then_pin(), p)

def run_editor(work, report):
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    handle = [None]
    def tick(dt):
        if les.is_in_play_in_editor():
            return
        unreal.unregister_slate_post_tick_callback(handle[0])
        try:
            result = work()
        except Exception:
            result = {'error': traceback.format_exc()}
            unreal.log_error(result['error'])
        (Path(unreal.Paths.project_saved_dir()) / report).write_text(json.dumps(result, indent=2), encoding='utf-8')
    handle[0] = unreal.register_slate_post_tick_callback(tick)
    les.editor_request_end_play()
