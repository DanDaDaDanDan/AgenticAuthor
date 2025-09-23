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