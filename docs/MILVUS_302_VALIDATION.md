# Milvus 3.0.2: local Advanced lab validation

Date: 2026-10-16. Single agent. Validation completed locally before source publication.

## Result and scope

The shared Advanced lab (`ops-advanced-security-lab`, guest `ops-advanced-lab`)
now runs Milvus 3.0.2 standalone. Alpha and Beta source and deployed validation
action fingerprints are unchanged. The comparative baseline's component versions
and configuration are unchanged; its direct comparison only created and dropped
temporary synthetic collections.

This is a fresh Milvus installation, not a migration of the 2.5.2 dataset.
The old PV, etcd metadata and S3 prefix are preserved. New synthetic application
fixtures were created through the existing, unmodified applications.

Milvus lab image:
`docker.io/miki3421/ops-advanced-milvus:3.0.2-zero-grace-20261016@sha256:2d0aeb4c19a657369636a1592d56ccac164a718a3f447ee7683ce53769153c37`.
This is an Advanced derivative, not stock upstream 3.0.2. It replaces the Go
server binary to route zero-grace Bounded reads through the existing Strong
execution path. Native libraries and storage formats remain those of the pinned
upstream image
`docker.io/milvusdb/milvus:v3.0.2@sha256:5f13bf88e110a517911c3e6dd8172454e90042c21e606a868084615a4302c8a0`.
The patch, pinned build recipe and focused Go tests are in the operator's
`images/milvus/` directory.
The complete recipe was built successfully, including its test stage. Its server
binary SHA-256 is
`e3c84312ca0a583342737b081a184dc17fdc1f1490bbca0c1a879582de9670e0`,
identical to the installed candidate. The rebuilt image has a different image
digest because the recipe adds version metadata; it was not published or swapped
into the cluster merely for that metadata change.

Operator image: `docker.io/miki3421/ops-advanced-operator:milvus-ready-20261016-r4`.
It was built on the host and imported into K3s; it has not been published.
Installed module/template hashes were checked against the local sources.

## Pulsar dependency

The previous full configuration declared `mq` twice; the effective value was
`rocksmq`. All five Milvus-specific Pulsar StatefulSets were scaled to zero.
Milvus 2.5.2 was then restarted and both application suites passed all 15 checks.
This verifies that Pulsar was unnecessary for this installed configuration.

Their measured combined working set before stopping was 5,938 MiB (5.80 GiB).
This is the removed Pulsar footprint, not a claim about total cluster savings
or a benchmark of the new Milvus process. The stopped StatefulSets and their
volumes remain available for recovery; new full/slim manifests omit Pulsar.
The OpenWhisk Kafka/ZooKeeper deployment is unchanged.

## Selected configuration

- Embedded Woodpecker with local WAL at `/var/lib/milvus/woodpecker`, on the PVC.
- SeaweedFS 4.48 remains the vector segment/object storage backend.
- Separate etcd and S3 prefixes: `milvus-v3`.
- Authentication and database-scoped tenant roles remain enabled.
- `common.gracefulTime: 0` removes the bounded-staleness grace window for reads.
- `proxy.timeTickInterval: 10` publishes visibility frequently. The local WAL
  sync maximum interval is `1ms`; sync/durable acknowledgement are not disabled.
- Service type ClusterIP; the previous Milvus and metrics NodePorts are removed.
- No Kubernetes service-account token is mounted into the Milvus container.
- The operator refuses implicit image, WAL, metadata prefix or PVC changes, and
  refuses orphaned configuration/PVC reuse before changing technical accounts.
- A resource allowlist excludes stale Pulsar files on the operator's deploy PVC.

Woodpecker object-storage mode was also tried. With the default consistency
settings, fresh-write probes returned empty immediate reads in two of six cases,
despite successful REST status/code responses. Initial Alpha/Beta suites also
failed in this mode. These results are retained; they are not counted as passes.
Local WAL plus the zero grace window passed the selected compatibility tests.
See [Woodpecker deployment modes](https://milvus.io/docs/woodpecker.md) and
[Milvus consistency](https://milvus.io/docs/consistency.md).

## Validation results

| Check | Result |
|---|---|
| Alpha/Beta before changes | 15/15 |
| Milvus 2.5.2 restarted with Pulsar stopped | 15/15 |
| Fresh 3.0.2 local-WAL candidate | 15/15 |
| Shared 3.0.2, provisioned through OPS functions | 15/15 |
| Shared 3.0.2 after restart and recovery | 15/15 |
| Direct tenant isolation and Milvus lifecycle checks | 23/23 |
| Direct S3 access/lifecycle regressions | 12/12 |
| Operator tests: Milvus / SeaweedFS shell / S3 access | 11 + 11 + 7 passed |

Shared/final application runs used 30 requests per tenant at concurrency four,
plus the concurrent two-tenant scenario, with zero load errors. Existing shared
fixtures were inspected after restart without re-insertion; all five component
counts and digests matched their pre-restart values after recovery.

Direct backend checks verified owner access, hidden peer collection listings,
denied reads and collection creation in the peer database, denied user
administration and anonymous access, and OPS tenant creation/profile metadata,
write/read, deletion, recreation with empty storage and credential invalidation.
Milvus returns an empty filtered collection list for an unauthorized database;
the test additionally attempts access to a collection known to exist there.

Both full and slim manifests were rendered and checked. Only the full shared
deployment was installed live in this turn. A complete cluster reinstall and an
independent security review were not performed. The application runner's other
platform acceptance gates are not certified by these component tests.

## Integration fix found during deployment

SeaweedFS 4.48 rejects creating an existing bucket. `make_bucket` now checks the
private filer first and preserves existing objects/permissions during
reconciliation. Missing buckets are created normally; unexpected probe statuses
fail before mutation. Unit and live S3 regression checks passed.

## Recovery readiness correction

The original health-only probe allowed requests before persisted collections
finished recovering. The new full/slim exec probe requires both health and the
top-level `Ready` result from
`/management/replica/loadconfig/compliance?output=summary` before first readiness.
HTTP 200 alone is insufficient: the endpoint also returns 200 for `NotReady`.

Recovery success is cached in the existing tools `emptyDir`, bound to PID 1 start
time. This matters because a container restart retains that volume. Failed
health clears the marker; a new process must pass the recovery gate again.
Once startup recovery succeeds, new DDL can load collections without removing
an otherwise healthy standalone process from its Service. A first prototype
that checked global compliance on every probe flapped during DDL and failed an
application run; that implementation was rejected.

Independent observers checked health, global compliance, Kubernetes readiness
and existing application fixtures. The first derivative rollout reached Ready
after 58.32 seconds, including replacement time; 34 samples had healthy HTTP
while recovery was incomplete. A forced restart of only the container, with
the old marker present, reached Ready after 31.01 seconds and had 25 such samples.
Alpha and Beta read their original fixture counts/digests at the first observed
Ready in both cases, without re-insertion. During the application suite there
were zero not-ready samples, including 16 samples of temporary DDL compliance
`NotReady`. These are lab observations, not recovery-time guarantees.

The probe is a startup recovery gate plus ongoing health check. It is not a
guarantee that every subsequent query or user-requested collection load succeeds.
Liveness remains a health check, avoiding restart loops during normal recovery.
A deliberately released synthetic collection stayed unloaded across replacement,
did not prevent readiness of the other collections, and returned its original
marker after an explicit reload. It was then removed by the test.

The final operator was installed and reconciled through its OPS Milvus rendering
path. Its modules and deployment/template hashes match the local sources, and
the existing image/storage compatibility guard accepted the same engine/storage.

## Latency diagnosis and correction

Two effects were separated: periodic visibility waits, and consistency semantics.
With a zero Bounded grace window, upstream 3.0.2 calculates the Strong guarantee
timestamp but skips fresh timestamp allocation and does not use the native
Strong local-WAL MVCC acceleration. The narrow server patch normalizes that
case for search/query, including collection defaults. Positive-grace Bounded,
Session, Eventually, Customized, legacy explicit timestamps and iterator
acceleration rules are unchanged. No Alpha/Beta application code was changed.

Direct tests repeatedly updated a marker, searched and queried, and checked the
latest marker rather than accepting successful status codes alone:

| Configuration | Upsert p50 | Search p50 | Query p50 | Latest-write mismatches |
|---|---:|---:|---:|---:|
| Stock 3.0.2, 20 ms tick, 1 ms sync, zero grace | 21.8 ms | 43.3 ms | 59.5 ms | 0/48 |
| Patched 3.0.2, same configuration | 21.4 ms | 10.3 ms | 2.1 ms | 0/48 |

These direct runs have 24 samples per operation and are exploratory. Full
application results include all five data components and request scheduling:

| Configuration | Samples per tenant | Alpha p50 | Beta p50 | Errors |
|---|---:|---:|---:|---:|
| Initial stock 3.0.2, 200 ms tick | 30 | 599.8 ms | 600.5 ms | 0 |
| Patched, 5 ms tick | 100 | 261.6 ms | 249.1 ms | 0 |
| Patched, 10 ms tuning run | 100 | 248.4 ms | 258.3 ms | 0 |
| Final operator, 10 ms, external readiness observer | 100 | 329.2 ms | 287.8 ms | 0 |
| Final operator, 10 ms, repeat 1 without observer | 100 | 279.9 ms | 277.8 ms | 0 |
| Final operator, 10 ms, repeat 2 without observer | 100 | 261.2 ms | 253.9 ms | 0 |

All runs used concurrency four and passed all 15 application checks. In the
10 ms tuning run, p95 was 339.6/306.3 ms and throughput 13.0 requests/s per tenant.
The final observed run had p95 507.9/375.6 ms and throughput 10.2/11.0 requests/s;
the unobserved repeats had p95 374.4/350.9 and 348.8/342.5 ms respectively.
These runs are retained rather than reporting only the fastest sample.
Concurrent two-tenant execution also passed without errors in every run.
First observed calls and tail samples include runtime/collection startup;
these are not verified cold-start benchmarks. The original and final sample
counts differ, and these results are not a universal throughput or percentile
guarantee. Total application latency still has measurable run-to-run variation;
this investigation does not attribute all request time to Milvus.

The final application run had zero not-ready samples out of 180 observations,
including 20 samples of temporary DDL compliance `NotReady`. The observer was
stopped for the following performance repeats; the timings therefore also show
the measurement conditions rather than assuming instrumentation is free.
Service/PVC UIDs and specifications were unchanged by tuning/reconciliation.
Final direct tenant lifecycle/isolation tests passed 23/23, S3 regressions 12/12,
and source/deployed-action hashes remained unchanged.

5 ms had no clear application advantage over 10 ms. Short idle measurements
were 0.366 versus 0.299 CPU cores respectively, so 10 ms was selected. CPU figures
are ten-second process-counter samples immediately after testing, not capacity
sizing recommendations.

The old 2.5.2 default Bounded configuration is not an equal-consistency baseline.
In a separate 24-cycle direct comparison it returned 46 outdated/empty latest
marker results in 48 immediate reads. Explicit Strong had zero mismatches, but
search/query p50 were 199.7/346.6 ms. Those permitted Bounded stale reads are not
reported as data loss or a security vulnerability. The faster historical
207–225 ms application run therefore does not establish parity under identical
freshness guarantees. The comparative baseline's code/configuration was not
changed by this investigation.

## Recovery state and evidence

New PV: `pvc-f7c65ec8-a8f6-49ab-b751-b4cf5d93ea40`.
Old PV: `pvc-20cbbe08-0ac2-4347-aeed-ae7abffa4f17`, Released/Retain.
The 3.0.2 process never mounted the old volume or used its metadata/S3 prefix.
Temporary candidate deployments are stopped and their PVCs are retained.

Local non-secret evidence:
`/root/ops-update-sso/ops-advanced/milvus-302-20261016/`.
Latency/readiness investigation and raw measurements:
`/root/ops-update-sso/ops-advanced/milvus-latency-readiness-20261016/`.
Original resource backups containing credentials remain private in the VM at
`/home/ubuntu/milvus-302-20261016/`; they are not included in these repositories.

Source publication is limited to the personal `miki3421` branches named
`advanced` in `openserverless-operator`, `openserverless-task-custom` and
`openserverless`. No Apache branch, PR or remote container image is published
by this source-code push. The selected Milvus/operator images currently exist
only in the local host/lab stores; another installation must build/import them
or wait for separately authorized image publication. Cloning the source alone
does not make those image references downloadable.
