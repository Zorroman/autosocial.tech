# ADR-004: FFmpeg via subprocess, not a Python video library

## Context

Rendering assembles footage clips, a TTS voiceover track, background music,
and burned-in word-level subtitles into a finished video, on a 3.8 GB VPS
with no swap. A naive "load the whole timeline into memory, render once"
approach is exactly the failure mode this architecture has to avoid — see
[SYSTEM_DESIGN.md](../../SYSTEM_DESIGN.md) and
[CASE_STUDIES.md #1](../../CASE_STUDIES.md#1-memory-safe-long-form-rendering)
for the real numbers behind that constraint.

## Decision

Shell out to the FFmpeg binary per segment/clip (one subprocess per chunk,
stream-copy chunking, `ffprobe` verification between stages), rather than
using a Python-native video library (MoviePy, and similar wrappers) that
holds frame/clip state in the Python process's own memory.

## Alternatives considered

- **MoviePy (or similar Python video libraries).** These are themselves
  wrappers around FFmpeg for the actual encode/decode, but they hold
  timeline/clip objects in Python-process memory and tend to load more of
  the working set at once. Rejected because it reintroduces the exact memory
  scaling problem — RSS growing with video length/complexity — that
  process-per-chunk FFmpeg calls were adopted specifically to avoid.
- **A cloud rendering API (e.g. Shotstack, Creatomate).** Would remove local
  memory pressure entirely, at the cost of a recurring per-render fee and an
  external dependency in the critical path of an automated, unattended daily
  pipeline. Rejected for a single-operator project where the entire point is
  running the full pipeline on owned infrastructure.
- **GPU-accelerated encoding.** Not available on this VPS tier; would also
  add a hosting cost step-change disproportionate to the actual output
  volume (Shorts + one long-form video/day).

## Trade-offs

- Shelling out to a subprocess per chunk means more process-spawn overhead
  and more surface for subprocess-failure handling (timeouts, non-zero exit
  codes, partial output files) than an in-process library call would need.
  Accepted, and handled explicitly via `ffprobe` verification between
  stages and resumable chunk state, rather than assumed away.
- Debugging a failed render means reading FFmpeg's own stderr output, not a
  Python traceback — a real, if minor, DX cost that's the direct
  counterpart of getting FFmpeg's own memory discipline for free instead of
  reimplementing it.

## Consequences

- Peak RSS during rendering is bounded and roughly constant regardless of
  final video length (measured 383–623 MB — see
  [SYSTEM_DESIGN.md](../../SYSTEM_DESIGN.md)), because no single process ever
  holds more than one chunk's working set.
- A render can resume from the last completed chunk after a crash or OOM
  kill, instead of restarting from zero — a property that falls out of the
  per-chunk subprocess design, not something bolted on afterward.
