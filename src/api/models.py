"""Model data structures and discovery."""
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ModelPricing(BaseModel):
    """Model pricing information."""

    prompt: float = Field(description="Cost per 1k prompt tokens")
    completion: float = Field(description="Cost per 1k completion tokens")
    request: Optional[float] = Field(None, description="Cost per request")


class Model(BaseModel):
    """OpenRouter model information."""

    id: str = Field(description="Model identifier")
    name: Optional[str] = Field(None, description="Human-readable name")
    description: Optional[str] = Field(None, description="Model description")
    context_length: int = Field(default=4096, description="Maximum context length")
    pricing: ModelPricing = Field(description="Pricing information")
    top_provider: Optional[Dict[str, Any]] = Field(None, description="Top provider info")
    per_request_limits: Optional[Dict[str, Any]] = Field(None, description="Request limits")
    created: Optional[datetime] = Field(None, description="Model creation date")
    updated: Optional[datetime] = Field(None, description="Last update date")

    @property
    def display_name(self) -> str:
        """Get display name for the model."""
        return self.name or self.id.split('/')[-1].replace('-', ' ').title()

    @property
    def is_free(self) -> bool:
        """Check if model is free to use."""
        return self.pricing.prompt == 0 and self.pricing.completion == 0

    @property
    def cost_per_1k_tokens(self) -> float:
        """Get average cost per 1k tokens."""
        return (self.pricing.prompt + self.pricing.completion) / 2

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate cost for a given number of tokens.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Estimated cost in dollars
        """
        prompt_cost = (prompt_tokens / 1000) * self.pricing.prompt
        completion_cost = (completion_tokens / 1000) * self.pricing.completion
        return prompt_cost + completion_cost

    def get_max_output_tokens(self) -> Optional[int]:
        """
        Get maximum output tokens from per_request_limits or top_provider.

        Returns:
            Maximum completion tokens or None if not specified
        """
        # First check per_request_limits (most specific)
        if self.per_request_limits:
            limit = self.per_request_limits.get('completion_tokens')
            if limit:
                return limit

        # Fallback to top_provider.max_completion_tokens
        if self.top_provider:
            return self.top_provider.get('max_completion_tokens')

        return None

    def get_max_prompt_tokens(self) -> Optional[int]:
        """
        Get maximum prompt tokens from per_request_limits.

        Returns:
            Maximum prompt tokens or None if not specified
        """
        if self.per_request_limits:
            return self.per_request_limits.get('prompt_tokens')
        return None

    def has_sufficient_output_capacity(self, required_tokens: int) -> bool:
        """
        Check if model can generate required number of tokens.

        Args:
            required_tokens: Number of output tokens needed

        Returns:
            True if model can handle it, False if definitely can't, True if unknown
        """
        max_output = self.get_max_output_tokens()
        if max_output is None:
            return True  # Unknown, assume yes
        return max_output >= required_tokens

    def has_sufficient_context(self, required_tokens: int) -> bool:
        """
        Check if model has sufficient context window.

        Args:
            required_tokens: Total tokens needed (prompt + completion)

        Returns:
            True if model can handle it, False otherwise
        """
        return self.context_length >= required_tokens


class ModelInfo(BaseModel):
    """Extended model information for caching."""

    model: Model
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    capabilities: Dict[str, bool] = Field(
        default_factory=lambda: {
            'chat': True,
            'completion': False,
            'function_calling': False,
            'vision': False
        }
    )

    def is_stale(self, hours: int = 1) -> bool:
        """Check if cached model info is stale."""
        age = datetime.now(timezone.utc) - self.fetched_at
        return age.total_seconds() > (hours * 3600)


class ModelList(BaseModel):
    """List of available models."""

    models: List[Model] = Field(description="Available models")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_by_id(self, model_id: str) -> Optional[Model]:
        """Get model by ID."""
        for model in self.models:
            if model.id == model_id:
                return model
        return None

    def search(self, query: str) -> List[Model]:
        """Search models by name or ID."""
        query = query.lower()
        results = []
        for model in self.models:
            if query in model.id.lower() or (model.name and query in model.name.lower()):
                results.append(model)
        return results

    def filter_by_context(self, min_context: int) -> List[Model]:
        """Filter models by minimum context length."""
        return [m for m in self.models if m.context_length >= min_context]

    def filter_free(self) -> List[Model]:
        """Get only free models."""
        return [m for m in self.models if m.is_free]

    def sort_by_price(self, ascending: bool = True) -> List[Model]:
        """Sort models by price."""
        return sorted(
            self.models,
            key=lambda m: m.cost_per_1k_tokens,
            reverse=not ascending
        )

    def select_by_requirements(
        self,
        min_context: Optional[int] = None,
        min_output_tokens: Optional[int] = None,
        prefer_free: bool = False,
        exclude_models: Optional[List[str]] = None
    ) -> Optional[Model]:
        """
        Select best model based on requirements.

        Args:
            min_context: Minimum context window needed
            min_output_tokens: Minimum output tokens needed
            prefer_free: Prefer free models if available
            exclude_models: List of model IDs to exclude

        Returns:
            Best matching model or None if no suitable model found
        """
        candidates = self.models.copy()
        exclude_models = exclude_models or []

        # Filter by exclusions
        candidates = [m for m in candidates if m.id not in exclude_models]

        # Filter by context requirement
        if min_context:
            candidates = [m for m in candidates if m.has_sufficient_context(min_context)]

        # Filter by output requirement
        if min_output_tokens:
            candidates = [m for m in candidates if m.has_sufficient_output_capacity(min_output_tokens)]

        if not candidates:
            return None

        # If prefer_free, try to get a free model
        if prefer_free:
            free_models = [m for m in candidates if m.is_free]
            if free_models:
                candidates = free_models

        # Sort by price and return cheapest
        candidates = sorted(candidates, key=lambda m: m.cost_per_1k_tokens)
        return candidates[0] if candidates else None