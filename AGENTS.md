# Development Handbook

Read this file before starting any development work in this repository.

## Required Workflow

- Before changing code, read this handbook and follow its rules.
- State assumptions when the task is ambiguous. Ask before making risky product or architecture choices.
- Keep changes narrow and directly tied to the requested task.
- After every completed code or documentation modification, create a git commit for the change.
- If the current work branch is more than 5 commits behind `main`, merge the latest `main` into the current branch, resolve conflicts, commit the merge if needed, and push the updated branch.
- After pushing changes to the remote `main` branch, rerun the relevant CI/CD pipeline and report the run ID and final status.

## Karpathy Guidelines

These behavioral guidelines reduce common LLM coding mistakes. They bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

Do not assume. Do not hide confusion. Surface tradeoffs.

Before implementing:

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them instead of picking silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what is confusing, and ask.

### 2. Simplicity First

Use the minimum code that solves the problem. Do not add speculative behavior.

- No features beyond what was asked.
- No abstractions for single-use code.
- No flexibility or configurability that was not requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, simplify.

Ask: would a senior engineer say this is overcomplicated? If yes, simplify.

### 3. Surgical Changes

Touch only what is necessary. Clean up only changes introduced by the current task.

When editing existing code:

- Do not improve adjacent code, comments, or formatting unless required.
- Do not refactor unrelated code.
- Match the existing style, even if another style would be preferable.
- If unrelated dead code is found, mention it instead of deleting it.

When your changes create orphans:

- Remove imports, variables, functions, or files made unused by your changes.
- Do not remove pre-existing dead code unless asked.

Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Define verifiable success criteria and loop until verified.

Examples:

- Add validation -> write tests for invalid inputs, then make them pass.
- Fix a bug -> write or identify a test that reproduces it, then make it pass.
- Refactor code -> ensure relevant tests pass before and after.

For multi-step tasks, use a brief plan:

```text
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria allow independent execution. Weak criteria require clarification.
