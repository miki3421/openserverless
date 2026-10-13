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

# OPS Advanced builder and Python dependencies

This guide describes the Advanced checkout inspected on 13 October 2026: task commit `427415b`, Admin API commit `b179b0a` plus the local AppArmor correction tested on 12 October. It describes implemented behavior, including incomplete paths; it is not a claim that every image-building workflow is production-ready.

## Choose a dependency workflow

| Need | Mechanism | Result |
| --- | --- | --- |
| Add Python packages to an action | `requirements.txt` beside `__main__.py`, then `ops ide deploy` | Dependencies packaged in the action ZIP; the base runtime image stays the same |
| Share preinstalled dependencies in a custom runtime | Builder REST API, then an action using `#--docker` | A new registry image, followed by a separate action deployment |
| Install OS packages or use a custom Dockerfile | An independently managed image build | Not supported by the current builder JSON API |

The current Advanced `ops ide deploy` implementation does **not** automatically call the builder REST API. A `#--docker` directive selects an existing image; it does not build it. Other forks may implement additional automation.

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

The task creates a local `virtualenv` using `uv` and `/usr/bin/python3`, installs the requirements, packages that environment with the Python source, and updates the action. The runtime loads the packaged dependencies. An equivalent action passed in the Advanced lab with `humanize==4.13.0`; the temporary action was removed afterwards.

Use a development environment compatible with the selected runtime's Python version, architecture and OS, especially for packages with native extensions. The pure-Python test above does not validate every compiled package. If removing dependencies or changing Python versions, clean the action environment before redeploying:

```bash
ops ide util clean A=example/format_number
ops ide deploy example/format_number
```

## Image builder prerequisites

The cluster must have the System/Admin API with builder support, permission to create build Jobs and ConfigMaps, a working registry, and registry credentials available to the builder. The developer authenticates using the OPS namespace API key obtained through login. Kubernetes access is only needed for the administrator's Job diagnostics below.

For Python extension builds, the selected source image must implement `/bin/extend` and accept `/tmp/requirements.txt`. The API generates:

```dockerfile
FROM <source>
COPY requirements.txt /tmp/requirements.txt
USER root
RUN /bin/extend
USER nobody
```

A generic `python:...` image is not sufficient. The inspected runtime source Dockerfiles do not install `/bin/extend`; verify a candidate image before choosing it. The lab's successful image build used a base image without a requirements file and does not prove this extension path works with the standard Python runtime images.

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

## Observe completion and deploy the result

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

Use the real, verified pull reference in place of the example. Then run `ops ide deploy example/format_number` and invoke the action. Avoid also shipping the same dependencies in an action virtualenv unless intentional; duplicate versions can change import behavior. A custom image must preserve the OpenWhisk runtime protocol, not merely contain Python.

## Registry resolution and credentials

The builder resolves its registry host in this order: Admin API process `REGISTRY_HOST`, the authenticated user's `REGISTRY_HOST`, the `registry_host` annotation on ConfigMap `config`, then `openserverless-registry-svc:5000`.

By default it mounts `registry-pull-secret` as a Docker config. `REGISTRY_SECRET` in the user environment can name another Kubernetes Secret or contain `username:password`. Prefer administrator-managed secrets. The current inline-credential branch changes target composition and is not validated end to end; do not assume arbitrary external registry paths are supported by the strict target validator.

Push and pull may use different network endpoints, but both must reach the same registry and have matching authentication and HTTP/TLS configuration. A Service DNS name that works in a Pod does not automatically work for containerd running on the node.

## Current lab status and troubleshooting

| Symptom or check | Meaning / action |
| --- | --- |
| RootlessKit `failed to share mount point: /: permission denied` | The lab's default AppArmor profile blocked startup. The local Admin API patch sets `appArmorProfile: Unconfined` only on BuildKit, retaining UID/GID 1000 and `privileged=false`. This removes that AppArmor restriction and needs security review. The structured field requires Kubernetes 1.30 or later. |
| Valid base-image build | Passed, including push to the private registry |
| Invalid target, source newline, another tenant's target | Rejected with HTTP 400 in the lab |
| Runtime `ErrImagePull` for `openserverless-registry-svc:5000/...` | Still open in the K3s lab: the node cannot resolve the Service hostname. Registry pull endpoint and credentials must be aligned before custom-runtime deployment can be considered complete. |
| `/bin/extend: not found` | Source image does not implement the API's extension contract |
| HTTP 401 | Check the OPS API key for API authentication, or registry credentials if the error is in build/pull logs |
| Package imports fail after ZIP deployment | Check packaged dependencies, Python/architecture compatibility and selected runtime |

The API uses `moby/buildkit:master-rootless`, a moving image tag. No reproducibility guarantee is implied by these tests. The AppArmor correction is local and not yet committed/pushed.

## Cleanup

`POST /system/api/v1/build/cleanup`, with the same authentication and JSON `{"max_age_hours": 24}`, removes completed successful build Jobs older than that age for the authenticated user. It does not remove registry images or running/failed Jobs. The build-start path also attempts cleanup of old completed Jobs.

The repository's `task builder:send` helper depends on `cleanjobs`, which searches broadly for build resources. Prefer the direct API example above on shared clusters.

## Implementation references

- [Build service and generated Job](../admin-api/openserverless/impl/builder/build_service.py)
- [REST endpoints](../admin-api/openserverless/rest/build.py)
- [Python packaging task](../oplugins/ide/python/opsfile.yml)
- [Local dependency installation](../oplugins/ide/python/build-venv.sh)
- [IDE deployment](../oplugins/ide/deploy/deploy.js)
