"""Tests for API client and related modules."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import aiohttp

from src.api import OpenRouterClient
from src.api.models import Model, ModelPricing, ModelInfo
from src.api.streaming import StreamHandler
from src.api.auth import validate_api_key


class TestOpenRouterClientCoverage:
    """Tests for OpenRouterClient coverage."""

    @pytest.fixture
    def client(self):
        """Create a mock client."""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'sk-or-test-key'}):
            return OpenRouterClient()

    @pytest.mark.asyncio
    async def test_ensure_session_creates_session(self, client):
        """Test ensuring session creates one if needed."""
        assert client.session is None
        await client.ensure_session()
        assert client.session is not None
        await client.close()

    @pytest.mark.asyncio
    async def test_close_no_session(self, client):
        """Test closing when no session exists."""
        await client.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_discover_models_success(self, client):
        """Test successful model discovery."""
        mock_response = {
            "data": [
                {
                    "id": "test/model",
                    "pricing": {"prompt": "0.001", "completion": "0.002"},
                    "context_length": 4096,
                    "top_provider": {"is_moderated": False}
                }
            ]
        }

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            models = await client.discover_models()

            assert len(models) == 1
            assert models[0].id == "test/model"

    @pytest.mark.asyncio
    async def test_discover_models_cached(self, client):
        """Test model discovery uses cache."""
        client._model_cache = [Mock(id="cached")]

        models = await client.discover_models()

        assert len(models) == 1
        assert models[0].id == "cached"

    @pytest.mark.asyncio
    async def test_completion_basic(self, client):
        """Test basic completion."""
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {
                "choices": [{"message": {"content": "Response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }

            response = await client.completion(
                model="test/model",
                prompt="Test prompt"
            )

            assert response == "Response"

    @pytest.mark.asyncio
    async def test_completion_with_messages(self, client):
        """Test completion with messages."""
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User"}
        ]

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {
                "choices": [{"message": {"content": "Response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }

            response = await client.completion(
                model="test/model",
                messages=messages
            )

            assert response == "Response"

    @pytest.mark.asyncio
    async def test_json_completion(self, client):
        """Test JSON completion."""
        with patch.object(client, 'completion', new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = '{"key": "value"}'

            result = await client.json_completion(
                model="test/model",
                prompt="Generate JSON"
            )

            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_json_completion_invalid_json(self, client):
        """Test JSON completion with invalid response."""
        with patch.object(client, 'completion', new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = 'Not valid JSON'

            result = await client.json_completion(
                model="test/model",
                prompt="Generate JSON"
            )

            assert result == {}

    @pytest.mark.asyncio
    async def test_streaming_completion(self, client):
        """Test streaming completion."""
        chunks = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            b'data: {"choices": [{"delta": {"content": " world"}}]}\n\n',
            b'data: [DONE]\n\n'
        ]

        async def mock_stream():
            for chunk in chunks:
                yield chunk

        mock_response = Mock()
        mock_response.content.iter_any = mock_stream
        mock_response.raise_for_status = Mock()

        with patch.object(client, 'ensure_session', new_callable=AsyncMock):
            client.session = Mock()
            client.session.post = AsyncMock(return_value=mock_response)

            tokens = []

            def on_token(token, count):
                tokens.append(token)

            result = await client.streaming_completion(
                model="test/model",
                messages=[{"role": "user", "content": "Test"}],
                on_token=on_token
            )

            assert result == "Hello world"
            assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_make_request_retry(self, client):
        """Test request retry on failure."""
        await client.ensure_session()

        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = [
            aiohttp.ClientError("Error"),  # First attempt fails
            None  # Second attempt succeeds
        ]
        mock_resp.json = AsyncMock(return_value={"result": "success"})

        client.session.post = AsyncMock(return_value=mock_resp)

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await client._make_request("test", {})

        assert result == {"result": "success"}


class TestModels:
    """Tests for model classes."""

    def test_model_pricing(self):
        """Test ModelPricing class."""
        pricing = ModelPricing(
            prompt=0.001,
            completion=0.002,
            request=0.0,
            image=0.0
        )

        cost = pricing.calculate_cost(100, 50)
        assert cost > 0

    def test_model_info(self):
        """Test ModelInfo class."""
        info = ModelInfo(
            max_completion_tokens=1000,
            max_images=0,
            allows_user_messages=True,
            allows_assistant_messages=True
        )

        assert info.max_completion_tokens == 1000

    def test_model_class(self):
        """Test Model class."""
        model = Model(
            id="test/model",
            name="Test Model",
            context_length=4096,
            pricing=ModelPricing(prompt=0.001, completion=0.002),
            info=ModelInfo()
        )

        assert model.id == "test/model"
        assert model.context_length == 4096


class TestStreamHandler:
    """Tests for StreamHandler."""

    def test_stream_handler_init(self):
        """Test StreamHandler initialization."""
        def callback(token, count):
            pass

        handler = StreamHandler(
            on_token=callback,
            on_complete=None,
            track_usage=True
        )

        assert handler.on_token == callback
        assert handler.buffer == ""
        assert handler.token_count == 0

    def test_process_chunk_with_content(self):
        """Test processing chunk with content."""
        tokens = []

        def on_token(token, count):
            tokens.append(token)

        handler = StreamHandler(on_token=on_token)

        chunk = {"choices": [{"delta": {"content": "Hello"}}]}
        handler.process_chunk(chunk)

        assert tokens == ["Hello"]
        assert handler.buffer == "Hello"

    def test_process_chunk_done(self):
        """Test processing [DONE] chunk."""
        completed = []

        def on_complete(text, tokens):
            completed.append((text, tokens))

        handler = StreamHandler(on_token=None, on_complete=on_complete)
        handler.buffer = "Complete text"
        handler.token_count = 10

        handler.process_chunk("[DONE]")

        assert completed == [("Complete text", 10)]

    def test_get_result(self):
        """Test getting result."""
        handler = StreamHandler(on_token=None)
        handler.buffer = "Result text"
        handler.token_count = 5

        result = handler.get_result()
        assert result == "Result text"


# TokenUsageTracker tests removed as class doesn't exist


class TestAuth:
    """Tests for auth module."""

    def test_validate_api_key_valid(self):
        """Test validating valid API key."""
        result = validate_api_key("sk-or-valid-key-123456789")
        assert result == "sk-or-valid-key-123456789"

    def test_validate_api_key_invalid(self):
        """Test validating invalid API key."""
        with pytest.raises(ValueError):
            validate_api_key("invalid-key")

        with pytest.raises(ValueError):
            validate_api_key("sk-wrong-prefix")

        with pytest.raises(ValueError):
            validate_api_key("")

    def test_validate_api_key_from_env(self):
        """Test validating API key from environment."""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'sk-or-test'}):
            key = validate_api_key()
            assert key == 'sk-or-test'

    def test_validate_api_key_missing(self):
        """Test validating when API key is missing."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                validate_api_key()
            assert "OPENROUTER_API_KEY" in str(exc_info.value)