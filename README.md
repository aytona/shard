# SHARD

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20474819.svg)](https://doi.org/10.5281/zenodo.20474819)

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
│   └── SHARD_v1.pdf
├── spec/                    # Protocol specifications
│   ├── overview.md
│   ├── memory-governance.md
│   ├── coordination.md
│   ├── skill-lifecycle.md
│   ├── self-improvement.md
│   └── composition.md
├── tests/                   # Mechanism validation tests
│   ├── test_memory.py
│   ├── test_coordination.py
│   ├── test_composition.py
│   ├── test_skills.py
│   ├── test_safety.py
│   └── test_adapters.py
├── examples/
│   └── quickstart.py
├── pyproject.toml
├── CITATION.cff
└── LICENSE
```

## Status

✅ **Paper published** — All milestones complete. 83 mechanism validation tests passing. Reference implementation and adapter interface ready for integration.

## Roadmap

| Milestone | Status |
|-----------|--------|
| Spec documents (4 subsystems + composition) | ✅ Complete |
| Research paper (benchmarks + findings) | ✅ Published |
| Mechanism validation tests | ✅ Passing |
| Reference implementation (`src/shard/`) | ✅ Complete (83 tests passing) |
| Harness adapter interface (`src/adapters/`) | ✅ Complete |

## License

Apache 2.0 — See [LICENSE](LICENSE) for details.
