"""Integration tests using real API calls with grok-4-fast model."""

import pytest
import asyncio
import json
import os
from pathlib import Path
from src.api import OpenRouterClient
from src.models import Project
from src.generation.premise import PremiseGenerator
from src.generation.treatment import TreatmentGenerator
from src.generation.chapters import ChapterGenerator
from src.generation.prose import ProseGenerator
from src.generation.taxonomies import TaxonomyLoader, PremiseAnalyzer, PremiseHistory


# Use grok-4-fast:free for all tests (free tier)
TEST_MODEL = "x-ai/grok-4-fast:free"


@pytest.fixture
async def real_client():
    """Create a real OpenRouter client."""
    # Make sure API key is set from environment
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    client = OpenRouterClient(api_key=api_key)
    await client.ensure_session()
    yield client
    await client.close()


@pytest.fixture
def test_project(temp_dir):
    """Create a test project."""
    project_dir = temp_dir / "integration_test"
    return Project.create(project_dir, name="Integration Test", genre="fantasy")


class TestRealAPIIntegration:
    """Integration tests with real API calls."""

    @pytest.mark.asyncio
    async def test_real_model_discovery(self, real_client):
        """Test discovering models from real API."""
        models = await real_client.discover_models()

        assert len(models) > 0

        # Check that grok-4-fast is available
        model_ids = [m.id for m in models]
        assert any("grok" in m.lower() for m in model_ids)

        # Check model properties
        grok_model = next((m for m in models if "grok-4-fast" in m.id.lower()), None)
        if grok_model:
            assert grok_model.context_length > 0
            assert grok_model.pricing is not None

    @pytest.mark.asyncio
    async def test_real_completion(self, real_client):
        """Test real completion with grok-4-fast."""
        response = await real_client.completion(
            model=TEST_MODEL,
            prompt="Write a one-sentence story about a cat.",
            max_tokens=50
        )

        assert response is not None
        assert len(response) > 0
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_real_json_completion(self, real_client):
        """Test real JSON completion."""
        result = await real_client.json_completion(
            model=TEST_MODEL,
            prompt='Return a JSON object with keys "name" and "age" for a fictional character.',
            max_tokens=100
        )

        assert isinstance(result, dict)
        assert "name" in result or "age" in result  # Should have at least one

    @pytest.mark.asyncio
    async def test_real_streaming_completion(self, real_client):
        """Test real streaming completion."""
        tokens = []

        def on_token(token, count):
            tokens.append(token)

        result = await real_client.streaming_completion(
            model=TEST_MODEL,
            messages=[{"role": "user", "content": "Count from 1 to 5"}],
            on_token=on_token,
            max_tokens=50
        )

        assert len(tokens) > 0
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_real_premise_generation(self, real_client, test_project):
        """Test real premise generation."""
        generator = PremiseGenerator(real_client, test_project, model=TEST_MODEL)

        result = await generator.generate(
            genre="fantasy",
            user_input="a world where dreams are currency"
        )

        assert "premise" in result
        assert len(result["premise"]) > 20
        assert "themes" in result

        # Check it was saved to project
        saved_premise = test_project.get_premise()
        assert saved_premise == result["premise"]

    @pytest.mark.asyncio
    async def test_real_premise_with_taxonomy(self, real_client, test_project):
        """Test premise generation with taxonomy selections."""
        generator = PremiseGenerator(real_client, test_project, model=TEST_MODEL)

        result = await generator.generate(genre="fantasy")

        assert "selections" in result
        assert isinstance(result["selections"], dict)
        assert len(result["selections"]) > 0

    @pytest.mark.asyncio
    async def test_real_premise_iteration(self, real_client, test_project):
        """Test iterating on a premise."""
        generator = PremiseGenerator(real_client, test_project, model=TEST_MODEL)

        # First generate a premise
        initial = await generator.generate(genre="fantasy")
        assert "premise" in initial

        # Now iterate on it
        updated = await generator.iterate("Make it darker and more mysterious")

        assert "premise" in updated
        assert updated["premise"] != initial["premise"]

    @pytest.mark.asyncio
    async def test_real_treatment_generation(self, real_client, test_project):
        """Test real treatment generation."""
        # First create a premise
        test_project.save_premise("A young mage discovers ancient powers")

        real_client.settings.active_model = TEST_MODEL
        generator = TreatmentGenerator(real_client, test_project)

        result = await generator.generate(target_words=500)  # Short for testing

        assert result is not None
        assert len(result) > 100
        assert "Act" in result or "act" in result  # Should have act structure

    @pytest.mark.asyncio
    async def test_real_chapter_generation(self, real_client, test_project):
        """Test real chapter outline generation."""
        # Setup premise and treatment
        test_project.save_premise("A hero's journey")
        test_project.save_treatment("Act 1: Beginning\nAct 2: Middle\nAct 3: End")

        real_client.settings.active_model = TEST_MODEL
        generator = ChapterGenerator(real_client, test_project)

        result = await generator.generate(num_chapters=3)  # Just 3 for testing

        assert "chapters" in result
        assert len(result["chapters"]) == 3
        assert all("title" in ch for ch in result["chapters"])

    @pytest.mark.asyncio
    async def test_real_prose_generation(self, real_client, test_project):
        """Test real prose generation for a chapter."""
        # Setup chapter outline
        outline = {
            "chapters": [
                {
                    "number": 1,
                    "title": "The Beginning",
                    "summary": "Hero starts journey",
                    "key_events": ["Meeting mentor", "First challenge"],
                    "word_count_target": 500
                }
            ]
        }
        test_project.save_chapter_outlines(outline)

        real_client.settings.active_model = TEST_MODEL
        generator = ProseGenerator(real_client, test_project)

        result = await generator.generate(chapter_num=1, target_words=300)

        assert result is not None
        assert len(result) > 100
        assert "Chapter" in result or "chapter" in result

    @pytest.mark.asyncio
    async def test_premise_analyzer_with_real_content(self, real_client):
        """Test premise analyzer with real generated content."""
        # Generate a real treatment
        response = await real_client.completion(
            model=TEST_MODEL,
            prompt="Write a 250-word story treatment about a space explorer",
            max_tokens=400
        )

        analysis = PremiseAnalyzer.analyze(response)

        assert analysis["word_count"] > 100
        assert analysis["type"] in ["detailed", "treatment"]

        if analysis["word_count"] > 200:
            assert analysis["is_treatment"] == True

    @pytest.mark.asyncio
    async def test_taxonomy_with_real_premise(self, real_client, test_project):
        """Test taxonomy extraction from real generated premise."""
        # Generate a detailed premise
        generator = PremiseGenerator(real_client, test_project, model=TEST_MODEL)

        # First generate a long treatment-like premise
        treatment = """
        In a world where magic is forbidden, a young scribe discovers she has powers.
        She must hide her abilities while uncovering a conspiracy in the kingdom.
        The story follows her journey from fearful novice to confident leader.
        Along the way she finds allies in unexpected places and learns the true cost of power.
        The climax involves a battle between old and new magic systems.
        """ * 3  # Make it long enough

        test_project.save_treatment(treatment)

        # Generate taxonomy for it
        result = await generator.generate_taxonomy_only(treatment, "fantasy")

        assert "selections" in result
        assert len(result["selections"]) > 0

    @pytest.mark.asyncio
    async def test_full_generation_pipeline(self, real_client, test_project):
        """Test the complete generation pipeline with real API."""
        # 1. Generate premise
        premise_gen = PremiseGenerator(real_client, test_project, model=TEST_MODEL)
        premise_result = await premise_gen.generate(
            genre="fantasy",
            user_input="a magical library"
        )
        assert "premise" in premise_result

        # 2. Generate treatment
        real_client.settings.active_model = TEST_MODEL
        treatment_gen = TreatmentGenerator(real_client, test_project)
        treatment_result = await treatment_gen.generate(target_words=300)
        assert treatment_result is not None

        # 3. Generate chapters
        chapter_gen = ChapterGenerator(real_client, test_project)
        chapters_result = await chapter_gen.generate(num_chapters=2)
        assert len(chapters_result["chapters"]) == 2

        # 4. Generate prose for first chapter
        prose_gen = ProseGenerator(real_client, test_project)
        prose_result = await prose_gen.generate(chapter_num=1, target_words=200)
        assert len(prose_result) > 50

        # Verify everything was saved
        assert test_project.get_premise() is not None
        assert test_project.get_treatment() is not None
        assert test_project.get_chapter_outlines() is not None
        assert test_project.get_chapter(1) is not None

    @pytest.mark.asyncio
    async def test_error_handling_with_real_api(self, real_client):
        """Test error handling with invalid requests."""
        # Test with invalid model
        with pytest.raises(Exception):
            await real_client.completion(
                model="invalid/model/name",
                prompt="Test"
            )

        # Test with empty prompt
        response = await real_client.completion(
            model=TEST_MODEL,
            prompt="",
            max_tokens=10
        )
        # Should still return something, even if minimal
        assert response is not None


class TestRealAPIStreaming:
    """Test streaming functionality with real API."""

    @pytest.mark.asyncio
    async def test_streaming_token_callback(self, real_client):
        """Test that streaming properly calls token callback."""
        token_counts = []
        tokens_received = []

        def on_token(token, count):
            tokens_received.append(token)
            token_counts.append(count)

        result = await real_client.streaming_completion(
            model=TEST_MODEL,
            messages=[{"role": "user", "content": "Write three words"}],
            on_token=on_token,
            max_tokens=20
        )

        assert len(tokens_received) > 0
        assert len(token_counts) > 0
        assert token_counts[-1] == len(tokens_received)  # Final count should match total

    @pytest.mark.asyncio
    async def test_streaming_completion_callback(self, real_client):
        """Test streaming with completion callback."""
        completed = []

        def on_complete(text, tokens):
            completed.append((text, tokens))

        result = await real_client.streaming_completion(
            model=TEST_MODEL,
            messages=[{"role": "user", "content": "Say hello"}],
            on_complete=on_complete,
            max_tokens=20
        )

        assert len(completed) == 1
        assert completed[0][0] == result
        assert completed[0][1] > 0