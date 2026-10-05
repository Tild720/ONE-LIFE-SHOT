import json
from pathlib import Path
import unreal
report={}
for path in ['/Engine/EngineFonts/Roboto','/Engine/EngineFonts/RobotoDistanceField']:
    font=unreal.load_asset(path)
    assert font,path
    row={'path':font.get_path_name()}
    for name in ['font_cache_type','legacy_font_size','characters','import_options']:
        try:
            value=font.get_editor_property(name)
            row[name]=str(value)[:1600] if name!='characters' else [{'height':c.get_editor_property('v_size'),'width':c.get_editor_property('u_size')} for c in list(value)[:4]]
        except Exception as e:row[name+'_error']=str(e)
    report[path]=row
(Path(unreal.Paths.project_saved_dir())/'QAFonts.json').write_text(json.dumps(report,indent=2))
