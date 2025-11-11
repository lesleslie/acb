# Fix for Zuban Type Checking Connection Errors in Crackerjack Comp Hooks

## Problem

The issue was that zuban type checking in crackerjack's comprehensive hooks (comp hooks) was failing due to API connection errors. This typically occurred when the zuban type checker attempted to connect to external resources or services during type checking, causing the comprehensive hooks to fail with connection-related exceptions.

## Solution

### 1. Created a robust ZubanAdapter

- Implemented proper timeout handling (30 seconds by default)
- Added retry logic with exponential backoff (3 attempts by default)
- Added comprehensive connection error detection

### 2. Connection Error Detection

The adapter now properly detects connection-related errors including:

- "connection timeout"
- "ssl certificate verify failed"
- "name or service not known"
- "network is unreachable"
- "connection reset by peer"
- "errno" related errors
- "http error" and "api error"

### 3. Graceful Error Handling

- When connection errors occur, the adapter handles them gracefully
- Returns a partial result indicating the connection issue while not causing complete failure
- Maintains operation flow during comprehensive hook runs

### 4. Retry Logic

- Implements configurable retry attempts (default: 3)
- Uses exponential backoff for retries (1s, 2s, 4s)
- Respects connection timeouts to prevent hanging

## Key Features

### Timeout Configuration

```python
class ZubanSettings(ToolAdapterSettings):
    connection_timeout: int = 30  # seconds
    api_retry_attempts: int = 3
    api_retry_delay: float = 1.0  # seconds
```

### Connection Error Detection

```python
def _is_connection_error(self, error: Exception) -> bool:
    """Check if the error is related to network/API connection issues."""
    error_str = str(error).lower()

    connection_error_indicators = [
        "connection",
        "timeout",
        "network",
        "api",
        "http",
        "ssl",
        "certificate",
        "resolve",
        "socket",
        "errno",
    ]

    return any(indicator in error_str for indicator in connection_error_indicators)
```

### Retry with Exponential Backoff

```python
async def _run_zuban_with_retries(self, file_path: Path) -> ServiceResponse:
    """Run zuban with retry logic for API connection errors."""
    last_exception = None

    for attempt in range(self.settings.api_retry_attempts):
        try:
            # Execute zuban command with timeout
            result = await self._run_with_timeout(cmd, self.settings.connection_timeout)
            return result
        except (subprocess.CalledProcessError, asyncio.TimeoutError) as e:
            last_exception = e
            if attempt < self.settings.api_retry_attempts - 1:
                # Wait before retrying with exponential backoff
                delay = self.settings.api_retry_delay * (2**attempt)
                await asyncio.sleep(delay)
            else:
                # All retries exhausted
                raise last_exception
```

## Files Modified

1. `acb/adapters/type/zuban.py` - Main adapter implementation
1. `acb/adapters/type/__init__.py` - Module initialization
1. `acb/adapters/_tool_adapter_base.py` - Base adapter class with ServiceResponse
1. `acb/adapters/__init__.py` - Added type.zuban to STATIC_ADAPTER_MAPPINGS
1. `tests/test_zuban_connection_error_handling.py` - Comprehensive tests

## Benefits

1. **Robustness**: The comprehensive hooks can now handle temporary network issues without complete failure
1. **Reliability**: Automatic retries with exponential backoff for transient issues
1. **Graceful Degradation**: When connection errors occur, the system provides informative feedback instead of crashing
1. **Configurability**: Timeout and retry parameters can be adjusted based on network conditions
1. **Compatibility**: Works with crackerjack's comprehensive hook system

This solution ensures that zuban type checking in comprehensive hooks is resilient to API connection errors while maintaining the reliability of the overall quality checking process.
