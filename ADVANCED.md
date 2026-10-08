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
export OPS_REPO="https://github.com/miki3421/openserverless-task-custom"
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

Status: the initial PostgreSQL 18 profile, replication, manual promotion and user provisioning passed in the September isolated Kind lab. The synthetic PostgreSQL 16-to-18 migration rehearsal passed on 2026-10-06. On 2026-10-08, a fresh full OPS Advanced installation on the retained K3s VM passed the integrated SQL/pgvector, application, replication and repeated-setup checks described below. The RC7 PostgreSQL 16 namespace was replaced using new volumes; the separate migration-lab namespace was retained. Migration of representative production data, ARM64 execution and node-failure recovery remain pending. See `oplugins-op/POSTGRES_ADVANCED.md` for the historical validation boundaries.

## Validazione integrata K3s di OPS Advanced (2026-10-08)

La prova usa sempre la VM `ops-advanced-rc7`: Ubuntu 24.04, amd64, 6 vCPU, 16 GiB RAM, K3s `v1.37.1+k3s1` con containerd e Traefik. La CLI resta `0.9.0-incubating+26i11g51-snapshot`; i task locali sono quelli del branch personale `advanced`, con un `OPS_HOME` dedicato. L'operatore Advanced e l'immagine PostgreSQL dumper sono stati costruiti sul Docker dell'host e importati nel containerd della VM. Le immagini non sono state pubblicate su registry.

Il namespace RC7 `openserverless` è stato sostituito con una installazione full e volumi nuovi; non è stato cambiato il tag sui dati PostgreSQL 16 esistenti. Il namespace `ops-pg-migration-lab` è stato conservato. Il setup completo termina con exit 0 e avvia PostgreSQL 18.6, pgvector 0.8.6 e due database pod, con checksum dei dati abilitati.

Risultati ed evidenze, conservati in `advanced/validation-20261008/`:

- 22 test Bun del setup/configurazione/ingress e 8 test Python PostgreSQL passati. Gli 8 test Python passano anche dentro l'immagine costruita.
- 11/12 test della suite applicativa ereditata passati: PostgreSQL, FerretDB, Redis, SeaweedFS, utenti/login, runtime JavaScript/Python e SSO HTTP mock. Il provisioning cloud e TLS sono esclusi dalla prova su questo K3s HTTP già predisposto.
- Due utenti non-superuser hanno scritto 1.000 record JSONB/vector ciascuno, usato HNSW e ottenuto gli stessi cinque risultati della ricerca esatta sul dataset sintetico. Connessioni al database dell'altro utente e password errate sono state rifiutate. La recall sul piccolo dataset non certifica la qualità di ricerca su dati reali.
- Conteggi e checksum sono identici su primario e replica prima e dopo il riavvio del pod primario. I due pod tornano Ready in 14,32 secondi, conservando le identità PVC/PV. Questa prova non simula la perdita del nodo.
- Il setup ripetuto termina con exit 0 e conserva dati, identità dei PVC e la specifica dell'utente `devel`.
- Un file caricato nel bucket statico viene recuperato byte per byte tramite il dominio utente. Dieci richieste alla root restituiscono il file HTML dell'operatore, con hash invariato. Cinque prove verificano streaming reale su percorsi tenant, percorsi diretti e dominio dedicato, incluse azioni autenticate. La prova SSO HTTP è stata ripetuta dopo le correzioni.

Correzioni locali necessarie per rendere riproducibile la prova:

- Allineati su `advanced` i fix già collaudati del setup: attesa dell'Ingress, credenziali opzionali del registry, dipendenze tra componenti e profilo `full`.
- Corretti i permessi del Dockerfile: directory padre create dall'utente runtime e UID/GID numerici nello stage dipendenze, che non definisce l'utente `openserverless`.
- Eliminata la collisione tra ingress statico e streamer sulla root `/` del dominio tenant. Lo streamer conserva `/web`, `/action`, `/stream/web`, `/stream/action` e il dominio dedicato; la root resta al frontend. Entrambi i template Nginx/Traefik sono verificati con e senza TLS, ma la prova live usa solo Traefik.
- Il setup crea `devel` solo quando manca. Un utente esistente deve diventare Ready; errori API o una cancellazione in corso non provocano una ricreazione. Il comando autonomo `add-user` mantiene il suo comportamento di creazione esplicita.

`7-static.sh` resta FAIL: richiede una vecchia frase non presente nel file HTML distribuito dall'operatore. Inoltre il controllo aggiuntivo ha rivelato la collisione ingress descritta sopra, ora corretta. Il test ereditato non è stato modificato per nascondere il fallimento; la verifica di upload/lettura HTTP e quella del file HTML sono registrate separatamente.

Durante la rimozione del vecchio namespace, il vecchio operatore RC7 ha fallito nel gestore SeaweedFS con `TypeError: can only concatenate str (not "NoneType") to str`. Dopo aver eliminato gli utenti, è stato rimosso il solo finalizer Kopf del Whisk in cancellazione, esclusivamente nel lab. Il difetto del teardown SeaweedFS resta da correggere; questa procedura manuale non diventa una strategia di uninstall generale.

### Primo confronto prestazionale PostgreSQL 16/18

Benchmark nei due database standalone del namespace separato, con il resto di OPS attivo e senza test applicativi concorrenti: stesso client pgbench 18, 2 milioni di account (`scale=20`), 4 connessioni, 2 thread, 20 secondi di warmup e tre esecuzioni di 40 secondi per versione, in ordine alternato. Entrambi i server hanno limite 1 CPU/1 GiB RAM e storage local-path sulla stessa VM. Tutte le sei esecuzioni terminano senza transazioni fallite.

| Mediana per esecuzione | PostgreSQL 16.15 | PostgreSQL 18.6 |
|---|---:|---:|
| Transazioni/s | 837,83 | 830,83 |
| Latenza p95, ms | 8,210 | 8,371 |
| CPU server, secondi consumati | 10,23 | 9,77 |
| Massimo RAM campionato, MiB | 907,89 | 895,21 |
| Letture fisiche, MiB | 0,00 | 0,31 |
| Scritture fisiche, MiB | 297,12 | 327,35 |

In questo carico PostgreSQL 18 ha throughput inferiore di circa 0,84% e p95 superiore di circa 1,96%; le variazioni tra le esecuzioni sono maggiori delle differenze tra le mediane. Non è dimostrato un vantaggio prestazionale. Il confronto usa i profili effettivi: checksum off su 16/on su 18, `effective_io_concurrency=1/16`; non isola causalmente il solo numero di versione. È una misura breve con cache calda su VM condivisa. RAM è campionata ogni cinque secondi; I/O è misurato dai contatori del cgroup e risente dei checkpoint. Non misura capacità di produzione, traffico OPS end-to-end, prestazioni ANN o comportamento su dati più grandi della RAM.

Gli script della prova sono in `advanced/lab/` e contengono vincoli al lab dedicato. Rimangono aperti: test ARM64, Nginx/Kind live, TLS live, recupero su perdita del nodo, migrazione applicativa con cutover e carichi rappresentativi dei progetti. Il lavoro sul backup del cluster resta accantonato.

## PostgreSQL 16-to-18 migration rehearsal (2026-10-06)

The rehearsal ran in the K3s VM `ops-advanced-rc7` (K3s `v1.37.1+k3s1`) while the OPS RC7 installation remained active. The existing OPS PostgreSQL 16 StatefulSets, services and 50 GiB PVCs were left untouched. All migration resources and synthetic data live in the separate `ops-pg-migration-lab` namespace.

The source image was the same `pgvector/pgvector:pg16` image used by the RC7 database: PostgreSQL `16.15`, pgvector `0.8.7`. The target used the pinned Advanced image `pgvector/pgvector:0.8.6-pg18-bookworm@sha256:2ba9ca5f2e7daa0f0e7723cba1ee9167bab54efd3640516a44ac1a928dd67e7a`: PostgreSQL `18.6`, pgvector `0.8.6`, with `PGDATA=/var/lib/postgresql/pgdata` on a volume mounted at `/var/lib/postgresql`.

The synthetic application database contained a role, JSONB rows, 1,000 vector rows and an HNSW index. Both the per-database `pg_dump`/`pg_restore` path and a full-cluster `pg_dumpall` restore passed when the target was initialized with a distinct bootstrap superuser. The restored database retained its application owner and SELECT grant; all 1,000 rows matched the source checksum (`d788fe94a3def182125b8e9b8c3996b9`); sample JSON values, vector nearest-neighbor results and HNSW index plans matched. This exercises pgvector data written by 0.8.7 and read by 0.8.6 for this test dataset; it does not establish general compatibility for every workload.

A direct `pg_dumpall` restore into a target initialized with the default `postgres` superuser stopped because the dump also creates the source `postgres` role. The tested full-cluster path therefore uses a separate bootstrap administrator that is not part of the source dump. Migration instructions must explicitly cover bootstrap credentials, role ownership, ACLs and restore validation; a naive `pg_dumpall | psql` into a default-initialized cluster is not sufficient.

This rehearsal used synthetic data only. It did not migrate or modify the OPS RC7 data, test a cutover or rollback under application traffic, measure downtime or large-database restore performance, or run the full OPS application regression suite. The isolated namespace is being retained for follow-up tests in the VM.

## Cluster-wide backup task (lab verification 2026-10-06)

The task fork has `ops backup cluster plan` and an offline archive workflow for a single-node K3s SQLite cluster: `create`, `verify`, `delete`, and `restore`. The archive contains K3s SQLite state, server token/configuration, the K3s binary/systemd unit and local-path PVs. It intentionally excludes containerd's image/runtime cache. Before snapshotting, it suspends CronJobs and gracefully scales workload controllers down, then restarts K3s and restores their original replica counts and CronJob schedules. It verifies SHA-256 checksums and requires explicit confirmation for cluster deletion and restoration. It refuses multi-node/etcd setups and PV data outside `/var/lib/rancher/k3s`.

The end-to-end rehearsal ran on the same VM `ops-advanced-rc7` (K3s `v1.37.1+k3s1`) hosting the OPS RC7 installation and PostgreSQL migration lab. Synthetic markers were written to all 25 bound local-path PVs and a ConfigMap recorded the tested component families. The archive was created at `/home/ubuntu/ops-cluster-backups/k3s-2026-10-06T14-12-44.241Z`, outside K3s state but on the same VM. Checksums passed before and after cluster deletion; K3s was removed and restored; the node, all StatefulSets and Deployments, the 25 PVs, the OPS components, and the three PostgreSQL migration-lab pods returned Ready. The marker verification passed after restore for the ConfigMap and all 25 PVs. These are filesystem/Kubernetes markers, not application-native database records.

The first restore attempt exposed a documented limitation of excluding containerd images: the private `miki3421/ops-advanced-operator:rc7-full-fix-39f7499` image could not be pulled from Docker Hub. It was available in a local image archive on this same VM and importing it with `sudo k3s ctr -n k8s.io images import /tmp/ops-advanced-operator-rc7-full-fix-39f7499.tar.gz` allowed the restore to complete. For future restores, private images must be available from an authenticated registry or imported from a separate image bundle; the K3s data archive does not include them. This same-VM destination survives K3s uninstall but is not an off-host disaster-recovery copy if the VM or disk is lost. The task does not provide application-level consistency for external volumes or replace database-native backup policies.

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
