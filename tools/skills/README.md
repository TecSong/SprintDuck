# External Skill Assets

Runtime skills live under `backend/app/agent/harness/skills/` because they are part of the backend agent harness.

Use this top-level directory only for future reusable skill assets that are not imported directly by the backend runtime, such as prompt templates, packaged skill documentation, or benchmark material.

Concept boundary:

- Tools are deterministic callable capabilities under `backend/app/agent/harness/tools/`.
- Skills are higher-level workflows under `backend/app/agent/harness/skills/` that choose and compose tools.
