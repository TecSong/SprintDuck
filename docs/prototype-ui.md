# UI Prototype Decision

## Prototype Question

What should the first usable SprintDuckAgent demo look like for a candidate?

## Decision

Use a professional two-column workbench:

- Left: agent chat intake.
- Right: live report panel with readiness, gaps, sprint plan, and interview questions.

This is the selected direction for implementation. It replaces the old landing-page/conversion-funnel UI entirely.

## Layout

```text
┌────────────────────────────────────────────────────────────┐
│ SprintDuckAgent · Open-source interview sprint coach       │
├───────────────────────┬────────────────────────────────────┤
│ Chat                  │ Report                             │
│ - transcript          │ - readiness score/band             │
│ - text input          │ - evidence coverage                │
│ - .txt/.md upload     │ - top gaps                         │
│ - send button         │ - adaptive sprint plan             │
│                       │ - likely interview questions       │
│                       │ - download Markdown                │
└───────────────────────┴────────────────────────────────────┘
```

## Interaction States

- Empty: shows three concise starter prompts and a privacy note.
- Collecting: chat shows agent follow-ups; report panel shows missing context checklist.
- Streaming: chat renders assistant deltas and status updates.
- Report ready: report panel becomes primary; chat remains available for another message.
- Error: inline error in chat and retry action.

## Visual Direction

- Professional workbench, not a landing page.
- Dense but readable panels.
- Neutral background, restrained accent colors, no decorative blobs or marketing hero.
- Stable two-column desktop layout; single-column stacked mobile layout.
- Buttons use direct action labels: Send, Upload text file, Download Markdown.

## Absorbed Prototype Outcome

No throwaway route remains after implementation. The useful prototype decision is captured here and absorbed into the production React workbench.
