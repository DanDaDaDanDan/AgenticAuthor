# Copy Editing Truncation Analysis

## Problem Statement
Copy editing consistently fails across **multiple Claude models** (Opus 4.1, Sonnet 4.5) and gpt-5-pro with JSON parsing errors at position ~9760.

## Evidence from Logs (2025-10-25)

### Failure Pattern
- **Chapter 5 failures:** 10:45:15, 10:59:40 (Claude Opus 4.1)
- **Chapter 7 failure:** 15:36:55 (Claude Opus 4.1)
- **Consistent error position:** ~9760 chars into line 2
- **Error type:** `Expecting ',' delimiter: line 2 column 9760`
- **Content received:** ~23,000 chars (full response)
- **finish_reason:** `stop` (completed normally)

### Key Findings from Debug Files

#### File: `.agentic/debug/truncated_json_1761403515.json`
```json
{
  "edited_chapter": "...call the firemen back?\\" \n\n\"What..."
}
```

**Problem:** Literal newline characters in JSON string value at position 9760!

#### Validation Test
```bash
node -e "const fs = require('fs'); JSON.parse(fs.readFileSync('...', 'utf-8'));"
# ERROR: Expected ',' or '}' after property value in JSON at position 9762 (line 2 column 9760)
```

**Root Cause:** The JSON contains LITERAL newlines instead of escaped `\n` sequences.

### What Should Happen
```json
"...call the firemen back?\"\n\n\"What..."
```
OR (if LLM is generating dialogue with escaped quotes):
```json
"...call the firemen back?\\\"\\n\\n\\\"What..."
```

### What Is Happening
```json
"...call the firemen back?\\" \n\n\"What..."
```
Note the space after `\\"` followed by LITERAL newline characters!

## Analysis

### NOT the Issue
1. ❌ Model reliability (happens across Opus, Sonnet, gpt-5-pro)
2. ❌ Context limits (105k prompt tokens is well under limits)
3. ❌ Empty responses (we're getting full 23k char responses)
4. ❌ Timeouts (finish_reason=stop, clean completion)
5. ❌ Output token limits (only ~6k-8k tokens generated)

### Likely Causes

#### Theory 1: LLM Generating Invalid JSON
The model itself is generating JSON with literal newlines in string values, possibly because:
- The prose content contains complex dialogue with quotes
- The model is not properly escaping the inner quotes and newlines
- At position ~9760, there's dialogue that trips up the JSON generation

#### Theory 2: SSE Stream Corruption
When OpenRouter streams the JSON via Server-Sent Events:
- The escape sequences are being corrupted during transmission
- Literal newlines are being injected into the stream
- Our accumulation code (`full_content += token`) is preserving these literal newlines

#### Theory 3: Our Stream Reconstruction Bug
In `streaming.py` line 189:
```python
full_content += token
```
We accumulate tokens without validation. If the SSE stream sends:
```
data: {"choices":[{"delta":{"content":"\\" }}]}
data: {"choices":[{"delta":{"content":" "}}]}
data: {"choices":[{"delta":{"content":"\n"}}]}  # LITERAL newline in JSON?
```

Our code would concatenate these directly, creating invalid JSON.

### Position 9760 Significance
This position consistently appears in chapter 5 copy editing:
- The prose content at this position contains dialogue
- Example: `"...call the firemen back?"`
- This quote needs escaping: `\"`
- Followed by paragraph break: `\n\n`
- Followed by more dialogue: `"What..."`

The full sequence requiring escaping:
```
"\"\n\n\""
```

## Evidence of LLM vs Stream Issue

### From Logs
```
2025-10-25 10:45:15 - DEBUG - streaming.py:367 - Stream finish_reason: stop
2025-10-25 10:45:15 - WARNING - streaming.py:407 - === STREAM FINISHED: NO finish_reason provided by API ===
```

**Contradiction:** We logged `finish_reason: stop` at line 367, but then logged "NO finish_reason" at line 407.

This suggests:
1. We detected `finish_reason: stop` in the SSE stream
2. But when we reached the end, `finish_reason` variable was `None`
3. Possible variable scoping issue in our code

### reserve_tokens Configuration
Copy editing sets `reserve_tokens=8000` in `copy_editor.py:304`.
- This should reserve 8000 tokens for output
- But we're only getting ~6000 tokens of actual content
- This suggests we're NOT hitting output limits

## Proposed Solutions

### 1. Enhanced Debug Logging (Immediate)
Capture MORE information when this happens:
- Save raw SSE events to debug file
- Log each token as it arrives
- Track escape sequence patterns
- Detect literal newlines in accumulation

### 2. Stream Validation (Medium Priority)
Add validation during stream accumulation:
```python
if '\n' in token and in_json_string:
    logger.warning("LITERAL NEWLINE in JSON string token!")
    # Should this be \\n instead?
```

### 3. JSON Repair (Workaround)
Enhance `_repair_json_escaping()` to detect and fix:
- Literal newlines in string values
- Missing escape sequences after dialogue quotes
- Pattern: `\\" \n\n\"` → `\\"\n\n\"`

### 4. Alternative Response Format
Instead of JSON with huge string values, use:
- Streaming plain text with markers
- Post-process into structured format
- Avoids JSON escaping issues entirely

### 5. Model-Specific Handling
Test if issue is model-specific:
- Try with different models
- Compare escape handling across providers
- Adjust prompt to guide JSON generation

## Next Steps

1. **Add comprehensive SSE event logging** to capture raw stream data
2. **Implement validation** during token accumulation
3. **Enhance JSON repair** to handle this specific pattern
4. **Test with smaller chapters** to see if size matters
5. **Compare successful vs failed sessions** to find pattern differences

## Files to Modify

1. `src/api/streaming.py` - Add SSE event logging, validation
2. `src/generation/copy_editor.py` - Add fallback strategies
3. New: `src/api/sse_debugger.py` - Dedicated SSE event capture tool
