# MeguvizShaderTools

独立 C++17 host 工具 `mgst`，直接使用锁定 glslang、SPIRV-Tools validator 和
SPIRV-Reflect 完成 GLSL 编译、静态验证、真实布局反射、ncnn ABI 检查、不可变
shaderpack、覆盖检查和复现。工具不枚举 GPU，不链接 Compute/Media/RIFE runtime，
不加载模型。当前已经实际验证 Windows x86-64；Linux Debug/Release CI 已建立，
本地交付时尚无该 runner 的成功证据。任务与证据见 `STATUS.json`。

开发机准备 MSVC C++17、CMake 3.24+、Ninja、Python3 和 Git。显式联网 bootstrap：

```text
python tools/bootstrap.py --root ../dependencies
```

之后构建只消费固定 checkout，无隐式联网：

```text
cmake --preset host-windows-release
cmake --build --preset host-windows-release --target mgst
ctest --preset host-windows-release --output-on-failure
cmake --install build/host-windows-release --prefix out/install/new-generation
```

Windows 请先进入 MSVC x64 开发者环境。`tools/build-host.cmd` 是本机已验证入口，
其他安装位置可直接使用上述 CMake 命令。Linux CI 使用同样的源锁与原生编译器；
不调用 Android 交叉编译工具。私有 ncnn 源仅用于构建期 recipe/helper，不链接
ncnn runtime。每个依赖 revision 在配置时核验，已跟踪源码有修改则拒绝。

可运行链：

```text
mgst --version-json
mgst doctor --lock deps.lock.json --offline
mgst compile --request request.json --out-dir new-artifact-generation
mgst validate --spirv new-artifact-generation/shader.spv --target-env vulkan1.0
mgst reflect --spirv new-artifact-generation/shader.spv --out reflection.json
mgst lint-abi --spirv new-artifact-generation/shader.spv --profile profile.json --expect expected-layout.json
mgst pack --index index.json --artifacts artifact-parent --out-dir new-pack-generation
mgst verify --pack new-pack-generation
mgst inspect --pack new-pack-generation --format text
mgst coverage --catalog catalog.json --requests trace.jsonl --pack new-pack-generation --strict
mgst reproduce --request request.json --baseline new-artifact-generation --work-dir new-reproduction-generation
```

`--version-json` 的 `result.toolchain_lock_hash` 是精确的可用工具身份，包含固定
库源、recipe、编译器二进制 hash/版本/配置和 mgst 源码 fingerprint。请求必须锁定
此值。Debug/Release 或其他 host 的身份可以不同，不能沿用旧 hash。所有命令支持
`--report`、`--diagnostics-json`、`--offline`；单请求编译不另启后台任务，`--jobs`
只接受 1–64 的合法值。

请求字段见 `schemas/compile-request.schema.json` 和
`examples/external_consumer/CMakeLists.txt`。source/include 路径相对 request 父目录，
内容 hash 必须匹配，符号链接解析后也不得逃离该目录。完整闭包先读取并冻结，
缺失 include 不从系统目录补救。JSON 为有界配置子集：重复 key、非法 UTF-8、
浮点 JSON 数字和不安全整数拒绝；浮点 specialization 使用 IEEE 位串。

`ncnn-compat/20261020` 与 `native-vulkan/1` 分开。前者检查单 set、连续 binding、
descriptor 数量/类型、`parameter` 和成员名字、4 字节 push 槽、连续业务 SpecID 与
233/234/235 保留边界。验证器通过不替代该 ABI 检查。默认无 optimizer pass，保留
名字。`render-ncnn` 使用明确 effective Options、目标环境、固定 resource/helper 和
有序 device macro tokens；synthetic facts 只用于 host 合同。当前未取得真实目标
展开输入、数值 oracle 或 GPU provider 资格，不能声明 GPU 等价或移除 runtime compiler。

包中 manifest 自身 hash 按 canonical JSON 排除 `manifest_hash` 后计算；SPIR-V 和
`reflection_sha256` 均对应精确文件 bytes，包括反射 JSON 的终末换行。`verify`
重新验证和反射 SPIR-V，并核对声明布局及所有 bytes hash。第一次跨项目消费发现的
canonical-only reflection hash 不一致及修复证据保留在验证记录中。

输出 generation 不可覆盖已有非空产物。CMake 预建的空目录可以被原子发布接管，
失败只留下本次临时诊断，不破坏旧包。外部消费者示例通过安装 target
`MeguvizShaderTools::mgst` 和 `mgst_compile_shaderpack` 构建完整包；新请求应选择
新 generation。第二次无修改构建已实测不会重新编译。

本地候选是 `out/MeguvizShaderTools-0.1.0-rc5-windows-x86_64.zip`，包括可执行文件、
schema、CMake helper、独立 consumer、锁、完整许可证、SBOM、收据和 checksums。
`tools/verify_release.py` 检查安装文件、PE 架构、精确校验和及禁止混入的制品和路径。
`catalog/ncnn-source-inventory.json` 记录全部 310 个固定 ncnn shader 源；尚未取得的
packing/shape/Options/driver 变体资格明确保持未完成，不把源码 inventory 当成
封闭 runtime coverage。

## CMake增量消费

`mgst_compile_shaderpack(REQUEST ... OUTPUT <前缀> OUT_PACK pack_dir DEPENDS ...)` 返回实际不可变generation目录；消费者依赖 `${pack_dir}/manifest.json` 并用该目录verify。generation绑定request、列出的源依赖和安装程序的实际字节hash。源码修改、回退或工具换版保留旧generation。`compile/pack --reuse` 只在完整身份与实际文件验证一致时复用，默认独立命令仍拒绝覆盖已有产物。此为首个未发布helper接口的明确合同。
