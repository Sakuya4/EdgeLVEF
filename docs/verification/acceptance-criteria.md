# Board acceptance criteria

## Required gates

| Gate | Acceptance rule |
|---|---|
| Revision | Tested Git commit is recorded |
| Model identity | Both entries in `SHA256SUMS` pass |
| Unit/integration tests | All repository tests pass |
| Runtime | Requested provider equals active provider |
| Output contract | Shape `[1,2,320,320]`, all values finite |
| Physical evidence | Benchmark executed on Linux with `--claim-physical-target` |
| Functional cine | Full-cycle de-identified PLAX cine completes or failure is documented |
| Visual wall check | Both paths follow opposing LV walls and ED/ES candidates are reviewed |
| Reporting | Median and p95 latency, OS, CPU, RAM and runtime versions retained |

## Informational measurements

Latency alone has no universal pass threshold yet because the intended display
frame rate and complete system budget have not been locked. Report wall-model
forward latency separately from video decoding and end-to-end analysis.

Power, thermal throttling, and NPU utilization are informational until measured
with identified tools. Never report theoretical TOPS as measured throughput.

## Automatic rejection

- checksum mismatch;
- silent CPU fallback reported as NPU;
- edited frozen head or threshold;
- use of the experimental INT8 model;
- exclusion of failed cines after viewing their predicted LVEF;
- reporting Windows or workstation results as board evidence.
