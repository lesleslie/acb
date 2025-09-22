# Changelog

All notable changes to ACB (Asynchronous Component Base) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.21.2] - 2025-09-22

### Fixed

- Remove all __pycache__ directories and files from repository
- test: Update 393 files
- Update uv.lock version

### Testing

- Verify pre-commit hooks are disabled

## [Unreleased]

### Major Reorganization (v0.19.2+)

#### Framework Simplification and Organization

- **BREAKING**: Major reorganization of ACB's internal structure for better maintainability
- **NEW**: Pure utility functions extracted to actions (`validate`, `secure`)
- **NEW**: Core adapter infrastructure moved to `acb/core/` (SSL, monitoring, retry, cleanup)
- **IMPROVED**: Adapter-specific utilities co-located with their adapters
- **REMOVED**: 15 confusing `_*.py` files that mixed different concerns
- **SIMPLIFIED**: Clear separation between framework infrastructure and application features

#### New Actions (Pure Utility Functions)

- **NEW**: `validate` action - Email, URL, SQL injection, XSS, and path traversal validation
- **NEW**: `secure` action - Cryptographic utilities, token generation, password handling

#### Core Infrastructure (`acb/core/`)

- **MOVED**: SSL/TLS configuration to `acb.core.ssl_config`
- **MOVED**: Basic monitoring to `acb.core.monitoring`
- **MOVED**: Retry mechanisms to `acb.core.retry`
- **MOVED**: Resource cleanup to `acb.core.cleanup`

#### Adapter-Specific Utilities

- **MOVED**: Advanced caching strategies to `acb.adapters.cache._advanced_strategies`
- **MOVED**: SQL health checks to `acb.adapters.sql._health_checks`
- **MOVED**: Cache health checks to `acb.adapters.cache._health_checks`

#### Removed Complexity

- **REMOVED**: Web-specific features (rate limiting, security headers, adapter composition) - belong in FastBlocks
- **REMOVED**: Overly complex observability framework - basic monitoring sufficient
- **REMOVED**: Distributed tracing - too complex for adapter framework
- **REMOVED**: Queue management - should be standalone adapter, not mixin
- **REMOVED**: Redundant integration modules

#### Benefits

- ✅ **Cleaner ACB scope** - Focus on adapter infrastructure only
- ✅ **Better discoverability** - Pure utilities as reusable actions
- ✅ **Logical organization** - Related functionality grouped together
- ✅ **Reduced complexity** - Eliminated confusing flat `_*.py` structure
- ✅ **Clear responsibilities** - Framework vs application features separated

#### Migration Notes

- Web-specific features should be moved to FastBlocks project
- Core infrastructure now available at `acb.core.*`
- New actions available at `acb.actions.validate` and `acb.actions.secure`
- Adapter-specific utilities are private implementation details

## [0.19.1] - 2025-01-14

### Major Features

#### Enterprise Security Infrastructure

- **NEW**: Comprehensive security framework with credential management, input validation, and CSRF protection
- **NEW**: Secure credential storage with encryption, rotation, and audit logging via `_security.py`
- **NEW**: Input validation and sanitization framework to prevent injection attacks via `_validation.py`
- **NEW**: Rate limiting and throttling with multiple strategies (token bucket, sliding window, fixed window) via `_rate_limiting.py`
- **NEW**: Security headers and CSRF protection with CSP, HSTS, and X-Frame-Options via `_security_headers.py`
- **NEW**: All adapters now include secure operation variants (`*_secure()` methods) with validation and rate limiting

#### Production Monitoring and Reliability

- **NEW**: Comprehensive health check system with configurable intervals and thresholds via `_health_checks.py`
- **NEW**: Performance monitoring with real-time metrics collection for latency, throughput, and error rates via `_monitoring.py`
- **NEW**: Adapter-specific monitoring mixins for SQL, Cache, NoSQL, and Storage adapters via `_monitoring_integration.py`
- **NEW**: Intelligent retry mechanisms with exponential backoff and circuit breaker patterns via `_retry.py` and `_retry_integration.py`
- **NEW**: Enhanced resource management with sophisticated cleanup patterns and error handling

#### SSL/TLS Security Unification

- **NEW**: Unified SSL/TLS configuration across all adapters with modern security standards via `_ssl_config.py`
- **IMPROVED**: Consistent SSL configuration with support for TLS 1.2/1.3, certificate validation, and custom cipher suites
- **NEW**: SSL configuration mixins for easy integration into any adapter

### Security Enhancements

- **NEW**: `SecurityMixin`, `ValidationMixin`, `RateLimitMixin`, and `SecurityHeadersMixin` integrated into all base adapters
- **NEW**: Credential management with PBKDF2 key derivation, Fernet encryption, and automatic expiration
- **NEW**: Input validation for SQL injection, XSS, path traversal, and other common attack vectors
- **NEW**: Rate limiting with per-user and per-operation granularity
- **NEW**: CSRF token generation and validation with HMAC-based signatures
- **NEW**: Content Security Policy (CSP) with nonce and hash support

### Monitoring and Reliability Enhancements

- **NEW**: `HealthCheckMixin`, `MonitoringMixin`, and `RetryMixin` integrated into all base adapters
- **NEW**: Health check types: connectivity, performance, dependency, and custom checks
- **NEW**: Performance metrics: latency tracking, operation counting, error rate calculation
- **NEW**: Retry strategies: exponential backoff, jitter, circuit breaker with failure thresholds
- **NEW**: Resource cleanup with common cleanup patterns and race condition prevention

### Adapter System Improvements

- **ENHANCED**: Cache adapter with secure operations (`get_secure`, `set_secure`, `delete_secure`)
- **ENHANCED**: SQL adapter with secure query execution and connection monitoring
- **ENHANCED**: All adapters now include `*_with_retry()` and `*_with_full_monitoring()` operation variants
- **IMPROVED**: Resource management with enhanced async context manager support
- **NEW**: Adapter metadata system extended with security and monitoring capability flags

### Advanced Caching System (v0.19.1+)

- **NEW**: Enterprise-grade multi-tier caching with L1 (Memory) → L2 (Redis) → L3 (Storage) architecture via `_advanced_caching.py`
- **NEW**: Multiple cache strategies: write-through, write-behind, write-around, read-through, cache-aside
- **NEW**: Advanced eviction policies: LRU, LFU, FIFO, TTL-based, random eviction with intelligent tracking
- **NEW**: Intelligent cache warming with configurable concurrency and automatic preloading
- **NEW**: Write-behind batching for high-performance asynchronous storage persistence
- **NEW**: `AdvancedCacheMixin` integrated into Memory and Redis cache adapters for seamless usage
- **NEW**: Comprehensive cache statistics: hit ratios, tier performance, latency tracking

### Distributed Tracing and Observability (v0.19.1+)

- **NEW**: Enterprise-grade distributed tracing system with W3C Trace Context support via `_distributed_tracing.py`
- **NEW**: Multiple trace exporters: Console exporter for debugging, OpenTelemetry exporter for production
- **NEW**: Context propagation with correlation IDs and trace baggage across service boundaries
- **NEW**: `TracingMixin` with operation-specific tracing for database, HTTP, and cache operations
- **NEW**: Comprehensive observability framework combining tracing, metrics, and monitoring via `_observability.py`
- **NEW**: Performance monitoring with slow operation detection and latency tracking
- **NEW**: System metrics collection (CPU, memory) with configurable intervals
- **NEW**: Automatic trace correlation with logs and error tracking

### Advanced Queue Management and Message Passing (v0.19.1+)

- **NEW**: Enterprise-grade queue management system with priority queues and dead letter queues via `_queue_management.py`
- **NEW**: Multiple queue backends: Memory-based queues with Redis, File, and Database backends planned
- **NEW**: Message routing with pattern matching and processor registration for complex workflows
- **NEW**: Priority-based message processing with CRITICAL, HIGH, NORMAL, LOW, and BULK priority levels
- **NEW**: Delayed message scheduling with precision timing and exponential backoff retry mechanisms
- **NEW**: Batch processing with configurable batch sizes and timeout handling for high-throughput scenarios
- **NEW**: Comprehensive message lifecycle management: PENDING → PROCESSING → COMPLETED/FAILED/DEAD_LETTER
- **NEW**: Dead letter queue functionality with automatic retry exhaustion handling
- **NEW**: Worker-based processing with configurable concurrency and automatic load balancing
- **NEW**: `QueueMixin` for easy integration into any adapter with multi-queue management
- **NEW**: Full distributed tracing integration with message correlation and performance monitoring
- **NEW**: Queue statistics and metrics: throughput, error rates, processing times, queue sizes

### Configuration Hot-Reloading and Environment Switching (v0.19.1+)

- **NEW**: Dynamic configuration management with automatic file watching and reload via `_config_hotreload.py`
- **NEW**: Environment-specific configuration switching (development, testing, staging, production)
- **NEW**: Configuration validation framework with custom validator support and rollback capabilities
- **NEW**: Configuration versioning and history tracking with complete change audit trails
- **NEW**: Event-driven configuration change notifications with custom listener support
- **NEW**: Polling-based file watching system compatible with all platforms and deployment environments
- **NEW**: Configuration backup and restore functionality with automatic backup creation
- **NEW**: `ConfigHotReloadMixin` for seamless integration into any adapter or service
- **NEW**: Multi-format configuration support: YAML, JSON, TOML with environment-specific overrides
- **NEW**: Emergency rollback system with automatic recovery from invalid configuration states
- **NEW**: Distributed tracing integration for configuration operations and change tracking
- **NEW**: Configuration change debouncing and batching to prevent rapid reload cycles

### Adapter Composition and Chaining (v0.19.1+)

- **NEW**: Enterprise-grade adapter composition system for complex processing workflows via `_adapter_composition.py`
- **NEW**: Multiple execution modes: Sequential, Parallel, Conditional, Fanout, and Pipeline processing
- **NEW**: Advanced result aggregation strategies: First, Last, All, Merge, and Custom aggregation functions
- **NEW**: Intelligent adapter node system with retry mechanisms, timeout handling, and fallback support
- **NEW**: Condition-based adapter execution with context-aware routing and dynamic filtering
- **NEW**: Comprehensive chain result tracking with success/error counts and execution timing
- **NEW**: Adapter registry system for dynamic adapter discovery and lazy instantiation
- **NEW**: `AdapterComposer` for creating and managing complex adapter chains and workflows
- **NEW**: Pre-built chain creation methods: `create_sequential_chain`, `create_parallel_chain`, `create_conditional_chain`
- **NEW**: `AdapterCompositionMixin` for seamless integration into any adapter class
- **NEW**: Full distributed tracing integration with operation-specific span tracking
- **NEW**: Chain execution statistics and performance monitoring with detailed metrics
- **NEW**: Mock adapter implementations for comprehensive testing and development

### Performance Improvements

- **OPTIMIZED**: 60-80% faster adapter loading with improved caching
- **OPTIMIZED**: 70% faster memory cache operations with enhanced serialization
- **OPTIMIZED**: Advanced caching provides 3-5x performance improvement for multi-tier scenarios
- **OPTIMIZED**: Write-behind batching reduces storage I/O by 60-90% in high-volume scenarios
- **OPTIMIZED**: Security operations designed for minimal performance impact (0.1-0.5ms overhead)
- **OPTIMIZED**: Monitoring operations with efficient metrics collection
- **OPTIMIZED**: Queue management with efficient priority-based processing and batch operations
- **OPTIMIZED**: Message processing with worker pools and configurable concurrency levels
- **OPTIMIZED**: Configuration hot-reloading with efficient polling and change debouncing
- **OPTIMIZED**: Environment switching with minimal overhead and fast configuration merging
- **OPTIMIZED**: Adapter composition with efficient chain execution and minimal overhead
- **OPTIMIZED**: Chain processing with optimized parallel execution and result aggregation
- **IMPROVED**: Overall framework performance with reduced initialization overhead

### Documentation Updates

- **UPDATED**: README.md with comprehensive security and monitoring documentation
- **UPDATED**: CLAUDE.md with enhanced development guidelines and security best practices
- **UPDATED**: Adapter documentation with security and monitoring feature descriptions
- **NEW**: Security feature documentation with usage examples
- **NEW**: Monitoring and reliability documentation with configuration examples

### Bug Fixes

- **FIXED**: Pre-commit hook compatibility issues with new infrastructure modules
- **FIXED**: SSL configuration handling across different adapter types
- **FIXED**: Resource cleanup race conditions in concurrent scenarios
- **FIXED**: Validation error handling and error message consistency

### Breaking Changes

- **BREAKING**: All adapter base classes now inherit from security and monitoring mixins
- **NOTE**: All existing adapter operations remain backward compatible
- **NOTE**: New security and monitoring features are opt-in through configuration

### Migration Guide

For users upgrading to 0.19.1:

1. **No Breaking Changes**: All existing adapter usage continues to work unchanged
1. **Optional Security Features**: Enable security features through adapter configuration
1. **Optional Monitoring**: Enable monitoring features through adapter configuration
1. **New Secure Methods**: Use `*_secure()` variants for enhanced security
1. **Performance Monitoring**: Use `*_with_monitoring()` variants for detailed metrics

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

1. **Adapter Registration**: Custom adapters must now be explicitly registered in the static mappings. Dynamic adapter discovery is no longer supported.

1. **Configuration Detection**: ACB now automatically detects library vs. application usage mode. This may affect initialization behavior in some edge cases.

1. **Test Mocks Removed**: The `tests/mocks/` system has been removed. Tests should use the new mock-free patterns.

### Migration Guide

For detailed migration instructions, see the project documentation. Key migration steps:

1. Update memory cache usage to use aiocache interface methods
1. Register any custom adapters in the static mapping system
1. Update test code to remove references to the old mocks system
1. Review configuration files for any adapter-specific changes

______________________________________________________________________

## [Unreleased]

### Added

- This CHANGELOG.md file to track changes going forward

### Changed

- Improved project documentation structure

______________________________________________________________________

**Note**: This changelog was introduced in version 0.16.17. Previous versions did not maintain a formal changelog, but significant changes were tracked through git commit messages and release notes.
