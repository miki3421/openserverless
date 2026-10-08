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

"""Run a fresh synthetic probe job; credentials stay in Kubernetes Secrets."""
import json
import os
import subprocess
from pathlib import Path

K = ["sudo", "-n", "k3s", "kubectl"]
NS = "ops-ferretdb2-lab"
nodes = json.loads(subprocess.check_output(K + ["get", "nodes", "-o", "json"]))
assert [n["metadata"]["name"] for n in nodes["items"]] == ["ops-advanced-rc7"]
mode = os.environ["MODE"]
assert mode in ("ferret", "native", "ferret18", "native_roles", "sql_roles", "legacy")
name = "mongo-probe-" + mode + os.environ.get("JOB_SUFFIX", "")
filename = mode + "_check.py" if mode in ("native_roles", "sql_roles", "legacy") else "mongo_check.py"
objs = [{"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "probe-source", "namespace": NS}, "data": {p.name:p.read_text() for p in Path(__file__).parent.glob("*check.py")}},
        {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": name.replace("_", "-"), "namespace": NS}, "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 420, "template": {"spec": {"restartPolicy": "Never", "containers": [{"name": "probe", "image": "docker.io/miki3421/ops-advanced-ferretdb-client:lab-20261008", "imagePullPolicy": "Never", "args": ["/probe/" + filename], "env": [{"name": "MODE", "value": mode}], "envFrom": [{"secretRef": {"name": "lab-auth"}}], "volumeMounts": [{"name": "source", "mountPath": "/probe", "readOnly": True}]}], "volumes": [{"name": "source", "configMap": {"name": "probe-source"}}]}}}}]
subprocess.run(K + ["apply", "-f", "-"], input=json.dumps({"apiVersion": "v1", "kind": "List", "items": objs}).encode(), check=True)
