"""Explicit network bootstrap. Existing source checkouts are never reset or replaced."""
import argparse
import json
import pathlib
import subprocess

p = argparse.ArgumentParser()
p.add_argument("--root", type=pathlib.Path, required=True)
args = p.parse_args()
pins = json.loads((pathlib.Path(__file__).resolve().parents[1] / "deps.lock.json").read_text())["libraries"]
sources = [("glslang", "nihui/glslang", "glslang"), ("SPIRV-Tools", "KhronosGroup/SPIRV-Tools", "spirv_tools"),
           ("SPIRV-Headers", "KhronosGroup/SPIRV-Headers", "spirv_headers"),
           ("SPIRV-Reflect", "KhronosGroup/SPIRV-Reflect", "spirv_reflect"), ("ncnn", "Tencent/ncnn", "ncnn")]
args.root.mkdir(parents=True, exist_ok=True)
for name, repo, key in sources:
    dest = (args.root / name).resolve()
    if dest.exists():
        actual = subprocess.check_output(["git", "-c", f"safe.directory={dest}", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
        if actual != pins[key]:
            raise SystemExit(f"existing checkout has wrong pin: {dest}: {actual}")
        continue
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", f"https://github.com/{repo}.git", str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "--detach", pins[key]], check=True)
print("all pinned source checkouts available; subsequent CMake configuration is offline")
