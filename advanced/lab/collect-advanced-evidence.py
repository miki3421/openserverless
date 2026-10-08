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

import hashlib
import json
import pathlib
import socket
import subprocess
import urllib.request

assert socket.gethostname() == "ops-advanced-rc7"
OUT = pathlib.Path("/home/ubuntu/ops-advanced-test/results")
KUBE = ["sudo", "-n", "k3s", "kubectl"]


def kube(*args):
    return json.loads(subprocess.check_output(KUBE + list(args) + ["-o", "json"]))


metadata_path = OUT / "benchmark/metadata.json"
metadata = json.loads(metadata_path.read_text())
for name in ["pg16", "pg18"]:
    pod = kube("get", "pod", name + "-0", "-n", "ops-pg-migration-lab")
    metadata["servers"][name]["image_id"] = pod["status"]["containerStatuses"][0]["imageID"]
metadata_path.write_text(json.dumps(metadata, indent=2))
assert (OUT/"pvc-before-repeat.txt").read_bytes() == (OUT/"pvc-after-repeat.txt").read_bytes()
assert (OUT/"devel-before-repeat.sha256").read_bytes() == (OUT/"devel-after-repeat.sha256").read_bytes()
workloads = kube("get", "sts,deploy", "-n", "openserverless")["items"]
assert all(w["status"].get("readyReplicas", 0) == w["spec"].get("replicas", 1) for w in workloads)
fixture_hash = "252d298a71a1ead209f6b254925984e56c7376857d97dc16b320ff96644078cf"
root_responses = []
for _ in range(10):
    with urllib.request.urlopen("http://demostaticuser.miniops.me/", timeout=10) as response:
        data = response.read()
        assert response.status == 200 and hashlib.sha256(data).hexdigest() == fixture_hash
    root_responses.append(hashlib.sha256(data).hexdigest())
node = kube("get", "nodes")["items"][0]
assert any(c["type"] == "Ready" and c["status"] == "True" for c in node["status"]["conditions"])
assert node["metadata"]["name"] == "ops-advanced-rc7"
result = {
    "node": node["metadata"]["name"], "node_uid": node["metadata"]["uid"],
    "k3s_version": node["status"]["nodeInfo"]["kubeletVersion"],
    "node_ready": True, "all_ops_workload_controllers_ready": True,
    "pvc_identities_preserved_on_repeat": True, "devel_spec_preserved_on_repeat": True,
    "static_root_exact_fixture_responses": len(root_responses),
    "obsolete_static_test_phrase_present": b" Welcome to Apache OpenServerless (incubating) static content distributor landing page!!!" in data,
    "workloads": [{"kind": w["kind"], "name": w["metadata"]["name"], "ready": w["status"].get("readyReplicas", 0), "desired": w["spec"].get("replicas", 1)} for w in workloads],
    "images": {}
}
for name in ["openserverless-operator-0", "openserverless-postgres-1-0", "openserverless-postgres-2-0"]:
    pod = kube("get", "pod", name, "-n", "openserverless")
    result["images"][name] = [{"image": c["image"], "image_id": c["imageID"]} for c in pod["status"]["containerStatuses"]]
(OUT/"final-state.json").write_text(json.dumps(result, indent=2))
print("PASS: OPS Ready, PVC/user identities preserved, static root matches fixture in 10/10 requests")
