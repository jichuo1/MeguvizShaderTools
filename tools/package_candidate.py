import argparse
import hashlib
import json
import pathlib
import subprocess
import zipfile

p=argparse.ArgumentParser()
p.add_argument("--prefix",type=pathlib.Path,required=True)
p.add_argument("--out",type=pathlib.Path,required=True)
args=p.parse_args()
prefix=args.prefix.resolve()
exe=prefix/'bin/mgst.exe'
version=json.loads(subprocess.check_output([str(exe),'--version-json'],text=True,encoding='utf-8'))['result']
share=prefix/'share/MeguvizShaderTools'
receipt={'schema_version':1,'host':'windows-x86_64','executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'effective_toolchain_lock':version['dependencies'],'toolchain_lock_hash':version['toolchain_lock_hash'],'qualified_scope':'host static compile/validate/reflect/package only','gpu_qualified':False,'no_runtime_compiler_qualified':False}
(share/'build-receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
sbom={'spdxVersion':'SPDX-2.3','dataLicense':'CC0-1.0','SPDXID':'SPDXRef-DOCUMENT','name':'MeguvizShaderTools-host-candidate','documentNamespace':'urn:meguviz:mgst:'+receipt['executable_sha256'],'creationInfo':{'creators':['Tool: mgst-package-0.1'],'created':'2026-10-28T00:00:00Z'},'packages':[]}
for name,pin in version['dependencies']['libraries'].items():
 sbom['packages'].append({'name':name,'SPDXID':'SPDXRef-'+name.replace('_','-'),'versionInfo':pin,'downloadLocation':{'glslang':'https://github.com/nihui/glslang','ncnn':'https://github.com/Tencent/ncnn','spirv_tools':'https://github.com/KhronosGroup/SPIRV-Tools','spirv_headers':'https://github.com/KhronosGroup/SPIRV-Headers','spirv_reflect':'https://github.com/KhronosGroup/SPIRV-Reflect'}[name],'filesAnalyzed':False})
(share/'sbom.spdx.json').write_text(json.dumps(sbom,sort_keys=True,indent=2)+'\n')
checks={x.relative_to(prefix).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(prefix.rglob('*')) if x.is_file() and x.name!='checksums.json'}
(prefix/'checksums.json').write_text(json.dumps(checks,sort_keys=True,indent=2)+'\n')
args.out.parent.mkdir(parents=True,exist_ok=True)
if args.out.exists():raise SystemExit('immutable archive exists')
with zipfile.ZipFile(args.out,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for file in sorted(prefix.rglob('*')):
  if file.is_file():
   info=zipfile.ZipInfo(file.relative_to(prefix).as_posix(),date_time=(1980,1,2,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
   z.writestr(info,file.read_bytes())
print(json.dumps({'archive':str(args.out),'bytes':args.out.stat().st_size,'sha256':hashlib.sha256(args.out.read_bytes()).hexdigest(),'toolchain_lock_hash':version['toolchain_lock_hash']}))
