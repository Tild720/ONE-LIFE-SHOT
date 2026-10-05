"""Author the shared ground warning/shockwave material through Unreal Editor.

Importing this source does not create or modify assets. The calling authoring
script must inspect the Content Browser and explicitly allow first creation.
The existing TelegraphMesh and RPG visual timer own all gameplay and lifetime.
"""

MATERIAL_PATH = '/Game/Enemies/Materials/M_AttackTelegraph'
SCALAR_DEFAULTS = {'ShapeMode': 0.0, 'EffectProgress': 0.0, 'Opacity': 0.85}
VECTOR_NAMES = {'TracerColor'}

FIELD_SHADER = r'''
// Engine Plane: local +X is the lane's direction. No textures are required.
float2 p = UV * 2.0 - 1.0;
float2 q = abs(p);
float aa = max(max(fwidth(p.x), fwidth(p.y)), 0.002);
float progress = saturate(EffectProgress);
float coverage = 0.0;
float fade = 1.0;
float flareHeat = 0.0;

if (ShapeMode < 0.5)
{
    // The plane bounds match damage length and half-width. Keep the ground
    // visible; edges and small direction marks carry the warning.
    float rectangle = max(q.x, q.y);
    float inside = 1.0 - smoothstep(1.0 - aa, 1.0, rectangle);
    float border = 1.0 - smoothstep(0.028, 0.045 + aa,
                                  min(1.0 - q.x, 1.0 - q.y));
    float lane = 1.0 - smoothstep(0.018, 0.032 + aa, q.y);
    float dashes = 1.0 - step(0.46, frac(UV.x * 8.0));
    float chevronX = 0.64 - q.y * 0.65;
    float chevron = 1.0 - smoothstep(0.015, 0.028 + aa,
                                   abs(frac(UV.x * 4.0) - chevronX));
    chevron *= 1.0 - smoothstep(0.32, 0.38, q.y);
    chevron *= smoothstep(0.04, 0.12, UV.x);
    chevron *= 1.0 - smoothstep(0.94, 0.99, UV.x);
    coverage = inside * max(0.045,
                            max(border, max(lane * dashes * 0.24,
                                            chevron * 0.38)));
}
else if (ShapeMode < 1.5)
{
    // A hollow perimeter gives the exact Heavy danger radius. The middle is
    // fully transparent, so robots, pickups, and floor remain readable.
    float radius = length(p);
    float ring = 1.0 - smoothstep(0.022, 0.040 + aa,
                                abs(radius - 0.958));
    float cardinal = 1.0 - smoothstep(0.010, 0.020 + aa,
                                    min(q.x, q.y));
    float tickBand = smoothstep(0.80, 0.83, radius)
                   * (1.0 - smoothstep(0.945, 0.96, radius));
    coverage = max(ring, cardinal * tickBand * 0.55)
               * (1.0 - smoothstep(1.0 - aa, 1.0, radius));
}
else if (ShapeMode < 2.5)
{
    // RPG impact: a thin wave expands quickly to the blast boundary, then
    // fades. It never becomes a filled disk or hides the next weapon.
    float radius = length(p);
    float travel = saturate(progress / 0.45);
    float angle = atan2(p.y, p.x);
    float irregularity = sin(angle * 11.0 + travel * 2.0) * 0.008
                       + sin(angle * 19.0 - travel) * 0.004;
    float waveRadius = lerp(0.025, 0.958, travel) + irregularity;
    float width = lerp(0.044, 0.027, travel);
    coverage = 1.0 - smoothstep(width, width + 0.018 + aa,
                                abs(radius - waveRadius));
    float wake = 1.0 - smoothstep(0.015, 0.034 + aa,
                                abs(radius - waveRadius * 0.78));
    coverage = max(coverage, wake * (1.0 - travel) * 0.24);
    coverage *= 1.0 - smoothstep(1.0 - aa, 1.0, radius);
    fade = 1.0 - smoothstep(0.35, 1.0, progress);
}
else
{
    // A small camera-facing impact plume with irregular hot edges and radial
    // sparks. Its bounded size leaves the large damage area and pickups clear.
    float radius = length(p);
    float angle = atan2(p.y, p.x);
    float growth = saturate(progress / 0.32);
    float lobes = sin(angle * 7.0 + progress * 5.0) * 0.075
                + sin(angle * 13.0 - progress * 4.0) * 0.038;
    float plumeRadius = lerp(0.14, 0.69, growth) * (1.0 - progress * 0.22);
    float irregularRadius = radius / max(1.0 + lobes, 0.8);
    float fire = 1.0 - smoothstep(plumeRadius * 0.53,
                                 plumeRadius + aa, irregularRadius);
    float streaks = pow(max(sin(angle * 11.0 + 0.7), 0.0), 20.0);
    float sparkRadius = lerp(0.20, 0.95, growth);
    float sparks = streaks * smoothstep(sparkRadius - 0.24,
                                        sparkRadius - 0.12, radius)
                  * (1.0 - smoothstep(sparkRadius - 0.035,
                                      sparkRadius + aa, radius));
    coverage = max(fire * 0.8, sparks);
    coverage *= 1.0 - smoothstep(0.97, 1.0, radius);
    fade = 1.0 - smoothstep(0.30, 0.68, progress);
    flareHeat = (1.0 - smoothstep(plumeRadius * 0.20,
                                 plumeRadius * 0.60, radius)) * fade;
}

// Existing Blueprint callers multiply TracerColor at aim lock/discharge.
// Preserve that contract but limit brightness so role hues do not wash white.
float3 rawColor = max(TracerColor, float3(0.0, 0.0, 0.0));
float peak = max(max(rawColor.r, rawColor.g), rawColor.b);
float3 hue = rawColor / max(peak, 0.001);
float commitment = saturate((peak - 1.0) / 3.0);
float3 emission = hue * (1.10 + commitment * 0.18);
if (ShapeMode >= 2.5)
    emission = lerp(hue * 2.2, float3(4.5, 3.3, 1.6), flareHeat);
float alpha = saturate(Opacity) * saturate(coverage) * fade;
return float4(emission, alpha);
'''


def author_field_material(allow_create=False):
    """Create/rebuild the inspected material and fail on shader compile errors.

    ``allow_create=True`` is required only after the caller has inspected the
    Content Browser and confirmed no existing equivalent. If the target exists,
    its complete parameter contract must already identify this field material.
    Returns the saved Unreal Material for the caller to assign to components.
    """
    import unreal
    from editor_toolset.toolsets.material import MaterialTools

    library = unreal.MaterialEditingLibrary
    material = unreal.load_asset(MATERIAL_PATH)
    if material is None:
        assert allow_create, 'Inspect the Content Browser before creating M_AttackTelegraph'
        folder, asset_name = MATERIAL_PATH.rsplit('/', 1)
        material = MaterialTools.create_material(folder, asset_name)
    else:
        assert isinstance(material, unreal.Material), MATERIAL_PATH
        scalars = {str(n) for n in library.get_scalar_parameter_names(material)}
        vectors = {str(n) for n in library.get_vector_parameter_names(material)}
        assert scalars == set(SCALAR_DEFAULTS) and vectors == VECTOR_NAMES, (
            'Existing material has a different contract; do not overwrite it',
            sorted(scalars), sorted(vectors))

    material.set_editor_property('material_domain', unreal.MaterialDomain.MD_SURFACE)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided', True)
    material.set_editor_property('disable_depth_test', False)
    library.delete_all_material_expressions(material)

    def expression(cls, x, y, **properties):
        node = library.create_material_expression(material, cls, x, y)
        assert node, cls
        for name, value in properties.items():
            node.set_editor_property(name, value)
        return node

    uv = expression(unreal.MaterialExpressionTextureCoordinate, -820, -260,
                    coordinate_index=0, u_tiling=1.0, v_tiling=1.0)
    color = expression(unreal.MaterialExpressionVectorParameter, -820, -100,
                       parameter_name='TracerColor',
                       default_value=unreal.LinearColor(1.0, 0.22, 0.035, 1.0),
                       group='Combat Field')
    nodes = {'UV': (uv, ''), 'TracerColor': (color, 'RGB')}
    for index, (name, default) in enumerate(SCALAR_DEFAULTS.items()):
        node = expression(unreal.MaterialExpressionScalarParameter,
                          -820, 80 + index * 150,
                          parameter_name=name, default_value=default,
                          group='Combat Field')
        nodes[name] = (node, '')

    custom_inputs = []
    for name in nodes:
        custom_input = unreal.CustomInput()
        custom_input.set_editor_property('input_name', name)
        custom_inputs.append(custom_input)
    field = expression(unreal.MaterialExpressionCustom, -280, 20,
                       code=FIELD_SHADER,
                       output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT4,
                       description='Ground threat outline and RPG shockwave',
                       inputs=custom_inputs)
    for name, (source, output_name) in nodes.items():
        assert library.connect_material_expressions(source, output_name, field, name), name

    rgb = expression(unreal.MaterialExpressionComponentMask, 100, -80,
                     r=True, g=True, b=True, a=False)
    alpha = expression(unreal.MaterialExpressionComponentMask, 100, 120,
                       r=False, g=False, b=False, a=True)
    for mask in [rgb, alpha]:
        assert library.connect_material_expressions(field, '', mask, '')
    assert library.connect_material_property(rgb, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assert library.connect_material_property(alpha, '', unreal.MaterialProperty.MP_OPACITY)
    library.layout_material_expressions(material)
    MaterialTools.recompile(material)

    assert {str(n) for n in library.get_scalar_parameter_names(material)} == set(SCALAR_DEFAULTS)
    assert {str(n) for n in library.get_vector_parameter_names(material)} == VECTOR_NAMES
    assert unreal.EditorAssetLibrary.save_loaded_asset(material, False), MATERIAL_PATH
    return material
