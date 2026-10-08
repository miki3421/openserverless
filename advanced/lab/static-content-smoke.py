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

"""Verify an uploaded object through the tenant's actual HTTP static route."""
import hashlib
import json
import os
import pathlib
import socket
import sys
import subprocess
import tempfile
import time
import urllib.request

user = sys.argv[1] if len(sys.argv) > 1 else "demostaticuser"
assert socket.gethostname() == "ops-advanced-rc7", "This test is restricted to the dedicated Advanced VM"
spec = json.loads(subprocess.check_output(["kubectl", "-n", "openserverless", "get", "wsku", user, "-o", "json"]))["spec"]
env = {**os.environ, "OPS_USER": user, "OPS_PASSWORD": spec["password"]}
logged = subprocess.run(["ops", "-login", "http://miniops.me"], env=env, capture_output=True, text=True)
assert logged.returncode == 0 and f"Successfully logged in as {user}." in logged.stdout
content = b"OPS Advanced static HTTP object verification 20261008\n"
name = "advanced-static-check-20261008.txt"
with tempfile.TemporaryDirectory(prefix="ops-advanced-static-") as directory:
    pathlib.Path(directory, name).write_bytes(content)
    uploaded = subprocess.run(["ops", "util", "upload", directory], capture_output=True, text=True)
    assert uploaded.returncode == 0, "static upload failed"
url = f"http://{user}.miniops.me/{name}"
for attempt in range(12):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            body = response.read()
            status = response.status
        if status == 200 and body == content:
            break
    except Exception:
        pass
    time.sleep(3)
else:
    raise AssertionError("uploaded static object was not retrieved byte-for-byte via HTTP")
result = {"url": url, "http_status": status, "exact_content_match": True, "sha256": hashlib.sha256(body).hexdigest()}
pathlib.Path("/home/ubuntu/ops-advanced-test/results/static-content-smoke.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
