"""Import the inspected KayKit facility pieces through Unreal Editor only.

Importing this module does nothing. ``work()`` reuses registered meshes with
the same name or original FBX source. Existing meshes outside the new facility
group retain their materials; the map author applies the shared atlas per actor.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unreal
from CombatAuthoring import run_editor
from editor_toolset.toolsets.material import MaterialTools


FACILITY_ROOT = '/Game/LevelPrototyping/KayKit'
MESH_FOLDER = FACILITY_ROOT + '/Meshes'
TEXTURE_PATH = FACILITY_ROOT + '/Textures/T_FacilityAtlas'
MATERIAL_PATH = FACILITY_ROOT + '/Materials/M_FacilityAtlas'
SOURCE_NAMES = (
    'Wall', 'Wall_Window_Open', 'Wall_Doorway', 'Wall_Decorated',
    'Pillar_A', 'Pillar_B', 'Barrel_A', 'Barrel_B', 'Barrel_C',
    'Workbench_Decorated', 'Locker', 'Locker_Decorated',
    'table_medium_Decorated', 'Box_A',
)


def source_root():
    root = (Path(__file__).resolve().parent.parent / 'One_life_Shot' /
            'Content' / 'KayKit_Prototype_Bits_1.1_EXTRA' /
            'KayKit_Prototype_Bits_1.1_EXTRA')
    assert root.is_dir(), 'Inspected KayKit source pack is missing: ' + str(root)
    return root


def _normalized_name(name):
    name = str(name)
    if name.lower().startswith('sm_'):
        name = name[3:]
    return re.sub(r'[^a-z0-9]', '', name.lower())


def _original_sources(asset):
    try:
        data = asset.get_editor_property('asset_import_data')
        return [str(name) for name in data.extract_filenames()] if data else []
    except Exception:
        return []


def _same_source(left, right):
    return Path(left).resolve().as_posix().lower() == Path(right).resolve().as_posix().lower()


def _registered_meshes():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    return [record for record in registry.get_assets_by_path('/Game', True)
            if str(record.asset_class_path.asset_name) == 'StaticMesh']


def _reuse_mesh(records, source_name, source_file):
    destination = MESH_FOLDER + '/SM_' + source_name
    direct = unreal.load_asset(destination)
    if direct:
        assert isinstance(direct, unreal.StaticMesh), destination
        return direct
    # Do not manufacture a second copy of an already imported KayKit model.
    named = [record for record in records
             if _normalized_name(record.asset_name) == _normalized_name(source_name)]
    for record in named:
        mesh = record.get_asset()
        sources = _original_sources(mesh)
        if any(_same_source(name, source_file) for name in sources):
            return mesh
        if sources and any(Path(name).stem.lower() == source_name.lower()
                           for name in sources):
            return mesh
    # Source identity catches a mesh that was given a different asset name.
    for record in records:
        if record in named:
            continue
        mesh = record.get_asset()
        if any(_same_source(name, source_file) for name in _original_sources(mesh)):
            return mesh
    return None


def _import_texture(source_file):
    texture = unreal.load_asset(TEXTURE_PATH)
    if not texture:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        for record in registry.get_assets_by_path('/Game', True):
            if str(record.asset_class_path.asset_name) != 'Texture2D':
                continue
            candidate = record.get_asset()
            if any(_same_source(name, source_file)
                   for name in _original_sources(candidate)):
                texture = candidate
                break
    created = texture is None
    if created:
        folder, name = TEXTURE_PATH.rsplit('/', 1)
        task = unreal.AssetImportTask()
        for key, value in {
            'filename': str(source_file), 'destination_path': folder,
            'destination_name': name, 'automated': True,
            'replace_existing': False, 'save': False,
            'factory': unreal.TextureFactory(),
        }.items():
            task.set_editor_property(key, value)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        textures = [unreal.load_asset(path) for path in task.get_editor_property('imported_object_paths')]
        textures = [asset for asset in textures if isinstance(asset, unreal.Texture2D)]
        assert len(textures) == 1, ('Texture import failed', str(source_file),
                                    list(task.get_editor_property('imported_object_paths')))
        texture = textures[0]
    assert isinstance(texture, unreal.Texture2D), str(texture)
    # This is an authored color atlas, not a packed mask or a normal map.
    texture.set_editor_property('srgb', True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(texture, False), texture.get_path_name()
    return texture, created


def _atlas_material(texture):
    material = unreal.load_asset(MATERIAL_PATH)
    created = material is None
    library = unreal.MaterialEditingLibrary
    if created:
        folder, name = MATERIAL_PATH.rsplit('/', 1)
        material = MaterialTools.create_material(folder, name)
        assert isinstance(material, unreal.Material), MATERIAL_PATH
        material.set_editor_property('material_domain', unreal.MaterialDomain.MD_SURFACE)
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        sample = library.create_material_expression(material, unreal.MaterialExpressionTextureSample, -480, -100)
        assert sample
        sample.set_editor_property('texture', texture)
        roughness = library.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 130)
        metal = library.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 240)
        assert roughness and metal
        roughness.set_editor_property('r', 0.78)
        metal.set_editor_property('r', 0.12)
        assert library.connect_material_property(sample, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
        assert library.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
        assert library.connect_material_property(metal, '', unreal.MaterialProperty.MP_METALLIC)
        library.layout_material_expressions(material)
        MaterialTools.recompile(material)
        assert unreal.EditorAssetLibrary.save_loaded_asset(material, False), MATERIAL_PATH
    else:
        assert isinstance(material, unreal.Material), MATERIAL_PATH
        # Repeated runs reuse this authored material. Never erase a graph that
        # could have been deliberately changed after the first map pass.
        base = MaterialTools.get_property_input(material, unreal.MaterialProperty.MP_BASE_COLOR)
        assert base.expression, 'Existing facility material has no BaseColor input'
    return material, created


def _import_mesh(source_file, source_name):
    options = unreal.FbxImportUI()
    for key, value in {
        'automated_import_should_detect_type': False,
        'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH,
        'original_import_type': unreal.FBXImportType.FBXIT_STATIC_MESH,
        'import_as_skeletal': False, 'import_mesh': True,
        'import_animations': False, 'create_physics_asset': False,
        'import_materials': False, 'import_textures': False,
        'override_full_name': True,
    }.items():
        options.set_editor_property(key, value)
    static_options = options.get_editor_property('static_mesh_import_data')
    for key, value in {
        'combine_meshes': True, 'generate_lightmap_u_vs': True,
        'auto_generate_collision': True, 'convert_scene': True,
        'convert_scene_unit': True, 'force_front_x_axis': False,
        'import_uniform_scale': 1.0, 'transform_vertex_to_absolute': True,
        'bake_pivot_in_vertex': False, 'build_nanite': False,
        'normal_import_method': unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
    }.items():
        static_options.set_editor_property(key, value)
    task = unreal.AssetImportTask()
    for key, value in {
        'filename': str(source_file), 'destination_path': MESH_FOLDER,
        'destination_name': 'SM_' + source_name,
        'automated': True, 'replace_existing': False, 'save': False,
        'factory': unreal.FbxFactory(), 'options': options,
    }.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.get_editor_property('imported_object_paths'))
    objects = [unreal.load_asset(path) for path in paths]
    meshes = [asset for asset in objects if isinstance(asset, unreal.StaticMesh)]
    assert len(meshes) == 1, ('Expected exactly one combined static mesh', source_name, paths)
    assert not any(isinstance(asset, unreal.SkeletalMesh) for asset in objects), paths
    return meshes[0]


def _mesh_manifest(mesh, name, source_file, created, material):
    bounds = mesh.get_bounds()
    origin, extent = bounds.origin, bounds.box_extent
    return {
        'source_name': name, 'source': str(source_file),
        'path': mesh.get_path_name(), 'created': created,
        'bounds': {
            'origin': [origin.x, origin.y, origin.z],
            'extent': [extent.x, extent.y, extent.z],
            'size': [extent.x * 2, extent.y * 2, extent.z * 2],
            'min': [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z],
            'max': [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z],
        },
        'material_slots': [str(slot.material_slot_name)
                           for slot in mesh.get_editor_property('static_materials')],
        'materials': [slot.material_interface.get_path_name() if slot.material_interface else None
                      for slot in mesh.get_editor_property('static_materials')],
        'actor_material_override': material.get_path_name(),
        'collision_note': 'Imported simple collision. Decorative actors disable collision; doorway box collision must not close the passage.',
    }


def work():
    root = source_root()
    atlas_source = root / 'Textures' / 'prototypebits_texture_alt_B.png'
    assert atlas_source.is_file(), 'Inspected grayscale atlas is missing: ' + str(atlas_source)
    source_folder = root / 'Assets' / 'fbx'
    assert source_folder.is_dir(), str(source_folder)
    records = _registered_meshes()
    texture, texture_created = _import_texture(atlas_source)
    material, material_created = _atlas_material(texture)
    result = {
        'texture': texture.get_path_name(), 'texture_created': texture_created,
        'texture_srgb': texture.get_editor_property('srgb'),
        'material': material.get_path_name(), 'material_created': material_created,
        'roughness': 0.78, 'metallic': 0.12,
        'meshes': [], 'skipped': [], 'reused_floor': '/Game/Characters/KayKit/Assets/fbx/Floor',
        'untouched': ['Player and enemy materials', 'Existing Floor geometry'],
    }
    for name in SOURCE_NAMES:
        source_file = source_folder / (name + '.fbx')
        if not source_file.is_file():
            result['skipped'].append({'source_name': name, 'reason': 'Inspected source file is no longer present'})
            continue
        mesh = _reuse_mesh(records, name, source_file)
        created = mesh is None
        if created:
            mesh = _import_mesh(source_file, name)
            assert len(mesh.get_editor_property('static_materials')) > 0, name
            for index in range(len(mesh.get_editor_property('static_materials'))):
                mesh.set_material(index, material)
            assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, False), mesh.get_path_name()
        # Reused mesh defaults stay untouched; the map applies the atlas to the
        # environment actor so unrelated users of that asset do not change.
        result['meshes'].append(_mesh_manifest(mesh, name, source_file, created, material))
    assert len(result['meshes']) + len(result['skipped']) == len(SOURCE_NAMES)
    return result


if __name__ == '__main__':
    run_editor(work, 'FacilityImport.json')
