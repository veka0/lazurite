# Getting Started

This guide will walk you through the process of creating your first shader with lazurite, step by step.
We will be creating a simple terrain shader, that modifies RenderChunk material.

## Requirements

First, you need to install lazurite (see [installation instructions](index.md#installation)). We will also need shaderc
compiler executable, in order to compile shaders from source code. See [build command](commands.md#build) for download links.

Some general [shader theory](https://thebookofshaders.com) and BGFX [shader compiler](https://bkaradzic.github.io/bgfx/tools.html#shader-compiler-shaderc)
knowledge would also help.

!!!tip "BGFX"

    BGFX is the cross platform graphics library that RenderDragon is built on top of.

## Creating a new project

First, let's create a new project. Make a new folder. In this guide we will call it `helloWorld`.
Add `project.json` file into it (leave it empty for now), and make a new `RenderChunk` folder inside of `helloWorld`.
This folder represents a RenderChunk material (RenderChunk.material.bin)
that we will be modifying. Then add `shaders` folder inside of `RenderChunk`, this is where shader source code will go.
Also add a `vanilla` folder, next to your project folder and copy your vanilla `RenderChunk.material.bin` file into it.

Resulting directory tree should look like this:

```
helloWorld/
├── RenderChunk/
│   └── shaders/
└── project.json
vanilla/
└── RenderChunk.material.bin
```

## Obtaining source code

Next step would be to get the source code. This guide will show you how to obtain it by yourself, for any game version.

Lazurite has a [restore](commands.md#restore) command that can partially recover source code from **_Android_** materials.
You can use it on RenderChunk.material.bin file that you copied from your Android game installation:

```sh
lazurite restore RenderChunk.material.bin
```

Which should generate 3 files:

```
RenderChunk.ESSL_310.Fragment.sc
RenderChunk.ESSL_310.Vertex.sc
RenderChunk.varying.def.sc
```

Or you can also get the results of a `restore` command from this repository: <https://github.com/veka0/mcbe-shader-codebase/tree/main/materials/RenderChunk>

You also need a [bgfx_shader.sh](https://github.com/SurvivalApparatusCommunication/RenderDragonSourceCodeInv/blob/1.20.60/include/bgfx_shader.sh) file

Copy those files into `shaders/` directory in RenderChunk and rename them, to get the following directory tree:

```
helloWorld/
├── RenderChunk/
│   └── shaders/
│       ├── bgfx_shader.sh
│       ├── fragment.sc
│       ├── vertex.sc
│       └── varying.def.sc
└── project.json
vanilla/
└── RenderChunk.material.bin
```

### Formatting

Source code, generated with restore command is not immediately compilable and requires manual editing to make it work.
We will be doing the bare minimum editing that's required to compile RenderChunk shaders.

#### vertex.sc

Let's start by editing vertex.sc.

First, add the `#include "bgfx_shader.sh"` line at the beginning of the file, but after `$input` and `$output` directives. This is a necessary step for all BGFX shaders and it should look something like this:

```glsl linenums="1" hl_lines="7"
$input a_color0, a_position, a_texcoord0, a_texcoord1
#ifdef INSTANCING__ON
$input i_data1, i_data2, i_data3
#endif
$output v_color0, v_fog, v_lightmapUV, v_texcoord0, v_worldPos

#include "bgfx_shader.sh"
```

---

Then remove the following code at the start of the file. It's not needed since `instMul` functions are added from `bgfx_shader.sh`

```glsl linenums="1"
#ifdef INSTANCING__ON
vec3 instMul(vec3 _vec, mat3 _mtx) {
    return ((_vec) * (_mtx)); // Attention!
}
vec3 instMul(mat3 _mtx, vec3 _vec) {
    return ((_mtx) * (_vec)); // Attention!
}
vec4 instMul(vec4 _vec, mat4 _mtx) {
    return ((_vec) * (_mtx)); // Attention!
}
vec4 instMul(mat4 _mtx, vec4 _vec) {
    return ((_mtx) * (_vec)); // Attention!
}
#endif
```

Next, we need to go through the code marked with `// Attention!` comment.
Lazurite marks lines of code in this way, if they may contain matrix multiplication or matrix element access.

By convention, multiplying matrices by other matrices or vectors in BGFX shaders has to be done with a `mul()` function.
In addition, GLSL uses a different matrix row-column order in comparison to other APIs, so we need to switch row and column indices
when shader is compiled for APIs other than GLSL.

Edit the following function:

```glsl linenums="1"
vec4 jitterVertexPosition(vec3 worldPosition) {
    mat4 offsetProj = Proj;
    offsetProj[2][0] += SubPixelOffset.x; // Attention!
    offsetProj[2][1] -= SubPixelOffset.y; // Attention!
    return ((offsetProj) * (((View) * (vec4(worldPosition, 1.0f))))); // Attention!
}
```

Into this:

```glsl linenums="1"
vec4 jitterVertexPosition(vec3 worldPosition) {
    mat4 offsetProj = Proj;
    #if BGFX_SHADER_LANGUAGE_GLSL
    offsetProj[2][0] += SubPixelOffset.x;
    offsetProj[2][1] -= SubPixelOffset.y;
    #else
    offsetProj[0][2] += SubPixelOffset.x;
    offsetProj[1][2] -= SubPixelOffset.y;
    #endif
    return mul(offsetProj, mul(View, vec4(worldPosition, 1.0f)));
}
```

---

In this function:

```glsl linenums="1" hl_lines="8"
void transformAsBillboardVertex(inout StandardVertexInput stdInput, inout VertexOutput vertOutput) {
    stdInput.worldPos += vec3(0.5, 0.5, 0.5);
    vec3 forward = normalize(stdInput.worldPos - ViewPositionAndTime.xyz);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), forward));
    vec3 up = cross(forward, right);
    vec3 offsets = stdInput.vertInput.color0.xyz;
    stdInput.worldPos -= up * (offsets.z - 0.5) + right * (offsets.x - 0.5);
    vertOutput.position = ((ViewProj) * (vec4(stdInput.worldPos, 1.0))); // Attention!
}
```

edit the highlighted line into this:

```glsl linenums="8"
vertOutput.position = mul(ViewProj, vec4(stdInput.worldPos, 1.0));
```

---

In this function:

```glsl linenums="1" hl_lines="4 14"
void StandardTemplate_VertSharedTransform(inout StandardVertexInput stdInput, inout VertexOutput vertOutput) {
    VertexInput vertInput = stdInput.vertInput;
    #ifdef INSTANCING__OFF
    vec3 wpos = ((World) * (vec4(vertInput.position, 1.0))).xyz; // Attention!
    #endif
    #ifdef INSTANCING__ON
    mat4 model;
    model[0] = vec4(vertInput.instanceData0.x, vertInput.instanceData1.x, vertInput.instanceData2.x, 0);
    model[1] = vec4(vertInput.instanceData0.y, vertInput.instanceData1.y, vertInput.instanceData2.y, 0);
    model[2] = vec4(vertInput.instanceData0.z, vertInput.instanceData1.z, vertInput.instanceData2.z, 0);
    model[3] = vec4(vertInput.instanceData0.w, vertInput.instanceData1.w, vertInput.instanceData2.w, 1);
    vec3 wpos = instMul(model, vec4(vertInput.position, 1.0)).xyz;
    #endif
    vertOutput.position = ((ViewProj) * (vec4(wpos, 1.0))); // Attention!
    stdInput.worldPos = wpos;
    vertOutput.worldPos = wpos;
}
```

edit the 2 highlighted lines into this:

```glsl linenums="4"
vec3 wpos = mul(World, vec4(vertInput.position, 1.0)).xyz;
```

```glsl linenums="14"
vertOutput.position = mul(ViewProj, vec4(wpos, 1.0));
```

And this is it! `vertex.sc` can now be compiled correctly.

#### fragment.sc

Next, let's edit fragment shader code. Similar to vertex shader, start by adding `#include "bgfx_shader.sh"` line at the beginning after `$input` directives, which should look like this:

```glsl linenums="1" hl_lines="3"
$input v_color0, v_fog, v_lightmapUV, v_texcoord0, v_worldPos

#include "bgfx_shader.sh"
```

Now we need to modify texture sampling methods to use the correct cross-platform BGFX functions, which requires changing the following code:

```glsl linenums="1"
vec4 textureSample(mediump sampler2D _sampler, vec2 _coord) {
    return texture(_sampler, _coord);
}
vec4 textureSample(mediump sampler3D _sampler, vec3 _coord) {
    return texture(_sampler, _coord);
}
vec4 textureSample(mediump samplerCube _sampler, vec3 _coord) {
    return texture(_sampler, _coord);
}
vec4 textureSample(mediump sampler2D _sampler, vec2 _coord, float _lod) {
    return textureLod(_sampler, _coord, _lod);
}
vec4 textureSample(mediump sampler3D _sampler, vec3 _coord, float _lod) {
    return textureLod(_sampler, _coord, _lod);
}
vec4 textureSample(mediump sampler2DArray _sampler, vec3 _coord) {
    return texture(_sampler, _coord);
}
vec4 textureSample(mediump sampler2DArray _sampler, vec3 _coord, float _lod) {
    return textureLod(_sampler, _coord, _lod);
}
```

Into this:

```glsl linenums="1"
vec4 textureSample(mediump sampler2D _sampler, vec2 _coord) {
    return texture2D(_sampler, _coord);
}
vec4 textureSample(mediump sampler3D _sampler, vec3 _coord) {
    return texture3D(_sampler, _coord);
}
vec4 textureSample(mediump samplerCube _sampler, vec3 _coord) {
    return textureCube(_sampler, _coord);
}
vec4 textureSample(mediump sampler2D _sampler, vec2 _coord, float _lod) {
    return texture2DLod(_sampler, _coord, _lod);
}
vec4 textureSample(mediump sampler3D _sampler, vec3 _coord, float _lod) {
    return texture3DLod(_sampler, _coord, _lod);
}
vec4 textureSample(mediump sampler2DArray _sampler, vec3 _coord) {
    return texture2DArray(_sampler, _coord);
}
vec4 textureSample(mediump sampler2DArray _sampler, vec3 _coord, float _lod) {
    return texture2DArrayLod(_sampler, _coord, _lod);
}
```

Then remove the following code, since it's already included in `bgfx_shader.sh`:

```glsl linenums="1"
#if defined(SEASONS__ON)&&(defined(ALPHA_TEST_PASS)|| defined(OPAQUE_PASS))
vec3 vec3_splat(float _x) {
    return vec3(_x, _x, _x);
}
#endif
```

Finally, we need to edit the following function:

```glsl linenums="1" hl_lines="19"
void StandardTemplate_Opaque_Frag(FragmentInput fragInput, inout FragmentOutput fragOutput) {
    StandardSurfaceInput surfaceInput = StandardTemplate_DefaultInput(fragInput);
    StandardSurfaceOutput surfaceOutput = StandardTemplate_DefaultOutput();
    surfaceInput.UV = fragInput.texcoord0;
    surfaceInput.Color = fragInput.color0.xyz;
    surfaceInput.Alpha = fragInput.color0.a;
    #if defined(ALPHA_TEST_PASS)|| defined(DEPTH_ONLY_PASS)
    RenderChunkSurfAlpha(surfaceInput, surfaceOutput);
    #endif
    #if defined(DEPTH_ONLY_OPAQUE_PASS)|| defined(OPAQUE_PASS)
    RenderChunkSurfOpaque(surfaceInput, surfaceOutput);
    #endif
    #ifdef TRANSPARENT_PASS
    RenderChunkSurfTransparent(surfaceInput, surfaceOutput);
    #endif
    StandardTemplate_CustomSurfaceShaderEntryIdentity(surfaceInput.UV, fragInput.worldPos, surfaceOutput);
    DirectionalLight primaryLight;
    vec3 worldLightDirection = LightWorldSpaceDirection.xyz;
    primaryLight.ViewSpaceDirection = ((View) * (vec4(worldLightDirection, 0))).xyz; // Attention!
    primaryLight.Intensity = LightDiffuseColorAndIlluminance.rgb * LightDiffuseColorAndIlluminance.w;
    CompositingOutput compositingOutput;
    compositingOutput.mLitColor = computeLighting_RenderChunk(fragInput, surfaceInput, surfaceOutput, primaryLight);
    fragOutput.Color0 = standardComposite(surfaceOutput, compositingOutput);
    RenderChunkApplyFog(fragInput, surfaceInput, surfaceOutput, fragOutput);
}
```

by changing highlighted line into this:

```glsl linenums="19"
primaryLight.ViewSpaceDirection = mul(View, vec4(worldLightDirection, 0)).xyz;
```

And we're done! Both fragment and vertex shaders are now compilable. `varying.def.sc` doesn't require any editing in this guide.

Below you can find the edited files (which were also additionally cleaned up, for better code readability):
???info "fragment.sc"

    ```glsl title="fragment.sc" linenums="1"
    /*
    * Available Macros:
    *
    * Passes:
    * - ALPHA_TEST_PASS
    * - DEPTH_ONLY_PASS
    * - DEPTH_ONLY_OPAQUE_PASS
    * - OPAQUE_PASS
    * - TRANSPARENT_PASS
    *
    * Instancing:
    * - INSTANCING__OFF (not used)
    * - INSTANCING__ON
    *
    * RenderAsBillboards:
    * - RENDER_AS_BILLBOARDS__OFF (not used)
    * - RENDER_AS_BILLBOARDS__ON (not used)
    *
    * Seasons:
    * - SEASONS__OFF
    * - SEASONS__ON
    */

    $input v_color0, v_fog, v_lightmapUV, v_texcoord0, v_worldPos

    #include "bgfx_shader.sh"

    vec4 textureSample(mediump sampler2D _sampler, vec2 _coord) {
        return texture2D(_sampler, _coord);
    }
    vec4 textureSample(mediump sampler3D _sampler, vec3 _coord) {
        return texture3D(_sampler, _coord);
    }
    vec4 textureSample(mediump samplerCube _sampler, vec3 _coord) {
        return textureCube(_sampler, _coord);
    }
    vec4 textureSample(mediump sampler2D _sampler, vec2 _coord, float _lod) {
        return texture2DLod(_sampler, _coord, _lod);
    }
    vec4 textureSample(mediump sampler3D _sampler, vec3 _coord, float _lod) {
        return texture3DLod(_sampler, _coord, _lod);
    }
    vec4 textureSample(mediump sampler2DArray _sampler, vec3 _coord) {
        return texture2DArray(_sampler, _coord);
    }
    vec4 textureSample(mediump sampler2DArray _sampler, vec3 _coord, float _lod) {
        return texture2DArrayLod(_sampler, _coord, _lod);
    }

    uniform vec4 FogAndDistanceControl;
    uniform vec4 FogColor;
    uniform vec4 GlobalRoughness;
    uniform vec4 LightDiffuseColorAndIlluminance;
    uniform vec4 LightWorldSpaceDirection;
    uniform vec4 MaterialID;
    uniform vec4 RenderChunkFogAlpha;
    uniform vec4 SubPixelOffset;
    uniform vec4 ViewPositionAndTime;
    vec4 ViewRect;
    mat4 Proj;
    mat4 View;
    vec4 ViewTexel;
    mat4 InvView;
    mat4 InvProj;
    mat4 ViewProj;
    mat4 InvViewProj;
    mat4 PrevViewProj;
    mat4 WorldArray[4];
    mat4 World;
    mat4 WorldView;
    mat4 WorldViewProj;
    vec4 PrevWorldPosOffset;
    vec4 AlphaRef4;
    float AlphaRef;

    struct FragmentInput {
        vec4 color0;
        vec4 fog;
        vec2 lightmapUV;
        vec2 texcoord0;
        vec3 worldPos;
    };

    struct FragmentOutput {
        vec4 Color0;
    };

    SAMPLER2D_AUTOREG(s_LightMapTexture);
    SAMPLER2D_AUTOREG(s_MatTexture);
    SAMPLER2D_AUTOREG(s_SeasonsTexture);
    struct StandardSurfaceInput {
        vec2 UV;
        vec3 Color;
        float Alpha;
        vec2 lightmapUV;
        vec4 fog;
        vec2 texcoord0;
    };

    StandardSurfaceInput StandardTemplate_DefaultInput(FragmentInput fragInput) {
        StandardSurfaceInput result;
        result.UV = vec2(0, 0);
        result.Color = vec3(1, 1, 1);
        result.Alpha = 1.0;
        result.lightmapUV = fragInput.lightmapUV;
        result.fog = fragInput.fog;
        result.texcoord0 = fragInput.texcoord0;
        return result;
    }
    struct StandardSurfaceOutput {
        vec3 Albedo;
        float Alpha;
        float Metallic;
        float Roughness;
        float Occlusion;
        float Emissive;
        float Subsurface;
        vec3 AmbientLight;
        vec3 ViewSpaceNormal;
    };

    StandardSurfaceOutput StandardTemplate_DefaultOutput() {
        StandardSurfaceOutput result;
        result.Albedo = vec3(1, 1, 1);
        result.Alpha = 1.0;
        result.Metallic = 0.0;
        result.Roughness = 1.0;
        result.Occlusion = 0.0;
        result.Emissive = 0.0;
        result.Subsurface = 0.0;
        result.AmbientLight = vec3(0.0, 0.0, 0.0);
        result.ViewSpaceNormal = vec3(0, 1, 0);
        return result;
    }
    vec3 applyFogVanilla(vec3 diffuse, vec3 fogColor, float fogIntensity) {
        return mix(diffuse, fogColor, fogIntensity);
    }
    vec4 applySeasons(vec3 vertexColor, float vertexAlpha, vec4 diffuse) {
        vec2 uv = vertexColor.xy;
        diffuse.rgb *= mix(vec3(1.0, 1.0, 1.0), textureSample(s_SeasonsTexture, uv).rgb * 2.0, vertexColor.b);
        diffuse.rgb *= vec3_splat(vertexAlpha);
        diffuse.a = 1.0;
        return diffuse;
    }
    void RenderChunkApplyFog(FragmentInput fragInput, StandardSurfaceInput surfaceInput, StandardSurfaceOutput surfaceOutput, inout FragmentOutput fragOutput) {
        fragOutput.Color0.rgb = applyFogVanilla(fragOutput.Color0.rgb, FogColor.rgb, surfaceInput.fog.a);
    }
    void RenderChunkSurfTransparent(in StandardSurfaceInput surfaceInput, inout StandardSurfaceOutput surfaceOutput) {
        vec4 diffuse = textureSample(s_MatTexture, surfaceInput.UV);
        diffuse.a *= surfaceInput.Alpha;
        diffuse.rgb *= surfaceInput.Color.rgb;
        surfaceOutput.Albedo = diffuse.rgb;
        surfaceOutput.Alpha = diffuse.a;
        surfaceOutput.Roughness = GlobalRoughness.x;
    }
    struct CompositingOutput {
        vec3 mLitColor;
    };

    vec4 standardComposite(StandardSurfaceOutput stdOutput, CompositingOutput compositingOutput) {
        return vec4(compositingOutput.mLitColor, stdOutput.Alpha);
    }
    void StandardTemplate_CustomSurfaceShaderEntryIdentity(vec2 uv, vec3 worldPosition, inout StandardSurfaceOutput surfaceOutput) {
    }
    struct DirectionalLight {
        vec3 ViewSpaceDirection;
        vec3 Intensity;
    };

    vec3 computeLighting_RenderChunk(FragmentInput fragInput, StandardSurfaceInput stdInput, StandardSurfaceOutput stdOutput, DirectionalLight primaryLight) {
        return textureSample(s_LightMapTexture, stdInput.lightmapUV).rgb * stdOutput.Albedo;
    }
    void RenderChunkSurfAlpha(in StandardSurfaceInput surfaceInput, inout StandardSurfaceOutput surfaceOutput) {
        vec4 diffuse = textureSample(s_MatTexture, surfaceInput.UV);
        const float ALPHA_THRESHOLD = 0.5;
        if (diffuse.a < ALPHA_THRESHOLD) {
            discard;
        }
        #ifdef ALPHA_TEST_PASS
        #ifdef SEASONS__ON
        diffuse = applySeasons(surfaceInput.Color, surfaceInput.Alpha, diffuse);
        #else
        diffuse.rgb *= surfaceInput.Color.rgb;
        #endif
        surfaceOutput.Albedo = diffuse.rgb;
        surfaceOutput.Alpha = diffuse.a;
        surfaceOutput.Roughness = GlobalRoughness.x;
        #endif
    }
    void RenderChunkSurfOpaque(in StandardSurfaceInput surfaceInput, inout StandardSurfaceOutput surfaceOutput) {
        #ifdef OPAQUE_PASS
        vec4 diffuse = textureSample(s_MatTexture, surfaceInput.UV);

        #ifdef SEASONS__ON
        diffuse = applySeasons(surfaceInput.Color, surfaceInput.Alpha, diffuse);
        #else
        diffuse.rgb *= surfaceInput.Color.rgb;
        diffuse.a = surfaceInput.Alpha;
        #endif

        surfaceOutput.Albedo = diffuse.rgb;
        surfaceOutput.Alpha = diffuse.a;
        surfaceOutput.Roughness = GlobalRoughness.x;
        #endif
    }
    void StandardTemplate_Opaque_Frag(FragmentInput fragInput, inout FragmentOutput fragOutput) {
        StandardSurfaceInput surfaceInput = StandardTemplate_DefaultInput(fragInput);
        StandardSurfaceOutput surfaceOutput = StandardTemplate_DefaultOutput();
        surfaceInput.UV = fragInput.texcoord0;
        surfaceInput.Color = fragInput.color0.xyz;
        surfaceInput.Alpha = fragInput.color0.a;
        #ifdef TRANSPARENT_PASS
        RenderChunkSurfTransparent(surfaceInput, surfaceOutput);
        #elif defined(ALPHA_TEST_PASS)|| defined(DEPTH_ONLY_PASS)
        RenderChunkSurfAlpha(surfaceInput, surfaceOutput);
        #elif defined(DEPTH_ONLY_OPAQUE_PASS)|| defined(OPAQUE_PASS)
        RenderChunkSurfOpaque(surfaceInput, surfaceOutput);
        #endif
        StandardTemplate_CustomSurfaceShaderEntryIdentity(surfaceInput.UV, fragInput.worldPos, surfaceOutput);
        DirectionalLight primaryLight;
        vec3 worldLightDirection = LightWorldSpaceDirection.xyz;
        primaryLight.ViewSpaceDirection = mul(View, vec4(worldLightDirection, 0)).xyz;
        primaryLight.Intensity = LightDiffuseColorAndIlluminance.rgb * LightDiffuseColorAndIlluminance.w;
        CompositingOutput compositingOutput;
        compositingOutput.mLitColor = computeLighting_RenderChunk(fragInput, surfaceInput, surfaceOutput, primaryLight);
        fragOutput.Color0 = standardComposite(surfaceOutput, compositingOutput);
        RenderChunkApplyFog(fragInput, surfaceInput, surfaceOutput, fragOutput);
    }
    void main() {
        FragmentInput fragmentInput;
        FragmentOutput fragmentOutput;
        fragmentInput.color0 = v_color0;
        fragmentInput.fog = v_fog;
        fragmentInput.lightmapUV = v_lightmapUV;
        fragmentInput.texcoord0 = v_texcoord0;
        fragmentInput.worldPos = v_worldPos;
        fragmentOutput.Color0 = vec4(0, 0, 0, 0);
        ViewRect = u_viewRect;
        Proj = u_proj;
        View = u_view;
        ViewTexel = u_viewTexel;
        InvView = u_invView;
        InvProj = u_invProj;
        ViewProj = u_viewProj;
        InvViewProj = u_invViewProj;
        PrevViewProj = u_prevViewProj;
        {
            WorldArray[0] = u_model[0];
            WorldArray[1] = u_model[1];
            WorldArray[2] = u_model[2];
            WorldArray[3] = u_model[3];
        }
        World = u_model[0];
        WorldView = u_modelView;
        WorldViewProj = u_modelViewProj;
        PrevWorldPosOffset = u_prevWorldPosOffset;
        AlphaRef4 = u_alphaRef4;
        AlphaRef = u_alphaRef4.x;
        StandardTemplate_Opaque_Frag(fragmentInput, fragmentOutput);
        gl_FragColor = fragmentOutput.Color0;
    }
    ```

???info "vertex.sc"

    ```glsl title="vertex.sc" linenums="1"

    /*
    * Available Macros:
    *
    * Passes:
    * - ALPHA_TEST_PASS (not used)
    * - DEPTH_ONLY_PASS (not used)
    * - DEPTH_ONLY_OPAQUE_PASS (not used)
    * - OPAQUE_PASS (not used)
    * - TRANSPARENT_PASS
    *
    * Instancing:
    * - INSTANCING__OFF
    * - INSTANCING__ON
    *
    * RenderAsBillboards:
    * - RENDER_AS_BILLBOARDS__OFF (not used)
    * - RENDER_AS_BILLBOARDS__ON
    *
    * Seasons:
    * - SEASONS__OFF (not used)
    * - SEASONS__ON (not used)
    */

    $input a_color0, a_position, a_texcoord0, a_texcoord1
    #ifdef INSTANCING__ON
    $input i_data1, i_data2, i_data3
    #endif

    $output v_color0, v_fog, v_lightmapUV, v_texcoord0, v_worldPos

    #include "bgfx_shader.sh"

    uniform vec4 FogAndDistanceControl;
    uniform vec4 FogColor;
    uniform vec4 GlobalRoughness;
    uniform vec4 LightDiffuseColorAndIlluminance;
    uniform vec4 LightWorldSpaceDirection;
    uniform vec4 MaterialID;
    uniform vec4 RenderChunkFogAlpha;
    uniform vec4 SubPixelOffset;
    uniform vec4 ViewPositionAndTime;
    vec4 ViewRect;
    mat4 Proj;
    mat4 View;
    vec4 ViewTexel;
    mat4 InvView;
    mat4 InvProj;
    mat4 ViewProj;
    mat4 InvViewProj;
    mat4 PrevViewProj;
    mat4 WorldArray[4];
    mat4 World;
    mat4 WorldView;
    mat4 WorldViewProj;
    vec4 PrevWorldPosOffset;
    vec4 AlphaRef4;
    float AlphaRef;

    struct VertexInput {
        vec4 color0;
        vec2 lightmapUV;
        vec3 position;
        vec2 texcoord0;
        #ifdef INSTANCING__ON
        vec4 instanceData0;
        vec4 instanceData1;
        vec4 instanceData2;
        #endif
    };

    struct VertexOutput {
        vec4 position;
        vec4 color0;
        vec4 fog;
        vec2 lightmapUV;
        vec2 texcoord0;
        vec3 worldPos;
    };

    struct StandardVertexInput {
        VertexInput vertInput;
        vec3 worldPos;
    };

    vec4 jitterVertexPosition(vec3 worldPosition) {
        mat4 offsetProj = Proj;
        #if BGFX_SHADER_LANGUAGE_GLSL
        offsetProj[2][0] += SubPixelOffset.x;
        offsetProj[2][1] -= SubPixelOffset.y;
        #else
        offsetProj[0][2] += SubPixelOffset.x;
        offsetProj[1][2] -= SubPixelOffset.y;
        #endif
        return mul(offsetProj, mul(View, vec4(worldPosition, 1.0f)));
    }
    float calculateFogIntensityFadedVanilla(float cameraDepth, float maxDistance, float fogStart, float fogEnd, float fogAlpha) {
        float distance = cameraDepth / maxDistance;
        distance += fogAlpha;
        return clamp((distance - fogStart) / (fogEnd - fogStart), 0.0, 1.0);
    }
    void transformAsBillboardVertex(inout StandardVertexInput stdInput, inout VertexOutput vertOutput) {
        stdInput.worldPos += vec3(0.5, 0.5, 0.5);
        vec3 forward = normalize(stdInput.worldPos - ViewPositionAndTime.xyz);
        vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), forward));
        vec3 up = cross(forward, right);
        vec3 offsets = stdInput.vertInput.color0.xyz;
        stdInput.worldPos -= up * (offsets.z - 0.5) + right * (offsets.x - 0.5);
        vertOutput.position = mul(ViewProj, vec4(stdInput.worldPos, 1.0));
    }
    float RenderChunkVert(StandardVertexInput stdInput, inout VertexOutput vertOutput) {
        #ifdef RENDER_AS_BILLBOARDS__ON
        vertOutput.color0 = vec4(1.0, 1.0, 1.0, 1.0);
        transformAsBillboardVertex(stdInput, vertOutput);
        #endif
        float cameraDepth = length(ViewPositionAndTime.xyz - stdInput.worldPos);
        float fogIntensity = calculateFogIntensityFadedVanilla(cameraDepth, FogAndDistanceControl.z, FogAndDistanceControl.x, FogAndDistanceControl.y, RenderChunkFogAlpha.x);
        vertOutput.fog = vec4(FogColor.rgb, fogIntensity);
        vertOutput.position = jitterVertexPosition(stdInput.worldPos);
        return cameraDepth;
    }
    void RenderChunkVertTransparent(StandardVertexInput stdInput, inout VertexOutput vertOutput) {
        float cameraDepth = RenderChunkVert(stdInput, vertOutput);
        bool shouldBecomeOpaqueInTheDistance = stdInput.vertInput.color0.a < 0.95;
        if (shouldBecomeOpaqueInTheDistance) {
            float cameraDistance = cameraDepth / FogAndDistanceControl.w;
            float alphaFadeOut = clamp(cameraDistance, 0.0, 1.0);
            vertOutput.color0.a = mix(stdInput.vertInput.color0.a, 1.0, alphaFadeOut);
        }
    }
    void StandardTemplate_VertSharedTransform(inout StandardVertexInput stdInput, inout VertexOutput vertOutput) {
        VertexInput vertInput = stdInput.vertInput;
        #ifdef INSTANCING__ON
        mat4 model;
        model[0] = vec4(vertInput.instanceData0.x, vertInput.instanceData1.x, vertInput.instanceData2.x, 0);
        model[1] = vec4(vertInput.instanceData0.y, vertInput.instanceData1.y, vertInput.instanceData2.y, 0);
        model[2] = vec4(vertInput.instanceData0.z, vertInput.instanceData1.z, vertInput.instanceData2.z, 0);
        model[3] = vec4(vertInput.instanceData0.w, vertInput.instanceData1.w, vertInput.instanceData2.w, 1);
        vec3 wpos = instMul(model, vec4(vertInput.position, 1.0)).xyz;
        #else
        vec3 wpos = mul(World, vec4(vertInput.position, 1.0)).xyz;
        #endif
        vertOutput.position = mul(ViewProj, vec4(wpos, 1.0));
        stdInput.worldPos = wpos;
        vertOutput.worldPos = wpos;
    }
    void StandardTemplate_VertexPreprocessIdentity(VertexInput vertInput, inout VertexOutput vertOutput) {
    }

    void StandardTemplate_InvokeVertexPreprocessFunction(inout VertexInput vertInput, inout VertexOutput vertOutput);
    void StandardTemplate_InvokeVertexOverrideFunction(StandardVertexInput vertInput, inout VertexOutput vertOutput);
    void StandardTemplate_InvokeLightingVertexFunction(VertexInput vertInput, inout VertexOutput vertOutput, vec3 worldPosition);

    void computeLighting_RenderChunk_Vertex(VertexInput vInput, inout VertexOutput vOutput, vec3 worldPosition) {
        vOutput.lightmapUV = vInput.lightmapUV;
    }
    void StandardTemplate_VertShared(VertexInput vertInput, inout VertexOutput vertOutput) {
        StandardTemplate_InvokeVertexPreprocessFunction(vertInput, vertOutput);
        StandardVertexInput stdInput;
        stdInput.vertInput = vertInput;
        StandardTemplate_VertSharedTransform(stdInput, vertOutput);
        vertOutput.texcoord0 = vertInput.texcoord0;
        vertOutput.color0 = vertInput.color0;
        StandardTemplate_InvokeVertexOverrideFunction(stdInput, vertOutput);
        StandardTemplate_InvokeLightingVertexFunction(vertInput, vertOutput, stdInput.worldPos);
    }
    void StandardTemplate_InvokeVertexPreprocessFunction(inout VertexInput vertInput, inout VertexOutput vertOutput) {
        StandardTemplate_VertexPreprocessIdentity(vertInput, vertOutput);
    }
    void StandardTemplate_InvokeVertexOverrideFunction(StandardVertexInput vertInput, inout VertexOutput vertOutput) {
        #ifdef TRANSPARENT_PASS
        RenderChunkVertTransparent(vertInput, vertOutput);
        #else
        RenderChunkVert(vertInput, vertOutput);
        #endif
    }
    void StandardTemplate_InvokeLightingVertexFunction(VertexInput vertInput, inout VertexOutput vertOutput, vec3 worldPosition) {
        computeLighting_RenderChunk_Vertex(vertInput, vertOutput, worldPosition);
    }
    void StandardTemplate_Opaque_Vert(VertexInput vertInput, inout VertexOutput vertOutput) {
        StandardTemplate_VertShared(vertInput, vertOutput);
    }
    void main() {
        VertexInput vertexInput;
        VertexOutput vertexOutput;
        vertexInput.color0 = (a_color0);
        vertexInput.lightmapUV = (a_texcoord1);
        vertexInput.position = (a_position);
        vertexInput.texcoord0 = (a_texcoord0);
        #ifdef INSTANCING__ON
        vertexInput.instanceData0 = i_data1;
        vertexInput.instanceData1 = i_data2;
        vertexInput.instanceData2 = i_data3;
        #endif
        vertexOutput.color0 = vec4(0, 0, 0, 0);
        vertexOutput.fog = vec4(0, 0, 0, 0);
        vertexOutput.lightmapUV = vec2(0, 0);
        vertexOutput.texcoord0 = vec2(0, 0);
        vertexOutput.worldPos = vec3(0, 0, 0);
        vertexOutput.position = vec4(0, 0, 0, 0);
        ViewRect = u_viewRect;
        Proj = u_proj;
        View = u_view;
        ViewTexel = u_viewTexel;
        InvView = u_invView;
        InvProj = u_invProj;
        ViewProj = u_viewProj;
        InvViewProj = u_invViewProj;
        PrevViewProj = u_prevViewProj;
        {
            WorldArray[0] = u_model[0];
            WorldArray[1] = u_model[1];
            WorldArray[2] = u_model[2];
            WorldArray[3] = u_model[3];
        }
        World = u_model[0];
        WorldView = u_modelView;
        WorldViewProj = u_modelViewProj;
        PrevWorldPosOffset = u_prevWorldPosOffset;
        AlphaRef4 = u_alphaRef4;
        AlphaRef = u_alphaRef4.x;
        StandardTemplate_Opaque_Vert(vertexInput, vertexOutput);
        v_color0 = vertexOutput.color0;
        v_fog = vertexOutput.fog;
        v_lightmapUV = vertexOutput.lightmapUV;
        v_texcoord0 = vertexOutput.texcoord0;
        v_worldPos = vertexOutput.worldPos;
        gl_Position = vertexOutput.position;
    }
    ```

???info "varying.def.sc"

    ```glsl title="varying.def.sc" linenums="1"
    vec3 a_position  : POSITION;
    vec2 a_texcoord0 : TEXCOORD0;

    vec3 v_projPosition : COLOR1;
    vec2 v_texcoord0    : TEXCOORD0;
    ```

## project.json

Now let's fill the project.json file:

```json linenums="1" title="project.json"
{
  "base_profile": {
    "platforms": [
      "Direct3D_SM40",
      "Direct3D_SM50",
      "Direct3D_SM60",
      "Direct3D_SM65",
      "ESSL_100",
      "ESSL_310"
    ],
    "merge_source": ["../vanilla"]
  },
  "profiles": {
    "windows": {
      "platforms": [
        "Direct3D_SM40",
        "Direct3D_SM50",
        "Direct3D_SM60",
        "Direct3D_SM65"
      ]
    },
    "android": {
      "platforms": ["ESSL_100", "ESSL_310"]
    }
  }
}
```

This project config targets windows and android platforms by default, but also adds separate profiles for them,
which allows you to choose which platform to compile to using `--profile` argument.

!!!warning "Compiling Windows shaders"

    Due to shaderc compiler limitations, you can only compile shaders for Windows (`Direct3D`) on a Windows machine.
    If you are following this tutorial on other OS then you won't be able to compile shaders for Windows.

## Adding shader effects

Currently our shader is exactly the same as vanilla and doesn't do anything different, so let's add some interesting effects!

Edit the `main()` function in `fragment.sc` and add the highlighted line at the very bottom:

```glsl title="fragment.sc" linenums="1" hl_lines="32"
void main() {
    FragmentInput fragmentInput;
    FragmentOutput fragmentOutput;
    fragmentInput.color0 = v_color0;
    fragmentInput.fog = v_fog;
    fragmentInput.lightmapUV = v_lightmapUV;
    fragmentInput.texcoord0 = v_texcoord0;
    fragmentInput.worldPos = v_worldPos;
    fragmentOutput.Color0 = vec4(0, 0, 0, 0);
    ViewRect = u_viewRect;
    Proj = u_proj;
    View = u_view;
    ViewTexel = u_viewTexel;
    InvView = u_invView;
    InvProj = u_invProj;
    ViewProj = u_viewProj;
    InvViewProj = u_invViewProj;
    PrevViewProj = u_prevViewProj;
    {
        WorldArray[0] = u_model[0];
        WorldArray[1] = u_model[1];
        WorldArray[2] = u_model[2];
        WorldArray[3] = u_model[3];
    }
    World = u_model[0];
    WorldView = u_modelView;
    WorldViewProj = u_modelViewProj;
    PrevWorldPosOffset = u_prevWorldPosOffset;
    AlphaRef4 = u_alphaRef4;
    AlphaRef = u_alphaRef4.x;
    StandardTemplate_Opaque_Frag(fragmentInput, fragmentOutput);
    fragmentOutput.Color0.rgb = vec3(1, 1, 1) - fragmentOutput.Color0.rgb; // Invert colors.
    gl_FragColor = fragmentOutput.Color0;
}
```

This will invert terrain colors.

## Compilation

Now, we're finally ready to compile the project!

Run the following commands (optionally, with `-p windows`, `-p android` or `-p windows, android`, depending on which platforms you wish to compile for):

```sh
lazurite build ./helloWorld
```

And it should compile shaders into material, generating a final `RenderChunk.material.bin` file in the project `helloWorld` directory.
Now you're ready to try out your shader in-game! If everything was done correctly, you should be able to see the inverted colors effect on blocks.
