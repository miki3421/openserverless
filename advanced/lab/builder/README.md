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

# Beta custom-runtime regression scenarios

These additive, private actions exercise the Advanced builder without changing
Alpha/Beta's existing application code. They were deployed only to Beta in the
Advanced lab on 13 October 2026. The source fixtures live here so publication is
limited to the personal `advanced` branch.

## Node.js

Build from `docker.io/apache/openserverless-runtime-nodejs:v22-26i22h40-snapshot`
through the authenticated builder API, with kind `nodejs`, target
`opsvalbeta:node-builder-reviewed-20261013`, and a base64-encoded package.json:

```json
{"dependencies":{"is-number":"7.0.0"}}
```

Copy `beta-node/index.js` to the Beta workspace at
`packages/builder/node/index.js`. Do not copy package.json into that action:
this scenario verifies dependencies in the image, not the action ZIP.
Run `ops ide login`, then `ops ide deploy builder/node`, and
`ops action invoke builder/node -r`. Expected: `pass: true`, version `7.0.0`,
resolved path under `/opt/ops-deps/node_modules`. Native ESM is not covered.

## Python extension hook

The tested source image is a lab-only Python runtime with an executable
`/bin/extend` hook that installs `/tmp/requirements.txt` using pip and writes
`extension-hook-used` to `/opt/ops-extension-marker`. This synthetic fixture
verifies that the builder preserves the extension-hook contract. It is not a
published production runtime.

Build from that image through the authenticated API with kind `python`, target
`opsvalbeta:python-extension-tested-20261013`, and base64-encoded
`humanize==4.13.0\n` requirements. Copy `beta-python/__main__.py` to
`packages/builder/python/__main__.py`, without a requirements file beside it.
Run `ops ide login`, then `ops ide deploy builder/python`, and
`ops action invoke builder/python -r`. Expected: `pass: true`, version `4.13.0`,
and `extension_hook: true`.

Reproducing the fixture requires creating the extension-aware base image first.
Use unique image tags for each run and update only these new fixture actions.
`ops ide deploy` selects an existing image; it does not trigger the builder API.

See [builder guide](../../../docs/BUILDER_GUIDE.md) for API requests,
authentication, worker prerequisites and registry configuration.
