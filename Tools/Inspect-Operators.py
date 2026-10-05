import json
from pathlib import Path
import unreal
bp = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EventGraph')
types = ed.list_available_nodes([])
matches = [x for x in types if any(q in x.casefold() for q in ['operator','연산','multiply','곱하','더하','나누','subtract','빼기','divide'])]
(Path(unreal.Paths.project_saved_dir())/'OperatorTypes.json').write_text(json.dumps(matches,ensure_ascii=False),encoding='utf-8')
