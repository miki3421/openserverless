#!/usr/bin/env bash
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

set -euo pipefail
source /home/ubuntu/ops-advanced-test/env.sh
test "$(hostname)" = ops-advanced-rc7
out=/home/ubuntu/ops-advanced-test/results/couchdb35
cd /home/ubuntu/ops-advanced-test/testing/tests
for script in 6-login.sh 14-runtime-testing.sh 11-sso-mock.sh; do
  timeout 900 bash "$script" k3s > "$out/post-$script.log" 2>&1
  printf 'PASS after reinstall: %s\n' "$script" | tee -a "$out/post-reinstall-summary.txt"
done
python3 /home/ubuntu/ops-advanced-test/static-content-smoke.py demouser > "$out/post-static.log" 2>&1
cp /home/ubuntu/ops-advanced-test/results/static-content-smoke.json "$out/post-static.json"
python3 /home/ubuntu/ops-advanced-test/streamer-content-smoke.py demouser > "$out/post-streamer.log" 2>&1
cp /home/ubuntu/ops-advanced-test/results/streamer-content-smoke.json "$out/post-streamer.json"
python3 /home/ubuntu/ops-advanced-test/couchdb-integrated-check.py > "$out/post-couchdb.log" 2>&1
cp "$out/couchdb-integrated-restart.json" "$out/post-couchdb-restart.json"
printf 'PASS after reinstall: static, streaming, action/activation persistence\n' | tee -a "$out/post-reinstall-summary.txt"
