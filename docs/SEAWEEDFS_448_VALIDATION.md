<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
-->

# SeaweedFS 4.48: Advanced lab validation

## Scope and deployed versions

Validated on 2026-10-16 in the Advanced K3s lab. The comparative baseline was
left unchanged. Application source and deployed action parameters were not
modified during promotion.

- SeaweedFS: 3.97 to 4.48, pinned to
  `sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`.
- Operator: `miki3421/ops-advanced-operator:seaweedfs-20261016-r2`.
- Milvus remains 2.5.2 and uses the shared upgraded S3 service.
- The image is local to the lab; it has not been uploaded to a registry.
  Other servers must build/import it before using this task catalog.

## Implementation

The operator treats a successful Seaweed shell command with empty stdout as
success. SeaweedFS 4.48 emits some successful quota/deletion messages on stderr
or no output at all. Nonzero exit status, explicit error diagnostics and timeouts
still fail the operation. In particular, a failed anonymous-access revocation
must not allow bucket deletion. Commands/responses containing credentials are
not logged, and newline/semicolon command separators are rejected.

The manifest includes startup and readiness probes and an explicit `/data`
working directory. Image changes on an existing SeaweedFS StatefulSet, and
implicit reuse of an orphaned PVC, remain blocked. These guards do not implement
a production migration or `ops setup cluster --upgrade`.

The operator starts by extracting `deploy.tar` onto its deployment volume.
The incremental lab image therefore updates that archive as well as the source
manifest. The deployed manifest and Python files were checked against the local
source hashes. A normal complete operator Dockerfile build already regenerates
this archive from the deployment sources.

## Promotion procedure used in the lab

The operator, controller, invoker and shared Milvus were paused. A private logical
export captured 1,399 objects from nine buckets, bucket quotas, object content
and custom metadata/tags, and the six S3 identities. The old volume's reclaim
policy was changed to `Retain` before retiring its PVC. A fresh PVC with a new
volume identity was created for 4.48; the old disk was not mounted by 4.48.

The shared service was kept disconnected while original credentials and scoped
grants were restored, followed by object data. All object SHA-256 hashes and
identity/action grants were verified before reconnecting the service and
resuming writers. Temporary copy credentials were removed. The old PV and the
restricted lab export remain available for recovery.

This bounded lab copy is not a reusable production migration procedure. It did
not attempt versioned-bucket migration, an HA upgrade or zero downtime.

## Checks and results

- Operator tests: 15/15 passed, including fail-closed revocation and volume guards.
- Direct S3 checks: 12/12 passed using the installed operator code against the
  shared service: owner read/write; peer read/write/copy denial; anonymous private
  reads, listing and writes denied; public web reads allowed; selective revocation;
  preservation of the other web bucket's grant; private bucket recreation.
- Byte-for-byte upload/download verification included 12 MiB multipart objects.
- Alpha/Beta suite before promotion: 15/15 passed.
- Alpha/Beta suite after promotion: 15/15 passed, including tenant isolation,
  persistence, concurrent tenants and 30 load requests per app at concurrency four,
  with zero load errors.
- Shared SeaweedFS pod restart: 15/15 application checks passed again. Both
  pre-promotion application fixtures were read successfully across all five
  components without recreating them.
- Source files, deployed action code/parameters/annotations/limits, and frontend
  content hashes matched before and after promotion.

Earlier isolated-candidate tests also verified a Milvus insertion/flush/search
of 100 vectors and read them after a Milvus pod restart. Both the candidate and
shared-service checks preserve the S3 security behavior; they are regression
checks, not an independent security audit or a general performance claim.

Local detailed evidence is under
`/root/ops-update-sso/ops-advanced/seaweedfs-promote-20261016/`.
The previous isolated candidate pods/services were retired; their test volumes
were retained. Credentials and object exports are excluded from the repositories.
