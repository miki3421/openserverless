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

"""Attach a candidate gateway to the isolated native PG18 backend only."""
import json
import subprocess
K = ["sudo", "-n", "k3s", "kubectl"]
NS = "ops-ferretdb2-lab"
nodes = json.loads(subprocess.check_output(K + ["get", "nodes", "-o", "json"]))
assert [n["metadata"]["name"] for n in nodes["items"]] == ["ops-advanced-rc7"]
patch = {"spec":{"template":{"spec":{"containers":[{"name":"ferret27-pg18","image":"ghcr.io/ferretdb/ferretdb:2.7.0","imagePullPolicy":"IfNotPresent","env":[{"name":"FERRETDB_POSTGRESQL_URL","value":"postgres://documentdb@localhost:9712/postgres"},{"name":"FERRETDB_TELEMETRY","value":"disable"}],"readinessProbe":{"tcpSocket":{"port":27017},"periodSeconds":3},"resources":{"requests":{"memory":"64Mi","cpu":"50m"},"limits":{"memory":"512Mi"}}}]}}}}
subprocess.run(K + ["patch","sts","native18","-n",NS,"--type=strategic","--patch",json.dumps(patch)],check=True)
patch = {"spec":{"ports":[{"port":10260,"targetPort":10260,"name":"native"},{"port":27017,"targetPort":27017,"name":"ferret"}]}}
subprocess.run(K + ["patch","svc","native18","-n",NS,"--type=merge","--patch",json.dumps(patch)],check=True)
