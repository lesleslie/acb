# Hook Parser Algorithm - Visual Explanation

## Input Format

```
hook_name + padding_dots + single_space + status_marker
```

## Example Breakdown

### Example 1: Simple Hook

```
Input: "refurb................................................................ ✅"
```

**Step-by-step parsing:**

```
1. Strip whitespace:
   "refurb................................................................ ✅"
   (no change - already clean)

2. Split from RIGHT on whitespace (maxsplit=1):
   ↓
   ["refurb................................................................", "✅"]
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^
    left_part                                                           status_marker

3. Validate status marker:
   "✅" ∈ {"✅", "❌", "Passed", "Failed"} → ✅ Valid
   passed = True

4. Strip padding dots from RIGHT:
   "refurb................................................................"
   ↓
   "refurb................................................................".rstrip(".")
   ↓
   "refurb"
   ^^^^^^
   hook_name

5. Return:
   HookResult(hook_name="refurb", passed=True)
```

### Example 2: Hook with Dots in Name

```
Input: "my...custom...hook.................................................... ✅"
```

**Critical insight: Why reverse parsing works**

```
1. Split from RIGHT:
   ["my...custom...hook....................................................", "✅"]
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    left_part = hook_name + padding_dots

2. Strip dots from RIGHT only:
   "my...custom...hook...................................................."
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ (stripped)
   ↓
   "my...custom...hook"
    ^^^^^^^^^^^^^^^^^^ (preserved - not part of padding)

Result: "my...custom...hook" ✓ Correct!
```

**Why this works:**
- Padding dots are ALWAYS at the end (rightmost)
- Hook name dots are NEVER stripped because they're not at the end
- The boundary is unambiguous: first non-dot from right = end of hook name

### Example 3: Minimal Padding

```
Input: "verylonghookname.. ✅"
```

```
1. Split from RIGHT:
   ["verylonghookname..", "✅"]

2. Strip dots from RIGHT:
   "verylonghookname.." → "verylonghookname"
                      ^^ (only 2 dots stripped)

Result: "verylonghookname" ✓ Correct!
```

## Algorithm Flow Diagram

```
┌─────────────────────────────────────────────────┐
│ Input: line (string)                            │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ 1. Strip whitespace                             │
│    stripped = line.strip()                      │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ 2. Check if empty                               │
│    if not stripped:                             │
│        raise ParseError("Cannot parse empty")   │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ 3. Split from RIGHT on whitespace               │
│    parts = stripped.rsplit(maxsplit=1)          │
│                                                  │
│    Example:                                      │
│    "hook.... ✅" → ["hook....", "✅"]           │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ 4. Validate 2 parts exist                       │
│    if len(parts) != 2:                          │
│        raise ParseError("No status marker")     │
│                                                  │
│    left_part, status_marker = parts             │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ 5. Validate status marker                       │
│    if status_marker not in _ALL_MARKERS:        │
│        raise ParseError("Unknown marker")       │
│                                                  │
│    passed = (status_marker in _PASS_MARKERS)    │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ 6. Extract hook name                            │
│    hook_name = left_part.rstrip(".")            │
│                                                  │
│    Example:                                      │
│    "refurb...." → "refurb"                      │
│    "my..hook...." → "my..hook"                  │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ 7. Validate hook name exists                    │
│    if not hook_name:                            │
│        raise ParseError("Only dots")            │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│ 8. Return result                                │
│    return HookResult(hook_name, passed)         │
└─────────────────────────────────────────────────┘
```

## Edge Case Handling

### Case 1: Triple Dots in Name

```
Input: "my...custom...hook.................................................... ❌"

Parse flow:
  rsplit → ["my...custom...hook....................................................", "❌"]
  rstrip → "my...custom...hook"
           ^^^ ^^^^^^^ ^^^^ (preserved)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ (stripped)

Result: hook_name="my...custom...hook", passed=False ✓
```

### Case 2: Very Long Name (Minimal Padding)

```
Input: "very.long.hook.name.with.many.segments.for.testing.purposes...... ✅"

Parse flow:
  rsplit → ["very.long.hook.name.with.many.segments.for.testing.purposes......", "✅"]
  rstrip → "very.long.hook.name.with.many.segments.for.testing.purposes"
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ (preserved)
                                                                   ^^^^^^ (stripped)

Result: hook_name="very.long.hook.name.with.many.segments.for.testing.purposes" ✓
```

### Case 3: Error - No Space Before Marker

```
Input: "refurb................................................................✅"

Parse flow:
  rsplit → ["refurb................................................................✅"]
           (only 1 part - no space found!)

Error: ParseError("Line has no space-separated status marker")
```

### Case 4: Error - Only Status Marker

```
Input: "✅"

Parse flow:
  rsplit → ["✅"]
           (only 1 part - no space)
  Check if part is a marker → Yes, it's "✅"

Error: ParseError("No hook name found before status marker")
```

## Complexity Analysis

### Time Complexity: O(n)

```
Operation                    | Complexity | Notes
----------------------------|------------|---------------------------
line.strip()                | O(n)       | Single pass
stripped.rsplit(maxsplit=1) | O(n)       | Single pass from right
status_marker in set        | O(1)       | Hash lookup
left_part.rstrip(".")       | O(k)       | k = padding length (small)
----------------------------|------------|---------------------------
Total                       | O(n)       | Linear in line length
```

### Space Complexity: O(n)

```
Variable       | Size | Notes
---------------|------|--------------------------------
stripped       | O(n) | Copy of input
parts          | O(n) | Two substrings (references)
hook_name      | O(n) | Substring reference
HookResult     | O(n) | Contains hook_name string
```

## Why Reverse Parsing Beats Regex

### Regex Attempt

```python
# Naive regex pattern
pattern = r'^(.+?)(\.+)\s+(✅|❌|Passed|Failed)$'

# Problem: Ambiguity for "my...hook....."
# Does (.+?) match:
#   - "my" (then (\.+) = "...hook.....")?  ❌ Wrong
#   - "my...hook" (then (\.+) = ".....")?  ✓ Correct
#
# Regex engine must backtrack to find correct split!
# Complexity: O(n²) in worst case
```

### Our Approach

```python
# Reverse parsing - no ambiguity
parts = line.rsplit(maxsplit=1)  # Always finds last space
hook_name = parts[0].rstrip(".")  # Always strips trailing dots

# Why it works:
# 1. Status marker position is FIXED (right end)
# 2. Padding dots are ALWAYS trailing (rightmost)
# 3. No need to guess where padding starts
# Complexity: O(n) guaranteed
```

## Key Insights

1. **Direction matters**: Parsing right-to-left eliminates ambiguity
2. **Fixed boundaries**: Status marker is always at the end
3. **Deterministic padding**: Padding dots are always trailing
4. **Simple operations**: `rsplit()` + `rstrip()` > complex regex
5. **Performance**: O(n) guaranteed vs O(n²) regex backtracking

## Visual: Why Left-to-Right Fails

```
Input: "my...custom...hook.................................................... ✅"

Left-to-right attempt:
  "my...custom...hook.................................................... ✅"
   ↑                                                                      ↑
   Start here                                                    Must find this first!

   Problem: Where does the hook name end?
   - After "my"? → No, too short
   - After "my...custom"? → No, still padding
   - After "my...custom...hook"? → Yes! But how do we know?

   Need to scan entire string first to find status marker position!

Reverse parsing (our approach):
  "my...custom...hook.................................................... ✅"
   ↑                                                                      ↑
   Find this by stripping dots                              Start here (known position)

   Steps:
   1. Find status marker: ✅ (at end - known position)
   2. Strip trailing dots: "my...custom...hook" (unambiguous)
   3. Done!
```

## Comparison Summary

| Aspect | Regex | Left-to-Right | Reverse (Ours) |
|--------|-------|---------------|----------------|
| **Ambiguity** | High (backtracking) | High (boundary unclear) | None (fixed positions) |
| **Complexity** | O(n²) worst case | O(n) with lookahead | O(n) guaranteed |
| **Readability** | Low (complex pattern) | Medium | High (simple steps) |
| **Edge cases** | Hard to handle | Requires scanning | Natural handling |
| **Performance** | Variable | Good | Optimal |

**Winner: Reverse Parsing** ✓
