# External Harness Assets

Runtime harness code lives under `backend/app/agent/harness/` because it is part of the backend agent, not a top-level developer utility.

Use this top-level directory only for future external harness assets, such as connector fixtures, benchmark cases, or scripts that are not imported by the backend runtime.

Backend harness modules are organized as:

- `backend/app/agent/harness/runtime.py`: intent routing, plan construction, skill dispatch, and summary assembly.
- `backend/app/agent/harness/tools/`: deterministic callable tools with input/output contracts.
- `backend/app/agent/harness/skills/`: higher-level workflows that compose tools.
