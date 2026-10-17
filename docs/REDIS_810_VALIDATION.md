# Redis 8.10.2 — local Advanced validation

Date: 2026-10-17. Single agent. The validated source and task-catalog changes are
published only on the personal `advanced` branches. No Apache repository or pull
request is involved. The tested operator image remains installed in the lab and
is not anonymously pullable.
The later Lua application extension is published separately in the private app repository.

## Installed configuration and scope

The Advanced K3s lab (`ops-advanced-security-lab`, guest `ops-advanced-lab`) runs
the official Redis 8.10.2 image, the security patch selected from the 8.10 series:

`docker.io/library/redis:8.10.2@sha256:2c2dff791878316e3b083188be0d578423b24813cdda5de0e80ea4f7b3e6bfd6`.

The operator image built and imported locally is
`docker.io/miki3421/ops-advanced-operator:redis-810-20261017-r6`.
No Redis server binary patch or new Python driver dependency was needed.
The installed changed modules and templates match the local source hashes.
The personal task catalog selects these tested images; a fresh server requires
authorized access to the operator image or a reproducible rebuild from the
published personal source branch.

Alpha and Beta source, action parameters and frontends were unchanged during the
initial Redis upgrade validation. The later user-authorized Lua extension is
documented below. Their original Redis credentials and prefixes are retained. The comparative baseline's versions and configuration are unchanged.

References: [8.10.2 release](https://github.com/redis/redis/releases/tag/8.10.2),
[official image](https://hub.docker.com/_/redis/),
[ACL model](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/),
[persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

## Fresh installation, not migration

The previous Bitnami Legacy 8.2.1 StatefulSet was stopped after the isolated
candidate passed its initial checks. Private resource snapshots were preserved.
The old `redis-pvc-redis-0` remains Bound and unmounted. Its data directory was
never opened by the native image or modified to change ownership.

The new claim template is `redis-data-v810`, mounted at `/data`, with a fresh
canonical PVC `redis-data-v810-redis-0`. New synthetic application fixtures were
created through the unchanged apps. Existing Redis engine images, volume
identities, persistence mode and administrator credentials cannot be replaced
implicitly: guards run before credential or account mutation. Native orphan PVCs
are rejected as well. Migration/upgrade orchestration remains deferred.

The `redis` Service preserves its UID and ClusterIP. It is now ClusterIP only;
the old NodePort 30379 is removed. The existing username/password Redis URLs and
port 6379 continue to work. Internal Redis transport remains TCP without TLS;
this change does not introduce encrypted Redis client connections.

## Native deployment and durable identities

The server runs as UID/GID 999, without a service-account token, with dropped
capabilities and a read-only container root filesystem. Only `/data` and `/tmp`
are writable. Startup/readiness/liveness use an authenticated `redis-cli -e`
PING, so missing credentials, server loading and authentication errors do not
produce a healthy result.

A dedicated `ops-admin` identity is used by trusted OPS administration and quota
checks. The default user is disabled. Bootstrap material lives in a Secret;
ordinary Redis configuration contains no administrator password. The persistent
ACL file stores SHA-256 password hashes. It is copied only for a fresh volume;
subsequent starts preserve it, and a missing ACL on an initialized volume fails
closed. Reconciliation never overwrites it with the bootstrap-only users.

With persistence enabled, Redis uses multi-part AOF with `appendfsync everysec`,
plus the existing RDB save schedule. The full lab has AOF enabled. With data
persistence disabled, AOF/RDB are disabled but the identity volume is retained to
keep ACLs durable. AOF/RDB mode changes on an active installation require explicit
review rather than silent data reuse. Every-second AOF is not a zero-loss promise
for arbitrary power failure; the forced-restart test used a confirmed WAITAOF
barrier for its durable marker.

## Tenant permissions

The old shell-driven `+@all` grant is replaced by structured Redis commands using
the existing Python client. Passwords are supplied as hashes when setting ACLs;
there is no tenant input interpolation into shell/redis-cli scripts.

- Data reads/writes and transactions are restricted to the tenant's literal
  prefix. Prefix globs, reserved identities and overlapping/nested prefixes are
  refused. ACL administration is serialized to prevent concurrent ownership of
  the same keyspace.
- Pub/Sub channels use the same prefix; peer publication/subscription and global
  channel enumeration are denied.
- Configuration, ACL management, replication, global flushes, migration, server
  saves, monitoring, global script/function management, global key discovery and
  database switching are denied to tenant users. EVAL/EVALSHA, their RO variants
  and SCRIPT LOAD/EXISTS are explicitly allowed with the caller's key/command ACLs. This is a stricter command contract than
  the previous `+@all`; applications needing those operations require a separate
  design. Standard database-zero data commands used by Alpha/Beta are preserved.
- Quota read-only mode preserves reads and scoped DEL/UNLINK for cleanup. Restoring
  writes restores the data policy, not `+@all`. Mode changes and user deletion are
  saved with ACL SAVE and survive restart. Password rotation closes old sessions.
- Deleting a Redis identity retains its keys, matching the previous deletion
  contract. A new identity cannot implicitly inherit that orphaned prefix:
  recreation fails until trusted administration explicitly cleans or recovers
  its data. The live test checks both refusal and recreation after cleanup.

New profiles identify the provider as `redis`. Both `REDIS_URL` and `REDIS_ALT_URL`
contain the username and an encoded password. Password-only default-user access
is intentionally unsupported. Existing Alpha/Beta deployed bindings were not
rewritten to obtain a passing result.

## Quota integration

The quota client measures scoped usage through administrator SCAN/MEMORY USAGE
rather than uploading shell/Lua files to the server container. Read-only and write
restoration use the same durable ACL policy as provisioning. The Redis quota
conversion is corrected from `1014 * 1024` to `1024 * 1024` bytes per MiB, and a
missing measurement fails without changing permissions or annotations.

A one-off job created from the actual `quota-checker` CronJob completed using the
new operator image. Finite quota transitions were exercised through the live OPS
quota client, and the exact MiB threshold was checked by unit tests. These are
periodic software quotas: tenants still share one Redis process, CPU and global
memory/eviction policy. This is not hard per-tenant resource reservation.

An existing unrelated PostgreSQL quota conversion in `check_pg_quota` still uses
`1014 * 1024`; it was not changed as part of this Redis work.

## Initial validation evidence before the Lua application extension

- 66 Python unit tests passed: 19 Redis tests and 47 existing etcd/Milvus/S3 tests.
- 69 live checks passed on both the isolated candidate and the installed service:
  authentication, own data/transactions/TTL, denied peer operations, restricted
  administrative/global commands, Pub/Sub, quota transitions, password/session
  revocation, deleted users, orphan data reuse, concurrent prefix ownership and
  Alpha/Beta's frozen bindings.
- The queued-transaction test revokes key access after MULTI and confirms EXEC
  returns a permission error, covering the relevant 8.10.2 ACL regression.
- The isolated candidate preserved data, read-only ACLs and revoked identities
  across a normal restart and a direct SIGKILL (recorded exit 137), without
  reprovisioning. RDB save, AOF rewrite and the durability barrier succeeded.
- After restarting the installed Redis pod, both applications inspected their
  previously written fixtures: PostgreSQL, MongoDB, Redis, S3 and Milvus all
  returned PASS with the expected three records and content digests.
- The administrator password was absent from the native server logs, ordinary
  ConfigMap and ACL file. Raw recovery manifests and secret-bearing output remain
  private. The old volume remains preserved and unmounted.

Application suite and timing results are recorded below. These scoped regression
checks are not an independent security certification; the runner's separate
unverified cluster gates remain unchanged.

## Initial unchanged Alpha/Beta application regression

The complete application suite passed 15/15 checks in both post-install runs,
including the repeat after restarting the installed Redis pod. Each run used
100 requests per tenant at concurrency four, with zero errors. Source and deployed
validation-action fingerprints (code, parameters, limits and annotations) match
before/after. No frontend or application deployment was needed.

End-to-end timings in milliseconds:

| Run | Alpha p50 / p95 | Beta p50 / p95 | Errors |
| --- | --- | --- | --- |
| Before, Bitnami Legacy 8.2.1 | 295.1 / 372.7 | 274.5 / 357.1 | 0 |
| After, native 8.10.2 | 265.3 / 350.6 | 276.6 / 340.0 | 0 |
| After installed Redis restart | 270.7 / 354.2 | 281.4 / 359.9 | 0 |

These are regression observations on a shared lab host with fresh Redis data,
not a Redis-specific performance comparison. Startup/cache state and other cluster
activity vary; first-observed requests are not verified cold-start measurements.

## Local evidence

Host: `/root/ops-update-sso/ops-advanced/redis-810-20261017/`.
VM: `/home/ubuntu/redis-810-20261017/`.
Private recovery manifests: `preserved-before-fresh/` in the VM evidence directory.

The isolated candidate is stopped with its volumes retained. The Advanced
installation remains running. Baseline component versions/configuration remain unchanged.
Alpha/Beta were extended afterwards as explicitly requested, described below.

## Lua application extension and current policy — 2026-10-17

The user explicitly authorized extending both applications with Lua checks.
The initial blanket scripting denial was too restrictive for existing clients.
The r6 operator permits EVAL/EVALSHA, EVAL_RO/EVALSHA_RO and only SCRIPT
LOAD/EXISTS. It does not grant the whole scripting category. SCRIPT FLUSH/KILL/DEBUG
and global Functions remain denied, as do all existing admin/global restrictions.
Read-only quota mode permits scripts but their underlying write commands remain
forbidden; reads and scoped cleanup continue to work. Both ACL modes persist.

The same protected validation/redislua Python source is deployed to all four
Alpha/Beta endpoints across the baseline and Advanced K3s VMs. Advanced passes
84/84 Lua checks, 16/16 quota-policy checks, 40 exact-allowlist administrator
DRYRUN checks and 23 endpoint/auth/source/frontend checks. After Redis pod restart,
Lua remains 84/84 and existing five-service fixtures are retained.

The unchanged baseline Redis 8.2.1 passes its owner functionality and measured
peer-key isolation checks, but the full Lua suite reports 76 PASS / 8 FAIL:
ACL USERS, SCAN, Lua SCAN and FUNCTION LIST are allowed for each tenant. The
quota policy reports 10 PASS / 6 FAIL because EVAL, EVAL_RO and SCRIPT LOAD are
denied even for legitimate read usage. No baseline fix was applied and both
original tenant ACLs were snapshotted privately and restored exactly.

Existing five-service application regression passes 15/15 on both clusters with
20 load samples per tenant and no errors; these are smoke checks, not a controlled
benchmark. Local verification passes 84 app unit tests, 56 focused operator tests
and frontend/spec/privacy checks. Global discovery responses and raw snapshots
are never included in the app reports. No destructive global command is run.

Evidence: ../redis-lua-20261017 on the host and /home/ubuntu/redis-lua-20261017
in each VM. Sanitized app guide/result: docs/redis-lua.md and
docs/redis-lua-validation.json in miki3421/ops-validation-app. Only the app
repository publication is authorized. The OPS Redis source is published only on
the personal `advanced` branches; the r6 image remains in the lab and is not
anonymously pullable. No shared-instance resource-isolation guarantee is claimed.

## Focused independent review

Codex Security completed a focused Daybreak Blue diff review of the Redis patch
as scan `21d8c4c8-6b73-45c7-95aa-03cb296b4e69`. It covered all nine changed
runtime files plus the build and test artifacts and reported no finding across
tenant ACL isolation, Lua command containment, quota transitions, credential
handling, persistent lifecycle, and pod/service hardening.

The review reran 20/20 current Redis unit tests inside the deployed r6 operator
and 40/40 live ACL/Lua allowlist checks. The earlier 84/84 Lua/isolation result
and 15/15 Alpha/Beta suites remain evidence from the identical deployed r6 image.
NetworkPolicy and Kubernetes RBAC are explicitly outside this Redis-scoped review.

## Subsequent 0.9.0 tenant-ACL backport

The user authorized applying the Redis security fix to the comparative baseline.
The earlier baseline failures above remain pre-fix evidence. Baseline Redis stays
at 8.2.1 and Advanced at 8.10.2. Both consume the same tenant command/key/channel
policy, including removal of secondary ACL selectors, while retaining Lua.
The internal administrative account remains separate from the tenant path.

The legacy backport preserves the 0.9.0 additive-password reconciliation contract:
existing valid password hashes are retained when grants are replaced. A real
Alpha profile/WhiskUser credential mismatch exposed this compatibility requirement
in the lab; no app code or deployed parameters were changed to hide it. Native
Advanced retains its existing explicit password/session-revocation behavior.

Legacy ACL-file persistence is not introduced by this patch. If an ACL file is
configured, changes are saved; otherwise the original in-memory ACL contract and
operator reconciliation remain. Database storage/image migrations are out of scope.
The baseline operator and quota job use the local redis-acl-090-20261017-r3 image;
Advanced uses local redis-810-20261017-r6. No images are published.

Focused validation: 12 backport unit tests, 67 Advanced operator regression tests,
46 baseline / 41 Advanced lifecycle checks, 84/84 Alpha/Beta Lua checks and 16/16
quota-policy checks on both clusters. Existing five-service suites pass 15/15
with zero errors in the short load run; endpoint/auth/source checks pass 23/23 per
cluster. Both one-off quota jobs complete. Credential recovery snapshots remain
private, and the original tenant data and app source are retained. These are
scoped author-run regression checks, not a new independent security review.

Redis restart validation exposed a pre-existing baseline availability limitation:
its Redis configuration has no ACL file, and Alpha/Beta identities were absent
after the restart. The lab was recovered from the private post-fix credential
snapshot, installing only the restricted tenant policy; broad legacy grants were
not restored. After recovery, Lua passes 84/84 and all five-service fixtures for
both tenants remain readable. Advanced restores its ACLs automatically and passes
the corresponding restart checks. Automatic legacy ACL recovery is still open;
this patch does not claim to resolve it or migrate Redis storage.
