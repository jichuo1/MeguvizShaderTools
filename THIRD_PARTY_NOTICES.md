# Third-party sources

The host executable statically links these exact, unmodified source revisions.
Their full license texts are installed in `share/MeguvizShaderTools/licenses`.

| Component | Source and revision | License |
| --- | --- | --- |
| glslang | https://github.com/nihui/glslang/tree/780b6a209132dc74e99458f62ebe5fa7e57c41cf | BSD and MIT notices in LICENSE.txt |
| SPIRV-Tools | https://github.com/KhronosGroup/SPIRV-Tools/tree/b707790a898e44038547df54580022fc1cf89c3d | Apache-2.0 |
| SPIRV-Headers | https://github.com/KhronosGroup/SPIRV-Headers/tree/29981f65241605e08b0ede4cfeb999fe3b723c6a | MIT |
| SPIRV-Reflect | https://github.com/KhronosGroup/SPIRV-Reflect/tree/563dc9a16d0e86145e12a66bb61f0695ca4a14b9 | Apache-2.0 |
| ncnn source recipes | https://github.com/Tencent/ncnn/tree/7e36d25cb153092ba87a60530455c7376fedf452 | BSD-3-Clause |

`profiles/ncnn_20261020/resource.hpp` derives the resource recipe from ncnn's
`src/gpu.cpp`; embedded `ncnn_glsl_ext.comp` and `vulkan_activation.comp` are
generated with that revision's original embedding script. The renderer's
option/extension order follows that source. Device macros are explicit ordered
tokens supplied by the target-facts exporter, never obtained from a host GPU.
No ncnn runtime, Vulkan loader, model weights, Android DSO, or image codec is linked.
