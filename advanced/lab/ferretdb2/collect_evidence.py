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

"""Capture redacted synthetic test evidence; never export Kubernetes Secrets."""
import base64
import datetime
import json
from pathlib import Path
import socket
import subprocess

assert socket.gethostname() == "ops-advanced-rc7"
K = ["sudo", "-n", "k3s", "kubectl"]
NS = "ops-ferretdb2-lab"
OUT = Path("/home/ubuntu/ops-advanced-test/results/ferretdb2")
OUT.mkdir(parents=True, exist_ok=True)
def get(kind, namespace):
    return json.loads(subprocess.check_output(K + ["get", kind, "-n", namespace, "-o", "json"]))
values = [base64.b64decode(v).decode() for v in get("secret/lab-auth", NS)["data"].values()]
def redact(text):
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, "[redacted]")
    return text
probes = {}
for job in get("jobs", NS)["items"]:
    name = job["metadata"]["name"]
    log = redact(subprocess.check_output(K + ["logs", "-n", NS, "job/" + name], stderr=subprocess.STDOUT).decode())
    (OUT / (name + ".log")).write_text(log)
    records = []
    for line in log.splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    probes[name] = {"conditions": job["status"].get("conditions"), "records": records}
def pods(namespace):
    return [{"name": p["metadata"]["name"], "uid":p["metadata"]["uid"], "phase":p["status"]["phase"],
             "containers":[{"name":c["name"],"image":c["image"],"imageID":c.get("imageID"),"ready":c["ready"],"restartCount":c["restartCount"],"state":c["state"]} for c in p["status"].get("containerStatuses",[])]} for p in get("pods",namespace)["items"]]
report = {"recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "vm":socket.gethostname(),
          "namespace":NS, "probes":probes, "candidate_pods":pods(NS), "ops_pods":pods("openserverless"),
          "pvcs":[{"name":p["metadata"]["name"],"uid":p["metadata"]["uid"],"volume":p["spec"].get("volumeName"),"phase":p["status"]["phase"]} for p in get("pvc",NS)["items"]]}
(OUT / "evidence.json").write_text(redact(json.dumps(report,indent=2)) + "\n")
for pod,container,user,port in [("pg17-docdb-0","pg17-docdb","postgres","5432"),("native18-0","native18","documentdb","9712")]:
    sql="SELECT version(); SELECT extname,extversion FROM pg_extension ORDER BY extname; SELECT rolname,rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname LIKE 'sql_%' OR rolname LIKE 'scoped_%' OR rolname LIKE 'default_%' ORDER BY rolname;"
    if pod=="native18-0":
        sql += " SELECT id, embedding <-> '[1,0,0]'::vector FROM advanced_vector_lab.synthetic ORDER BY id;"
    result=subprocess.check_output(K+["exec","-n",NS,pod,"-c",container,"--","psql","-h","localhost","-p",port,"-U",user,"-d","postgres","-At","-c",sql],stderr=subprocess.STDOUT).decode()
    (OUT/(pod+"-sql.log")).write_text(redact(result))
print("Redacted logs and evidence saved. No Secrets exported.")
