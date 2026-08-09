# AGENTS.md

This is a **monorepo root** for storing multiple independent projects. There is no single project configuration here.

## Structure
- Each subdirectory under this root is a separate project
- No shared build, test, or lint configuration at this level
- Check individual project directories for their own `AGENTS.md`, `README.md`, `package.json`, `pyproject.toml`, `Cargo.toml`, etc.

## Working in this repo
- `cd` into a specific project directory before running any commands
- Do not run build/test/lint from this root directory
- Each project manages its own dependencies and tooling