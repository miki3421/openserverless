<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements. See the NOTICE file
distributed with this work for additional information
regarding copyright ownership. The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License. You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied. See the License for the
specific language governing permissions and limitations
under the License.
-->

# Internal registry pulls on K3s

The OPS builder pushes to `openserverless-registry-svc:5000`. That name is
resolved by cluster DNS inside Pods, but the node's containerd cannot resolve
it using its normal host DNS. The internal registry is also exposed through
NodePort 32000.

The accompanying [registries.yaml](registries.yaml) maps exactly that image
registry name to `http://127.0.0.1:32000` for containerd. The original image
reference stays unchanged. Pod `imagePullSecrets` continue to authenticate
against the original registry name; this file contains no credentials.
There are no wildcard or public-registry mirror entries.

## Apply to a node

This configuration is for the OPS internal HTTP registry with NodePort 32000.
Verify that the node can reach that port (an unauthenticated HTTP 401 from
`/v2/` is expected), and that the Pod has a matching pull secret.

On **each K3s node that runs actions**, install the configuration at
`/etc/rancher/k3s/registries.yaml`. If that file already exists, merge just the
`openserverless-registry-svc:5000` mirror into it after reviewing any existing
entry for the same name. Preserve all unrelated mirrors, authentication and
TLS configuration. Do not overwrite an existing configuration with this file.

For a fresh node with no existing configuration, run from this directory:

```bash
sudo test ! -e /etc/rancher/k3s/registries.yaml && \
  sudo install -D -m 600 registries.yaml /etc/rancher/k3s/registries.yaml
```

Restart the appropriate service to load the configuration:

```bash
# K3s server node
sudo systemctl restart k3s
# On an agent node, use k3s-agent instead of k3s.
```

Plan node restarts appropriately on a shared installation. This explicit
configuration step is not automatically wired into `ops cloud k3s install`.
For a registry with another NodePort, TLS or an external address, use its
verified endpoint instead. Loopback access relies on the node's NodePort
networking being available.

## Validation

Use an image that was pushed to the private registry, with
`imagePullPolicy: Always` and `imagePullSecrets: [{name: registry-pull-secret}]`.
Confirm a successful pull and execution, then test a public image as well.
A private pull without credentials must still fail. Standard OpenWhisk
invoker/standalone Pod templates in this checkout already refer to
`registry-pull-secret`.

The 13 October 2026 Advanced lab check passed all three pull cases: authenticated
private pull succeeded, unauthenticated private pull failed, and a public
Docker Hub image still pulled and ran. Kubernetes version: `v1.37.1+k3s1`.

Reference: [K3s private registry configuration](https://docs.k3s.io/installation/private-registry).
