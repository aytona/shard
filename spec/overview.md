# SHARD Architecture Overview

## Core Principle

Complex, reliable agent behavior is not the product of a single sophisticated system. It emerges from the composition of independent subsystems, each governing a distinct aspect of agent operation, interacting through typed interfaces.

## The Four Subsystems

### 1. Memory Governance

Agents accumulate knowledge across sessions. Without governance, this knowledge degrades — stale facts persist, contradictions accumulate, and the agent's behavior drifts from its intended function.

Memory Governance provides:
- **Staleness detection** — Identifying when stored knowledge no longer reflects reality
- **3D validation** — Checking consistency across temporal, semantic, and structural dimensions
- **Conflict resolution** — Deterministic rules for handling contradictory memories

This is not memory *storage* (which the gateway provides). This is memory *quality control*.

### 2. Intent-Based Coordination

When multiple agents operate in a shared environment, uncoordinated action produces conflicts. Intent-Based Coordination implements a three-phase protocol:

1. **DECLARE** — Agent announces intended action before executing
2. **REVIEW** — Other agents (or the system) check for conflicts
3. **EXECUTE** — Action proceeds only after review passes

This prevents semantic conflicts (two agents modifying the same resource with incompatible goals) without requiring a central orchestrator.

### 3. Quality-Gated Skill Lifecycle

Agents that can acquire new capabilities must have constraints on *what* they acquire and *how much trust* new capabilities receive. The lifecycle implements:

- **Four gates**: Discard (reject), Similarity (deduplicate), Benchmark (validate), Trust Assignment
- **Four trust tiers**: T1 Sandboxed → T2 Validated → T3 Promoted → T4 Trusted

A capability enters at T1 (sandboxed, limited invocation) and can only promote through demonstrated reliability. Demotion is always possible; promotion is never automatic.

### 4. Safety-Constrained Self-Improvement

An agent that can modify its own behavior is powerful but dangerous. Safety constraints bound what modifications are permissible:

- **Rate limiting** — Maximum modifications per time window
- **Scope guards** — Certain files/configs are immutable by the agent
- **Rollback capability** — Every modification is reversible
- **Programmatic enforcement** — Constraints are code, not prompts

## Composition Interfaces

Subsystems communicate through **typed read/write protocols**. Each subsystem exposes:
- A read interface (what it makes available to others)
- A write interface (what it accepts from others)

Example: The Skill Lifecycle reads from Memory Governance (to check if a skill's knowledge dependencies are still valid) and writes to Safety Constraints (to register new capability boundaries).

## Compositional Fault Recovery

The key emergent property: when one subsystem detects a fault, the composition of all four subsystems enables recovery paths that no individual subsystem could achieve alone.

Example: Memory Governance detects a stale dependency → Skill Lifecycle demotes affected skills → Coordination Protocol announces the capability change → Safety Constraints verify the demotion didn't violate bounds.

No single subsystem "designed" this recovery. It emerges from their composition.
