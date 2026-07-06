# RPG Maker Translator

Production-focused tooling for translating RPG Maker MV/MZ projects from English to Russian.

Current implementation status: Phase 2 complete.

Implemented:

- project/package structure
- core domain models
- layered TOML configuration loading
- RPG Maker MV/MZ project detection
- structured logging setup
- JSON loading for detected RPG Maker data files
- extraction of translatable RPG Maker strings into segments
- JSON pointer tracking for extracted strings
- event command parsing for dialogue, choices, and scrolling text
- placeholder protection/restoration for control codes, tags, format args, and escapes

Not implemented yet:

- provider calls
- LLM translation pipeline
- GUI
- output generation