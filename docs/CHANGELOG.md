# Changelog

All notable changes to AgenticAuthor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Core infrastructure and project setup
- OpenRouter API client with streaming support
- Interactive REPL with prompt_toolkit
- Slash command system with auto-completion
- Project and story data models
- Git integration for version control
- Configuration management with .env support
- Model discovery and selection
- Basic test suite with pytest
- Comprehensive documentation structure

### Changed
- Commands now use `/` prefix (e.g., `/help` instead of `help`)
- Natural language input (without `/`) reserved for iteration

### Fixed
- InteractiveSession initialization order bug
- DateTime deprecation warnings (using timezone-aware UTC)
- Taxonomy serialization issues
- Test console compatibility issues

### Security
- API key validation (must start with 'sk-or-')
- .env file excluded from git
- No credentials in logs

## [0.1.0] - Not Released Yet

Initial development version with basic functionality.

### Planned for 1.0.0
- [ ] Complete generation system (premise, treatment, chapters, prose)
- [ ] Natural language iteration with intent checking
- [ ] Story analysis system
- [ ] Export functionality
- [ ] 80%+ test coverage
- [ ] Full documentation

## Version History

- **Current**: Development (unreleased)
- **Target 1.0.0**: Q1 2024 - Full feature release
- **Target 0.1.0**: Alpha release with core features