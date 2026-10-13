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

# Advanced builder closeout — 13 October 2026

## Scope

Personal Advanced repositories only. Existing Alpha and Beta application source
was not modified. Two new private Beta actions (`builder/node`, `builder/python`)
exercise custom runtimes. No Apache publication or remote container-image push.

## Final worker design

- Kubernetes Pod user namespace (`hostUsers:false`), UID/GID1000, no privileged
  mode, no service-account token, no host mounts/PID/network namespace.
- BuildKit process sandbox enabled (`noProcessSandbox=false`). The earlier
  shared-process lab configuration is superseded, not published.
- Dedicated worker uses AppArmor/seccomp Unconfined and procMount Unmasked inside
  the private Pod user namespace. BuildKit pinned by digest.
- Subordinate mappings exclude Pod root and support child IDs0–65534. Requires
  compatible Kubernetes/containerd user namespaces; only K3s1.37.1 amd64 tested.
- Python and Node retain executable `/bin/extend`. Standard-image fallbacks use
  pip or npm respectively. Node modules are linked into `/app/node_modules`;
  existing directories and dangling symlinks are rejected, never overwritten.

## Validation

- Eight builder unit tests passed, including generated-shell collision tests.
- Python standard runtime build/push passed with humanize4.13.0.
- Synthetic extension-aware Python build/push and Beta invocation passed; the
  action checked both import and the marker written by `/bin/extend`.
- Node22 runtime build/push and Beta invocation passed with is-number7.0.0;
  module resolved from `/opt/ops-deps/node_modules`.
- Actual API-created Pod persisted hostUsers=false and token automount=false.
- Isolated worker marker test passed with process sandbox enabled and overlayfs;
  daemon marker inaccessible; chown to65534:65534 succeeded. This bounded test
  does not prove absence of all container/kernel vulnerabilities.
- Malformed target, source newline and another tenant's target returned HTTP400.
- Fresh Alpha/Beta functional suite: four checks passed, exercising all five
  data services. Both frontends HTTP200; permanent workloads ready;22 PVC Bound.
- Old fixture inspection failed Redis only (fixture keys have a24-hour TTL);
  the other four services retained their records. Fresh fixtures passed.

Independent sub-agent code review completed after corrections, with no remaining
blocking finding in the scoped diff. This was not a canonical Daybreak scan:
security scan MCP tools were unavailable. Runtime tests were performed by the
parent agent separately from the code reviewer.

## Limitations

`ops ide deploy` does not call the builder API automatically. Build, deploy and
invoke were separate steps. Native Node ESM, multi-node K3s and Docker+Kind were
not tested. OpenWhisk still discards @sha256 action-image digests; tests use
unique tags and record image digests. Sources are published separately from
container images: the updated Admin API image was imported only into the lab.
MongoDB modernization and migration orchestration are outside this closeout.
