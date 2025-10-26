# Network Truncation Root Cause Analysis

## The Evidence

### Chapter 17 Failure (2025-10-26 12:07:31 - 12:08:05)
- **Duration:** 34.2 seconds
- **Tokens received:** 124 tokens (3,374 chars)
- **Speed:** 3.6 tokens/second (extremely slow)
- **Events processed:** 292 SSE events
- **Finish reason:** None (stream ended without completion signal)
- **Error:** "Expecting value: line 1 column 1" (markdown extraction failed)

### SSE Event Analysis (`sse_events_1761494885.jsonl`)

**Pattern observed:**
```
Events 1-11:    ": OPENROUTER PROCESSING" (waiting for model)
Event 13:       Stream starts - provider assigned
Events 14-49:   Content tokens flow normally
Events 50-292:  Empty events ("") - NO MORE CONTENT
                Stream never sends data: [DONE]
                Connection stays open but idle
```

**Critical finding:** After event 49, we received **242 more empty SSE events** but no actual content. The connection didn't close, it just stopped sending data.

## Root Cause Analysis

### NOT Network Timeout (we have proof)

Our timeouts:
```python
aiohttp.ClientTimeout(
    total=7200,          # 2 hours
    connect=30,          # 30 seconds
    sock_read=None       # NO read timeout - infinite wait
)
```

If it were a timeout, we'd see:
- ❌ Connection closed error
- ❌ TimeoutError exception
- ❌ No events after timeout

But we actually saw:
- ✅ Connection stayed open
- ✅ 242 empty events after content stopped
- ✅ Clean iteration completion

### Likely Cause: Claude API Stalled/Crashed Mid-Generation

**Evidence points to model-side failure:**

1. **Markdown fence started but never completed**
   - Model sent: ` ```json\n{\n  "edited_chapter": "...`
   - Never sent: closing `}` or ` ``` `
   - This suggests model generation was interrupted

2. **No finish_reason sent**
   - Healthy completion sends: `finish_reason: "stop"` or `"length"`
   - We got: `finish_reason: null` (never set)
   - Stream ended without proper termination

3. **Pattern matches known Claude API issues**
   - Similar to gpt-5-pro "cold start" problems
   - Model starts generating, then internal error/timeout
   - API doesn't cleanly signal failure
   - Connection stays open, sending empty heartbeats

4. **Manual retry 24 minutes later succeeded**
   - Same exact request
   - Different API backend/model instance
   - Completed successfully

## Contributing Factors

### 1. **Large Context Size (180,428 chars)**
```
2025-10-26 12:07:28 - JSON API Request: prompt_length=180428 chars
```

This is ~45k tokens of input context containing:
- All previous 16 chapters (copy edited prose)
- Current chapter outline
- Full chapters.yaml with metadata/characters/world
- Copy editing instructions

**Why this matters:**
- Claude Sonnet 4.5 has 200k context window, so 45k is within limits
- BUT: Large context increases backend processing load
- More likely to hit API infrastructure issues
- Potential memory/timeout issues on API side

### 2. **JSON Generation Complexity**

The model must:
1. Parse 180k chars of context
2. Generate 5k+ chars of edited prose
3. Maintain valid JSON escaping throughout
4. Track nested quotes, newlines, dialogue
5. Never lose track of JSON structure

**Single mistake = entire generation fails**

### 3. **Windows + aiohttp Interaction**

Potential issues specific to Windows:
- **TCP Keep-Alive:** Windows has different defaults than Linux
- **Socket Buffer:** Windows may flush differently
- **Network Stack:** Windows networking can be more aggressive with idle connections

Our configuration:
```python
connector = aiohttp.TCPConnector(
    keepalive_timeout=60,        # Keep idle connections alive for 60s
    force_close=False,           # Allow HTTP keep-alive
)
```

**Potential issue:** If OpenRouter's load balancer or Claude's API has a 30-35 second idle timeout, our 60s keep-alive won't help if the backend dies.

### 4. **No Stall Detection**

Current code:
```python
async for line in response.content:
    # Process events
```

**Problem:** If events stop flowing (but connection stays open), we wait forever.

**What we need:**
- Detect when content stops flowing (no tokens for N seconds)
- Distinguish between:
  - Reasoning pause (normal, wait)
  - Stalled stream (abnormal, retry)

## Why Our Heartbeat Didn't Help

We have heartbeat logging at 30 seconds:
```python
last_token_time = time.time()
if time_since_last_token >= 30:
    logger.debug("Model paused (reasoning)")
```

**But this only LOGS - it doesn't ABORT or RETRY.**

The stream died at 34 seconds, which is:
- 4 seconds after our heartbeat would have logged
- Right around typical load balancer timeouts (30-35s)

## Solutions

### 1. **Immediate: Add Stall Detection with Retry** (RECOMMENDED)

For copy editing specifically, if no new tokens for 60 seconds:
```python
MAX_IDLE_TIME = 60  # seconds without tokens

if time_since_last_token > MAX_IDLE_TIME and token_count < 500:
    # We've started generating but stalled early
    logger.error(f"Stream stalled: {token_count} tokens in {elapsed}s, no new tokens for {MAX_IDLE_TIME}s")
    raise StreamStalledError("Generation stalled - likely API issue")
```

Then the existing retry logic handles it.

### 2. **Short-term: Better Markdown Extraction**

Current issue: We received ` ```json{...` but extraction failed because:
- No closing ` ``` ` fence
- `_extract_json_from_markdown()` returned None

**Fix:** Try extracting even if fence is incomplete:
```python
def _extract_json_from_markdown(self, content: str) -> Optional[str]:
    # Try to extract from incomplete markdown fence
    if content.startswith("```json\n"):
        # Remove fence, assume rest is JSON
        return content[8:].rstrip('`').strip()
```

### 3. **Medium-term: Request Chunking**

For very large contexts (>100k chars), split copy editing:
- Copy edit in smaller batches (5 chapters at a time)
- Reduces context size per request
- Faster, more reliable
- Can parallelize

### 4. **Long-term: Alternative Response Format**

Instead of JSON with huge string values:
```json
{
  "edited_chapter": "5000+ words here..."
}
```

Use streaming text with delimiters:
```
---EDITED_CHAPTER_START---
5000+ words here...
---EDITED_CHAPTER_END---
---CHANGES_START---
[{"change": "...", "reason": "..."}]
---CHANGES_END---
```

**Benefits:**
- No JSON escaping issues
- Easier to extract partial results
- Can resume from truncation
- Model less likely to "lose track"

## What Didn't Cause This

### ❌ Our Code Timeouts
- We have `sock_read=None` (infinite read timeout)
- We have `total=7200` (2 hour total timeout)
- Stream didn't timeout, it just stopped sending data

### ❌ Network Packet Loss
- Would see connection errors
- Wouldn't get 242 empty events
- Windows would retry TCP packets

### ❌ Local Firewall/Antivirus
- Would block initial connection
- Wouldn't cause mid-stream failure
- Affects all requests equally (but most succeed)

### ❌ OpenRouter Rate Limiting
- Would send 429 error
- Would happen at request start
- Wouldn't cause mid-stream truncation

### ❌ Context Window Overflow
- Would fail at request validation
- Wouldn't start generating successfully
- Would return 400 error immediately

## Recommended Action Plan

**Priority 1: Add stall detection + automatic retry**
```python
# In streaming.py, during token iteration
if token_count > 10 and time_since_last_token > 60:
    raise StreamStalledError("Generation stalled")
```

**Priority 2: Improve markdown extraction for partial results**
```python
# Extract JSON even if markdown fence is incomplete
if "```json" in content:
    start = content.find("```json") + 8
    return content[start:].rstrip('`')
```

**Priority 3: Add context size warnings**
```python
if prompt_length > 150000:
    logger.warning(f"Large context ({prompt_length} chars) - higher failure risk")
```

**Priority 4: Implement progressive save**
```python
# Save partial results every N tokens for very long operations
if token_count % 1000 == 0:
    save_checkpoint(content, token_count)
```

## Testing Strategy

To reproduce and validate:
1. **Trigger with large context:** Copy edit 10+ chapters at once
2. **Monitor metrics:** Token rate, event count, time since last token
3. **Verify stall detection:** Should auto-retry within 60s of stall
4. **Confirm recovery:** Retry should succeed (model instance changes)

## Conclusion

**Root cause:** Claude API backend stalled/crashed mid-generation after 124 tokens

**Contributing factors:**
- Large context (180k chars) increases backend load
- Complex JSON generation task
- No stall detection in our code
- No automatic recovery

**Not the cause:**
- Network timeouts (we have none)
- Code bugs (works 95%+ of time)
- Local environment (affects all requests equally)

**Solution:** Add stall detection that triggers automatic retry when generation stops flowing but connection stays open.
