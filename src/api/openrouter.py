"""OpenRouter API client implementation."""
import json
import asyncio
from typing import List, Dict, Any, Optional, Callable, Union
from datetime import datetime, timedelta, timezone
from pathlib import Path
import aiohttp
from rich.console import Console

from ..config import get_settings
from .models import Model, ModelList, ModelPricing
from .streaming import StreamHandler, TokenCounter
from .auth import validate_api_key
from ..utils.tokens import estimate_messages_tokens, calculate_max_tokens
from ..utils.session_logger import get_session_logger


class OpenRouterClient:
    """Handles all OpenRouter API interactions with caching and retry logic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        console: Optional[Console] = None
    ):
        """
        Initialize OpenRouter client.

        Args:
            api_key: Optional API key (uses environment if not provided)
            console: Optional Rich console for output
        """
        self.settings = get_settings()
        self.api_key = validate_api_key(api_key or self.settings.openrouter_api_key)
        self.base_url = self.settings.openrouter_base_url
        self.console = console or Console()
        self.stream_handler = StreamHandler(self.console)
        self.token_counter = TokenCounter()
        self._model_cache: Optional[ModelList] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def ensure_session(self):
        """Ensure aiohttp session is created with appropriate timeouts for long-running streams."""
        if not self._session:
            # Configure timeouts optimized for long-running streaming requests
            # - sock_connect: 30s max to establish connection
            # - sock_read: 120s per chunk (model can take time between tokens)
            # - total: None (no limit on total request time for long generations)
            self._session = aiohttp.ClientSession(
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(
                    total=None,          # No total timeout - allow long generations
                    connect=30,          # 30s to establish connection
                    sock_read=120        # 120s between chunks (generous for slow models)
                )
            )

    async def close(self):
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/agentic-author",
            "X-Title": "AgenticAuthor"
        }

    async def discover_models(self, force_refresh: bool = False) -> List[Model]:
        """
        Fetch available models with caching.

        Args:
            force_refresh: Force refresh even if cache is valid

        Returns:
            List of available models
        """
        # Check cache
        if not force_refresh and self._model_cache:
            cache_age = datetime.now(timezone.utc) - self._model_cache.fetched_at
            if cache_age < timedelta(hours=1):
                return self._model_cache.models

        await self.ensure_session()

        try:
            async with self._session.get(
                f"{self.base_url}/models"
            ) as response:
                response.raise_for_status()
                data = await response.json()

                models = []
                for model_data in data.get('data', []):
                    # Parse pricing - OpenRouter returns price per token in dollars
                    # We want price per 1k tokens
                    pricing_data = model_data.get('pricing', {})
                    pricing = ModelPricing(
                        prompt=float(pricing_data.get('prompt', 0)) * 1000,  # Convert to per 1k tokens
                        completion=float(pricing_data.get('completion', 0)) * 1000,  # Convert to per 1k tokens
                        request=float(pricing_data.get('request', 0)) if 'request' in pricing_data else None
                    )

                    # Create model object
                    model = Model(
                        id=model_data['id'],
                        name=model_data.get('name'),
                        description=model_data.get('description'),
                        context_length=model_data.get('context_length', 4096),
                        pricing=pricing,
                        top_provider=model_data.get('top_provider'),
                        per_request_limits=model_data.get('per_request_limits')
                    )
                    models.append(model)

                # Cache the results
                self._model_cache = ModelList(models=models)
                return models

        except aiohttp.ClientError as e:
            self.console.print(f"[red]Error fetching models: {e}[/red]")
            # Return cached models if available
            if self._model_cache:
                self.console.print("[yellow]Using cached model list[/yellow]")
                return self._model_cache.models
            # No cache available - fail early
            raise Exception(f"Failed to fetch models from OpenRouter and no cache available: {e}")

    async def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a specific model by ID.

        Args:
            model_id: Model identifier

        Returns:
            Model object or None if not found
        """
        models = await self.discover_models()
        for model in models:
            if model.id == model_id:
                return model
        return None

    async def streaming_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        on_token: Optional[Callable[[str, int], None]] = None,
        stream: bool = True,
        display: bool = True,
        min_response_tokens: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a streaming completion with the OpenRouter API.

        Args:
            model: Model ID to use
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate (auto-calculated if None)
            on_token: Optional callback for each token
            stream: Whether to stream the response
            display: Whether to display output in console
            min_response_tokens: Minimum tokens to reserve for response
            **kwargs: Additional API parameters

        Returns:
            Response data including content and usage
        """
        await self.ensure_session()

        # If max_tokens not specified, calculate based on model's context window
        if max_tokens is None:
            # Get model info to know context window and output limits
            model_obj = await self.get_model(model)
            if not model_obj:
                raise ValueError(
                    f"Model '{model}' not found in OpenRouter model list. "
                    f"Use /models to see available models, or check model ID spelling."
                )

            # Estimate prompt tokens
            prompt_tokens = estimate_messages_tokens(messages)

            # Get model's max output tokens (if specified)
            max_output_tokens = model_obj.get_max_output_tokens()

            # Debug log
            from ..utils.logging import get_logger
            debug_logger = get_logger()
            if debug_logger:
                debug_logger.debug(f"Model {model}: max_output_tokens from get_max_output_tokens() = {max_output_tokens}")
                debug_logger.debug(f"Model {model}: per_request_limits = {model_obj.per_request_limits}")
                debug_logger.debug(f"Model {model}: top_provider = {model_obj.top_provider}")

            # Calculate optimal max_tokens
            # Use model's context window, leave room for prompt + buffer
            # Cap at model's output limit if specified
            max_tokens = calculate_max_tokens(
                context_window=model_obj.context_length,
                prompt_tokens=prompt_tokens,
                min_response_tokens=min_response_tokens,
                max_response_tokens=max_output_tokens,  # Cap at model's output limit
                buffer_percentage=0.05  # 5% buffer for safety
            )

            # Log calculation for debugging
            from ..utils.logging import get_logger
            logger = get_logger()
            if logger:
                logger.debug(
                    f"Token calculation for {model}: "
                    f"context={model_obj.context_length}, "
                    f"prompt={prompt_tokens}, "
                    f"max_output={max_output_tokens}, "
                    f"calculated_max={max_tokens}"
                )

        # Prepare request data
        request_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            "max_tokens": max_tokens,
            **kwargs
        }

        # Log request BEFORE making the call
        from ..utils.logging import get_logger
        logger = get_logger()
        if logger:
            prompt_tokens_est = estimate_messages_tokens(messages)
            logger.debug(
                f"API Request: model={model}, temp={temperature}, "
                f"max_tokens={max_tokens}, stream={stream}, "
                f"prompt_tokens_est={prompt_tokens_est}"
            )

        # Retry logic for streaming errors
        max_retries = 2
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                async with self._session.post(
                    f"{self.base_url}/chat/completions",
                    json=request_data,
                    headers=self._get_headers()
                ) as response:
                    response.raise_for_status()

                    if stream:
                        # Handle streaming response with live status
                        model_display = model.split('/')[-1] if '/' in model else model
                        result = await self.stream_handler.handle_sse_stream_with_status(
                            response,
                            model_name=model_display,
                            on_token=on_token,
                            display=display,
                            display_mode=self.settings.streaming_display_mode
                        )

                        # Check if stream was interrupted
                        if result.get('finish_reason') == 'connection_error' and retry_count < max_retries:
                            retry_count += 1
                            self.console.print(f"[yellow]Retrying ({retry_count}/{max_retries})...[/yellow]")
                            await asyncio.sleep(1)  # Brief delay before retry
                            continue

                    else:
                        # Handle non-streaming response
                        data = await response.json()
                        result = {
                            'content': data['choices'][0]['message']['content'],
                            'usage': data.get('usage', {}),
                            'finish_reason': data['choices'][0].get('finish_reason'),
                            'model': data.get('model')
                        }
                        if display:
                            self.console.print(result['content'])

                    # Log API call with FULL details
                    logger = get_session_logger()
                    if logger:
                        # Extract prompt from messages for backward compatibility
                        prompt_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                        logger.log_api_call(
                            model=model,
                            prompt=prompt_text,
                            response=result.get('content', ''),
                            tokens=result.get('usage', {}),
                            error=None,
                            full_messages=messages,  # Log complete messages array
                            request_params={
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                                "stream": stream,
                                **kwargs
                            }
                        )

                    # Update token counter
                    if result.get('usage'):
                        # Calculate cost if model info is available
                        model_obj = await self.get_model(model)
                        cost = 0.0
                        if model_obj:
                            cost = model_obj.estimate_cost(
                                result['usage'].get('prompt_tokens', 0),
                                result['usage'].get('completion_tokens', 0)
                            )
                        self.token_counter.update(result['usage'], cost)

                        # Show usage if enabled
                        if self.settings.show_token_usage:
                            self._display_usage(result['usage'], cost)

                    # Stream completed successfully or non-streaming, break retry loop
                    break

            except aiohttp.ClientError as e:
                last_error = e
                if retry_count < max_retries and stream:
                    retry_count += 1
                    self.console.print(f"[yellow]Connection error: {e}[/yellow]")
                    self.console.print(f"[yellow]Retrying ({retry_count}/{max_retries})...[/yellow]")
                    await asyncio.sleep(1)
                    continue
                else:
                    # Max retries reached or non-streaming error
                    self.console.print(f"[red]API Error: {e}[/red]")

                    # Log the error with FULL request details
                    session_logger = get_session_logger()
                    if session_logger:
                        session_logger.log_api_error(
                            model=model,
                            error=e,
                            request_params={
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                                "stream": stream,
                                **kwargs
                            },
                            full_messages=messages  # Log complete messages array
                        )

                    raise

        # Return the result after successful completion or retries
        return result

    async def completion(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        display: bool = True,
        min_response_tokens: int = 100,
        **kwargs
    ) -> str:
        """
        Simple completion interface.

        Args:
            model: Model ID to use
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate (auto-calculated if None)
            display: Whether to display output in console
            min_response_tokens: Minimum tokens to reserve for response
            **kwargs: Additional API parameters

        Returns:
            Generated text content
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        result = await self.streaming_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            display=display,
            min_response_tokens=min_response_tokens,
            **kwargs
        )
        return result['content']

    async def json_completion(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        display_field: Optional[str] = None,
        display_label: Optional[str] = None,
        display_mode: str = "field",  # "field", "array_first", or "full"
        min_response_tokens: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get a JSON response from the model.

        Args:
            model: Model ID to use
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (lower for more consistent JSON)
            max_tokens: Maximum tokens to generate (auto-calculated if None)
            display_field: Optional field to display while streaming (e.g., "premise", "summary")
            display_label: Optional label for what's being generated
            display_mode: Display mode - "field" (extract field from object),
                         "array_first" (show first element of array), "full" (show all)
            min_response_tokens: Minimum tokens to reserve for response
            **kwargs: Additional API parameters

        Returns:
            Parsed JSON response
        """
        # Add JSON instruction to system prompt
        json_instruction = "You must respond with valid JSON only. No markdown, no explanation, just JSON."
        if system_prompt:
            system_prompt = f"{system_prompt}\n\n{json_instruction}"
        else:
            system_prompt = json_instruction

        await self.ensure_session()

        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # If max_tokens not specified, calculate based on model's context window
        if max_tokens is None:
            # Get model info to know context window
            model_obj = await self.get_model(model)
            if model_obj:
                # Estimate prompt tokens
                prompt_tokens = estimate_messages_tokens(messages)

                # For JSON, we often need more space for structured output
                # So we use a higher min_response_tokens default
                effective_min_response = max(min_response_tokens, 500)

                # Calculate optimal max_tokens
                max_tokens = calculate_max_tokens(
                    context_window=model_obj.context_length,
                    prompt_tokens=prompt_tokens,
                    min_response_tokens=effective_min_response,
                    max_response_tokens=model_obj.get_max_output_tokens(),  # Respect model's output limit
                    buffer_percentage=0.05  # 5% buffer
                )
            else:
                # Fallback if model not found
                prompt_tokens = estimate_messages_tokens(messages)
                max_tokens = calculate_max_tokens(
                    context_window=8192,
                    prompt_tokens=prompt_tokens,
                    min_response_tokens=max(min_response_tokens, 500),
                    buffer_percentage=0.05
                )

        request_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,  # Always stream for JSON to show progress
            "max_tokens": max_tokens,
            **kwargs
        }

        # Log request details
        from ..utils.logging import get_logger
        logger = get_logger()
        if logger:
            prompt_chars = sum(len(m.get('content', '')) for m in messages)
            logger.debug(f"=== JSON API Request START ===")
            logger.debug(f"JSON API Request: model={model}, max_tokens={max_tokens}, temp={temperature}")
            logger.debug(f"JSON API Request: prompt_length={prompt_chars} chars")
            logger.debug(f"JSON API Request: display_field={display_field}, display_label={display_label}, display_mode={display_mode}")
            logger.debug(f"JSON API Request: stream=True (always streams for JSON)")
            logger.debug(f"JSON API Request: will_use_display={'YES' if display_field else 'NO (no display_field)'}")

        try:
            async with self._session.post(
                f"{self.base_url}/chat/completions",
                json=request_data,
                headers=self._get_headers()
            ) as response:
                # Log response status
                if logger:
                    logger.debug(f"JSON API Response: status={response.status}, content_type={response.content_type}")

                response.raise_for_status()

                # Use the JSON stream handler if we have a display field
                if display_field:
                    if logger:
                        logger.debug(f"JSON API: Using handle_json_stream_with_display (display_field={display_field})")

                    model_display = model.split('/')[-1] if '/' in model else model
                    # Get model object for capability checking - required, not optional
                    model_obj = await self.get_model(model)
                    if not model_obj:
                        raise Exception(f"Failed to fetch model capabilities for {model}")

                    if logger:
                        logger.debug(f"JSON API: Calling handle_json_stream_with_display with model_display={model_display}")

                    stream_result = await self.stream_handler.handle_json_stream_with_display(
                        response,
                        model_name=model_display,
                        display_field=display_field,
                        display_label=display_label or f"Generating {display_field}",
                        model_obj=model_obj,
                        mode=display_mode
                    )
                    if logger:
                        logger.debug(f"JSON API: handle_json_stream_with_display returned, type={type(stream_result)}")

                    # Extract the actual data from the wrapper if needed
                    if isinstance(stream_result, dict) and 'data' in stream_result:
                        result = stream_result['data']
                        # Store usage info for later
                        if 'usage' in stream_result:
                            usage_info = stream_result['usage']
                        if logger:
                            logger.debug(f"JSON API: Extracted data from wrapper, result type={type(result)}")
                    else:
                        result = stream_result
                        usage_info = stream_result.get('usage', {}) if isinstance(stream_result, dict) else {}
                        if logger:
                            logger.debug(f"JSON API: Using stream_result directly")
                else:
                    if logger:
                        logger.debug(f"JSON API: No display_field, using handle_sse_stream_with_status")

                    # Use regular streaming without display
                    result = await self.stream_handler.handle_sse_stream_with_status(
                        response,
                        model_name=model.split('/')[-1] if '/' in model else model,
                        display=False,  # Don't show raw JSON
                        display_mode=self.settings.streaming_display_mode
                    )

                    # Parse the JSON from content
                    content = result['content'].strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    result = json.loads(content.strip())

                # Update token counter if we have usage info
                # Check for usage info from stream_result (if using display_field) or result
                usage = None
                if display_field and 'usage_info' in locals():
                    usage = usage_info
                elif isinstance(result, dict) and 'usage' in result:
                    usage = result['usage']

                if usage:
                    # Calculate cost if model info is available
                    model_obj = await self.get_model(model)
                    cost = 0.0
                    if model_obj:
                        cost = model_obj.estimate_cost(
                            usage.get('prompt_tokens', 0),
                            usage.get('completion_tokens', 0)
                        )
                    self.token_counter.update(usage, cost)

                    # Show usage if enabled
                    if self.settings.show_token_usage:
                        self._display_usage(usage, cost)

                return result

        except json.JSONDecodeError as e:
            self.console.print(f"[red]Failed to parse JSON response: {e}[/red]")

            # Log the JSON parse error with FULL request details
            session_logger = get_session_logger()
            if session_logger:
                session_logger.log_api_error(
                    model=model,
                    error=e,
                    request_params={
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "display_field": display_field,
                        "display_mode": display_mode,
                        **kwargs
                    },
                    full_messages=messages  # Log complete messages array
                )

            raise
        except aiohttp.ClientError as e:
            self.console.print(f"[red]API Error: {e}[/red]")

            # Log the error with FULL request details
            session_logger = get_session_logger()
            if session_logger:
                session_logger.log_api_error(
                    model=model,
                    error=e,
                    request_params={
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "display_field": display_field,
                        "display_mode": display_mode,
                        **kwargs
                    },
                    full_messages=messages  # Log complete messages array
                )

            raise

    def _display_usage(self, usage: Dict[str, int], cost: float = 0.0):
        """Display token usage information in a compact format."""
        prompt = usage.get('prompt_tokens', 0)
        completion = usage.get('completion_tokens', 0)
        total = usage.get('total_tokens', 0)

        # Create inline status display like Claude Code
        from rich.text import Text
        status = Text()
        status.append(f"{prompt:,} + {completion:,} = {total:,} tokens", style="dim")
        if cost > 0:
            status.append(f" | ${cost:.4f}", style="yellow dim")

        self.console.print(status)

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get token usage summary for the session."""
        return self.token_counter.get_summary()

    def reset_usage(self):
        """Reset token usage counters."""
        self.token_counter.reset()