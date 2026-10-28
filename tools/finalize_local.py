import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time

p=argparse.ArgumentParser()
p.add_argument('--cmake',required=True)
p.add_argument('--ninja',required=True)
p.add_argument('--dumpbin',required=True)
p.add_argument('--generation',default='rc1')
args=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
prefix=root/'out/install'/('windows-x86_64-'+args.generation)
evidence=root/'verification/installation'/('run-'+str(time.time_ns()))
evidence.mkdir(parents=True)
if prefix.exists():raise SystemExit('immutable install generation already exists')
records=[]
def run(argv):
 r=subprocess.run(list(map(str,argv)),capture_output=True,text=True,encoding='utf-8',errors='replace')
 records.append({'argv':list(map(str,argv)),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 (evidence/'commands.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 if r.returncode:raise SystemExit(json.dumps(records[-1],ensure_ascii=False))
 return r.stdout
run([args.cmake,'--install',root/'build/host-windows-release','--prefix',prefix])
consumer=evidence/'独立 consumer build'
run([args.cmake,'-S',prefix/'share/MeguvizShaderTools/examples/external_consumer','-B',consumer,'-G','Ninja','-DCMAKE_MAKE_PROGRAM='+args.ninja,'-DCMAKE_PREFIX_PATH='+str(prefix)])
run([args.cmake,'--build',consumer,'--target','verify'])
dependencies=run([args.dumpbin,'/DEPENDENTS',prefix/'bin/mgst.exe'])
if 'vulkan' in dependencies.lower():raise SystemExit('unexpected Vulkan runtime import')
(evidence/'dependents.txt').write_text(dependencies,encoding='utf-8')
archive=root/'out'/('MeguvizShaderTools-0.1.0-'+args.generation+'-windows-x86_64.zip')
run([sys.executable,root/'tools/package_candidate.py','--prefix',prefix,'--out',archive])
run([sys.executable,root/'tools/verify_release.py','--prefix',prefix,'--report',evidence/'release-check.json'])
summary={'status':'PASS','host':'windows-x86_64','prefix':str(prefix),'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'executable_sha256':hashlib.sha256((prefix/'bin/mgst.exe').read_bytes()).hexdigest(),'consumer_manifest_sha256':hashlib.sha256((consumer/'identity-pack/manifest.json').read_bytes()).hexdigest(),'commands_sha256':hashlib.sha256((evidence/'commands.json').read_bytes()).hexdigest(),'output':str(evidence),'device_qualification':'INCONCLUSIVE'}
(evidence/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
