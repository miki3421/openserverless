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

# OPS Advanced builder and custom runtime dependencies

This guide describes the Advanced builder, including the isolated Kubernetes build worker and Python/Node.js dependency installation validated in the K3s lab on 13 October 2026. `ops ide deploy` automatically builds and monitors Python and Node.js custom runtimes before updating dependency-bearing actions.

## Automatic deployment

Developers use two commands from the application directory:

```sh
ops ide login
ops ide deploy
```

Keep only `OPS_USER`, `OPS_APIHOST`, and `OPS_PASSWORD` in the private application
`.env`. The deployer uses the active login profile for authenticated builder API
requests. Developers do not need Kubernetes credentials.

A `requirements.txt` beside `__main__.py`, or a `package.json` with production
`dependencies` beside `index.js`, triggers a build. `--kind` selects the base from
OPS's runtime catalog. `--docker` selects an explicit **base image** when a
manifest is present; without a dependency manifest it selects an existing image.
Put each runtime directive on its own comment line.

OPS submits the dependency manifest, monitors the tenant-owned job, waits for
its image push, packages the action source, then updates the action with the
resulting image. Build failures and monitoring failures return a nonzero exit
code before updating that action. A full project deployment is sequential, not
transactional: actions already deployed before a later failure remain updated.

Successful build receipts are cached locally by API host, tenant, runtime and
manifest content. Reuse requires the authenticated API to confirm the job still
exists and succeeded. Removing the receipt directory
`$OPS_TMP/ide-runtime-cache` forces a new build. The cache does not detect a
registry image deleted independently of its retained successful job; invalidate
receipts after registry cleanup. Pin dependency versions and base image tags;
unchanged manifests do not automatically refresh floating versions.

The server limits jobs to 15 minutes. The client displays state changes and
periodic progress. Interrupting the client does not cancel the server job.
Python virtualenvs and Node node_modules are excluded from the new source ZIP,
as are dependency manifests and `.env` files. Dependencies live in the image.
Node lockfiles are currently rejected rather than silently ignored; local path
dependencies, arbitrary Dockerfiles and OS package installation are not supported
by this manifest-only API. Other language workflows retain their existing behavior.

The cluster must run the matching Advanced Admin API (including build status),
have its builder worker prerequisites and registry configured, and allow runtime
image pulls. See the administrator sections below.

## Standard Python action: working example

Create this structure in an OPS application:

```text
.env
packages/
  example/
    format_number/
      __main__.py
      requirements.txt
```

Use the application's normal login configuration in `.env`:

```dotenv
OPS_USER=your-namespace
OPS_APIHOST=https://your-ops-host.example
OPS_PASSWORD=your-password
```

Keep this file private and outside version control. Service connection parameters are inherited from the OPS login profile; they do not need to be copied into this example's `.env`.

`requirements.txt`:

```text
humanize==4.13.0
```

`__main__.py`:

```python
#--kind python:3.12

import humanize


def main(args):
    return {"formatted": humanize.intcomma(1234567)}
```

From the application root:

```bash
ops ide login
ops ide deploy example/format_number
ops action invoke example/format_number -r
```

Expected result:

```json
{"formatted": "1,234,567"}
```

The deployer builds the selected runtime with `humanize`, waits for a successful
push, and deploys the action source using that image. No local Python environment
is required. The image must implement the OpenWhisk runtime protocol.

## Image builder prerequisites

The cluster must have the System/Admin API with builder support, permission to create build Jobs and ConfigMaps, a working registry, and registry credentials available to the builder. The developer authenticates using the OPS namespace API key obtained through login. Kubernetes access is only needed for the administrator's Job diagnostics below.

For Python, the builder uses `/bin/extend` when provided by the source image, and otherwise installs `/tmp/requirements.txt` through `python -m pip`. The API generates:

```dockerfile
FROM <source>
COPY requirements.txt /tmp/requirements.txt
USER root
RUN if [ -x /bin/extend ]; then /bin/extend; else python -m pip install --no-cache-dir -r /tmp/requirements.txt; fi
USER nobody
```

A generic `python:...` image is not sufficient to serve an OPS action: the image must implement the OpenWhisk runtime protocol. The standard OPS Python 3.12 image was successfully extended in the lab with `humanize==4.13.0`, then deployed as an action with no virtualenv in its ZIP. Node.js likewise preserves `/bin/extend` when present. Otherwise it installs dependencies in `/opt/ops-deps` and links them into `/app/node_modules`, where the standard OPS runtime resolves action imports. An existing `/app/node_modules` makes this fallback fail rather than overwrite it. Other languages require `/bin/extend`. Rebuild and deploy the updated Admin API before using these paths.

## Builder API

`POST /system/api/v1/build/start` accepts JSON:

| Field | Required | Meaning |
| --- | --- | --- |
| `source` | Yes | One source image reference; shell syntax, whitespace and injected Dockerfile lines are rejected |
| `target` | Yes | `<authenticated-namespace>:<tag>`; do not include a registry host or repository path |
| `kind` | Yes | Selects the dependency filename using the table below |
| `file` | No | Base64-encoded contents of the dependency file; omit it for a base-image-only build |

| `kind` | Dependency filename |
| --- | --- |
| `python` | `requirements.txt` |
| `nodejs` | `package.json` |
| `go` | `go.mod` |
| `java` | `pom.xml` |
| `php` | `composer.json` |
| `ruby` | `Gemfile` |
| `dotnet` | `project.json` |

This mapping is implemented by the API; it does not certify a compatible source image for every language. Tags follow `[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}`. The default strict user check requires the target's namespace to match the authenticated user.

The following Python 3 example prompts for the API key without displaying it. Run it from a directory containing `requirements.txt`, using a source image whose extension interface has been verified:

```python
import base64
import getpass
import json
import urllib.request

api_host = input("OPS URL: ").rstrip("/")
namespace = input("OPS namespace: ")
source = input("Compatible runtime source image: ")
auth = getpass.getpass("OPS API key (uuid:secret): ")
with open("requirements.txt", "rb") as requirements:
    payload = {
        "source": source,
        "target": namespace + ":python-deps-v1",
        "kind": "python",
        "file": base64.b64encode(requirements.read()).decode(),
    }
request = urllib.request.Request(
    api_host + "/system/api/v1/build/start",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": "Basic " + base64.b64encode(auth.encode()).decode(),
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=180) as response:
    print(response.read().decode())
```

A successful response contains `status`, `message`, `id` and `job_name` at the top level. HTTP 200 means the build was initiated, **not** that the image has been built and pushed.

## Administrator diagnostics for manual API builds

The authenticated `GET /system/api/v1/build/status/<job_name>` endpoint returns
only `job_name`, `state` (`pending`, `running`, `failed`, or `succeeded`) and
`image`. Missing jobs and jobs belonging to another tenant both return 404;
anonymous requests return 401. This is the endpoint used by `ops ide deploy`.

An administrator can inspect the returned Job name:

```bash
kubectl -n openserverless get job <job-name>
kubectl -n openserverless logs job/<job-name> -c buildkit
kubectl -n openserverless wait --for=condition=complete job/<job-name> --timeout=10m
```

If the wait fails, inspect Job conditions and logs: a failed Job will not become Complete. Confirm the push completed and record the image digest. Do not publish logs containing application files or credentials.

After verifying that the cluster's runtime nodes can pull the image, select it in the action:

```python
#--docker registry.example/your-namespace:python-deps-v1

import humanize


def main(args):
    return {"formatted": humanize.intcomma(1234567)}
```

For this manual-image workflow, omit the action dependency manifest to avoid triggering another build. Use the real, verified pull reference in place of the example. Then run `ops ide deploy example/format_number` and invoke the action. Avoid also shipping the same dependencies in an action virtualenv unless intentional; duplicate versions can change import behavior. A custom image must preserve the OpenWhisk runtime protocol, not merely contain Python.

## Registry resolution and credentials

The builder resolves its registry host in this order: Admin API process `REGISTRY_HOST`, the authenticated user's `REGISTRY_HOST`, the `registry_host` annotation on ConfigMap `config`, then `openserverless-registry-svc:5000`.

By default it mounts `registry-pull-secret` as a Docker config. `REGISTRY_SECRET` in the user environment can name another Kubernetes Secret or contain `username:password`. Prefer administrator-managed secrets. The current inline-credential branch changes target composition and is not validated end to end; do not assume arbitrary external registry paths are supported by the strict target validator.

Push and pull may use different network endpoints, but both must reach the same registry and have matching authentication and HTTP/TLS configuration. A Service DNS name that works in a Pod does not automatically work for containerd running on the node.

## Current lab status and troubleshooting

| Symptom or check | Meaning / action |
| --- | --- |
| RootlessKit startup or `/proc` mount failure | Verify the worker user-namespace prerequisites below. Do not disable the process sandbox to work around it. |
| Valid base-image build | Passed, including push to the private registry |
| Invalid target, source newline, another tenant's target | Rejected with HTTP 400 in the lab |
| Runtime `ErrImagePull` for `openserverless-registry-svc:5000/...` | Resolved in the single-node K3s lab by the scoped mirror below; configure every action-running node. Authenticated pull and custom action execution passed. |
| `/bin/extend: not found` | Python and Node.js have standard-runtime fallbacks; other languages require an extension-aware source image. |
| Image digest disappears from an action pull | The current OpenWhisk `ImageName.fromString` parser accepts a digest but discards it. Use a unique tag for this tested workflow and record/verify its digest separately. Immutable digest support remains an open core issue. |
| HTTP 401 | Check the OPS API key for API authentication, or registry credentials if the error is in build/pull logs |
| Package imports fail after ZIP deployment | Check packaged dependencies, Python/architecture compatibility and selected runtime |

## Build worker isolation and prerequisites

The worker pins BuildKit by digest, runs with UID/GID 1000 and `privileged=false`, disables Kubernetes service-account token mounting, and requests a private Pod user namespace (`hostUsers: false`). BuildKit uses `noProcessSandbox = false`: dependency commands retain their own process sandbox.

AppArmor and seccomp are Unconfined for this dedicated worker, and `procMount: Unmasked` permits mounting proc inside the private user namespace. These settings are not a claim of protection against every kernel/container vulnerability. Validate the actual persisted Pod settings and node UID mapping before enabling the builder on another cluster; older API servers may discard unsupported fields. This configuration was tested on K3s `v1.37.1+k3s1`, with working Kubernetes/containerd user namespaces. Compatibility with older clusters and Docker+Kind has not been established.

Read-only subordinate UID/GID mappings use `user:1:999` and `user:1001:64535`. Child root maps to Pod ID 1000; subordinate ranges exclude Pod root and ID 1000. Build IDs 0–65534 are representable, including `nobody`; images requiring UID/GID 65535 or larger are unsupported. No host UID/GID configuration is changed.

Both the Admin API and task BuildKit configuration must be updated together. Do not retain the previous `noProcessSandbox=true` lab configuration. The Admin API image used for validation was built and imported locally; pushing these source commits does not publish a ready-made container image.

## K3s internal registry mirror

`ops cloud k3s create <server> [<user>]` now installs the scoped mirror before
K3s starts. For an existing single-server installation, run:

```sh
ops cloud k3s registry <server> [<user>]
```

The command writes this exact entry only when the file is absent or empty:

```yaml
mirrors:
  "openserverless-registry-svc:5000":
    endpoint:
      - "http://127.0.0.1:32000"
```

On an existing server the command restarts K3s after installing the file. It is
idempotent for the exact OPS-managed content and refuses to replace a non-empty
custom `registries.yaml`. Merge the entry manually when other registry settings
must be preserved. Configure every action-running node in a multi-node cluster;
the current `ops cloud k3s` task manages one server.

The mirror requires working loopback NodePort access. Credentials remain in
`registry-pull-secret`, referenced by the action Pod; no node-level credentials
or wildcard mirror are added.

The 17 October lab retest confirmed authenticated private pulls, rejection of
anonymous private pulls, and an unchanged public Docker Hub pull. Fresh Node.js
and Python builds were pushed and then executed through `ops ide deploy`. The
mirror is specific to the OPS internal registry and does not redirect public
images. See [K3s private registry configuration](https://docs.k3s.io/installation/private-registry).

## Cleanup

`POST /system/api/v1/build/cleanup`, with the same authentication and JSON `{"max_age_hours": 24}`, removes completed successful build Jobs older than that age for the authenticated user. It does not remove registry images or running/failed Jobs. The build-start path also attempts cleanup of old completed Jobs.

The repository's `task builder:send` helper depends on `cleanjobs`, which searches broadly for build resources. Prefer the direct API example above on shared clusters.

## Implementation references

- [Build service and generated Job](../admin-api/openserverless/impl/builder/build_service.py)
- [REST endpoints](../admin-api/openserverless/rest/build.py)
- [Python packaging task](../oplugins/ide/python/opsfile.yml)
- [Local dependency installation](../oplugins/ide/python/build-venv.sh)
- [IDE deployment](../oplugins/ide/deploy/deploy.js)

## Additive Beta regression scenarios

The [Python and Node.js fixtures](../advanced/lab/builder/README.md) exercise automatic image building during deployment. Existing Alpha/Beta application actions are unchanged.
