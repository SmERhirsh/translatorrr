# RPG Translator Architecture

## Goal

Build a production-quality translation tool for RPG Maker MV/MZ games using local or remote LLMs through OpenAI-compatible APIs.

The project is developed in phases.

---

# Translation Pipeline

```
Project
    ↓
Project Detection
    ↓
JSON Loading
    ↓
Text Extraction
    ↓
Segment Creation
    ↓
Placeholder Protection
    ↓
Glossary Lookup
    ↓
Translation Memory Lookup
    ↓
Cache Lookup
    ↓
Batch Builder
    ↓
Prompt Builder
    ↓
LLM Provider
    ↓
Response Validation
    ↓
Placeholder Restoration
    ↓
Quality Validation
    ↓
Merge Into Segments
    ↓
JSON Reconstruction
    ↓
Output Writer
```

---

# Responsibilities

## rpgmaker/

Responsible only for:

- detecting RPG Maker projects
- loading JSON files
- extracting translatable text
- rebuilding JSON

Never communicates with LLMs.

---

## translation/

Responsible for:

- batching
- prompts
- orchestration
- validation
- translation workflow

Never writes files directly.

---

## providers/

Responsible only for communicating with LLM providers.

No translation logic.

No JSON parsing.

---

## memory/

Responsible for:

- translation cache
- translation memory
- glossary
- job state

---

## output/

Responsible only for writing translated projects safely.

---

## gui/

Responsible only for the interface.

No translation logic.

---

# Design Rules

- Never duplicate business logic.
- Every module has a single responsibility.
- Translation must be resumable.
- Every translated segment must be traceable back to its source.
- Placeholders must never be modified.
- All providers must implement the same interface.
- GUI must only consume public APIs.
- Pipeline must work without GUI.

---

# Prompt Builder

The Prompt Builder is responsible only for converting extracted TextSegments into ChatRequests.

Responsibilities:

- group segments into translation batches
- preserve segment ordering
- preserve segment IDs
- inject glossary rules
- generate system prompt
- generate user prompt
- optimize prompt size
- estimate token count
- never communicate with providers
- never parse provider responses

Output format:

Input:

[0001]
Hello.

[0002]
How are you?

[0003]
Open the door.

Expected model response:

{
  "0001": "Привет.",
  "0002": "Как дела?",
  "0003": "Открой дверь."
}