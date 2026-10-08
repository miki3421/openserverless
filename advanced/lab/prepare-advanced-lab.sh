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
test "$(hostname)" = ops-advanced-rc7
test "$(id -un)" = ubuntu
mkdir -p /home/ubuntu/.ops-advanced/tmp /home/ubuntu/ops-advanced-test/results
chmod 700 /home/ubuntu/.ops-advanced
if ! test -e /home/ubuntu/.ops-advanced/linux-amd64; then
  ln -s /home/ubuntu/.ops/linux-amd64 /home/ubuntu/.ops-advanced/linux-amd64
fi
sudo -n k3s kubectl config view --raw > /home/ubuntu/.ops-advanced/tmp/kubeconfig
chmod 600 /home/ubuntu/.ops-advanced/tmp/kubeconfig
cat > /home/ubuntu/ops-advanced-test/env.sh <<'ENV'
export OPS_HOME=/home/ubuntu/.ops-advanced
export OPS_TMP=$OPS_HOME/tmp
export OPS_BIN=$OPS_HOME/linux-amd64/bin
export OPS_ROOT=/home/ubuntu/ops-advanced-test/oplugins
export OPS_REPO=https://github.com/miki3421/openserverless-task-custom
export OPS_BRANCH=advanced
export KUBECONFIG=$OPS_HOME/tmp/kubeconfig
export PATH=/home/ubuntu/.local/bin:$OPS_HOME/linux-amd64/bin:$PATH
ENV
source /home/ubuntu/ops-advanced-test/env.sh
ops -info
ops config disable --all
ops config apihost miniops.me --protocol=http
ops config full
ops config status
