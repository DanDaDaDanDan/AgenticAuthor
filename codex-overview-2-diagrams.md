# AgenticAuthor — Diagrammed Architecture Overview (v2)

This document visualizes the core architecture, runtime flow, file hierarchy, and data hand-offs. It is self-contained and aligns with the current source tree and on-disk layout.

## System Context
```mermaid
flowchart LR
  subgraph CLI & UX
    A[agentic (Typer CLI)] --> B[interactive.py (REPL)]
    B --> C[command_completer.py]
    B --> D[model_selector.py]
    B --> E[taxonomy_editor.py]
  end

  subgraph Generation
    G1[premise.py]
    G2[treatment.py]
    G3[chapters.py]
    G4[variants.py]
    G5[judging.py]
    G6[prose.py]
    G7[depth_calculator.py]
    G8[lod_context.py]
    G9[copy_editor.py]
  end

  subgraph Prompts
    P0[prompts/__init__.py\nPromptLoader]
    P1[generation/*.j2]
    P2[editing/*.j2]
    P3[kdp/*.j2]
  end

  subgraph API
    X1[openrouter.py]
    X2[streaming.py]
    X3[models.py]
    X4[auth.py]
  end

  subgraph Storage & Utils
    S1[models/project.py]
    S2[storage/git_manager.py]
    U1[utils/tokens.py]
    U2[utils/yaml_utils.py]
    U3[utils/session_logger.py]
  end

  A --> B
  B -->|/generate ...| G1 & G2 & G3 & G6
  G1 & G2 & G3 & G6 --> P0 --> P1
  G6 --> P2
  G3 --> G4 --> G5
  B -->|LLM calls| X1 --> X2
  X1 --> X3 --> B
  B --> S1
  S1 --> S2
  G1 & G2 & G3 & G6 --> U1 & U2 & U3
```

ASCII fallback:
- CLI → REPL → Generation (premise/treatment/chapters/prose)
- Generation → Prompts (Jinja) → API (OpenRouter) → streaming
- Storage (Project/Git) + Utils (tokens/YAML/logger) support each step

## Runtime Flow (New Book → Export)
```mermaid
sequenceDiagram
  participant U as User
  participant CLI as agentic / REPL
  participant Gen as Generation Pipeline
  participant P as Prompts
  participant API as OpenRouterClient
  participant FS as Project Files (books/<name>)

  U->>CLI: /new <name>
  CLI->>FS: Create project structure + init shared git (books/)
  U->>CLI: /model (select)
  U->>CLI: /generate premise
  CLI->>Gen: premise.py (with taxonomy)
  Gen->>P: render premise template
  P->>API: completion (YAML/text)
  API-->>Gen: premise result
  Gen->>FS: premise_metadata.json

  U->>CLI: /generate treatment
  CLI->>Gen: treatment.py
  Gen->>P: treatment_generation.j2
  P->>API: completion (YAML with prose)
  API-->>Gen: treatment
  Gen->>FS: treatment.md + metadata

  U->>CLI: /generate chapters
  CLI->>Gen: chapters.py (foundation + single-shot)
  Gen->>P: chapter_foundation.j2, chapter_single_shot.j2
  P->>API: completion (YAML)
  API-->>Gen: foundation + chapter-XX outlines
  Gen->>FS: chapter-beats/foundation.yaml + chapter-XX.yaml

  U->>CLI: /generate prose all
  CLI->>Gen: prose.py (sequential)
  Gen->>FS: load prior prose for context
  Gen->>P: prose_generation.j2
  P->>API: streaming completion (prose)
  API-->>Gen: narrative prose
  Gen->>FS: chapters/chapter-XX.md

  U->>CLI: /export rtf
  CLI->>FS: read artifacts
  CLI->>Export: md/rtf exporters
  Export->>FS: RTF/MD outputs
```

## File Hierarchy (key areas)
```mermaid
flowchart TD
  A[repo/] --> B[src/]
  A --> C[books/]
  A --> D[docs/]
  A --> E[taxonomies/]
  A --> F[logs/]

  subgraph src
    B1[cli/]
    B2[api/]
    B3[config/]
    B4[generation/]
    B5[prompts/]
    B6[models/]
    B7[storage/]
    B8[export/]
    B9[utils/]
  end

  subgraph books/<name>
    C1[premise/]
    C2[treatment/]
    C3[chapter-beats/]
    C4[chapter-beats-variants/]
    C5[chapters/]
    C6[analysis/]
    C7[exports/]
    C8[project.yaml]
  end
```

Notes
- `chapter-beats/` holds structured YAML (foundation + per‑chapter outlines). `chapters/` holds prose as Markdown.
- Variants + judging live under `chapter-beats-variants/` and record decisions.

## Data Artifacts & Formats
```mermaid
flowchart LR
  Prem[Premise (JSON)] --> Treat[Treatment (YAML prose)]
  Treat --> Found[Foundation (YAML: metadata/characters/world)]
  Found --> Beats[Chapter Beats (YAML per chapter)]
  Beats --> Prose[Chapter Prose (Markdown per chapter)]
  Prose --> Export[RTF/MD Exports]

  Beats -.-> Analysis[Analysis Reports (MD)]
  Prose -.-> Analysis
```

## Prompt Contracts & Validation
```mermaid
flowchart LR
  Loader[prompts/__init__.py\nPromptLoader] --> SysUser[[SYSTEM/USER split]]
  SysUser --> GenPrompts[generation/*.j2]
  GenPrompts --> Strict[Strict YAML/JSON rules]
  Strict --> Parsers[utils/yaml_utils.py]
  ProseVal[validation/prose_fidelity.j2] --> SurgIter[prose_iteration.j2]
```

Principles
- Prompts instruct exact formats; validators flag deviations (e.g., summary‑only prose → insufficient_detail).
- Robust YAML parsing falls back gracefully with explicit warnings and debug saves.

## Git & Observability
```mermaid
flowchart LR
  Books[books/] -->|shared repo| Git[(.git)]
  Project[models/project.py] --> Books
  GitMgr[storage/git_manager.py] --> Git
  Logger[utils/session_logger.py] --> Logs[logs/]
  Analyzer[analysis/*] --> Reports[books/<name>/analysis/]
```

- Shared Git at `books/` ensures related works share history, while each project remains self‑contained.
- Session logs and analysis reports aid reproducibility and debugging.
```
ASCII fallback
- books/ is a shared Git repo; each project folder contains premise, treatment, chapter‑beats, chapters, analysis, exports.
- session_logger writes prompt/response artifacts and errors to logs and .agentic/debug.
```

## Development Philosophies (recap)
- Full context, fail fast, single model, quality over quotas.
- Global chapter plan; sequential prose with prior prose as authority.
- Deterministic prompt/output contracts; strict parsing; analysis‑driven iteration.
- Disk‑first artifacts with Git traceability.
