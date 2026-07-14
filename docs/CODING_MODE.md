# Coding Mode

First-class Spark page for software engineering. Does **not** replace Chat.

## Entry

- Sidebar **Tools → Coding**
- Icon rail **Coding**
- Route `/coding`

## Architecture

```
Coding Mode UI (engine-agnostic)
    → Workspace Manager APIs
    → Harness Manager (OpenCode today)
    → Semantic Twin / Spark OS / Runtime / Knowledge
```

## Features

| Feature | Source |
|---------|--------|
| Explorer / editor / save | Workspace file APIs |
| Status strip | Workspace status + manifest |
| Explain | Twin `explain` / search |
| Execution animation | OS runtime visualization + stages |
| X-Ray | Twin graph index + hover |
| Learning (quiz/tutorial/simulate) | Twin APIs |
| Multi-agent chips | Prompt context roles |
| Twin auto-sync on save | `on_files_changed` |

## Files

- `static/js/coding/mode.js` — shell UI
- `static/js/coding/api.js` — API client
- `static/js/coding/styles.css` — layout
