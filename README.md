# SHARD

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20474819.svg)](https://doi.org/10.5281/zenodo.20474819)
[![SSRN](https://img.shields.io/badge/SSRN-6898739-blue)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6898739)

**Self-Healing Agent with Resilient Delegation**

A composable infrastructure layer that enables governed, self-improving LLM agents. SHARD provides four independent subsystems that, when composed, produce reliability and safety behaviors none could achieve alone.

## What is SHARD?

SHARD is an **agent harness** — a persistent runtime layer that manages one or more LLM-backed agents, providing session lifecycle, tool dispatch, memory persistence, scheduling, multi-agent coordination, and fault recovery, independent of the underlying model. It sits between the harness's execution environment and the agent's operational context, adding:

- **Memory Governance** — Staleness detection, conflict resolution, and validation for persistent agent memory
- **Intent-Based Coordination** — DECLARE→REVIEW→EXECUTE protocol for multi-agent collaboration
- **Quality-Gated Skill Lifecycle** — Four gates and four trust tiers controlling what capabilities an agent can acquire
- **Safety-Constrained Self-Improvement** — Bounded modification with programmatic enforcement

Each subsystem operates independently. Their composition produces emergent properties — most notably, compositional fault recovery — that no individual subsystem was designed to provide.

## Design Philosophy

SHARD is built on the principle that coherent agent behavior arises from the interaction of independent, contextually-activated components rather than from a monolithic controller. No single subsystem is sufficient. No central orchestrator decides everything. The architecture's reliability is a compositional property, not a designed feature of any one part.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Agent Harness                    │
├─────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │  Memory   │  │  Coord    │  │   Skill   │    │
│  │Governance │◄─┤ Protocol  ├─►│ Lifecycle │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        │              │              │          │
│        └───────┬──────┴───────┬──────┘          │
│                │              │                 │
│         ┌──────▼──────┐ ┌─────▼───────┐         │
│         │   Safety    │ │ Composition │         │
│         │ Constraints │ │ Interfaces  │         │
│         └─────────────┘ └─────────────┘         │
└─────────────────────────────────────────────────┘
```

## Key Findings (27 Months of Production)

From continuous deployment (May 2024 — August 2026), operating across 500 self-improvement experiments, 159 skills, and 31 coordinated agents:

**Memory Governance:**
- Staleness detection accuracy: 96% (48/50). Two false negatives occur near threshold boundaries, suggesting a graduated warning zone rather than binary cutoff would improve detection.
- Dependency cascades are the primary recovery mechanism. When a stale memory is detected, the cascade invalidation path (memory → skill demotion → coordination broadcast) fires without operator intervention in 100% of observed cases.
- The `max_cascade_depth` parameter (default 3) has never needed adjustment in production. Deep chains exist but are rare enough that depth-limiting has not caused missed invalidations.

**Coordination Protocol:**
- Syntactic conflict detection: 90% (9/10). Semantic conflict detection: 70% (7/10). The 30% semantic miss rate is a performance concern (wasted work), not a safety concern, because memory governance and rollback catch post-execution inconsistencies.
- Transitive dependency conflicts (changes that only conflict through a mediating third file) remain the primary gap. These require dependency graph construction that the current protocol does not implement.

**Skill Lifecycle:**
- T4 promotion validated retrospectively: 12 skills have operated autonomously for 30+ days without incident, confirming the T4 criteria discriminate correctly at deployment timescales.
- The original 30-day T3→T4 threshold was initially untestable in evaluation (noted as an acknowledged gap in v1). Production operation has since validated this threshold directly.
- Self-generated skills (from the research loop) have a 68% discard rate at Gate 1, confirming the gate's value as a quality filter before any resources are spent on validation.

**Safety Constraints:**
- Zero irreversible state corruptions in 27 months. The composition of rollback registry + scope guard + rate limiter provides defense-in-depth that has never been simultaneously breached.
- The cron expression validation gap (identified in E4 of the original paper) was resolved within 48 hours of discovery, demonstrating the system's own evaluation driving improvement.

**Composition Properties:**
- Compositional fault recovery fires approximately 2-3 times per week without operator awareness. Most common path: stale memory → skill demotion → coordination re-route.
- The ablation result (4/5 silent failures without composition vs 0/5 with composition) holds at scale. No new failure mode has emerged from composition that was not predicted by the original architecture.

## Harness Agnostic

SHARD is not tied to any specific agent harness or framework. It communicates through typed read/write protocols (composition interfaces) that any harness can implement. Public examples of compatible harnesses include:

- [OpenClaw](https://github.com/nousresearch/openclaw)
- [AutoGen](https://github.com/microsoft/autogen) (Microsoft)
- [CrewAI](https://github.com/crewAIInc/crewAI)
- [LangGraph](https://github.com/langchain-ai/langgraph) (LangChain)
- [Semantic Kernel](https://github.com/microsoft/semantic-kernel) (Microsoft)

## Project Structure

```
shard/
├── paper/                   # Published research paper
│   ├── SHARD_v1.pdf         # Original publication (Zenodo)
│   ├── SHARD_v2.pdf         # Revised version (SSRN)
│   └── src/                 # LaTeX source for arXiv
├── spec/                    # Protocol specifications
│   ├── overview.md
│   ├── memory-governance.md
│   ├── coordination.md
│   ├── skill-lifecycle.md
│   ├── self-improvement.md
│   └── composition.md
├── src/shard/               # Reference implementation (1,133 LOC)
│   ├── memory.py            # Memory governance + staleness detection
│   ├── coordination.py      # Intent-based DECLARE→REVIEW→EXECUTE
│   ├── skills.py            # Quality-gated skill lifecycle (4 gates, 4 tiers)
│   ├── safety.py            # Rate limiter, scope guard, rollback registry
│   └── composition.py       # Cross-subsystem composition interfaces
├── src/adapters/            # Harness adapter interface
│   └── base.py              # Abstract base contract (93 LOC)
├── tests/                   # Mechanism validation (83 tests passing)
│   ├── test_memory.py
│   ├── test_coordination.py
│   ├── test_composition.py
│   ├── test_skills.py
│   ├── test_safety.py
│   ├── test_adapters.py
│   └── test_t4_accelerated.py
├── examples/
│   └── quickstart.py
├── pyproject.toml
├── CITATION.cff
└── LICENSE
```

## Status

✅ **Production validated** — 27 months of continuous single-operator deployment. 500 self-improvement experiments completed. 159 skills under governance. 31 agents coordinated. 83 mechanism validation tests passing. Reference implementation and adapter interface complete.

## Roadmap

| Milestone | Status |
|-----------|--------|
| Spec documents (4 subsystems + composition) | ✅ Complete |
| Research paper (benchmarks + findings) | ✅ Published ([Zenodo](https://doi.org/10.5281/zenodo.20474819), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6898739)) |
| Mechanism validation tests | ✅ 83 tests passing |
| Reference implementation (`src/shard/`) | ✅ Complete (1,133 LOC) |
| Harness adapter interface (`src/adapters/`) | ✅ Complete |
| Production deployment validation | ✅ 27 months continuous operation |
| arXiv submission (LaTeX, v2 terminology) | 🚧 In progress |

## License

Apache 2.0 — See [LICENSE](LICENSE) for details.
