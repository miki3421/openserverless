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

"""Verify tenant and dedicated-host streaming routes after the ingress fix."""
import json
import os
import pathlib
import socket
import subprocess
import tempfile
import urllib.request

user = "demostaticuser"
assert socket.gethostname() == "ops-advanced-rc7", "This test is restricted to the dedicated Advanced VM"
spec = json.loads(subprocess.check_output(["kubectl", "-n", "openserverless", "get", "wsku", user, "-o", "json"]))["spec"]
env = {**os.environ, "OPS_USER": user, "OPS_PASSWORD": spec["password"]}
logged = subprocess.run(["ops", "-login", "http://miniops.me"], env=env, capture_output=True, text=True)
assert logged.returncode == 0 and f"Successfully logged in as {user}." in logged.stdout
action = "advancedstream"
message = "OPS Advanced streaming verification 20261008"
source = '''const net = require('net');
async function main(args) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({host: args.STREAM_HOST, port: Number(args.STREAM_PORT)},
      () => socket.end('OPS Advanced streaming verification 20261008'));
    socket.setTimeout(10000, () => socket.destroy(new Error('stream timeout')));
    socket.on('error', reject);
    socket.on('close', () => resolve({ok: true}));
  });
}
'''
with tempfile.TemporaryDirectory(prefix="ops-advanced-stream-") as directory:
    script = pathlib.Path(directory, "stream.js")
    script.write_text(source)
    created = subprocess.run(["ops", "-wsk", "action", "update", action, str(script), "--kind", "nodejs:22", "--web", "true"], capture_output=True, text=True)
    assert created.returncode == 0, "failed to create the synthetic streaming action"
paths = [(f"http://{user}.miniops.me/stream/web/{action}", False),
    (f"http://{user}.miniops.me/web/{user}/{action}", False),
    (f"http://stream.miniops.me/web/{user}/{action}", False),
    (f"http://{user}.miniops.me/stream/action/{action}", True),
    (f"http://{user}.miniops.me/action/{user}/{action}", True)]
results = []
for url, private in paths:
    headers = {"Content-Type": "application/json"}
    if private:
        headers["Authorization"] = "Bearer " + spec["auth"]
    request = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode().strip()
        assert response.status == 200 and body == message, "streamed content mismatch"
    results.append({"url": url, "authenticated": private, "exact_stream_content": True})
pathlib.Path("/home/ubuntu/ops-advanced-test/results/streamer-content-smoke.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
