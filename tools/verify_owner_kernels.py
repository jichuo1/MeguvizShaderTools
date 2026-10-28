import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time

exe = pathlib.Path(sys.argv[1]).resolve()
root = pathlib.Path(sys.argv[2]).resolve()
out = pathlib.Path(sys.argv[3]).resolve() / ("run-" + str(time.time_ns()))
out.mkdir(parents=True)
version = json.loads(subprocess.check_output([str(exe), "--version-json"], text=True, encoding="utf-8"))["result"]
commands = []
sources = [("compute-affine", root / "MeguvizCompute/src/kernels/affine_f32/affine.comp", "MeguvizCompute", "native-vulkan"),
           ("rife-warp", root / "MeguvizRIFE/src/backends/ncnn/legacy/upstream/warp.comp", "MeguvizRIFE", "ncnn-compat"),
           ("rife-warp-pack4", root / "MeguvizRIFE/src/backends/ncnn/legacy/upstream/warp_pack4.comp", "MeguvizRIFE", "ncnn-compat")]
for name, source, owner, profile in sources:
    case = out / name
    case.mkdir()
    data = source.read_bytes()
    (case / "source.comp").write_bytes(data)
    q = {"schema_version": 1, "logical_shader_id": owner + "/" + name,
         "owner": {"repository": owner, "source_path": source.name, "source_sha256": hashlib.sha256(data).hexdigest(),
                   "revision": "a7532fc3f9f8f008cd6eecd6f2ffe2a9698e0cf7" if owner == "MeguvizRIFE" else "working-source-content-hash"},
         "source": {"path": "source.comp", "sha256": hashlib.sha256(data).hexdigest()}, "includes": [],
         "profile_id": profile, "profile_version": "20261020" if profile == "ncnn-compat" else "1",
         "entry_point": "main", "target_env": "vulkan1.0", "effective_options": {}, "numeric_profile": "reference-fp32",
         "toolchain_lock_hash": version["toolchain_lock_hash"], "required_flags": [], "optimization_passes": [],
         "resource_recipe": "ncnn-20261020" if profile == "ncnn-compat" else "glslang-default-pinned"}
    if profile == "ncnn-compat":
        q.update(ncnn_revision="7e36d25cb153092ba87a60530455c7376fedf452",
                 target_facts={"provenance": "synthetic", "maintenance4_enabled": False, "support_fp16_storage": False,
                               "shader_int64": False, "shader_int16": False, "moltenvk": False, "device_defines": []})
    (case / "request.json").write_text(json.dumps(q, sort_keys=True, indent=2), encoding="utf-8")
    argv = [str(exe), "compile", "--request", str(case / "request.json"), "--out-dir", str(case / "artifact")]
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
    commands.append({"argv": argv, "exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr})
    (out / "commands.json").write_text(json.dumps(commands, ensure_ascii=False, indent=2), encoding="utf-8")
    if r.returncode:
        raise SystemExit(r.stdout)
    a = json.loads(r.stdout)["result"]
    assert a["spirv_sha256"] == hashlib.sha256((case / "artifact/shader.spv").read_bytes()).hexdigest()
    assert a["reflection_sha256"] == hashlib.sha256((case / "artifact/reflection.json").read_bytes()).hexdigest()
summary = {"status": "PASS", "owners": ["MeguvizCompute", "MeguvizRIFE"], "kernels": len(sources),
           "tool_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(), "toolchain_lock_hash": version["toolchain_lock_hash"],
           "commands_sha256": hashlib.sha256((out / "commands.json").read_bytes()).hexdigest(),
           "device_qualification": "INCONCLUSIVE - synthetic target facts, compilation only", "output": str(out)}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
