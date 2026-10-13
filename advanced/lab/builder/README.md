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

## Automatic build during deployment

Copy `beta-node/` to Beta's `packages/builder/node/` and `beta-python/` to
`packages/builder/python/`, including the dependency manifests. Then use:

```sh
ops ide login
ops ide deploy
```

For a focused rerun use `ops ide deploy builder/node` or
`ops ide deploy builder/python`. No manual build API request is needed.
Invoke both private actions with `ops action invoke builder/node -r` and
`ops action invoke builder/python -r`.

Node expects `is-number` 7.0.0 resolved from `/opt/ops-deps/node_modules`.
Python expects `humanize` 4.13.0 and the extension marker. Both return `pass: true`.

The Python fixture uses a lab-only extension-aware base image, named explicitly
in its main file. Prepare that base before reproducing the extension-hook test:
it is the OPS Python 3.12 runtime with executable `/bin/extend` installing
`/tmp/requirements.txt` and writing `extension-hook-used` to
`/opt/ops-extension-marker`. It is not a publicly published runtime. Ordinary
Python actions can instead select `#--kind python:3.12` and use the default pip
fallback without the marker assertion.

A repeat deployment should reuse the completed build. An invalid dependency
must fail deployment and leave the previously deployed action callable. Restore
the valid manifest after testing that failure.

See the [builder guide](../../../docs/BUILDER_GUIDE.md) for prerequisites,
cache limits, authentication and registry configuration.
