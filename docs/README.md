# Documentation Index

Welcome to the AgenticAuthor documentation. This directory contains comprehensive documentation for developers and users.

## Core Documentation

### For Claude/AI Assistants
- **[../CLAUDE.md](../CLAUDE.md)** - Instructions for AI assistants working on this codebase. **START HERE if you're Claude!**

### For Developers
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, components, and data flow
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Setup, workflow, testing, and contribution guide
- **[API_REFERENCE.md](API_REFERENCE.md)** - Command reference and Python API documentation
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** - Current progress, todo list, known issues
- **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Detailed implementation patterns and code examples

### Project Information
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes
- **[PROJECT_README.md](PROJECT_README.md)** - Main project README (user-facing)
- **[LOD.md](LOD.md)** - Level of Detail system explanation

### Taxonomies
- **[taxonomies/](taxonomies/)** - Genre-specific taxonomy files for story generation

## Documentation Standards

### When to Update Each File

| File | Update When | Audience |
|------|------------|----------|
| CLAUDE.md | Project structure changes | AI assistants |
| ARCHITECTURE.md | Design decisions made | Technical team |
| DEVELOPMENT.md | Dev process changes | Contributors |
| API_REFERENCE.md | API/command changes | Developers/Users |
| IMPLEMENTATION_STATUS.md | Features completed/started | Project managers |
| CHANGELOG.md | Preparing releases | Users |
| README.md | User-facing changes | End users |

### Documentation Principles

1. **Keep docs close to code** - Update immediately when making changes
2. **Write for your audience** - Technical for devs, simple for users
3. **Include examples** - Show, don't just tell
4. **Track everything** - Use IMPLEMENTATION_STATUS.md for progress
5. **Version carefully** - Update CHANGELOG.md for releases

## Quick Links

### Common Tasks
- [How to add a new command](DEVELOPMENT.md#adding-new-features)
- [How to run tests](DEVELOPMENT.md#running-tests)
- [API authentication](API_REFERENCE.md#environment-variables)
- [Project structure](ARCHITECTURE.md#file-structure)

### Key Concepts
- [Level of Detail (LOD)](LOD.md)
- [Natural language iteration](ARCHITECTURE.md#iteration-flow)
- [Git integration](ARCHITECTURE.md#storage-layer)
- [Slash commands](API_REFERENCE.md#slash-commands)

## Documentation TODO

- [ ] Add user guide for book creation workflow
- [ ] Create prompt engineering guide
- [ ] Add troubleshooting guide
- [ ] Create example projects
- [ ] Add performance tuning guide