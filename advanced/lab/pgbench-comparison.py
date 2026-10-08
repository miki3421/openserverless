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

"""Compare lab PostgreSQL 16/18 using one client and equal server limits."""
import json
import math
import pathlib
import re
import socket
import statistics
import subprocess
import time

NS = "ops-pg-migration-lab"
assert socket.gethostname() == "ops-advanced-rc7", "This benchmark is restricted to the dedicated Advanced VM"
OUT = pathlib.Path("/home/ubuntu/ops-advanced-test/results/benchmark")
OUT.mkdir(parents=True, exist_ok=True)
KUBE = ["sudo", "-n", "k3s", "kubectl", "-n", NS]
IMAGE = "docker.io/pgvector/pgvector:0.8.6-pg18-bookworm@sha256:2ba9ca5f2e7daa0f0e7723cba1ee9167bab54efd3640516a44ac1a928dd67e7a"


def kube(*args, input=None):
    return subprocess.check_output(KUBE + list(args), input=input, text=True)


def server_sql(server, query, database="postgres"):
    return kube("exec", server + "-0", "--", "sh", "-c",
        'PGPASSWORD="$POSTGRES_PASSWORD" psql -w -U postgres -d "$1" -At -v ON_ERROR_STOP=1 -c "$2"',
        "sh", database, query)


def metrics(server):
    data = kube("exec", server + "-0", "--", "sh", "-c",
        "cat /sys/fs/cgroup/cpu.stat; echo MEMORY; cat /sys/fs/cgroup/memory.current; echo IO; cat /sys/fs/cgroup/io.stat")
    cpu, rest = data.split("MEMORY\n")
    memory, io = rest.split("IO\n")
    cpu = dict(line.split() for line in cpu.strip().splitlines())
    totals = {"rbytes": 0, "wbytes": 0}
    for line in io.strip().splitlines():
        for field in line.split()[1:]:
            key, value = field.split("=")
            if key in totals:
                totals[key] += int(value)
    return {"cpu_seconds": int(cpu["usage_usec"])/1e6, "memory_bytes": int(memory.strip()), **totals}


pod = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "pgbench-client", "namespace": NS},
    "spec": {"automountServiceAccountToken": False, "restartPolicy": "Never", "containers": [{
        "name": "client", "image": IMAGE, "imagePullPolicy": "IfNotPresent", "command": ["sleep", "7200"],
        "env": [{"name": "PGPASSWORD", "valueFrom": {"secretKeyRef": {"name": "pg-migration-test", "key": "POSTGRES_PASSWORD"}}}],
        "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}}}]}}
kube("apply", "-f", "-", input=json.dumps(pod))
kube("wait", "--for=condition=Ready", "pod/pgbench-client", "--timeout=120s")
kube("exec", "pgbench-client", "--", "mkdir", "-p", "/tmp/pgbench-results")
metadata = {"client_image": IMAGE, "scale": 20, "clients": 4, "threads": 2, "seconds": 40,
    "warmup_seconds": 20, "repeats": 3, "order": ["pg16", "pg18", "pg18", "pg16", "pg16", "pg18"],
    "caveat": "Shared VM with running OPS; warm-cache exploratory benchmark, not a production capacity result.", "servers": {}}
for server in ["pg16", "pg18"]:
    spec = json.loads(kube("get", "sts", server, "-o", "json"))["spec"]["template"]["spec"]["containers"][0]
    assert spec["resources"]["limits"] == {"cpu": "1", "memory": "1Gi"}
    query = "SELECT name,setting FROM pg_settings WHERE name IN ('server_version','shared_buffers','fsync','synchronous_commit','data_checksums','effective_io_concurrency','max_connections') ORDER BY name"
    settings = server_sql(server, query)
    metadata["servers"][server] = {"image": spec["image"], "resources": spec["resources"], "settings": settings}
    pod_status = json.loads(kube("get", "pod", server + "-0", "-o", "json"))["status"]
    metadata["servers"][server]["image_id"] = pod_status["containerStatuses"][0]["imageID"]
    server_sql(server, "DROP DATABASE IF EXISTS opsadv_bench")
    server_sql(server, "CREATE DATABASE opsadv_bench")
    init = kube("exec", "pgbench-client", "--", "pgbench", "-h", server, "-U", "postgres", "-i", "-s", "20", "opsadv_bench")
    (OUT / (server + "-init.txt")).write_text(init)
    query = "SELECT count(*),sum(aid),sum(abalance) FROM pgbench_accounts"
    metadata["servers"][server]["dataset"] = server_sql(server, query, "opsadv_bench").strip()
    kube("exec", "pgbench-client", "--", "pgbench", "-h", server, "-U", "postgres", "-c", "4", "-j", "2", "-T", "20", "-n", "-M", "prepared", "--random-seed=42", "opsadv_bench")
assert metadata["servers"]["pg16"]["dataset"] == metadata["servers"]["pg18"]["dataset"]
(OUT / "metadata.json").write_text(json.dumps(metadata, indent=2))
results = []
for run_no, server in enumerate(metadata["order"], 1):
    label = f"run-{run_no}-{server}"
    before = metrics(server)
    memory_samples = [before["memory_bytes"]]
    command = KUBE + ["exec", "pgbench-client", "--", "pgbench", "-h", server, "-U", "postgres", "-c", "4", "-j", "2", "-T", "40", "-n", "-M", "prepared", "--random-seed=42", "--exit-on-abort", "-l", f"--log-prefix=/tmp/pgbench-results/{label}", "opsadv_bench"]
    started = time.monotonic()
    with (OUT / (label + ".txt")).open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            memory_samples.append(metrics(server)["memory_bytes"])
            time.sleep(5)
        assert process.returncode == 0, label
    elapsed = time.monotonic()-started
    after = metrics(server)
    text = (OUT / (label + ".txt")).read_text()
    assert "number of failed transactions: 0" in text, text
    raw = kube("exec", "pgbench-client", "--", "sh", "-c", f"cat /tmp/pgbench-results/{label}.*")
    (OUT / (label + ".transactions")).write_text(raw)
    latencies = sorted(float(line.split()[2])/1000 for line in raw.splitlines())
    results.append({"run": run_no, "server": server, "tps": float(re.search(r"tps = ([\d.]+)", text)[1]),
        "p95_ms": latencies[math.ceil(len(latencies)*0.95)-1], "transactions": len(latencies),
        "cpu_seconds": after["cpu_seconds"]-before["cpu_seconds"],
        "sampled_memory_peak_mib": max(memory_samples)/1024**2,
        "read_mib": (after["rbytes"]-before["rbytes"])/1024**2,
        "write_mib": (after["wbytes"]-before["wbytes"])/1024**2, "elapsed_s": elapsed})
    (OUT / "runs.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results[-1]), flush=True)
summary = {}
for server in ["pg16", "pg18"]:
    rows = [row for row in results if row["server"] == server]
    summary[server] = {key: statistics.median(row[key] for row in rows) for key in
        ["tps", "p95_ms", "cpu_seconds", "sampled_memory_peak_mib", "read_mib", "write_mib"]}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2), flush=True)
