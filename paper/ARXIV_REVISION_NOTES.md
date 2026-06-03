# arXiv Revision Notes

Terminology and content changes to apply when converting SHARD_v1.pdf to LaTeX for arXiv submission.

## Terminology Update: "agent gateway" → "agent harness"

**Rationale:** "Agent harness" is the consensus term in 2025-2026 systems papers (OpenClaw, AWS internal docs) for a persistent runtime layer that manages LLM-backed agents. "Gateway" undersells the autonomy/memory/scheduling layers. "Framework" implies a library, not a running system.

**Definition to include (first use, Section 1 or 2):**
> An *agent harness* is a persistent runtime layer that manages one or more LLM-backed agents, providing: session lifecycle, tool dispatch, memory persistence, scheduling, multi-agent coordination, and fault recovery — independent of the underlying model.

**Search-and-replace in paper body:**
- "agent gateway" → "agent harness"
- "gateway" (when referring to SHARD's role) → "harness"
- "Gateway Agnostic" (section title) → "Harness Agnostic"

**Distinguish from:**
- Framework = library you build with (LangChain, CrewAI)
- Harness = running system that manages agent execution
- Model = the LLM itself (swappable)
- Tools/MCPs = capabilities exposed to the agent

## Other Pending Changes
- Update DOI badge if Zenodo issues a new version
- Add arXiv identifier once accepted
