import copy
import concurrent.futures
import hashlib
import json
import pathlib
import shutil
import struct
import subprocess
import sys
import time

EXE = pathlib.Path(sys.argv[1]).resolve()
OUT = pathlib.Path(sys.argv[2]).resolve() / ("run-" + str(time.time_ns()))
OUT.mkdir(parents=True)
RECORDS = []


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def run(*args, code=0):
    completed = subprocess.run([str(EXE), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    record = {"argv": [str(EXE), *map(str, args)], "exit_code": completed.returncode,
              "stdout": completed.stdout, "stderr": completed.stderr, "expected_exit": code}
    RECORDS.append(record)
    put(OUT / "commands.json", RECORDS)
    if completed.returncode != code:
        raise AssertionError(record)
    if completed.stdout.startswith("{"):
        return json.loads(completed.stdout)


ver = run("--version-json")["result"]
LOCKHASH = ver["toolchain_lock_hash"]
root = pathlib.Path(__file__).resolve().parents[1]
run("doctor", "--lock", root / "deps.lock.json", "--offline")

# SHA-256 expected values are independently produced by CPython hashlib.
for index, value in enumerate([b"", b"abc", bytes(range(256)), b"a" * 55, b"a" * 56,
                               b"a" * 63, b"a" * 64, b"a" * 65, b"a" * 1000000]):
    path = OUT / f"nist-{index}.data"
    path.write_bytes(value)
    assert run("hash", "--file", path)["result"]["sha256"] == digest(value)

shader = """#version 450
#extension GL_GOOGLE_include_directive : require
#include "a.glsl"
layout(local_size_x=8,local_size_y=1,local_size_z=1) in;
layout(set=0,binding=0) buffer Data { float values[]; } data;
layout(push_constant) uniform parameter {
FIELDS
} p;
layout(constant_id=0) const uint factor=1;
void main(){data.values[gl_GlobalInvocationID.x]=f(data.values[gl_GlobalInvocationID.x])+float(p.p0)*float(factor);}
""".replace("FIELDS", "\n".join(f"uint p{i};" for i in range(20)))
case = OUT / "fixture"
case.mkdir()
(case / "shader.comp").write_text(shader, encoding="utf-8")
(case / "a.glsl").write_text('#include "b.glsl"\nfloat f(float x){return g(x);}\n', encoding="utf-8")
(case / "b.glsl").write_text("float g(float x){return x+1.0;}\n", encoding="utf-8")
request = {"schema_version": 1, "logical_shader_id": "fixture/convert", "owner": {"repository": "fixture", "revision": "test-v1"},
           "source": {"path": "shader.comp", "sha256": digest((case / "shader.comp").read_bytes())},
           "includes": [{"name": n, "path": n, "sha256": digest((case / n).read_bytes())} for n in ["a.glsl", "b.glsl"]],
           "profile_id": "native-vulkan", "profile_version": "1", "entry_point": "main", "target_env": "vulkan1.0",
           "effective_options": {}, "numeric_profile": "reference-fp32", "toolchain_lock_hash": LOCKHASH,
           "required_flags": [], "optimization_passes": [], "resource_recipe": "glslang-default-pinned"}
put(case / "request.json", request)
a = run("compile", "--request", case / "request.json", "--out-dir", OUT / "artifacts/native")["result"]
assert a["spirv_sha256"] == digest((OUT / "artifacts/native/shader.spv").read_bytes())
assert a["reflection_sha256"] == digest((OUT / "artifacts/native/reflection.json").read_bytes())
abi = a["layout_abi"]
assert abi["local_size"] == [8, 1, 1]
assert len(abi["descriptor_sets"]) == 1 and abi["descriptor_sets"][0]["binding"] == 0
assert abi["push_constants"][0]["size"] == 80
assert len(abi["push_constants"][0]["members"]) == 20
assert abi["specialization_constants"][0]["id"] == 0
put(case / "expect.json", abi)
put(case / "ncnn-profile.json", {"profile_id": "ncnn-compat"})
run("validate", "--spirv", OUT / "artifacts/native/shader.spv", "--target-env", "vulkan1.0")
run("reflect", "--spirv", OUT / "artifacts/native/shader.spv", "--out", OUT / "standalone-reflection.json")
run("lint-abi", "--spirv", OUT / "artifacts/native/shader.spv", "--profile", case / "ncnn-profile.json", "--expect", case / "expect.json")
run("reproduce", "--request", case / "request.json", "--baseline", OUT / "artifacts/native", "--work-dir", OUT / "reproduced")
run("diff-abi", "--before", OUT / "standalone-reflection.json", "--after", OUT / "reproduced/reflection.json")

ncnn = copy.deepcopy(request)
ncnn.update(profile_id="ncnn-compat", profile_version="20261020", resource_recipe="ncnn-20261020",
            ncnn_revision="7e36d25cb153092ba87a60530455c7376fedf452",
            target_facts={"provenance": "synthetic", "maintenance4_enabled": False, "support_fp16_storage": False,
                          "shader_int64": False, "shader_int16": False, "moltenvk": False, "device_defines": []})
put(case / "ncnn.json", ncnn)
run("render-ncnn", "--request", case / "ncnn.json", "--out-dir", OUT / "rendered")
run("compile", "--request", case / "ncnn.json", "--out-dir", OUT / "artifacts/ncnn")

unicode_case = OUT / "空格 Unicode consumer"
shutil.copytree(case, unicode_case)
assert run("compile", "--request", unicode_case / "request.json", "--out-dir", unicode_case / "产物")["result"]["variant_key"] == a["variant_key"]

# Different output generations can compile concurrently without a shared mutable cache.
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures = [pool.submit(subprocess.run, [str(EXE), "compile", "--request", str(case / "request.json"),
                "--out-dir", str(OUT / f"parallel-{i}")], capture_output=True, text=True, encoding="utf-8") for i in range(3)]
    for i, future in enumerate(futures):
        r = future.result()
        RECORDS.append({"case": f"parallel-{i}", "exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr})
        assert r.returncode == 0 and json.loads(r.stdout)["result"]["spirv_sha256"] == a["spirv_sha256"]

# Native Vulkan accepts layouts that ncnn's deliberately narrow parser cannot consume.
for tag, source in [("set-one", shader.replace("set=0", "set=1")),
                    ("sparse-binding", shader.replace("binding=0", "binding=2")),
                    ("sparse-spec", shader.replace("constant_id=0", "constant_id=2"))]:
    q = copy.deepcopy(request)
    (case / f"{tag}.comp").write_text(source, encoding="utf-8")
    q["source"] = {"path": f"{tag}.comp", "sha256": digest((case / f"{tag}.comp").read_bytes())}
    put(case / f"{tag}.json", q)
    run("compile", "--request", case / f"{tag}.json", "--out-dir", OUT / tag)
    run("validate", "--spirv", OUT / tag / "shader.spv", "--target-env", "vulkan1.0")
    run("lint-abi", "--spirv", OUT / tag / "shader.spv", "--profile", case / "ncnn-profile.json", "--expect", case / "expect.json", code=7)

# Removing OpName and OpMemberName keeps valid SPIR-V but breaks the ncnn layout protocol.
words = list(struct.unpack("<" + "I" * ((OUT / "artifacts/native/shader.spv").stat().st_size // 4),
                           (OUT / "artifacts/native/shader.spv").read_bytes()))
stripped = words[:5]
i = 5
while i < len(words):
    count, opcode = words[i] >> 16, words[i] & 65535
    assert count and i + count <= len(words)
    if opcode not in (5, 6):
        stripped.extend(words[i:i+count])
    i += count
(OUT / "stripped.spv").write_bytes(struct.pack("<" + "I" * len(stripped), *stripped))
run("validate", "--spirv", OUT / "stripped.spv", "--target-env", "vulkan1.0")
run("lint-abi", "--spirv", OUT / "stripped.spv", "--profile", case / "ncnn-profile.json", "--expect", case / "expect.json", code=7)

put(case / "index.json", {"schema_version": 1, "profile_id": "native-vulkan", "profile_version": "1", "artifacts": ["native"]})
run("pack", "--index", case / "index.json", "--artifacts", OUT / "artifacts", "--out-dir", OUT / "pack")
manifest = run("verify", "--pack", OUT / "pack")["result"]
run("inspect", "--pack", OUT / "pack", "--format", "json")
for entry in manifest["artifacts"]:
    assert entry["reflection_sha256"] == digest((OUT / "pack" / entry["reflection_path"]).read_bytes())
claimed = manifest.pop("manifest_hash")
assert claimed == digest(canonical(manifest).encode())
put(case / "catalog.json", {"variants": [{"variant_key": a["variant_key"], "declared_conditions": ["synthetic-only"]}]})
put(case / "trace.json", {"requests": [{"variant_key": a["variant_key"], "conditions": ["synthetic-only"]}]})
run("coverage", "--catalog", case / "catalog.json", "--requests", case / "trace.json", "--pack", OUT / "pack", "--strict")
put(case / "missing.json", {"variants": [{"variant_key": "1" * 64, "declared_conditions": []}]})
run("coverage", "--catalog", case / "missing.json", "--requests", case / "trace.json", "--pack", OUT / "pack", "--strict", code=10)
(case / "trace.jsonl").write_text(canonical({"variant_key": a["variant_key"], "conditions": ["synthetic-only"]}) + "\n", encoding="utf-8")
run("coverage", "--catalog", case / "catalog.json", "--requests", case / "trace.jsonl", "--pack", OUT / "pack", "--strict")
put(case / "no-conditions.json", {"requests": [{"variant_key": a["variant_key"]}]})
run("coverage", "--catalog", case / "catalog.json", "--requests", case / "no-conditions.json", "--pack", OUT / "pack", "--strict", code=10)
run("inspect", "--pack", OUT / "pack", "--format", "text")
run("inspect", "--pack", OUT / "pack", "--format", "invalid", code=2)
run("doctor", "--lock", root / "deps.lock.json", "--jobs", "1x", code=2)
run("doctor", "--lock", root / "deps.lock.json", "--unknown-option", "value", code=2)
empty_output = OUT / "cmake-precreated-empty-directory"
empty_output.mkdir()
run("compile", "--request", case / "request.json", "--out-dir", empty_output)

# Stable schema failures, Unicode, complexity and bounded parser errors.
negative_json = [("duplicate", '{"schema_version":1,"schema_version":1}', 4),
                 ("float", '{"x":1.5}', 4), ("unsafe", '{"x":9007199254740992}', 4),
                 ("surrogate", '{"x":"\\ud800"}', 4), ("leading-zero", '{"x":01}', 4),
                 ("trailing", '{} garbage', 4), ("depth", '['*66+'0'+']'*66, 4)]
for tag, content, code in negative_json:
    f = case / (tag + ".json")
    f.write_text(content, encoding="utf-8")
    run("compile", "--request", f, "--out-dir", OUT / ("bad-" + tag), code=code)
bad = case / "invalid-utf8.json"
bad.write_bytes(b'{"x":"\xff"}')
run("compile", "--request", bad, "--out-dir", OUT / "bad-utf8", code=4)
for tag, key, value, code in [("source-hash", "source", {"path": "shader.comp", "sha256": "1" * 64}, 8),
                             ("traversal", "source", {"path": "../shader.comp", "sha256": "1" * 64}, 4),
                             ("unknown", "unknown", 1, 4), ("major", "schema_version", 2, 4),
                             ("flags", "required_flags", ["new-required"], 3),
                             ("lock", "toolchain_lock_hash", "2" * 64, 8),
                             ("env", "target_env", "vulkan9.0", 3)]:
    q = copy.deepcopy(request); q[key] = value
    put(case / f"{tag}.json", q)
    run("compile", "--request", case / f"{tag}.json", "--out-dir", OUT / tag, code=code)
for tag, source in [("syntax", "#version 450\nnot a shader"), ("include", shader.replace('"a.glsl"', '"missing.glsl"'))]:
    q = copy.deepcopy(request)
    (case / f"{tag}.comp").write_text(source, encoding="utf-8")
    q["source"] = {"path": f"{tag}.comp", "sha256": digest((case / f"{tag}.comp").read_bytes())}
    put(case / f"{tag}.json", q)
    run("compile", "--request", case / f"{tag}.json", "--out-dir", OUT / tag, code=5)
for tag, data in [("magic", b'not a shader'*8), ("truncated", (OUT / "artifacts/native/shader.spv").read_bytes()[:-1])]:
    f = OUT / (tag + ".spv"); f.write_bytes(data)
    run("validate", "--spirv", f, "--target-env", "vulkan1.0", code=6)
shutil.copytree(OUT / "pack", OUT / "corrupted-pack")
blob = next((OUT / "corrupted-pack/blobs").iterdir())
blob.write_bytes(blob.read_bytes() + b'bad')
run("verify", "--pack", OUT / "corrupted-pack", code=8)
run("compile", "--request", case / "request.json", "--out-dir", OUT / "artifacts/native", code=9)
assert digest((OUT / "artifacts/native/shader.spv").read_bytes()) == a["spirv_sha256"]
run("compile", "--request", case / "request.json", "--source", "ignored.comp", "--out-dir", OUT / "override", code=2)

# Include changes alter the key, reverting restores the original content identity.
original = (case / "b.glsl").read_bytes()
(case / "b.glsl").write_bytes(original.replace(b'1.0', b'2.0'))
run("compile", "--request", case / "request.json", "--out-dir", OUT / "stale-include", code=8)
changed = copy.deepcopy(request)
changed["includes"][1]["sha256"] = digest((case / "b.glsl").read_bytes())
put(case / "changed-include.json", changed)
assert run("compile", "--request", case / "changed-include.json", "--out-dir", OUT / "changed-include")["result"]["variant_key"] != a["variant_key"]
(case / "b.glsl").write_bytes(original)
assert run("compile", "--request", case / "request.json", "--out-dir", OUT / "reverted-include")["result"]["variant_key"] == a["variant_key"]

# Independent regressions for rejected versions, final diagnostic state and verified reuse.
shutil.copytree(OUT / "pack", OUT / "unknown-version-pack")
unknown = json.loads((OUT / "unknown-version-pack/manifest.json").read_text(encoding="utf-8"))
unknown["profile_version"] = "unknown"
unknown.pop("manifest_hash", None)
unknown["manifest_hash"] = digest(canonical(unknown).encode("utf-8"))
put(OUT / "unknown-version-pack/manifest.json", unknown)
run("verify", "--pack", OUT / "unknown-version-pack", code=3)
report_failure = run("--version-json", "--report", OUT, code=9)
assert report_failure["status"] == "FAIL" and report_failure["exit_code"] == 9
mixed = run("--version-json", "--report", OUT / "mixed-report.json", "--diagnostics-json", OUT, code=9)
assert mixed["status"] == "FAIL" and mixed["exit_code"] == 9
mixed_file = json.loads((OUT / "mixed-report.json").read_text(encoding="utf-8"))
assert mixed_file["status"] == "FAIL" and mixed_file["exit_code"] == 9
reused = run("compile", "--request", case / "request.json", "--out-dir", OUT / "artifacts/native", "--reuse")
assert reused["reused_existing"] and reused["result"]["spirv_sha256"] == a["spirv_sha256"]
reused_pack = run("pack", "--index", case / "index.json", "--artifacts", OUT / "artifacts", "--out-dir", OUT / "pack", "--reuse")
assert reused_pack["reused_existing"]
other_identity = copy.deepcopy(request)
other_identity["logical_shader_id"] = "fixture/different-owner"
put(case / "different-owner.json", other_identity)
run("compile", "--request", case / "different-owner.json", "--out-dir", OUT / "artifacts/native", "--reuse", code=8)
shutil.copytree(OUT / "artifacts/native", OUT / "corrupt-reuse")
(OUT / "corrupt-reuse/shader.spv").write_bytes((OUT / "corrupt-reuse/shader.spv").read_bytes() + b"bad")
run("compile", "--request", case / "request.json", "--out-dir", OUT / "corrupt-reuse", "--reuse", code=8)
assert digest((OUT / "artifacts/native/shader.spv").read_bytes()) == a["spirv_sha256"]

summary = {"status": "PASS", "tool_sha256": digest(EXE.read_bytes()), "command_count": len(RECORDS),
           "toolchain_lock_hash": LOCKHASH, "pack": str(OUT / "pack"),
           "pack_manifest_sha256": digest((OUT / "pack/manifest.json").read_bytes()),
           "commands_sha256": digest((OUT / "commands.json").read_bytes()),
           "physical_device_qualification": "INCONCLUSIVE - host fixtures only", "output": str(OUT)}
put(OUT / "summary.json", summary)
print(canonical(summary))
