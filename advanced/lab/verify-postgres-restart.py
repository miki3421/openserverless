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

"""Verify synthetic data on both integrated replicas, then restart the primary."""
import json
import pathlib
import subprocess
import sys
import time

KUBE = ["sudo", "-n", "k3s", "kubectl", "-n", "openserverless"]
OUT = pathlib.Path("/home/ubuntu/ops-advanced-test/results")
expected = json.loads((OUT / "integrated-postgres.json").read_text())


def kube(*args):
    return subprocess.check_output(KUBE + list(args), text=True)


def pods():
    return json.loads(kube("get", "pods", "-l", "app=openserverless-postgres", "-o", "json"))["items"]


def pvc_identity():
    return {p["metadata"]["name"]: {"uid": p["metadata"]["uid"], "pv": p["spec"]["volumeName"]}
        for p in json.loads(kube("get", "pvc", "-o", "json"))["items"]
        if p["metadata"]["name"].startswith("postgres-db-openserverless-postgres-")}


def verify_data():
    result = {}
    current = pods()
    assert len(current) == 2
    for pod in current:
        name = pod["metadata"]["name"]
        data = {}
        for user in ["demopostgresuser", "testactionuser"]:
            query = f"SELECT pg_is_in_recovery(); SELECT count(*), md5(string_agg(id::text || payload::text || embedding::text, ',' ORDER BY id)) FROM {user}_schema.advanced_records"
            raw = kube("exec", name, "--", "sh", "-c",
                'PGPASSWORD="$POSTGRES_PASSWORD" psql -w -U postgres -d "$1" -At -v ON_ERROR_STOP=1 -c "$2"', "sh", user, query).strip().splitlines()
            count, checksum = raw[-1].split("|")
            assert int(count) == expected[user]["records"] and checksum == expected[user]["checksum"]
            data[user] = {"rows": int(count), "checksum": checksum}
        result[name] = {"in_recovery": raw[0] == "t", "datasets": data}
    assert sorted(p["in_recovery"] for p in result.values()) == [False, True]
    return result


nodes = json.loads(kube("get", "nodes", "-o", "json"))["items"]
assert len(nodes) == 1 and nodes[0]["metadata"]["name"] == "ops-advanced-rc7"
before = verify_data()
pvc_before = pvc_identity()
if "--check-only" in sys.argv:
    print(json.dumps({"replicas": before, "pvcs": pvc_before}, indent=2))
    sys.exit(0)
primary = next(name for name, details in before.items() if not details["in_recovery"])
old_uid = next(p["metadata"]["uid"] for p in pods() if p["metadata"]["name"] == primary)
started = time.monotonic()
kube("delete", "pod", primary, "--timeout=120s")
for attempt in range(120):
    current = pods()
    replacement = next((p for p in current if p["metadata"]["name"] == primary), None)
    if replacement and replacement["metadata"]["uid"] != old_uid and all(
            any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", []))
            for p in current) and len(current) == 2:
        break
    time.sleep(3)
else:
    raise RuntimeError("PostgreSQL replicas did not return Ready after the primary restart")
after = verify_data()
assert pvc_before == pvc_identity()
result = {"before": before, "after": after, "pvc_identity_preserved": True,
    "primary_pod_recreated": primary, "ready_after_seconds": round(time.monotonic()-started, 2)}
(OUT / "replication-restart.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
