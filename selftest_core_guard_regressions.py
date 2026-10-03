#!/usr/bin/env python3
"""Exercise positive and broken fixtures for source-grounded Core guard corrections."""
import importlib.util, json, tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('core',Path(__file__).with_name('validate_core_services.py'))
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
root=Path(tempfile.mkdtemp(prefix='bp-core-guard-'));v.ROOT=root
results=[]
def check(name, condition):
 assert condition,name
 results.append(name)
def write(name,body):
 p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body);return p
# Mappings in strings/comments are preserved/excluded; hidden and opt-in endpoints remain runtime routes.
write('App/src/main/java/C.java','''@RestController
@RequestMapping("/api")
public class C {
// @GetMapping("/comment")
@GetMapping("/real") public void getReal() {}
@Hidden
@GetMapping("/compat") public void getCompat() {}
@GetMapping("/gone")
@Operation(hidden = true)
public void getGone() {}
}''')
write('App/src/main/java/Dev.java','''@RestController
@Profile("dev & !prod")
public class Dev {
@GetMapping("/otp") public void getOtp() {}
}''')
check('actual routes retained',v._controller_routes('App')=={('GET','/api/real'),('GET','/api/compat'),('GET','/api/gone'),('GET','/otp')})
check('spec respects hidden and opt-in routes',v._controller_routes('App',for_spec=True)=={('GET','/api/real')})
check('string URLs retained', 'https://host/path' in v._java_code('String x="https://host/path"; // comment'))
check('Spring default numeric rates resolve',v._numeric_rate('${gateway.rate:400}')==400)
for value in ['${gateway.rate}','bad',0,-1,True]:
 try:v._numeric_rate(value)
 except (TypeError,ValueError):check('reject invalid rate '+str(value),True)
 else:raise AssertionError('invalid rate accepted '+str(value))
# Accessor guard excludes mapped endpoints, still rejects hand-written DTO getters.
capture=[];v.check=lambda cid,desc,ok,detail='':capture.append((cid,ok,detail));v.MODULES=['App']
body='\n'.join('@GetMapping("/'+str(i)+'")\n public String getX'+str(i)+'() { return "x"; }' for i in range(6))
file=write('App/src/main/java/C.java','@RestController\npublic class C {\n'+body+'\n}')
v.check_i16();check('six mapped operations allowed',capture[-1][1])
file.write_text('public class C {\n'+body.replace('@GetMapping', '// @GetMapping')+'\n}')
v.check_i16();check('six real DTO accessors rejected',not capture[-1][1])
# Required contract fields still fail when lost.
write('App/openapi.json',json.dumps({'components':{'schemas':{'Entry':{'required':['entryId','accountId','direction']}}}}))
v.STRICT_SCHEMAS={'App:Entry':['entryId','accountId','direction']};v.check_schema_strictness_ratchet();check('entry contract accepted',capture[-1][1])
write('App/openapi.json',json.dumps({'components':{'schemas':{'Entry':{'required':['accountId','direction']}}}}))
v.check_schema_strictness_ratchet();check('lost immutable entry identity rejected',not capture[-1][1])
# Scoped fresh-Dev authority is hash bound and ends on production declaration.
import hashlib
sql=write('App/src/main/resources/db/migration/V1__init.sql','CREATE TABLE example(id UUID PRIMARY KEY);')
write('schema-proof.json','[{"schemaAndSeedsPass":true}]');write('constraint-proof.json','[{"passed":true}]')
manifest={'environment':'dev','productionDeployed':False,'expiresOnProductionDeployment':True,'requiredDeployment':'clean --wipe','initialSchemas':[{'path':str(sql.relative_to(root)),'sha256':hashlib.sha256(sql.read_bytes()).hexdigest()}],'retiredSql':[],'schemaEvidence':'schema-proof.json','constraintEvidence':'constraint-proof.json'}
mf=write('RandomDocuments/BusinessPlatform_2026-10-03/DEV-SCHEMA-RECREATION.json',json.dumps(manifest))
allowed,errors=v._reviewed_dev_schema_paths();check('scoped verified Dev schema allowed',bool(allowed) and not errors)
sql.write_text(sql.read_text()+' altered');allowed,errors=v._reviewed_dev_schema_paths();check('unverified SQL bytes rejected',not allowed and bool(errors))
manifest['productionDeployed']=True;mf.write_text(json.dumps(manifest));allowed,_=v._reviewed_dev_schema_paths();check('production restores strict protection',not allowed)
# Libraries have no Compose image tag. Their published commit still protects shared SQL.
import subprocess
def commit_fixture(directory):
 subprocess.run(['git','init','-q',str(directory)],check=True)
 subprocess.run(['git','-C',str(directory),'add','.'],check=True)
 subprocess.run(['git','-C',str(directory),'-c','user.name=Guard fixture','-c','user.email=guard@fixture.invalid','commit','-qm','Fixture baseline'],check=True)
 return subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()
app_sha=commit_fixture(root/'App')
write('Deployment/service-map.tsv','App\tapp\t.\tApp/Dockerfile\n')
write('Deployment/env_deployments/dev/app.env','APP_TAG='+app_sha+'\n')
shared=write('CommonLibrary/common-core/src/main/resources/db/migration/common/V1.sql','CREATE TABLE shared(id UUID PRIMARY KEY);')
common_sha=commit_fixture(root/'CommonLibrary')
provenance=write('Deployment/published-libraries.json',json.dumps({'CommonLibrary':{'commit':common_sha}}))
v.check_schema_immutable();check('published shared SQL accepted',capture[-1][1])
shared.write_text(shared.read_text()+' ALTER TABLE shared ADD COLUMN value TEXT;')
v.check_schema_immutable();check('unreviewed shared SQL rejected after production declaration',not capture[-1][1])
shared.write_text('CREATE TABLE shared(id UUID PRIMARY KEY);')
provenance.write_text('{}');v.check_schema_immutable();check('missing library publication rejected',not capture[-1][1])
provenance.write_text(json.dumps({'CommonLibrary':{'commit':'0'*40}}));v.check_schema_immutable();check('unknown library publication rejected',not capture[-1][1])
print(json.dumps({'checks':len(results),'passed':len(results),'names':results},indent=2))
