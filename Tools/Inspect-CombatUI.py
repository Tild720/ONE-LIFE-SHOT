"""Read the existing combat/progress UI through editor APIs; changes no assets."""
import sys
import importlib
import inspect
import pkgutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

PATHS = ['/Game/ThirdPerson/Blueprints/BP_AmmoHUD',
         '/Game/UI/WBP_RunnerProgress', '/Game/Runner/BP_RunnerProgress']


def properties(obj, names):
    found, errors = {}, {}
    for name in names:
        try:
            found[name] = str(obj.get_editor_property(name))
        except Exception as error:
            errors[name] = str(error)
    return {'values': found, 'unexposed': errors}


def inspect_widgets(bp):
    result = {'widgets': [], 'errors': []}
    try:
        tree = bp.get_editor_property('widget_tree')
        result['tree'] = str(tree)
    except Exception as error:
        result['errors'].append('widget_tree: ' + str(error))
        tree = None
    roots = []
    if tree:
        try:
            root = tree.get_editor_property('root_widget')
            if root:
                roots.append(root)
        except Exception as error:
            result['errors'].append('root_widget: ' + str(error))
        if hasattr(tree, 'get_all_widgets'):
            try:
                roots.extend(tree.get_all_widgets())
            except Exception as error:
                result['errors'].append('get_all_widgets: ' + str(error))
    if not roots:
        # This method/class path is declared in the local UE 5.8 UMGToolSet.h.
        try:
            if hasattr(unreal, 'UMGToolSet') and hasattr(unreal.UMGToolSet, 'get_widgets'):
                native = unreal.UMGToolSet.get_widgets(bp)
            else:
                tool_class = unreal.load_class(None, '/Script/UMGToolSet.UMGToolSet')
                assert tool_class, 'Local UUMGToolSet class is not loaded'
                native = unreal.get_default_object(tool_class).call_method('GetWidgets', args=(bp,))
            roots.extend(info.get_editor_property('widget')
                         for info in native.get_editor_property('widgets'))
            result['source'] = 'UMGToolSet.GetWidgets'
        except Exception as error:
            result['errors'].append('native GetWidgets: ' + str(error))
    seen = set()
    while roots:
        widget = roots.pop(0)
        if not widget or widget.get_path_name() in seen:
            continue
        seen.add(widget.get_path_name())
        row = {'name': widget.get_name(), 'path': widget.get_path_name(),
               'class': widget.get_class().get_path_name(),
               'properties': properties(widget, [
                   'visibility', 'render_opacity', 'render_transform',
                   'render_transform_pivot', 'color_and_opacity', 'brush',
                   'text', 'font', 'justification', 'is_variable',
                   'desired_size_scale', 'horizontal_alignment',
                   'vertical_alignment', 'padding', 'widget_style',
                   'fill_color_and_opacity', 'bar_fill_type', 'bar_fill_style',
                   'border_padding', 'clipping'])}
        try:
            slot = widget.get_editor_property('slot')
            if slot:
                row['slot'] = {'class': slot.get_class().get_path_name(),
                               'properties': properties(slot, [
                                   'layout', 'auto_size', 'z_order', 'padding',
                                   'horizontal_alignment', 'vertical_alignment'])}
                row['slot']['getters'] = {}
                for name in ['get_position', 'get_size', 'get_alignment',
                             'get_anchors', 'get_offsets']:
                    if hasattr(slot, name):
                        try:
                            row['slot']['getters'][name] = str(getattr(slot, name)())
                        except Exception as error:
                            result['errors'].append(name + ': ' + str(error))
        except Exception as error:
            result['errors'].append(widget.get_name() + '.slot: ' + str(error))
        children = []
        if isinstance(widget, unreal.PanelWidget):
            children = [widget.get_child_at(index)
                        for index in range(widget.get_children_count())]
        row['children'] = [child.get_name() for child in children if child]
        roots.extend(children)
        result['widgets'].append(row)
    return result


def read_umg_api():
    """Describe available editor helper APIs without invoking them."""
    result = {}
    try:
        import editor_toolset.toolsets as toolsets
        for entry in pkgutil.iter_modules(toolsets.__path__):
            if not any(part in entry.name.casefold() for part in ['widget', 'umg']):
                continue
            module = importlib.import_module('editor_toolset.toolsets.' + entry.name)
            types = {}
            for name, cls in vars(module).items():
                if not isinstance(cls, type) or not name.endswith('Tools'):
                    continue
                members = {}
                for method_name in dir(cls):
                    if method_name.startswith('_'):
                        continue
                    method = getattr(cls, method_name)
                    if not callable(method):
                        continue
                    try:
                        signature = str(inspect.signature(method))
                    except Exception:
                        signature = ''
                    members[method_name] = {'signature': signature,
                                           'doc': inspect.getdoc(method)}
                types[name] = members
            result[entry.name] = {'file': module.__file__, 'classes': types}
    except Exception as error:
        result['error'] = str(error)
    return result


def work():
    result = {'blueprints': {}, 'umg_api': read_umg_api()}
    for path in PATHS:
        bp = unreal.load_asset(path)
        assert bp, path
        graphs = {}
        for graph in unreal.BlueprintEditorLibrary.list_graphs(bp):
            ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
            def pin(p):
                return {'name': p.name, 'type': p.type_id, 'value': p.value,
                        'links': [str(q.node.get_name()) + ':' + str(q.index_id)
                                  for q in p.connected_pins]}
            graphs[graph.get_name()] = [
                {'name': info.node.get_name(), 'type': info.type_id,
                 'in': [pin(p) for p in info.input_pins],
                 'out': [pin(p) for p in info.output_pins]}
                for info in BT.get_node_infos(list(ed.list_all_nodes()))]
        cdo = unreal.get_default_object(bp.generated_class())
        row = {'graphs': graphs,
               'defaults': properties(cdo, [str(name) for name in
                   unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)])}
        if path == '/Game/UI/WBP_RunnerProgress':
            row['widget_tree'] = inspect_widgets(bp)
        result['blueprints'][path] = row
    result['font_exists'] = bool(unreal.load_asset('/Engine/EngineFonts/Roboto'))
    return result


run_editor(work, 'CombatUIInspection.json')
