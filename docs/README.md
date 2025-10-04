# ACB Documentation

> **Current Version:** 0.23.0 | **Python:** 3.13+

Welcome to the ACB (Asynchronous Component Base) documentation. This directory contains essential guides and templates for working with ACB.

## Quick Start

- **New to ACB?** Start with [ARCHITECTURE.md](<./ARCHITECTURE.md>) to understand the framework
- **Upgrading?** See [MIGRATION.md](<./MIGRATION.md>) for version-specific upgrade guides
- **Performance tuning?** Check [PERFORMANCE-GUIDE.md](<./PERFORMANCE-GUIDE.md>)
- **Having issues?** Review [TROUBLESHOOTING.md](<./TROUBLESHOOTING.md>)

## Documentation Index

### Core Guides

- **[ARCHITECTURE.md](<./ARCHITECTURE.md>)** - ACB's simplified architecture and design patterns

  - Core design principles
  - Architecture layers
  - Adapter pattern
  - Actions system
  - Integration patterns

- **[MIGRATION.md](<./MIGRATION.md>)** - Version upgrade guide and breaking changes

  - v0.19.1+ simplified architecture migration
  - v0.16.17+ performance optimizations
  - Migration best practices
  - Troubleshooting common issues

- **[PERFORMANCE-GUIDE.md](<./PERFORMANCE-GUIDE.md>)** - Performance optimization techniques

  - Dependency injection performance
  - Adapter optimization strategies
  - Async best practices
  - Production deployment

- **[TROUBLESHOOTING.md](<./TROUBLESHOOTING.md>)** - Common issues and solutions

  - Installation problems
  - Configuration issues
  - Adapter troubleshooting
  - Testing issues

### Templates

- **[ACTION_TEMPLATE.md](<./ACTION_TEMPLATE.md>)** - Template for creating ACB actions

  - Semantic action pattern
  - Naming conventions
  - Complete examples
  - Testing patterns

- **[ADAPTER_TEMPLATE.md](<./ADAPTER_TEMPLATE.md>)** - Template for creating ACB adapters

  - Module header template
  - Metadata guidelines
  - Implementation patterns
  - Version updating

## Documentation Structure

```
/docs
├── ACTION_TEMPLATE.md      # Template for creating actions
├── ADAPTER_TEMPLATE.md     # Template for creating adapters
├── ARCHITECTURE.md         # Core architecture guide (NEW)
├── MIGRATION.md           # Version migration guide (NEW)
├── PERFORMANCE-GUIDE.md   # Performance optimization
├── TROUBLESHOOTING.md     # Common issues & solutions
└── README.md             # This file
```

## Additional Resources

### Adapter-Specific Documentation

Each adapter category has detailed documentation in the source tree:

- [Cache Adapters](<../acb/adapters/cache/README.md>) - Memory, Redis
- [SQL Adapters](<../acb/adapters/sql/README.md>) - PostgreSQL, MySQL, SQLite
- [NoSQL Adapters](<../acb/adapters/nosql/README.md>) - MongoDB, Firestore, Redis
- [Storage Adapters](<../acb/adapters/storage/README.md>) - S3, GCS, Azure, File
- [Secret Adapters](<../acb/adapters/secret/README.md>) - Infisical, GCP, Azure, Cloudflare
- [Monitoring Adapters](<../acb/adapters/monitoring/README.md>) - Sentry, Logfire
- [Request Adapters](<../acb/adapters/requests/README.md>) - HTTPX, Niquests
- [SMTP Adapters](<../acb/adapters/smtp/README.md>) - Gmail, Mailgun
- [DNS Adapters](<../acb/adapters/dns/README.md>) - Cloud DNS, Cloudflare, Route53
- [FTPD Adapters](<../acb/adapters/ftpd/README.md>) - FTP, SFTP
- [Models Adapter](<../acb/adapters/models/README.md>) - SQLModel, Pydantic, Redis-OM

### Project Documentation

- [Main README](<../README.md>) - Project overview and quick start
- [CHANGELOG](<../CHANGELOG.md>) - Version history and changes
- [CLAUDE.md](<../CLAUDE.md>) - Development guidelines for AI assistants

## What's New in v0.19.1+

ACB underwent a **major simplification** in v0.19.1, removing complex enterprise features to focus on its core mission:

### ✅ What Remains (Core Features)

- Clean adapter interfaces for external systems
- Dependency injection via `bevy`
- Configuration management with hot-reload
- Async-first design
- Action utilities
- Simple resource cleanup
- Essential SSL/TLS support

### ❌ What Was Removed

- Services layer
- Event system
- Task queue system
- Workflow engine
- Complex health checking
- Advanced retry mechanisms
- Multi-tier caching
- Distributed tracing

See [MIGRATION.md](<./MIGRATION.md>) for detailed upgrade instructions.

## Getting Help

1. **Check documentation** - Review relevant guides above
1. **Search issues** - Check [GitHub Issues](https://github.com/lesleslie/acb/issues)
1. **Review examples** - See adapter READMEs for usage examples
1. **Ask questions** - Create a GitHub issue with details

## Contributing

When contributing documentation:

1. **Follow existing structure** - Keep docs organized and scannable
1. **Use examples** - Include code examples for clarity
1. **Be concise** - Focus on essential information
1. **Update index** - Keep this README in sync with changes
1. **Test code** - Ensure all code examples work

## Documentation Philosophy

ACB documentation follows these principles:

- **Clarity over completeness** - Essential information only
- **Examples over explanation** - Show, don't just tell
- **Practical over theoretical** - Focus on real-world usage
- **Maintenance-friendly** - Easy to keep current
