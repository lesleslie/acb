# ACB Test Coverage Summary

## Overall Coverage: 34% (18,170 / 27,700 lines)

### Coverage by Module

```
acb/
├── actions/                          ████████████████████░░░░░░░░░░░░ 95%
├── adapters/
│   ├── ai/                          ██████████░░░░░░░░░░░░░░░░░░░░░░ 55%
│   ├── embedding/                   ████████░░░░░░░░░░░░░░░░░░░░░░░░ 40%
│   ├── messaging/                   ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 20%
│   ├── models/                      ██████████░░░░░░░░░░░░░░░░░░░░░░ 65%
│   ├── reasoning/                   █████████░░░░░░░░░░░░░░░░░░░░░░░ 45%
│   ├── smtp/                        ███████░░░░░░░░░░░░░░░░░░░░░░░░░ 35%
│   ├── sql/                         ███████████░░░░░░░░░░░░░░░░░░░░░ 60%
│   └── vector/                      ██████████████░░░░░░░░░░░░░░░░░░ 70%
├── core/                            ██████████████████░░░░░░░░░░░░░░ 85%
├── events/                          █████░░░░░░░░░░░░░░░░░░░░░░░░░░░ 25%
├── mcp/                             ██████████░░░░░░░░░░░░░░░░░░░░░░ 50%
├── queues/                          ██████░░░░░░░░░░░░░░░░░░░░░░░░░░ 30%
├── services/                        ███████░░░░░░░░░░░░░░░░░░░░░░░░░ 35%
└── workflows/                       █████████░░░░░░░░░░░░░░░░░░░░░░░ 45%
```

### Test Status

| Category | Count | Status |
|----------|-------|--------|
| **Passing** | 1,470 | ✅ 71% |
| **Failing** | 410 | ❌ 20% |
| **Errors** | 150 | ⚠️ 7% |
| **Skipped** | 51 | ⏭️ 2% |
| **Total** | 2,081 | - |

### Coverage Rating by Component

**Excellent (80%+)**

- ✅ actions/ - 95% coverage
- ✅ core/ - 85% coverage

**Good (60-79%)**

- ✅ vector/ - 70% coverage
- ✅ models/ - 65% coverage
- ✅ sql/ - 60% coverage

**Fair (40-59%)**

- ⚠️ ai/ - 55% coverage
- ⚠️ mcp/ - 50% coverage
- ⚠️ reasoning/ - 45% coverage
- ⚠️ workflows/ - 45% coverage

**Poor (20-39%)**

- ❌ services/ - 35% coverage
- ❌ smtp/ - 35% coverage
- ❌ embedding/ - 40% coverage
- ❌ queues/ - 30% coverage
- ❌ events/ - 25% coverage
- ❌ messaging/ - 20% coverage

### Not Analyzed (Optional Adapters)

These adapters require additional dependencies and weren't included in the baseline coverage analysis:

- cache/ (Redis, Memory)
- dns/ (Cloud DNS, Cloudflare, Route53)
- ftpd/ (FTP, SFTP)
- graph/ (Neo4j, ArangoDB)
- logger/ (Loguru, Structlog)
- monitoring/ (Sentry, Logfire)
- nosql/ (MongoDB, Firestore)
- requests/ (HTTPX, Niquests)
- secret/ (Infisical, GCP, Azure)
- storage/ (S3, GCS, Azure, File)
- templates/ (Jinja2)

## High-Impact Improvement Opportunities

### Quick Wins (< 2 hours each)

1. **Fix Events System Initialization** → +15-20% coverage
1. **Complete Services Layer** → +12-18% coverage
1. **Fix Queue Operations** → +10-15% coverage

### Medium Effort (2-4 hours each)

4. **Enhance AI Adapter Tests** → +5-10% coverage
1. **Complete Reasoning Tests** → +8-12% coverage
1. **Add Message Adapter Tests** → +8-12% coverage

### Planned Work

7. **Install Cache Adapter Dependencies** → +8-12% coverage
1. **Add Storage Adapter Tests** → +10-15% coverage
1. **Complete Optional Adapters** → +15-25% coverage

## Test Failure Hotspots

### By Frequency

1. **Event System** - 60+ failures
1. **Services Module** - 50+ failures
1. **SQL Adapters** - 40+ failures
1. **Reasoning Adapters** - 35+ failures
1. **Message Adapters** - 20+ failures

### Common Patterns

- **Missing Attributes** - 45% of failures
- **Import Errors** - 30% of failures
- **Logic Errors** - 15% of failures
- **Not Implemented** - 10% of failures

## Improvement Timeline

```
Week 1: Foundation
├─ Fix Event System (60 test fixes)
├─ Fix Services Layer (50 test fixes)
└─ Fix Queue System (30 test fixes)
   → Target: 40% coverage

Week 2: Adapters
├─ Cache Adapter Tests (20 tests)
├─ Storage Adapter Tests (25 tests)
└─ Messaging Adapter Tests (15 tests)
   → Target: 50% coverage

Week 3: Integration
├─ Add Integration Tests (30 tests)
├─ Edge Case Coverage (20 tests)
└─ Performance Tests (10 tests)
   → Target: 60%+ coverage
```

## Next Steps

1. ✅ **Read TEST_COVERAGE_ANALYSIS.md** for detailed improvement plan
1. 📝 **Start with Events Module** - highest impact, clear patterns
1. 🧪 **Use test patterns from repository/** as templates
1. 📊 **Track progress weekly** - aim for +5-10% coverage gain per week
1. 🚀 **Deploy improvements** - run `python -m crackerjack -t --ai-fix` after changes

## Commands for Ongoing Coverage Monitoring

```bash
# Run tests with coverage report
python -m pytest --cov=acb --cov-report=html --cov-report=term-missing

# Generate HTML coverage report (opens in browser)
coverage html && open htmlcov/index.html

# Run specific test category
python -m pytest tests/events/ -v --cov=acb.events

# Run with detailed failure info
python -m pytest --tb=short -v 2>&1 | grep -E "FAILED|ERROR"
```

## Files to Review

- **Main Analysis:** `TEST_COVERAGE_ANALYSIS.md`
- **This Summary:** `COVERAGE_SUMMARY.md`
- **Test Infrastructure:** `tests/TESTING.md`
- **Project Guidelines:** `CLAUDE.md`
