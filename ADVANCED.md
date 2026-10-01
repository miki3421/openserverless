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

# OPS Advanced

Personal distribution under the miki3421 account, based on Apache OpenServerless 0.9.0. It is not an Apache release. Original licensing, NOTICE and attribution are retained.

## Repository isolation

The root repository and all nine submodules use personal forks and the `advanced` branch. Gitlinks pin exact commits; `.gitmodules` points only to miki3421 repositories. `advanced/baseline.json` records the upstream starting commits.

Inherited GitHub Actions workflows are archived on this branch, outside `.github/workflows`, pending a dedicated review of image registries, release names and credentials. No automatic build/publication pipeline is enabled for Advanced. Existing 0.9.0 branches and Apache PRs are unchanged.

```sh
git clone --branch advanced --recurse-submodules https://github.com/miki3421/openserverless.git ops-advanced
```

The CLI source defaults to the personal task repository and `advanced` branch. For local development using an existing CLI, set these variables in a dedicated shell:

```sh
export OPS_HOME="$HOME/.ops-advanced"
export OPS_REPO="https://github.com/miki3421/openserverless-task-new"
export OPS_BRANCH=advanced
export OPS_ROOT="/absolute/path/to/ops-advanced/oplugins"
```

This isolates CLI configuration. It does not isolate Kubernetes: explicitly select the Advanced test cluster before running any deployment command. No Advanced CLI binary or container images have been published yet. The operator and PostgreSQL backup now reference personal development images that must be built and loaded into the test cluster; other components still use upstream images. See `oplugins-op/POSTGRES_ADVANCED.md`.

## First milestone: integrated PostgreSQL 18

Target PostgreSQL 18 with pgvector inside Kubernetes. Do not change the image tag of an existing PostgreSQL 16 data directory to migrate it.

The recorded upstream baseline uses pgvector/pgvector:pg16 and Kubegres 1.18. Advanced now selects a digest-pinned PostgreSQL 18.6/pgvector 0.8.6 image for new installations, retaining Kubegres 1.18 after isolated validation. The inspected K3s installation runs PostgreSQL 16.15 and has pgvector 0.8.6 available. As of 2026-09-17, the selected stable PostgreSQL target is 18.6, pgvector is 0.8.6, and Kubegres has a v1.19 tag. Kubegres 1.19 remains a research target; it was not included in this increment.

Before enabling PostgreSQL 18:

1. Resolve the target image and pin its digest; verify the actual PostgreSQL and pgvector versions for each supported architecture.
2. Validate Kubegres compatibility, PostgreSQL 18 data-directory layout, storage mounts, initialization, replication, failover and backup scripts. Decide whether Kubegres needs updating without changing other components at the same time.
3. Build the personal operator image; align its deployment template, backup tooling and the task image catalogue. A task catalogue edit alone does not change the operator's embedded manifest.
4. Test a fresh integrated installation in an isolated cluster: database/user provisioning, grants, vector extension, SQL/JSON, JavaScript/Python clients and services depending on PostgreSQL.
5. Implement and rehearse explicit PostgreSQL 16 to 18 migration using dump/restore or pg_upgrade. Keep the source volumes and verify rollback before any cutover. Test backup restoration and data integrity.
6. Benchmark the same dataset and workload on 16 and 18 with equal resources, recording throughput, p95 latency, CPU, memory and storage I/O.

Status: the PostgreSQL 18 development profile, local operator/backup builds, replication, manual promotion, user provisioning and backup/restore passed in a new isolated Kind cluster inside the retained VM. Eight unit tests pass. PostgreSQL 16-to-18 migration, full OPS application regression tests, ARM64 execution and performance benchmarks remain pending. The host K3s database and original Kind cluster remain unchanged. The VM runtime inotify limit was raised from 128 to 1024 to support the additional cluster. See `oplugins-op/POSTGRES_ADVANCED.md` for build instructions and exact validation limits.

The Helm work in Apache task PR #235 remains a separate change and is not implicitly included in this baseline.

## References

- https://www.postgresql.org/support/versioning/
- https://www.postgresql.org/docs/18/upgrading.html
- https://github.com/pgvector/pgvector
- https://github.com/reactive-tech/kubegres/tree/v1.19
- https://github.com/docker-library/docs/blob/master/postgres/README.md

## RC7 alignment (2026-10-01)

Merged upstream `v0.9.0-incubating-RC7` and its exact submodule commits into the personal Advanced branches. PostgreSQL 18 and the personal development image references are retained. Updated operator images must be rebuilt before Advanced deployment. Upstream workflows remain archived and inactive. See `advanced/rc7-alignment.json`.

The previous validation VM has been removed outside this task; previous test results remain historical evidence, not validation of this merge. A new K3s-only VM is prepared for a pristine RC7 full installation before Advanced regression testing. OPS installation is intentionally deferred to the guided session.
