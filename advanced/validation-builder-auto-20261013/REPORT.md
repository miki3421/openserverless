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

# Automatic runtime builds during IDE deployment

Validated on 13 October 2026 in the existing `ops-advanced-security-lab` VM,
K3s, using the patched Advanced Admin API and task sources. This is a scoped
builder regression, not a new independent security certification.

## Results

- `ops ide login`, then `ops ide deploy builder/node`: automatic build, monitored
  registry push, action update, invocation PASS. `is-number` 7.0.0 resolves from
  `/opt/ops-deps/node_modules` inside the runtime image.
- `ops ide deploy builder/python`: automatic extension-aware build, monitored
  push, action update, invocation PASS. `humanize` 4.13.0 and extension marker verified.
- Repeat deployment of both actions reused the successful tenant-owned build receipts.
- Added a deliberately nonexistent Python requirement and ran full `ops ide deploy`:
  exit 1; previous Python action JSON hash unchanged; its invocation still PASS.
  Restored the manifest in a finally block.
- Full `ops ide deploy` after restoration: exit 0, including frontend upload.
- Status isolation over HTTP: anonymous 401, Alpha querying Beta's job 404,
  Beta querying its own job 200. Response fields limited to job_name/state/image.
- Fresh Alpha/Beta functional suite: four PASS checks, exercising and reading
  the five data services. The suite's unrelated gates remain explicitly unverified.
- 61 existing Alpha/Beta source files match the previous hash snapshot. Only
  the additive builder fixtures changed. ZIPs contain the main source only,
  with no bundled dependencies or credentials.
- Local tests: 6 Bun tests (22 assertions); 12 Python unit tests; deployer bundle
  compilation and whitespace checks pass.

## Reproduction and limits

See [fixtures](../lab/builder/README.md) and the
[builder guide](../../docs/BUILDER_GUIDE.md). The Python extension-aware base is
lab-only and must exist before reproducing that fixture. This change publishes
source, not container images; an installation needs the matching Admin API image.

Cache receipts are tied to successful Jobs; independent registry garbage
collection requires receipt invalidation. Lockfiles are rejected by the current
manifest-only builder contract. Full deployments are sequential, not atomic.
No MongoDB upgrade or changes to existing application source were included.
