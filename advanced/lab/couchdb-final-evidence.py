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

"""Collect sanitized evidence from the final CouchDB lab deployment."""
import base64
import json
import pathlib
import socket
import subprocess

assert socket.gethostname()=="ops-advanced-rc7"
OUT=pathlib.Path("/home/ubuntu/ops-advanced-test/results/couchdb35")
KUBE=["sudo","-n","k3s","kubectl"]

def get(*args):
    return json.loads(subprocess.check_output(KUBE+["get",*args,"-o","json"]))

workloads=get("sts,deploy","-n","openserverless")["items"]
assert all(w["status"].get("readyReplicas",0)==w["spec"].get("replicas",1) for w in workloads)
node=get("nodes")["items"][0]
assert node["metadata"]["name"]=="ops-advanced-rc7"
assert any(c["type"]=="Ready" and c["status"]=="True" for c in node["status"]["conditions"])
whisk=get("whisk","controller","-n","openserverless")["spec"]
values=set()
def secrets_in(obj,trail=()):
    if isinstance(obj,dict):
        for key,value in obj.items(): secrets_in(value,trail+(key,))
    elif isinstance(obj,str) and len(obj)>=8:
        path=".".join(trail).lower()
        if any(k in path for k in ["password","secret","auth"]) or "openwhisk.namespaces" in path: values.add(obj)
secrets_in(whisk)
couch=get("sts","couchdb","-n","openserverless")
env=couch["spec"]["template"]["spec"]["containers"][0]["env"]
ref=next(item["valueFrom"]["secretKeyRef"] for item in env if item["name"]=="COUCHDB_PASSWORD")
secret=get("secret",ref["name"],"-n","openserverless")
values.add(base64.b64decode(secret["data"][ref["key"]]).decode())
logs=subprocess.check_output(KUBE+["logs","-n","openserverless","job/couchdb-init","-c","init-couchdb"],text=True)
assert values and not any(value in logs for value in values),"known initializer credentials appeared in logs"
pvc=get("pvc","couchdb-pvc-couchdb-0","-n","openserverless")
assert pvc["metadata"]["uid"]!=(OUT/"first-couchdb-pvc-uid.txt").read_text().strip()
external=subprocess.check_output(KUBE+["get","pvc","-n","ops-pg-migration-lab","-o","custom-columns=NAME:.metadata.name,UID:.metadata.uid,PV:.spec.volumeName"],text=True)
assert external==(OUT/"external-pvc-before.txt").read_text()
result={"node":node["metadata"]["name"],"node_ready":True,"all_ops_workloads_ready":True,"k3s":node["status"]["nodeInfo"]["kubeletVersion"],"fresh_couchdb_pvc_on_reinstall":True,"other_namespace_pvc_identities_preserved":True,"known_initializer_credentials_absent_from_logs":True,"credential_values_checked":len(values),"workloads":[{"kind":w["kind"],"name":w["metadata"]["name"],"ready":w["status"].get("readyReplicas",0)} for w in workloads],"images":{}}
for name in ["couchdb-0","openserverless-operator-0","openserverless-postgres-1-0"]:
    pod=get("pod",name,"-n","openserverless")
    result["images"][name]=[{"image":c["image"],"image_id":c["imageID"]} for c in pod["status"]["containerStatuses"]]
(OUT/"final-state.json").write_text(json.dumps(result,indent=2))
print("PASS: OPS Ready, new CouchDB volumes, other namespaces preserved, initializer credentials absent from logs")
