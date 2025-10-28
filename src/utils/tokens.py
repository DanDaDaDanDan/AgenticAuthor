"""Token estimation and management utilities."""
from typing import List, Dict, Optional, Union
import re

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class TokenEstimator:
    """Estimate token counts for prompts and manage context windows."""

    def __init__(self):
        """Initialize token estimator with fallback methods."""
        self._encoder = None
        self._try_load_tiktoken()

    def _try_load_tiktoken(self):
        """Try to load tiktoken encoder."""
        if not TIKTOKEN_AVAILABLE:
            self._encoder = None
            return

        try:
            # Try to use cl100k_base (GPT-4 tokenizer) as a reasonable default
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fall back to simple estimation if tiktoken unavailable
            self._encoder = None

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a given text.

        Uses tiktoken if available, otherwise falls back to heuristic estimation.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        if self._encoder:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                # Fall back to heuristic if encoding fails
                pass

        # Heuristic estimation (conservative - overestimate slightly)
        # Based on empirical observations:
        # - English text: ~3-4 chars per token
        # - JSON/code: ~2-3 chars per token
        # - Mixed content: ~3 chars per token
        # We use 2.5 to be conservative and avoid hitting limits

        # Count words and special characters separately
        words = len(re.findall(r'\b\w+\b', text))
        special_chars = len(re.findall(r'[^\w\s]', text))
        whitespace = len(re.findall(r'\s+', text))

        # Estimate tokens
        # Words: average 1.3 tokens per word (accounting for subword tokenization)
        # Special chars: often 1 token each
        # Whitespace: usually part of adjacent tokens
        estimated_tokens = int(words * 1.3 + special_chars * 0.5 + whitespace * 0.1)

        # Add 10% buffer for safety
        return int(estimated_tokens * 1.1)

    def estimate_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Estimate token count for a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Estimated total token count
        """
        # Message overhead (role tokens, special tokens, etc.)
        # Typically 3-4 tokens per message for formatting
        overhead_per_message = 4

        total_tokens = 0
        for message in messages:
            total_tokens += overhead_per_message
            total_tokens += self.estimate_tokens(message.get('content', ''))
            # Role name tokens (system/user/assistant)
            total_tokens += 1

        # Add some tokens for message boundaries and special tokens
        total_tokens += 3

        return total_tokens

    def calculate_max_tokens(
        self,
        context_window: int,
        prompt_tokens: int,
        reserve_tokens: int = 100,
        max_response_tokens: Optional[int] = None,
        buffer_percentage: float = 0.05
    ) -> int:
        """
        Calculate optimal max_tokens for a response given context constraints.

        Args:
            context_window: Total context window size for the model
            prompt_tokens: Estimated tokens in the prompt
            reserve_tokens: Minimum tokens to reserve for response
            max_response_tokens: Maximum tokens to allow for response (optional)
            buffer_percentage: Percentage of context to reserve as buffer (default 5%)

        Returns:
            Optimal max_tokens value
        """
        # Calculate buffer
        buffer_tokens = int(context_window * buffer_percentage)

        # Calculate available tokens
        available_tokens = context_window - prompt_tokens - buffer_tokens

        # Check if prompt exceeds context window
        if available_tokens < reserve_tokens:
            # Get logger for error reporting
            from ..utils.logging import get_logger
            logger = get_logger()

            # If available tokens is negative or very small, prompt is too large
            if available_tokens <= 0:
                error_msg = (
                    f"Prompt exceeds model context window!\n"
                    f"  Context window: {context_window:,} tokens\n"
                    f"  Prompt size: {prompt_tokens:,} tokens\n"
                    f"  Buffer: {buffer_tokens:,} tokens\n"
                    f"  Available: {available_tokens:,} tokens (NEGATIVE - prompt too large!)\n\n"
                    f"Solutions:\n"
                    f"  • Use a model with larger context window\n"
                    f"  • Reduce prompt size (fewer previous chapters, shorter beats)\n"
                    f"  • Generate earlier chapters first to reduce cumulative context"
                )
                if logger:
                    logger.error(error_msg)
                raise ValueError(error_msg)

            # Available tokens positive but less than reserve - log warning and continue
            if logger:
                logger.warning(
                    f"Low available tokens: {available_tokens:,} < reserve {reserve_tokens:,}. "
                    f"Prompt: {prompt_tokens:,}, Context: {context_window:,}. "
                    f"Response may be truncated."
                )
            return reserve_tokens

        # Apply max_response_tokens cap if specified
        if max_response_tokens:
            available_tokens = min(available_tokens, max_response_tokens)

        return available_tokens


# Global instance for convenience
token_estimator = TokenEstimator()


def estimate_tokens(text: str) -> int:
    """Convenience function to estimate tokens."""
    return token_estimator.estimate_tokens(text)


def estimate_messages_tokens(messages: List[Dict[str, str]]) -> int:
    """Convenience function to estimate message tokens."""
    return token_estimator.estimate_messages_tokens(messages)


def calculate_max_tokens(
    context_window: int,
    prompt_tokens: int,
    reserve_tokens: int = 100,
    max_response_tokens: Optional[int] = None,
    buffer_percentage: float = 0.05
) -> int:
    """Convenience function to calculate max tokens."""
    return token_estimator.calculate_max_tokens(
        context_window,
        prompt_tokens,
        reserve_tokens,
        max_response_tokens,
        buffer_percentage
    )