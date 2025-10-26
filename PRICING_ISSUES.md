# Model Pricing Issues Analysis

## Issue 1: `/models` Display Shows Wrong Pricing

**Location:** `src/cli/interactive.py` lines 909-911

**Current Code:**
```python
# Convert price from per 1K to per 1M tokens
input_price = model.cost_per_1k_tokens * 1000
# Assume output is 2x input price (typical for most models)
output_price = model.cost_per_1k_tokens * 2000
```

**Problems:**
1. Uses `cost_per_1k_tokens` which **averages** input+output costs: `(prompt + completion) / 2`
2. Then **makes up** output as "2x input"
3. Results in completely wrong displayed pricing

**Example (Claude Sonnet 4.5):**
- **Actual:** $3/1M input, $15/1M output (5x ratio)
- **Displayed:** $9/1M input, $18/1M output (averaged, then made up 2x)

We have the correct data (`model.pricing.prompt` and `model.pricing.completion`) but aren't using it!

## Issue 2: `cost_per_1k_tokens` Property is Misleading

**Location:** `src/api/models.py` lines 39-41

**Current Code:**
```python
@property
def cost_per_1k_tokens(self) -> float:
    """Get average cost per 1k tokens."""
    return (self.pricing.prompt + self.pricing.completion) / 2
```

**Problem:**
- Averaging input and output costs is meaningless
- Different models have different input:output ratios
- Claude Sonnet 4.5: 5x ratio (output is 5x more expensive)
- Some models: 2x ratio
- o1/o3: Even higher for reasoning tokens

**Used in:**
- Line 813: Model selection display (averaging)
- Line 891: Sorting models (using average is misleading)

## What's Actually Correct

### 1. Data Fetching (✅ Correct)

`src/api/openrouter.py` lines 137-141:
```python
pricing = ModelPricing(
    prompt=float(pricing_data.get('prompt', 0)) * 1000,  # per token -> per 1k tokens
    completion=float(pricing_data.get('completion', 0)) * 1000,
    request=float(pricing_data.get('request', 0)) if 'request' in pricing_data else None
)
```

✅ Correctly converts from per-token to per-1k-tokens
✅ Preserves separate input/output pricing

### 2. Cost Calculation (✅ Correct)

`src/api/models.py` lines 43-56:
```python
def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_cost = (prompt_tokens / 1000) * self.pricing.prompt
    completion_cost = (completion_tokens / 1000) * self.pricing.completion
    return prompt_cost + completion_cost
```

✅ Uses actual prompt_tokens and completion_tokens
✅ Uses separate pricing for each
✅ Math is correct

## Example: Claude Sonnet 4.5

**OpenRouter API returns:**
```json
"pricing": {
  "prompt": "0.000003",     // $0.000003 per token
  "completion": "0.000015"   // $0.000015 per token
}
```

**We convert to:**
```python
pricing.prompt = 0.003      # $0.003 per 1k tokens = $3 per 1M tokens
pricing.completion = 0.015  # $0.015 per 1k tokens = $15 per 1M tokens
```

**Actual cost for 100k input + 10k output:**
```
Input:  100,000 tokens * $0.003/1k = $0.30
Output:  10,000 tokens * $0.015/1k = $0.15
Total: $0.45
```

**What we currently display:**
```
Input:  $9/1M  (wrong - averaged then displayed)
Output: $18/1M (wrong - made up 2x assumption)
```

**What we should display:**
```
Input:  $3/1M  (correct - actual pricing.prompt * 1000)
Output: $15/1M (correct - actual pricing.completion * 1000)
```

## Solution

1. **Fix `/models` display** - use actual `pricing.prompt` and `pricing.completion`
2. **Remove misleading `cost_per_1k_tokens` property** - not useful when input≠output
3. **Fix model selection display** - show "Input: $X/1M, Output: $Y/1M" format
4. **Fix model sorting** - sort by input cost (or let user choose)
