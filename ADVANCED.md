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

### Publication rule

All OPS Advanced changes belong to the personal `miki3421` repositories and branches. Do not push commits, branches, tags, releases, or other changes to Apache repositories, and do not open or update PRs targeting Apache, without the user's explicit authorization for that specific publication action. Approval to implement a change does not itself authorize publishing it. Read-only fetches and inspection of Apache repositories are allowed. Never push to repositories whose names start with `olaris`, and do not delete existing branches or remote refs without explicit authorization. This rule covers core OPS, CLI, tasks, operators, admin API, runtimes, and related repositories.

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

## Pending complete review: installation and automatic builds

Added to the review scope on 2026-10-01. These checks are pending, not validated by the K3s laboratory results.

Implementation sources to inspect and pin to exact branches/commits:
- https://github.com/miki3421/openserverless-task-custom
- https://github.com/miki3421/openserverless-admin-api

Review `ops cloud k3s install`: version selection, installation options, containerd registry configuration, repeat execution, upgrade behavior and isolation from existing workloads.

Review the automatic image build performed by `ops ide deploy` across the task and admin-api forks:
- Trace the annotations written and consumed by both components, including missing values, defaults, precedence and backward compatibility.
- Verify compatibility with the Docker + Kind production topology as a separate test matrix from native K3s + containerd. Production compatibility is a requirement, not authorization to mutate production.
- Verify private registry endpoint resolution from the builder and runtime, authentication, TLS/trust configuration, push/pull permissions and credential handling without secret disclosure.
- Verify generated image names, tags and destinations stay within the intended private registry. Assert no unintended push, overwrite, retagging or deletion of public images, and no regression in public-image pulls or deployments that do not need a build.
- Exercise build failure, authentication failure, retries and repeated deployments; ensure failed builds do not replace a working deployment.
- Record exact source commits, image digests, topology and evidence before marking any check passed.

Repository boundary: do not push to any `olaris*` repository. Keep changes in authorized personal forks; no remote publication is implied by this review entry.

Also track safe uninstall ordering: delete managed WhiskUser/Whisk resources while their operator is still running, wait for finalizer completion, then remove the operator and namespace. The RC7 laboratory required targeted removal of two orphaned Kopf finalizers after direct namespace deletion. Do not make blanket finalizer removal the normal uninstall behavior.

## Prova di OPS RC7 su un altro server K3s (2026-10-06)

I seguenti rami sono pubblicati sui fork personali:

- Task: `miki3421/openserverless-task-custom:fix/setup-cluster-readiness`, commit `597006e9e2c3acf63a656e28c0afbd73f6fafea3`, basato sul commit dei task `7981be97` della snapshot OPS 0.9.0.
- Operatore RC7: `miki3421/openserverless-operator:fix/alertmanager-no-destinations-rc7`, commit `acd8999` (fix al commit `39f7499`), basato sul commit operatore RC7 `5d509e30`. Include solo la correzione di Alert Manager e mantiene la versione PostgreSQL prevista da RC7.
- Anche il ramo operatore `advanced` contiene la fix, insieme al lavoro su PostgreSQL 18. **Per questa prova isolata di RC7 usa il ramo qui sopra**, non `advanced`.

L’immagine non è stata pubblicata su alcun registry. Il workflow ereditato per l’immagine è partito perché il filtro `branches-ignore: '*'` non escludeva un ramo il cui nome contiene `/`. L’ho annullato durante la creazione di Kind, prima della build, del login al registry e del push. Ho archiviato i workflow ereditati nel ramo di test. Costruisci l’immagine sul server di prova e importala nel containerd di K3s.

### 1. Seleziona i task corretti

Sul server deve essere installata la CLI OPS 0.9.0. Prima di aggiornarne i task:

```sh
export OPS_REPO=https://github.com/miki3421/openserverless-task-custom
export OPS_BRANCH=fix/setup-cluster-readiness
ops -update
ops -info
```

Nell’output di `ops -info`, verifica che `OPS_TASKS` sia:

```text
597006e9e2c3acf63a656e28c0afbd73f6fafea3
```

Questo ramo attende la creazione dell’Ingress API, evita di cercare i pod SeaweedFS o Milvus quando i relativi servizi sono disabilitati, gestisce le credenziali del registry privato come opzionali, applica le dipendenze tra componenti, aggiunge `ops config full` e interrompe il setup se mancano SeaweedFS o il frontend statico.

### 2. Costruisci e importa localmente l’immagine dell’operatore RC7

Assicurati che Docker e K3s siano installati sul server. Clona il ramo RC7 dell’operatore e costruisci l’immagine:

```sh
git clone --branch fix/alertmanager-no-destinations-rc7 \
  https://github.com/miki3421/openserverless-operator.git ops-operator-rc7
cd ops-operator-rc7

docker build \
  --build-arg OPERATOR_IMAGE_DEFAULT=docker.io/miki3421/ops-advanced-operator \
  --build-arg OPERATOR_TAG_DEFAULT=rc7-full-fix-39f7499 \
  -t docker.io/miki3421/ops-advanced-operator:rc7-full-fix-39f7499 \
  .
```

Importala nel containerd usato da K3s:

```sh
docker save docker.io/miki3421/ops-advanced-operator:rc7-full-fix-39f7499 | \
  sudo k3s ctr images import -
```

Poi indica a OPS di usare il tag caricato localmente. Il comando aggiorna solo il catalogo task locale sotto `OPS_ROOT`:

```sh
OPS_ROOT="${OPS_ROOT:-$HOME/.ops/0.9.0/oplugins}"
jq '.config.images.operator = "docker.io/miki3421/ops-advanced-operator:rc7-full-fix-39f7499"' \
  "$OPS_ROOT/opsroot.json" > "$OPS_ROOT/opsroot.json.tmp"
mv "$OPS_ROOT/opsroot.json.tmp" "$OPS_ROOT/opsroot.json"
```

La policy `IfNotPresent` consente a K3s di usare l’immagine importata. Questa procedura non fa login né push verso Docker Hub, GHCR o altri registry e non cambia immagini pubbliche.

### 3. Configura il profilo completo ed esegui il setup

```sh
ops config disable --all
ops config full
ops config status
ops setup cluster
```

`ops config full` abilita il profilo completo, compresi SeaweedFS, frontend statico, PostgreSQL RC7, Milvus, etcd, monitoraggio e registry. Lascia disabilitate le notifiche Slack/mail, affinity e tolerations. Se vuoi le notifiche, configura prima `ops config slack` oppure `ops config mail`, poi abilita esplicitamente il canale scelto. Prima del setup verifica con `ops config status` che SeaweedFS e static siano `true` e che i canali non configurati siano disabilitati. Il cluster deve avere RAM e spazio disco sufficienti per il profilo completo.

A installazione terminata, controlla i pod con `kubectl get pods -A`: Alert Manager deve risultare pronto anche senza notifiche, etcd e Milvus devono avviarsi e il setup deve completare il caricamento del frontend. Questa procedura riguarda K3s con containerd e build Docker locale; non copre Docker + Kind. Non è stato fatto alcun push a repository `olaris*`.
