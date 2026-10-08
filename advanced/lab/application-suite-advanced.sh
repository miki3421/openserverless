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

set -uo pipefail
source /home/ubuntu/ops-advanced-test/env.sh
test "$(hostname)" = ops-advanced-rc7 || exit 2
cd /home/ubuntu/ops-advanced-test/testing/tests || exit 2
results="${1:-/home/ubuntu/ops-advanced-test/results/application-suite}"
mkdir -p "$results"
chmod 700 "$results"
: > "$results/summary.txt"
failed=0
# Provisioning was tested by the full setup. TLS is excluded from this HTTP lab.
for script in 3-sys-redis.sh 4a-sys-ferretdb.sh 4b-sys-postgres.sh \
  5-sys-seaweedfs.sh 6-login.sh 7-static.sh 8-user-redis.sh \
  9a-user-ferretdb.sh 9b-user-postgres.sh 10-user-seaweedfs.sh \
  14-runtime-testing.sh 11-sso-mock.sh; do
  if timeout 900 bash "$script" k3s > "$results/$script.log" 2>&1; then
    printf 'PASS %s\n' "$script" | tee -a "$results/summary.txt"
  else
    rc=$?
    printf 'FAIL %s (exit %s)\n' "$script" "$rc" | tee -a "$results/summary.txt"
    failed=$((failed+1))
  fi
  chmod 600 "$results/$script.log"
done
exit "$failed"
