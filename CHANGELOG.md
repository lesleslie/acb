# Changelog

All notable changes to ACB (Asynchronous Component Base) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Removed incorrect hardcoded "essential adapters" registration that violated opt-in principle
- Updated tests to reflect proper opt-in adapter behavior
- Restored ACB's core design principle: adapters are opt-in based on application requirements

### Changed
- Only config and loguru adapters are automatically registered (truly essential for ACB operation)
- All other adapters (cache, storage, sql, requests, dns) must be explicitly configured
- Test suite updated to verify opt-in behavior instead of expecting automatic registration

## [0.16.17] - 2025-07-02

### Major Changes

#### Adapter System Refactor
- **BREAKING CHANGE**: Removed dynamic adapter discovery in favor of hardcoded adapter registration system
- **NEW**: Static adapter mappings for improved performance and reliability
- **BREAKING CHANGE**: Adapter imports now use explicit static mappings instead of dynamic module discovery
- **NEW**: Essential adapter registration system with predefined core adapters (config, loguru)

#### Memory Cache Adapter Rewrite
- **BREAKING CHANGE**: Complete rewrite of memory cache adapter to use aiocache interface
- **NEW**: Memory cache now implements full aiocache BaseCache abstract methods
- **IMPROVED**: Better performance and consistency with Redis cache adapter interface
- **NEW**: Added support for all aiocache operations: multi_set, multi_get, add, increment, expire

#### Configuration System Improvements
- **NEW**: Library usage mode detection for better integration in library contexts
- **IMPROVED**: Automatic detection when ACB is used as a dependency vs. standalone application
- **NEW**: Enhanced adapter configuration loading with better error handling
- **IMPROVED**: Smarter project setup detection to avoid conflicts in library usage

### Performance Improvements
- **REMOVED**: Test mocks system (tests/mocks/) - reduced complexity and improved startup performance
- **OPTIMIZED**: Adapter loading with caching and lock-based initialization
- **IMPROVED**: Configuration loading performance through better caching mechanisms
- **STREAMLINED**: Package registration and adapter discovery process

### Dependencies and Build
- **UPDATED**: Major cleanup of PDM lock file with dependency optimizations
- **REMOVED**: Obsolete action handler system (acb/actions/handle/)
- **UPDATED**: Pre-commit configuration improvements
- **CLEANED**: Removed obsolete ZENCODER.md documentation

### Bug Fixes
- **FIXED**: FTP adapter initialization and configuration handling
- **FIXED**: Secret adapter (Infisical) configuration and initialization
- **FIXED**: Storage adapter base class improvements for better reliability
- **FIXED**: SQL adapter base class enhancements
- **IMPROVED**: Better error handling in adapter loading and initialization

### Documentation Updates
- **UPDATED**: Adapter README with current system documentation
- **UPDATED**: Storage adapter documentation reflecting recent changes
- **IMPROVED**: Core dependency injection documentation
- **UPDATED**: Testing documentation for new patterns

### Testing Improvements
- **NEW**: Comprehensive test suite for memory cache adapter
- **IMPROVED**: Enhanced test coverage for adapter system
- **UPDATED**: Test configurations to work with new adapter system
- **ADDED**: Better test utilities for adapter testing

### Breaking Changes Summary

If you're upgrading from a previous version, please note these breaking changes:

1. **Memory Cache Interface**: The memory cache adapter now uses aiocache interface. Update any direct cache usage to use the new interface methods.

2. **Adapter Registration**: Custom adapters must now be explicitly registered in the static mappings. Dynamic adapter discovery is no longer supported.

3. **Configuration Detection**: ACB now automatically detects library vs. application usage mode. This may affect initialization behavior in some edge cases.

4. **Test Mocks Removed**: The `tests/mocks/` system has been removed. Tests should use the new mock-free patterns.

### Migration Guide

For detailed migration instructions, see the project documentation. Key migration steps:

1. Update memory cache usage to use aiocache interface methods
2. Register any custom adapters in the static mapping system
3. Update test code to remove references to the old mocks system
4. Review configuration files for any adapter-specific changes

---

## [Unreleased]

### Added
- This CHANGELOG.md file to track changes going forward

### Changed
- Improved project documentation structure

---

**Note**: This changelog was introduced in version 0.16.17. Previous versions did not maintain a formal changelog, but significant changes were tracked through git commit messages and release notes.
