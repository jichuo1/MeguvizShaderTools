import argparse
import hashlib
import json
import pathlib
import re
import struct
import subprocess

p = argparse.ArgumentParser()
p.add_argument("--prefix", type=pathlib.Path, required=True)
p.add_argument("--report", type=pathlib.Path, required=True)
args = p.parse_args()
prefix = args.prefix.resolve()
expected = json.loads((prefix / "checksums.json").read_text(encoding="utf-8"))
failures = []
files = []
for rel, claimed in expected.items():
    path = prefix / rel
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != claimed:
        failures.append("checksum:" + rel)
    files.append(rel)
for path in prefix.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(prefix).as_posix()
    if path.suffix.lower() in (".so", ".aar", ".apk", ".bin"):
        failures.append("forbidden-artifact:" + rel)
    if rel not in expected and rel != "checksums.json":
        failures.append("unlisted-file:" + rel)
    data = path.read_bytes()
    for marker in (b"D:\\MeguvizPack", b"D:/MeguvizPack", b"C:\\Users\\Administrator", b"C:/Users/Administrator"):
        if marker.lower() in data.lower() or marker.decode().encode("utf-16le").lower() in data.lower():
            failures.append("private-path:" + rel)
exe = prefix / "bin/mgst.exe"
data = exe.read_bytes()
pe = struct.unpack_from("<I", data, 0x3c)[0]
if data[:2] != b"MZ" or data[pe:pe+4] != b"PE\0\0" or struct.unpack_from("<H", data, pe+4)[0] != 0x8664:
    failures.append("host-format")
version = subprocess.run([str(exe), "--version-json"], capture_output=True, text=True, encoding="utf-8")
doctor = subprocess.run([str(exe), "doctor", "--lock", str(prefix / "share/MeguvizShaderTools/deps.lock.json"), "--offline"], capture_output=True, text=True, encoding="utf-8")
if version.returncode or doctor.returncode:
    failures.append("installed-tool")
report = {"status": "FAIL" if failures else "PASS", "failures": failures,
          "file_count": len(files), "executable_sha256": hashlib.sha256(data).hexdigest(),
          "version": json.loads(version.stdout), "doctor": json.loads(doctor.stdout),
          "checksums_sha256": hashlib.sha256((prefix / "checksums.json").read_bytes()).hexdigest(),
          "device_qualification": "INCONCLUSIVE", "host": "windows-x86_64"}
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k not in ("version", "doctor")}, ensure_ascii=False))
raise SystemExit(bool(failures))
