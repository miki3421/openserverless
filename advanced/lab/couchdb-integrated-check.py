# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the License for the
# specific language governing permissions and limitations
# under the License.

"""Verify actual OPS identities, actions and activations across a CouchDB restart."""
import hashlib
import json
import os
import pathlib
import socket
import subprocess
import tempfile
import time
import urllib.parse

assert socket.gethostname()=="ops-advanced-rc7"
OUT=pathlib.Path("/home/ubuntu/ops-advanced-test/results/couchdb35")
KUBE=["kubectl","-n","openserverless"]

def get(kind,name):
    return json.loads(subprocess.check_output(KUBE+["get",kind,name,"-o","json"]))

def ops(*args):
    p=subprocess.run(["ops",*args],capture_output=True,text=True)
    if p.returncode: raise RuntimeError("OPS command failed: "+" ".join(args[:3]))
    return p.stdout

def document(text):
    return json.loads(text[text.index("{"):])

def activation(identifier):
    for _ in range(30):
        try: return document(ops("-wsk","activation","get",identifier))
        except (RuntimeError,ValueError): time.sleep(1)
    raise RuntimeError("activation was not retrieved from OPS")

def couch_bytes(path):
    return subprocess.check_output(KUBE+["exec","couchdb-0","--","sh","-c",
        'curl -fsS -u "$COUCHDB_USER:$COUCHDB_PASSWORD" "$1"',"sh","http://localhost:5984/"+path])

def direct_state(identifier):
    hashes={}
    attachments=0
    for database,suffix in [("subjects",user),("whisks","advancedcouchprobe"),("activations",identifier)]:
        prefix="openserverless_"+database
        rows=json.loads(couch_bytes(prefix+"/_all_docs"))["rows"]
        ids=[row["id"] for row in rows if row["id"]==suffix or row["id"].endswith("/"+suffix)]
        assert len(ids)==1,(database,"expected one direct CouchDB document")
        doc_path=prefix+"/"+urllib.parse.quote(ids[0],safe="")
        doc=json.loads(couch_bytes(doc_path))
        entry={"document":hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest(),"attachments":{}}
        for name in doc.get("_attachments",{}):
            entry["attachments"][name]=hashlib.sha256(couch_bytes(doc_path+"/"+urllib.parse.quote(name,safe=""))).hexdigest()
            attachments+=1
        hashes[database]=entry
    return hashes,attachments

def settings():
    result={}
    for section,key in [("couchdb","single_node"),("cluster","n"),("query_server_config","reduce_limit"),("compactions","openserverless_activations"),("compactions","openserverless_subjects"),("compactions","openserverless_whisks")]:
        result[section+"/"+key]=json.loads(couch_bytes("_node/_local/_config/"+section+"/"+key))
    assert result["couchdb/single_node"]=="true"
    assert result["cluster/n"]=="1"
    assert result["query_server_config/reduce_limit"]=="false"
    return result

user="demouser"
spec=get("wsku",user)["spec"]
login=subprocess.run(["ops","-login","http://miniops.me"],env={**os.environ,"OPS_USER":user,"OPS_PASSWORD":spec["password"]},capture_output=True,text=True)
assert login.returncode==0
source='function main(args) { console.log("couchdb35-verification"); return {marker:"couchdb35",value:args.value}; }'
with tempfile.TemporaryDirectory(prefix="ops-couchdb35-") as directory:
    file=pathlib.Path(directory,"action.js");file.write_text(source)
    ops("-wsk","action","update","advancedcouchprobe",str(file),"--kind","nodejs:22")
first=document(ops("-wsk","action","invoke","advancedcouchprobe","--blocking","-p","value","7"))
assert first["response"]["result"]=={"marker":"couchdb35","value":7}
first_id=first["activationId"]
assert activation(first_id)["response"]["result"]["value"]==7
direct_before,attachments=direct_state(first_id)
settings_before=settings()
negative=subprocess.run(["ops","-wsk","action","get","/openserverless/hello/hello"],capture_output=True,text=True)
assert negative.returncode!=0,"another namespace's private action was accessible"
pvc=get("pvc","couchdb-pvc-couchdb-0")
pod=get("pod","couchdb-0")
version=json.loads(subprocess.check_output(KUBE+["exec","couchdb-0","--","curl","-fsS","http://localhost:5984"]))["version"]
assert version=="3.5.2"
started=time.monotonic()
subprocess.run(KUBE+["delete","pod","couchdb-0","--timeout=90s"],check=True,stdout=subprocess.DEVNULL)
for _ in range(120):
    try:
        replacement=get("pod","couchdb-0")
        if replacement["metadata"]["uid"]!=pod["metadata"]["uid"] and any(c["type"]=="Ready" and c["status"]=="True" for c in replacement["status"].get("conditions",[])):
            healthy=subprocess.run(KUBE+["exec","couchdb-0","--","curl","-fsS","http://localhost:5984/_up"],capture_output=True)
            if healthy.returncode==0: break
    except subprocess.CalledProcessError: pass
    time.sleep(1)
else: raise RuntimeError("CouchDB did not recover after restart")
old=activation(first_id)
assert old["response"]["result"]["value"]==7
assert any("couchdb35-verification" in line for line in old["logs"])
direct_after,_=direct_state(first_id)
assert direct_before==direct_after,"CouchDB documents or attachment bytes changed across restart"
assert settings_before==settings(),"CouchDB configuration changed across restart"
with tempfile.TemporaryDirectory(prefix="ops-couchdb35-code-") as directory:
    restored_code=pathlib.Path(directory,"restored.js")
    ops("-wsk","action","get","advancedcouchprobe","--save-as",str(restored_code))
    assert restored_code.read_text().strip()==source
second=document(ops("-wsk","action","invoke","advancedcouchprobe","--blocking","-p","value","8"))
assert second["response"]["result"]=={"marker":"couchdb35","value":8}
assert activation(second["activationId"])["response"]["result"]["value"]==8
assert get("pvc","couchdb-pvc-couchdb-0")["metadata"]["uid"]==pvc["metadata"]["uid"]
assert get("wsku",user)["spec"]==spec
result={"version":version,"user":user,"action":"advancedcouchprobe","activation_before":first_id,"activation_after":second["activationId"],"action_code_persisted":True,"activation_result_and_logs_persisted":True,"direct_couchdb_document_hashes_preserved":True,"direct_attachment_bytes_verified":attachments,"declarative_configuration_preserved":True,"settings":settings_before,"user_spec_preserved":True,"pvc_uid_preserved":True,"other_namespace_private_action_denied":True,"recover_and_verify_seconds":round(time.monotonic()-started,2)}
(OUT/"couchdb-integrated-restart.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
