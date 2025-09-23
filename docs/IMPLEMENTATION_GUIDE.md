# Implementation Guide

This document contains detailed implementation guidance for developers working on AgenticAuthor features.

## Generation System Implementation

### Prompt Templates (Jinja2)

#### Premise Generation Template
```jinja2
Generate a compelling fiction premise for the {{ genre }} genre.

{% if user_input %}
Build upon this concept: {{ user_input }}
{% endif %}

REQUIREMENTS:
1. 2-3 sentences that capture the core conflict
2. Clear protagonist and stakes
3. Unique hook that sets it apart

TAXONOMY SELECTIONS (choose relevant):
{{ taxonomy | format_options }}

Return as JSON:
{
    "premise": "...",
    "taxonomySelections": {...}
}
```

#### Treatment Generation Template
```jinja2
Based on this premise:
{{ premise }}

Generate a detailed story treatment that:
1. Expands the world and characters
2. Outlines the three-act structure
3. Maintains the core premise essence
4. Target length: {{ target_words }} words

Include:
- Act breakdowns
- Major plot points
- Character arcs
- Thematic elements
```

### Token Management

#### Dynamic Token Calculation
```python
def calculate_max_tokens(model_id: str, input_tokens: int) -> int:
    """
    Dynamic token calculation based on context window.

    Formula: context_limit - input_tokens - safety_buffer
    Safety buffer: max(input_tokens * 0.2, 2000)
    """
    model_context = get_model_context_limit(model_id)
    safety_buffer = max(input_tokens * 0.2, 2000)
    return model_context - input_tokens - safety_buffer
```

### Error Recovery Patterns

#### Exponential Backoff for API Calls
```python
async def api_call_with_retry(func, max_retries=3):
    """Retry with exponential backoff: [1, 2, 4, 8] seconds."""
    delays = [1, 2, 4, 8]

    for attempt in range(max_retries):
        try:
            return await func()
        except APIError as e:
            if not e.retryable or attempt == max_retries - 1:
                raise

            delay = delays[min(attempt, len(delays) - 1)]
            await asyncio.sleep(delay)

    raise APIError("Max retries exceeded")
```

#### SSE Stream Parsing
```python
async def parse_sse_stream(response):
    """Parse Server-Sent Events stream from OpenRouter."""
    content = ""

    async for line in response.content:
        line = line.decode('utf-8').strip()

        if not line or not line.startswith('data: '):
            continue

        if line == 'data: [DONE]':
            break

        try:
            data_str = line[6:]  # Remove 'data: ' prefix
            data = json.loads(data_str)

            # Extract token from delta
            if 'choices' in data and data['choices']:
                choice = data['choices'][0]
                if 'delta' in choice and 'content' in choice['delta']:
                    token = choice['delta']['content']
                    content += token
                    yield token
        except json.JSONDecodeError:
            continue

    return content
```

### Caching Strategy

#### Model List Caching
```python
class ModelCache:
    """Cache model list with 1-hour TTL."""

    def __init__(self, cache_dir: Path):
        self.cache_file = cache_dir / "models.json"
        self.ttl = 3600  # 1 hour in seconds

    def get(self) -> Optional[List[Model]]:
        """Get cached models if fresh."""
        if not self.cache_file.exists():
            return None

        with open(self.cache_file) as f:
            data = json.load(f)

        cached_time = datetime.fromisoformat(data['cached_at'])
        if (datetime.now() - cached_time).total_seconds() > self.ttl:
            return None  # Cache expired

        return [Model(**m) for m in data['models']]

    def set(self, models: List[Model]):
        """Cache model list."""
        data = {
            'cached_at': datetime.now().isoformat(),
            'models': [m.dict() for m in models]
        }

        self.cache_file.parent.mkdir(exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(data, f)
```

## Model Characteristics

### Detailed Model Profiles

#### Claude Opus 4.1 (`anthropic/claude-opus-4.1`)
- **Context**: 200K tokens
- **Strengths**:
  - Literary prose quality
  - Character psychological depth
  - Nuanced dialogue
  - Complex narrative structures
- **Best For**: Final prose generation, character development
- **Temperature**: 0.7-0.9 for creativity

#### GPT-5 (`openai/gpt-5`)
- **Context**: 128K tokens
- **Strengths**:
  - Logical consistency
  - Structured storytelling
  - Reduced hallucinations
  - Rich metaphors
- **Best For**: Treatment and chapter outlines
- **Temperature**: 0.6-0.7 for balance

#### Claude Sonnet 4 (`anthropic/claude-sonnet-4`)
- **Context**: 200K tokens
- **Strengths**:
  - Natural dialogue
  - Style refinement
  - Character voice consistency
- **Best For**: Dialogue polish, style editing
- **Temperature**: 0.3-0.5 for editing

#### Gemini 2.5 Pro (`google/gemini-2.5-pro`)
- **Context**: 1M tokens
- **Strengths**:
  - Can process entire novels
  - Maintains long-term consistency
  - Cross-reference checking
- **Best For**: Full-book analysis, consistency checks
- **Temperature**: 0.5-0.7

#### Grok 4 Fast (`xai/grok-4-fast`)
- **Context**: 128K tokens
- **Strengths**:
  - Humor and wit
  - Unique voice
  - Pop culture awareness
  - Irreverent tone
- **Best For**: Comedy, satire, contemporary fiction
- **Temperature**: 0.8-0.95 for humor

## Intent Checking Implementation

### Structured JSON Intent Response
```python
async def check_intent(feedback: str, context: dict) -> dict:
    """
    Single LLM call for intent determination.

    Returns structured JSON with confidence scoring.
    """
    prompt = f"""
    Story Context:
    - Current: {context['current_file']}
    - Beats: {context.get('beats', 'N/A')}
    - Stats: {context.get('stats', {})}

    User Feedback: "{feedback}"

    Analyze the user's intent and return JSON:
    {{
        "confidence": 0.0-1.0,  // How certain you are
        "action": "string",      // What to do (if confidence > 0.8)
        "target": "string",      // What to modify
        "description": "string", // Human-readable description
        "clarification": "string", // Question to ask (if confidence <= 0.8)
        "options": []            // Suggested options (if unclear)
    }}
    """

    response = await client.json_completion(
        prompt=prompt,
        temperature=0.1,  # Low temperature for consistency
        max_tokens=500
    )

    return response
```

### Confidence Thresholds
- **High (>0.8)**: Execute immediately
- **Medium (0.5-0.8)**: Ask for confirmation
- **Low (<0.5)**: Request clarification with options

## Testing Strategy

### Integration Test Example
```python
import pytest
from pathlib import Path

@pytest.mark.asyncio
async def test_full_generation_pipeline():
    """Test complete LOD3 → LOD2 → LOD0 generation."""

    # Setup
    project = Project.create(Path("test_book"))
    client = OpenRouterClient()

    # Generate premise
    premise_gen = PremiseGenerator(client)
    premise = await premise_gen.generate(
        user_input="A story about time travel",
        genre="scifi"
    )
    assert premise.text
    assert premise.taxonomy_selections

    # Generate treatment
    treatment_gen = TreatmentGenerator(client)
    treatment = await treatment_gen.generate(
        premise=premise,
        target_words=2000
    )
    word_count = len(treatment.text.split())
    assert 1500 < word_count < 2500

    # Generate chapter outlines
    chapter_gen = ChapterGenerator(client)
    outline = await chapter_gen.generate(
        treatment=treatment,
        chapter_count=None  # Auto-calculate
    )
    assert len(outline.chapters) > 0

    # Generate prose for first chapter
    prose_gen = ProseGenerator(client)
    chapter_1 = await prose_gen.generate_chapter(
        chapter_beats=outline.chapters[0].beats,
        chapter_num=1,
        treatment=treatment
    )
    assert len(chapter_1.split()) > 1000

    # Verify git commits
    git = GitManager(project.path)
    log = git.log(limit=4)
    assert "Generate premise" in log
    assert "Generate treatment" in log
```

### Mock API Response for Testing
```python
def mock_streaming_response():
    """Generate mock SSE stream for testing."""
    responses = [
        'data: {"choices": [{"delta": {"content": "Once "}}]}',
        'data: {"choices": [{"delta": {"content": "upon "}}]}',
        'data: {"choices": [{"delta": {"content": "a "}}]}',
        'data: {"choices": [{"delta": {"content": "time"}}]}',
        'data: [DONE]'
    ]

    for response in responses:
        yield response.encode('utf-8') + b'\n'
```

## Performance Optimization

### Parallel Chapter Generation
```python
async def generate_chapters_parallel(outline, treatment):
    """Generate independent chapters concurrently."""
    tasks = []

    for chapter in outline.chapters:
        if chapter.is_independent:  # No dependency on previous chapters
            task = generate_chapter(chapter, treatment)
            tasks.append(task)

    results = await asyncio.gather(*tasks)
    return dict(zip(range(len(results)), results))
```

### Token Usage Tracking
```python
class TokenTracker:
    """Track token usage and costs across requests."""

    def __init__(self):
        self.usage = defaultdict(lambda: {'tokens': 0, 'cost': 0})

    def track(self, model: str, prompt_tokens: int, completion_tokens: int):
        """Update usage statistics."""
        cost = calculate_cost(model, prompt_tokens, completion_tokens)

        self.usage[model]['tokens'] += prompt_tokens + completion_tokens
        self.usage[model]['cost'] += cost

        self.usage['total']['tokens'] += prompt_tokens + completion_tokens
        self.usage['total']['cost'] += cost

    def get_summary(self) -> dict:
        """Get usage summary."""
        return dict(self.usage)
```

## Git Commit Message Formats

### Standard Formats
```
Generate premise: [brief description]
Generate treatment from premise (2500 words)
Generate chapter outlines (12 chapters)
Generate chapter 3 prose: The Confrontation
Iterate treatment: make villain more sympathetic
Iterate chapter 5: add dialogue to confrontation
Polish chapter 7: grammar and pacing
Analyze: commercial viability at abc123d
Export: markdown format
Rollback: revert chapter 5 changes
```

### Automated Message Generation
```python
def generate_commit_message(action: str, target: str, details: dict) -> str:
    """Generate standardized commit message."""

    templates = {
        'generate': "Generate {target}: {description}",
        'iterate': "Iterate {target}: {change}",
        'polish': "Polish {target}: {improvements}",
        'analyze': "Analyze: {analysis_type} at {sha}",
        'export': "Export: {format} format",
        'rollback': "Rollback: {reason}"
    }

    template = templates.get(action, "{action} {target}")
    return template.format(target=target, **details)
```