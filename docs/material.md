# Material Format

Unpacked material has the following file structure:

```
MyMaterial/
├─ material.json
├─ uniforms/
│  ├─ ...
│  ├─ MyUniform.json
├─ buffers/
│  ├─ ...
│  ├─ MyBuffer.json
├─ passes/
│  ├─ ...
│  ├─ MyPass.json
│  ├─ MyPass/
│  │  ├─ ...
│  │  ├─ 0.ESSL_310.Fragment.glsl

```

## Material Schema

material.json

```json
{
  "version": 22,
  "name": "RenderChunk",
  "parent": "",
  "buffers": ["LightMapTexture", "MatTexture", "SeasonsTexture"],
  "uniforms": [
    "SubPixelOffset",
    "GlobalRoughness",
    "FogAndDistanceControl",
    "FogColor",
    "LightDiffuseColorAndIlluminance",
    "RenderChunkFogAlpha",
    "LightWorldSpaceDirection",
    "MaterialID",
    "ViewPositionAndTime",
    "MyAwesomeUniform"
  ],
  "uniform_overrides": {
    "MyAwesomeUniform": "BUILTIN_MinecraftCameraPosition"
  },
  "passes": [
    "DepthOnlyOpaque",
    "AlphaTest",
    "DepthOnly",
    "Opaque",
    "Transparent"
  ]
}
```

| Property                                             | Description               | Allowed values or types |
| ---------------------------------------------------- | ------------------------- | ----------------------- |
| `version`                                            | Material format version   | `22`                    |
| `name`                                               | Material name             | string                  |
| `parent`                                             | Parent material name      | string                  |
| `buffers`                                            | List of buffer names      | list of strings         |
| `uniforms`                                           | List of uniform names     | list of strings         |
| [`uniform_overrides`](material.md#uniform_overrides) | List of uniform overrides | dictionary of strings   |
| `passes`                                             | List of pass names        | list of strings         |

### uniform_overrides

This field enables overriding behavior of existing uniforms in the material.
Specifying override ID per uniform changes the behavior of that uniform.

For example, if you want uniform `MyAwesomeUniform` to return camera position, and `FogColor` to return cloud color, it can be achieved in the following way:

```json
"uniform_overrides": {
  "MyAwesomeUniform": "BUILTIN_MinecraftCameraPosition",
  "FogColor": "BUILTIN_MinecraftFogColor"
}
```

Below is a list of built-in (vanilla) uniform override IDs.

| Override ID                                | Notes                                                                                                                                                             |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| BUILTIN_MinecraftBiomeID                   | Biome ID (integer). List of biome IDs is available [here](https://github.com/Mojang/bedrock-samples/blob/preview/metadata/vanilladata_modules/mojang-biomes.json) |
| BUILTIN_MinecraftCloudHeight               | Y coordinate of where the clouds layer begins                                                                                                                     |
| BUILTIN_MinecraftDay                       | Current day count                                                                                                                                                 |
| BUILTIN_MinecraftDimensionID               | 0 - overworld, 1 - nether, 2 - end                                                                                                                                |
| BUILTIN_MinecraftLocalClientID             | Unknown, probably some kind of unique integer ID per player that can be accessed from scripting API                                                               |
| BUILTIN_MinecraftMoonIntensity             | Moon intensity from vibrant visuals (1 if VV is disabled)                                                                                                         |
| BUILTIN_MinecraftMoonPhase                 | FULL_MOON=0, WANING_GIBBOUS=1, FIRST_QUARTER=2, WANING_CRESCENT=3, NEW_MOON=4, WAXING_CRESCENT=5, LAST_QUARTER=6, WAXING_GIBBOUS=7                                |
| BUILTIN_MinecraftRenderDistance            | Render distance (in blocks)                                                                                                                                       |
| BUILTIN_MinecraftSunIntensity              | Sun intensity from vibrant visuals (1 if VV is disabled)                                                                                                          |
| BUILTIN_MinecraftTimeOfDay                 | 0 - noon, 0.25 - sunset, 0.5 - midnight, 0.75 - sunrise                                                                                                           |
| BUILTIN_MinecraftElapsedFrameTime          | Frame time (1/fps)                                                                                                                                                |
| BUILTIN_MinecraftWeatherID                 | 0 - clear, 1 - rain, 2 - snow                                                                                                                                     |
| BUILTIN_MinecraftCameraFacingDirection     |                                                                                                                                                                   |
| BUILTIN_MinecraftCameraPosition            |                                                                                                                                                                   |
| BUILTIN_MinecraftLastCameraFacingDirection | Camera direction from last frame                                                                                                                                  |
| BUILTIN_MinecraftLastCameraPosition        | Camera position from last frame                                                                                                                                   |
| BUILTIN_MinecraftSunDirection              |                                                                                                                                                                   |
| BUILTIN_MinecraftCloudColor                |                                                                                                                                                                   |
| BUILTIN_MinecraftFogColor                  |                                                                                                                                                                   |
| BUILTIN_MinecraftMoonColor                 | Moon color from vibrant visuals (1 if VV is disabled)                                                                                                             |
| BUILTIN_MinecraftSunColor                  | Sun color from vibrant visuals (1 if VV is disabled)                                                                                                              |

## Buffer Schema

```json
{
  "name": "PBRData",
  "reg1": 2,
  "reg2": 2,
  "type": "structBuffer",
  "precision": "lowp",
  "access": "readonly",
  "texture_format": "",
  "default_texture": "",
  "unordered_access": true,
  "always_one": 1,
  "texture_path": "",
  "sampler_state": {
    "filter": "Point",
    "wrapping": "Clamp"
  },
  "custom_type_info": {
    "struct": "PBRTextureData",
    "size": 64
  }
}
```

| Property                                           | Description                                                                             | Allowed values or types                                                                                                                                                 | Details                                                                                                                  |
| -------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `name`                                             | Buffer name                                                                             | string                                                                                                                                                                  |                                                                                                                          |
| `reg1`                                             | Register or binding                                                                     | integer                                                                                                                                                                 | Same as reg2                                                                                                             |
| `reg2`                                             | Register or binding                                                                     | integer                                                                                                                                                                 | Same as reg1                                                                                                             |
| `type`                                             | Buffer type                                                                             | `texture2D` `texture2DArray` `external2D` `texture3D` `textureCube` `textureCubeArray` `structBuffer` `rawBuffer` `accelerationStructure` `shadow2D` `shadow2DArray`    |                                                                                                                          |
| `precision`                                        | Buffer precision                                                                        | `lowp` `mediump` `highp`                                                                                                                                                |                                                                                                                          |
| `access`                                           | Buffer access type                                                                      | `undefined` `readonly` `writeonly` `readwrite`                                                                                                                          |                                                                                                                          |
| `texture_format`                                   | Texture format                                                                          | Arbitrary string, possible values include (but not limited to): (empty string) `r32ui` `rg32ui` `rgba32ui` `r32f` `r16f` `rg16f` `rgba16f` `rgba8` `rg8` `r8` `rgba32f` | Possible values were extracted from [bgfx_compute.sh](https://github.com/bkaradzic/bgfx/blob/master/src/bgfx_compute.sh) |
| `default_texture`                                  | Default texture (unknown what it does)                                                  | string (empty string means that the buffer doesn't have this property)                                                                                                  | The only observed value in the game was `white`                                                                          |
| `unordered_access`                                 | Enables unordered access (UBO)                                                          | bool                                                                                                                                                                    |                                                                                                                          |
| `always_one`                                       | Unknown (must always be 1, otherwise buffer breaks)                                     | integer                                                                                                                                                                 | All materials have a value of 1                                                                                          |
| `texture_path`                                     | Specifies texture that will be used by this buffer. Example: `textures/environment/sun` | string (empty string means that the buffer doesn't have this property)                                                                                                  |                                                                                                                          |
| [`sampler_state`](material.md#sampler_state)       | Overwrites sampler state properties                                                     | enum. If set to empty object `{}` that means that the buffer doesn't have this property                                                                                 |                                                                                                                          |
| [`custom_type_info`](material.md#custom_type_info) | Information about custom structured buffer (SSBO) type                                  | enum. If set to empty object `{}` that means that the buffer doesn't have this property                                                                                 |                                                                                                                          |

??? warning "Changing Buffer Registers"

    The difference between `reg1` and `reg2` is unknown, in the material files they always have the same value. Lazurite uses `reg1` for setting AUTOREG macros, however the game seems to be using `reg2` for deciding which register to actually use. Therefore it is recommended to set both properties when changing buffer register or binding.

### sampler_state

| Property   | Description      | Allowed values or types |
| ---------- | ---------------- | ----------------------- |
| `filter`   | Texture filter   | `Point` `Bilinear`      |
| `wrapping` | Texture wrapping | `Clamp` `Repeat`        |

### custom_type_info

| Property | Description            | Allowed values or types |
| -------- | ---------------------- | ----------------------- |
| `struct` | Struct name            | string                  |
| `size`   | Struct size (in bytes) | integer                 |

## Uniform Schema

```json
{
  "name": "GlobalRoughness",
  "type": "vec4",
  "count": 1,
  "default": [0.5, 0.5, 0.5, 0.5]
}
```

| Property  | Description              | Allowed values or types                | Details                                                        |
| --------- | ------------------------ | -------------------------------------- | -------------------------------------------------------------- |
| `name`    | Uniform name             | string                                 |                                                                |
| `type`    | Uniform type             | `vec4` `mat3` `mat4` `external`        |                                                                |
| `count`   | Number of array elements | integer (1 if uniform is not an array) | For example, in case of `uniform vec4 Bones[5];` it would be 5 |
| `default` | Default value            | list of floats                         | 4 elements for `vec4`, 9 for `mat3`, 16 for `mat4`             |

## Pass schema

```json
{
  "name": "ColorPostProcess",
  "supported_platforms": {
    "Direct3D_SM40": true,
    "Direct3D_SM50": true,
    "Direct3D_SM60": true,
    "Direct3D_SM65": true,
    "Direct3D_XB1": true,
    "Direct3D_XBX": true,
    "GLSL_120": true,
    "GLSL_430": true,
    "ESSL_300": true,
    "ESSL_310": true,
    "Metal": true,
    "Vulkan": true,
    "Nvn": true,
    "PSSL": true,
    "Unknown": true
  },
  "fallback_pass": "Fallback",
  "default_blend_mode": "",
  "default_variant": {
    "AlphaTest": "On"
  },
  "variants": [
    {
      "is_supported": true,
      "flags": {
        "AlphaTest": "On"
      },
      "shaders": [
        {
          "file_name": "0.ESSL_300.Fragment.glsl",
          "stage": "Fragment",
          "platform": "ESSL_300",
          "inputs": [
            {
              "name": "texcoord0",
              "type": "vec2",
              "semantic": "TEXCOORD0",
              "per_instance": false,
              "precision": "",
              "interpolation": ""
            }
          ],
          "hash": 6879661314034565044,
          "bgfx_shader": {
            "hash": 1010703983,
            "uniforms": [
              {
                "name": "ExposureCompensation",
                "type_bits": 2,
                "count": 1,
                "reg_index": 0,
                "reg_count": 1
              }
            ],
            "group_size": [],
            "attributes": [],
            "size": -1
          }
        }
      ]
    }
  ]
}
```

| Property              | Description                      | Allowed values or types                                                                                                                                                               | Details                                                                                                                        |
| --------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `name`                | Shader pass name                 | string                                                                                                                                                                                |                                                                                                                                |
| `supported_platforms` | Platforms that support this pass | dictionary with [platforms](platforms.md) as keys and bool as values                                                                                                                  | Unsupported platforms will not render this pass and instead use fallback_pass (if defined)                                     |
| `fallback_pass`       | Name of the fallback pass        | string                                                                                                                                                                                | This pass will be used if current pass is unsupported                                                                          |
| `default_blend_mode`  | Unknown                          | (empty string) `NoneMode` `Replace` `AlphaBlend` `ColorBlendAlphaAdd` `PreMultiplied` `InvertColor` `Additive` `AdditiveAlpha` `Multiply` `MultiplyBoth` `InverseSrcAlpha` `SrcAlpha` | Empty string indicates that shader pass doesn't have this property                                                             |
| `default_variant`     | Default variant flags            | Dictionary of strings                                                                                                                                                                 | Variant with specified flags will be used as default, if the game fails to find a variant with requested flags in the material |
| `variants`            | List of variants                 | See [variant schema](material.md#variant) for details                                                                                                                                 |                                                                                                                                |

### variant

| Property       | Description                           | Allowed values or types |
| -------------- | ------------------------------------- | ----------------------- |
| `is_supported` | Unknown                               | bool                    |
| `flags`        | Dictionary with `flag: value` pairs   | Dictionary of strings   |
| `shaders`      | List of individual shader definitions |                         |

### shader

| Property      | Description                                                               | Allowed values or types                  |
| ------------- | ------------------------------------------------------------------------- | ---------------------------------------- |
| `file_name`   | Name of the file with compiled shader (in `material/passes/<pass name>/`) | string                                   |
| `stage`       | Shader pipeline stage                                                     | `Vertex` `Fragment` `Compute` `Unknown`  |
| `platform`    | List of platforms                                                         | See possible values [here](platforms.md) |
| `hash`        | Unknown                                                                   | 64bit unsigned int                       |
| `inputs`      | List of input (attributes or varyings) definitions                        | Details [here](material.md#input)        |
| `bgfx_shader` | Data of BGFX compiled shader                                              | Undocumented                             |

### input

| Property        | Description                         | Allowed values or types                                                                                           | Details                                                                                                                                 |
| --------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `name`          | Input name                          | string                                                                                                            |                                                                                                                                         |
| `type`          | Input type                          | `float` `vec2` `vec3` `vec4` `int` `ivec2` `ivec3` `ivec4` `uint` `uvec2` `uvec3` `uvec4` `mat4`                  |                                                                                                                                         |
| `semantic`      | Input semantic                      | `POSITION` `NORMAL` `TANGENT` `BITANGENT` `COLOR` `BLENDINDICES` `BLENDWEIGHT` `TEXCOORD` `UNKNOWN` `FRONTFACING` | Semantic string is also alowed to end with an integer index e.g. `COLOR1`, `TEXCOORD3`. If no index is provides, it is assumed to be 0. |
| `per_instance`  | Indicates if input is instance data | bool                                                                                                              | Typically it's only set to true for `instanceData` attribute.                                                                           |
| `precision`     | Precision qualifier                 | (empty string) `lowp` `mediump` `highp`                                                                           | Empty string indicates that shader input doesn't have this property.                                                                    |
| `interpolation` | Interpolation qualifier             | (empty string) `flat` `smooth` `noperspective` `centroid`                                                         | Empty string indicates that shader input doesn't have this property.                                                                    |
