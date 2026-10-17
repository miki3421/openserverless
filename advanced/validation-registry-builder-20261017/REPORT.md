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

# K3s private registry and automatic builder validation

Validated on 17 October 2026 in the `ops-advanced-security-lab` single-node
K3s VM. Alpha and Beta application sources were not changed.

## Sources under test

- Tasks: `miki3421/openserverless-task-custom:advanced`, commit `ce718f3`.
- Admin API: `miki3421/openserverless-admin-api:advanced`, commit `e96f790`.
- The Admin API was built locally as
  `localhost/ops-advanced-admin-api:registry-builder-20261017`, image ID and OCI
  manifest `sha256:ba9c87826567d1c51789138e7163d2b5510b5549279cbe23c60658ef7ce23f43`.
  It was imported into the lab K3s containerd store and was not published.

## Results

- The new `ops cloud k3s registry` command recognized the existing exact mirror
  as configured and made no change or restart. Unit coverage also exercises a
  fresh install, repeated execution, custom-file refusal, concurrent-change
  refusal, invalid SSH targets and remote failures.
- The mirror is scoped only to `openserverless-registry-svc:5000` and points to
  `http://127.0.0.1:32000`. It contains no credentials and no Docker Hub or
  wildcard entry.
- A private image with `registry-pull-secret` pulled successfully. The same
  image without a pull secret reached `ErrImagePull`. A forced public pull of
  `docker.io/library/busybox:1.36` completed successfully.
- A fresh Beta Node.js runtime build completed, was monitored, deployed and
  invoked with `is-number` 7.0.0.
- A fresh Beta Python runtime build completed, was monitored, deployed and
  invoked with `humanize` 4.13.0 and `Faker` 30.8.2.
- Both successful build Jobs have the tenant-owner label, resulting-image
  annotation, `hostUsers: false` and
  `automountServiceAccountToken: false` expected by the Advanced builder.
- The selected Alpha/Beta source-file hashes were identical before and after
  the builder test.
- Fresh Alpha and Beta live exercises passed PostgreSQL, MongoDB, Redis, S3 and
  Milvus for three synthetic documents per tenant.
- Local regression checks passed: 22 Bun tests with 61 assertions, YAML parsing,
  whitespace validation and 9 Admin API builder security unit tests in the
  locally built image.

## Image consistency finding

The Admin API image previously running in the lab exposed the status endpoint
but created build Jobs without the owner label, image annotation, private user
namespace or explicit BuildKit state volume. Monitoring returned 404 and the
old worker then failed to mount `/proc`. Rebuilding the image from the current
`advanced` commit restored the expected manifest and both builds passed. This
confirms that the task and Admin API source commits must be deployed together;
the older mutable lab image is not a valid representation of the branch.

The builder continues to use the operator-managed `registry-pull-secret`. The
additional `registry-pull-secret-int` has the same internal registry host in
this installation, but changing the builder secret was unnecessary.
