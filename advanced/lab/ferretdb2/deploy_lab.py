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

"""Create disposable, internal-only candidates in the retained OPS lab VM.

Never run against a production cluster. The VM identity and namespace are checked.
Credentials are generated in memory and passed directly to kubectl, never logged.
"""
import json
import secrets
import subprocess

NS = "ops-ferretdb2-lab"
K = ["sudo", "-n", "k3s", "kubectl"]
nodes = json.loads(subprocess.check_output(K + ["get", "nodes", "-o", "json"]))
assert [n["metadata"]["name"] for n in nodes["items"]] == ["ops-advanced-rc7"]
existing = subprocess.check_output(K + ["get", "ns", NS, "--ignore-not-found", "-o", "name"])
assert not existing, "Lab already exists; inspect it instead of replacing credentials or data."

objects = [{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": NS}}]
def obj(kind, name, **body):
    api = "apps/v1" if kind == "StatefulSet" else "batch/v1" if kind == "Job" else "v1"
    value = {"apiVersion": api, "kind": kind, "metadata": {"name": name, "namespace": NS}, **body}
    objects.append(value)
    return value

passwords = {key: secrets.token_urlsafe(32) for key in ["PG_PASSWORD", "NATIVE_PASSWORD", "ALPHA_PASSWORD", "BETA_PASSWORD"]}
passwords["FERRET_URL"] = "postgres://postgres:" + passwords["PG_PASSWORD"] + "@pg17-docdb:5432/postgres"
obj("Secret", "lab-auth", type="Opaque", stringData=passwords)
def literal(key, value):
    return {"name": key, "value": value}
def secret(key, source):
    return {"name": key, "valueFrom": {"secretKeyRef": {"name": "lab-auth", "key": source}}}
def stateful(name, image, port, env, mount=None, probe=None):
    container = {"name": name, "image": image, "imagePullPolicy": "IfNotPresent", "env": env,
                 "ports": [{"containerPort": port}], "resources": {"requests": {"cpu": "100m", "memory": "256Mi"}, "limits": {"memory": "1536Mi"}}}
    if probe:
        container["readinessProbe"] = probe
    spec = {"serviceName": name, "replicas": 1, "selector": {"matchLabels": {"app": name}},
            "template": {"metadata": {"labels": {"app": name}}, "spec": {"containers": [container]}}}
    if mount:
        container["volumeMounts"] = [{"name": "data", "mountPath": mount}]
        spec["volumeClaimTemplates"] = [{"metadata": {"name": "data"}, "spec": {"accessModes": ["ReadWriteOnce"], "storageClassName": "local-path", "resources": {"requests": {"storage": "2Gi"}}}}]
    obj("StatefulSet", name, spec=spec)
    obj("Service", name, spec={"selector": {"app": name}, "ports": [{"port": port, "targetPort": port}], "type": "ClusterIP"})

stateful("pg17-docdb", "ghcr.io/ferretdb/postgres-documentdb:17-0.107.0-ferretdb-2.7.0", 5432,
         [literal("POSTGRES_USER", "postgres"), secret("POSTGRES_PASSWORD", "PG_PASSWORD"), literal("PGDATA", "/var/lib/postgresql/data/pgdata")],
         "/var/lib/postgresql/data", {"exec": {"command": ["pg_isready", "-U", "postgres"]}, "periodSeconds": 3})
stateful("ferret27", "ghcr.io/ferretdb/ferretdb:2.7.0", 27017,
         [secret("FERRETDB_POSTGRESQL_URL", "FERRET_URL"), literal("FERRETDB_TELEMETRY", "disable")],
         probe={"tcpSocket": {"port": 27017}, "periodSeconds": 3})
stateful("native18", "ghcr.io/documentdb/documentdb/documentdb-local:pg18-0.117.0", 10260,
         [literal("USERNAME", "lab_admin"), secret("PASSWORD", "NATIVE_PASSWORD"), literal("DATA_PATH", "/data/pgdata"), literal("ENABLE_TELEMETRY", "false"), literal("TLS_MODE", "requireTLS")],
         "/data", {"tcpSocket": {"port": 10260}, "periodSeconds": 3})

subprocess.run(K + ["apply", "-f", "-"], input=json.dumps({"apiVersion": "v1", "kind": "List", "items": objects}).encode(), check=True, stdout=subprocess.DEVNULL)
print("Isolated candidates created in " + NS + "; no public ports or ingress.")
