---
ticket: T157
linear_id: G1L-778
linear_url: https://linear.app/g1lom/issue/G1L-778
status: In Progress
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T157 - Shorten the full CI pipeline

## Objective

Reduce elapsed time to `CI / gate` and GitHub-hosted runner time for a complete pull-request
run while preserving every required check, test domain, and final-image identity check.

## Acceptance criteria

- Compare at least five successful complete pull-request runs and three light runs with the
  hosted run of the change. Record the time to the gate, total job execution time, and critical path.
- Preserve affected-domain selection. Scheduled, release, merge-queue, and manual events select
  every test domain.
- Keep the required `CI / gate` result and the existing pinning, permissions, and blocking checks.
- Verify the change with the CI policy and selection tests and a successful complete hosted run.

## Dependencies

- T03 (selective CI and required gate) and T147 (run-scoped final-image archives and verified loading).
- GitHub Actions job timestamps and logs for before/after measurement.

## Measurements

### Before

Durations are minutes:seconds. Wall time ends when `CI / gate` completes. Runner time is the
sum of successful job execution times, before rounding or billing. Queue time comes from the
job's own creation timestamp and excludes the time it waited for prerequisites. The critical
path follows the last successful prerequisite to finish at each dependency join.

| Sample | Run | Suite | Wall | Runner | Critical path |
| --- | --- | --- | --- | --- | --- |
| F1 | [44835213982](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/44835213982) | full | 17:59 | 91:17 | detect domains → build images → e2e-distributed-1 → gate |
| F2 | [44831304834](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/44831304834) | full | 28:37 | 93:19 | detect domains → build images → e2e-distributed-1 → gate |
| F3 | [44830817257](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/44830817257) | full | 29:32 | 95:04 | detect domains → build images → e2e-distributed-1 → gate |
| F4 | [44829951765](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/44829951765) | full | 30:02 | 95:28 | detect domains → build images → container → gate |
| F5 | [44824567847](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/44824567847) | full | 16:37 | 97:14 | detect domains → build images → container → gate |
| L1 | [39667972442](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/39667972442) | light | 7:26 | 12:18 | light → gate |
| L2 | [39664595780](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/39664595780) | light | 3:55 | 11:31 | Python distributed coverage → Python coverage → gate |
| L3 | [39627901705](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/39627901705) | light | 3:25 | 11:12 | Python tests (1) → Python coverage → gate |

| Job | F1 | F2 | F3 | F4 | F5 | L1 | L2 | L3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| affected domains | 6/5 | 274/5 | 186/5 | 272/4 | 3/3 | 3/3 | 47/3 | 2/4 |
| build images | 4/315 | 228/377 | 11/342 | 330/388 | 2/278 | — | — | — |
| ci-infrastructure | 56/16 | 470/15 | 175/26 | 525/16 | 3/21 | — | — | — |
| compose-podman-insecure | 74/95 | 508/97 | 531/96 | 435/85 | 4/97 | — | — | — |
| compose-secure | 57/276 | 529/298 | 628/298 | 523/265 | 2/287 | — | — | — |
| compose-simple-docker | 82/253 | 525/245 | 322/286 | 524/280 | 2/312 | — | — | — |
| compose-simple-podman | 105/362 | 210/348 | 447/362 | 414/396 | 2/353 | — | — | — |
| container | 13/598 | 279/515 | 370/593 | 439/522 | 2/676 | — | — | — |
| detect domains | 1/7 | 60/11 | 231/7 | 84/10 | 2/10 | 2/7 | 4/8 | 3/11 |
| document-engines | 13/148 | 373/150 | 19/164 | 522/151 | 2/144 | — | — | — |
| e2e-distributed-1 | 137/578 | 424/584 | 499/653 | 243/541 | 2/533 | — | — | — |
| e2e-distributed-2 | 113/565 | 23/572 | 356/578 | 231/632 | 2/546 | — | — | — |
| e2e-standalone-1 | 18/599 | 181/517 | 327/494 | 12/598 | 3/624 | — | — | — |
| e2e-standalone-2 | 34/486 | 145/551 | 458/569 | 14/605 | 2/593 | — | — | — |
| frontend | 136/80 | 483/60 | 423/53 | 121/50 | 3/90 | — | — | — |
| gate | 10/3 | 2/4 | 25/3 | 25/3 | 2/2 | 2/4 | 3/4 | 2/3 |
| light | 2/145 | 6/201 | 238/199 | 265/134 | 2/153 | 3/196 | 4/136 | 3/186 |
| mutation | 2/53 | 400/50 | 8/58 | 198/46 | 2/45 | 3/14 | 47/13 | 3/13 |
| Python coverage | 3/30 | 185/26 | 467/31 | 268/21 | 2/30 | 2/21 | 3/21 | 2/21 |
| Python distributed coverage | 2/185 | 181/241 | 238/190 | 23/257 | 3/186 | 2/191 | 4/199 | 2/163 |
| Python tests (0) | 1/142 | 182/161 | 240/164 | 237/114 | 2/121 | 2/146 | 9/139 | 3/99 |
| Python tests (1) | 2/147 | 251/184 | 241/186 | 144/146 | 3/140 | 3/156 | 4/168 | 3/172 |
| supply-chain | 112/389 | 410/387 | 480/347 | 490/464 | 3/590 | — | — | — |

Cells show queue/execution in seconds. L1 elapsed time includes the failed first attempt and
the rerun wait. Its successful jobs come from both attempts, using each job's original
timestamps. L3 shows the successful third attempt.

The complete-run median was **28:37 wall / 95:04 runner**. The two least queued runs reached
the gate in **16:37 and 17:59**. All five critical paths passed through the image build job.
In F1 the backend, frontend, and reverse-attempt build/export times were 118, 84, and 33 seconds
in series. The three sequential archive downloads took 20 seconds on the critical E2E job,
165 seconds on standalone shard 1, and 93 seconds on the container job. Logs confirmed hits
for the LibreOffice RPM archive, heavy uv dependencies, and the pnpm store in sampled jobs.

### After

[Full PR run 44838614776](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/44838614776)
passed all 23 jobs with head `20e37b2bc3b80e6f3e2985a7c2501d44eecbe5f0`. Its path was
detect domains → build images → e2e-distributed-1 → gate. The workflow diff selected every
active domain, so the PR run supplied the full-suite measurement.

| Metric | Before, median of five full runs | After, full PR run |
| --- | ---: | ---: |
| Wall time to gate | 28:37 | 31:29 |
| Runner execution time | 95:04 | 90:07 |
| Critical path, modeled without runner queues | 16:16 | 15:12 |
| Image build job | 5:42 | 4:29 |
| Build, export, and verify step | 4:35 | 3:59 |
| Archive download, median consumer per run | 0:28 | 0:18 |
| Archive downloads, all consumers combined | 5:55 | 6:05 |
| Gate queue | 0:10 | 4:45 |

The queue-free model sums execution time along each dependency path and takes the longest.
The measured run used 4:57 fewer runner minutes than the baseline median, with 1:04 less
modeled critical-path execution. Its observed wall time was 2:52 longer amid runner contention.
The gate's queue alone was 4:35 longer than the before median. Download times varied by runner,
with a lower median and a higher total in this sample.

## Progress

- Recorded the baseline from GitHub Actions run and job metadata before changing the pipeline.
- Overlapped up to two image builds and exports on the existing runner. Consumers download
  the required archives concurrently by immutable artifact ID and retain the image ID checks.
- Made merge-queue domain and mutation selection explicit. The workflow validator protects
  the complete-suite events, producer bindings, and download and load order.
- Passed Ruff formatting and lint, ty, the workflow validator, and 511 targeted pytest cases
  on macOS. Rootless image and end-to-end verification run in hosted CI.
- The full pull-request run passed container and supply-chain validation, both shards of both
  final-image profiles, and `CI / gate`.

## Synchronization

- Repository mirror only. Linear issue G1L-778 was left untouched at the owner's request.
