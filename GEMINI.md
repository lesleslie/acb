# Gemini Context: Asynchronous Component Base (ACB)

This document provides a comprehensive overview of the `acb` project to be used as instructional context for Gemini.

## Project Overview

The Asynchronous Component Base (ACB) is a modular Python framework for building high-performance, asynchronous applications. Its core purpose is to provide a structured, pluggable architecture that separates business logic from infrastructure concerns.

The project is built on a layered architecture:

1. **Core Infrastructure:** Handles configuration, dependency injection, and logging.
1. **Adapter Layer:** Provides standardized interfaces to external systems like databases (SQL, NoSQL), caches (Redis, memory), storage (S3, GCS), and AI services.
1. **Orchestration Layer:** Manages communication and background processes through events, tasks, workflows, and the Model Context Protocol (MCP).
1. **Services Layer:** Implements stateful business logic with lifecycle management.
1. **Application Layer:** The final user-facing application (e.g., a web app or API).

Key technologies include:

- **Python 3.13+**
- **uv** for package management
- **Pydantic** for configuration and data validation
- **bevy** for dependency injection
- **Loguru** for logging
- **FastMCP** for the Model Context Protocol (MCP) server, which exposes the framework's capabilities to AI agents.
- Extensive integrations with AI libraries like **OpenAI, Anthropic, Google Vertex AI (for Gemini), LangChain, and LlamaIndex**.

The central idea is "convention over configuration." By using specific directory structures and configuration files (e.g., `settings/adapters.yml`), developers can easily swap out backend implementations (like switching a database from PostgreSQL to MongoDB) without changing application code.

## Building and Running

### Installation

The project uses `uv` for dependency management.

- **Base install:**
  ```bash
  uv add acb
  ```
- **Installation with optional extras:**
  The project is highly modular. Features are installed via "groups." For example, to install AI-related dependencies:
  ```bash
  uv add acb --group ai
  ```
  Other important groups include `cache`, `sql`, `nosql`, `storage`, `dev`, and `all`.

### Running the Application

The primary entry point for interacting with the framework's capabilities, especially for an AI agent, is the Model Context Protocol (MCP) server.

- **Run the MCP Server:**
  ```bash
  uv run python -m acb.mcp.server
  ```

### Running Tests

The project uses `pytest` for testing.

- **Run all tests:**
  ```bash
  pytest
  ```
  The configuration in `pyproject.toml` automatically handles test paths and coverage reporting.

## Development Conventions

- **Code Style:** The project uses **Ruff** for linting and formatting, ensuring a consistent code style. Docstrings follow the **Google** convention.
- **Type Checking:** **Pyright** is used in `strict` mode, enforcing strong type safety.
- **Architecture:** The core pattern is the **Adapter Pattern**. New integrations with external systems should be implemented as adapters. Business logic should be encapsulated in **Services**.
- **Configuration:** All configuration is managed in YAML files within the `settings/` directory. Secrets are kept separate in `settings/secrets/`.
- **Dependency Injection:** The `bevy` framework is used for DI. Dependencies are injected into functions based on type hints, promoting loose coupling and testability.
- **Testing:** A strong emphasis is placed on testing. The `tests/` directory contains a comprehensive suite of unit and integration tests. Mocks are used extensively to isolate components during testing.
