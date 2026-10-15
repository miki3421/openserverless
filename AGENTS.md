# OPS Advanced project rules

## Repository ownership and publication

- All OPS Advanced changes belong to the personal `miki3421` repositories and branches.
- Do not push OPS Advanced commits, branches, tags, releases, or other changes to any Apache repository unless the user explicitly authorizes that specific publication action.
- Do not open or update a pull request targeting an Apache repository unless the user explicitly authorizes that specific pull request.
- Read-only operations against Apache repositories, such as fetch, inspect, and compare, are allowed when useful for the work.
- Keep changes local until the user authorizes publishing them to a personal fork. Do not assume that approval to implement a change also authorizes a remote push.
- Never push to repositories whose names start with `olaris`.
- Do not delete existing branches or remote refs unless the user explicitly asks for that exact deletion.

These rules apply to all OPS Advanced work, including core OPS, CLI, task, operator, admin API, runtimes, and related repositories.

## Component upgrades and migration scope

- During component modernization, develop and validate fresh installations in the dedicated lab.
- Defer migration orchestration and development of `ops setup cluster --upgrade` until component modernization is complete. At that stage, evaluate the command with the user before implementing it.
- Retain guards that refuse implicit reuse or upgrades of existing database volumes; deferring migration work does not authorize bypassing them.

## Comparative laboratory

- The current comparative baseline is VM `ops-baseline-k3s`; the Advanced lab is VM `ops-advanced-security-lab` (guest hostname `ops-advanced-lab`). Both run K3s. The older `ops-advanced-rc7` VM was removed with explicit user authorization and is no longer the active baseline.
- Preserve the current baseline's component versions and configuration unless the user explicitly authorizes changing them. Authorized application comparisons may run against both labs without changing Alpha/Beta source code.
- Run future OPS Advanced installations and upgrades in a separate VM with its own writable disk. Place VM storage on the largest available partition, currently `/var/lib/libvirt/images` on `/dev/md3`.
- The baseline disk `baseline-original-0.9.0-20261009.qcow2` is an overlay backed by the preserved Advanced `disk.qcow2`. Preserve the whole backing chain and never boot or modify that backing disk directly while retaining the baseline. An Advanced VM must use an independent disk copy or another overlay whose backing chain remains unchanged.
- Baseline evidence and disk/domain details are recorded in `/root/ops-update-sso/baseline-lab-20261009/`.
