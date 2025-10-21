"""Generate book-specific dedications based on premise and tone."""

from typing import Optional, Dict, Any
from pathlib import Path
from ..prompts import get_prompt_loader


class DedicationGenerator:
    """Generates customized dedications for books based on their genre and tone."""

    def __init__(self, client, project, model: str):
        """
        Initialize dedication generator.

        Args:
            client: OpenRouter API client
            project: Project to generate dedication for
            model: Model to use for generation
        """
        self.client = client
        self.project = project
        self.model = model
        self.prompt_loader = get_prompt_loader()

    async def generate_dedication(self) -> str:
        """
        Generate a book-specific dedication based on the project's premise and tone.

        Returns:
            Dedication text (2-4 sentences)

        Raises:
            Exception: If template not found or generation fails
        """
        # Load template dedication
        template_path = Path(__file__).parent.parent.parent / "misc" / "dedication.md"
        if not template_path.exists():
            raise Exception(f"Dedication template not found at {template_path}")

        template_text = template_path.read_text(encoding='utf-8').strip()

        # Get book details
        book_details = self._extract_book_details()

        # Render prompt from template
        prompts = self.prompt_loader.render(
            "generation/dedication_generation",
            title=book_details['title'],
            genre=book_details['genre'],
            themes=book_details['themes'],
            hook=book_details.get('hook', ''),
            template_text=template_text,
            genre_guidance=self._get_genre_guidance(book_details['genre']),
            genre_example=self._get_genre_example(book_details['genre'])
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature("generation/dedication_generation", default=0.8)

        # Generate with LLM
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            display=False  # Silent generation
        )

        dedication = result.get('content', result) if isinstance(result, dict) else result
        return dedication.strip()

    def _extract_book_details(self) -> Dict[str, Any]:
        """Extract relevant details from project for dedication generation."""
        details = {}

        # Get metadata
        metadata = self.project.get_book_metadata()
        details['title'] = metadata.get('title', 'Untitled')
        details['author'] = metadata.get('author', 'Unknown')

        # Get premise metadata
        premise_metadata_file = self.project.premise_metadata_file
        if premise_metadata_file.exists():
            import json
            with open(premise_metadata_file, 'r') as f:
                premise_data = json.load(f)

                # Extract genre from taxonomy or direct field
                selections = premise_data.get('selections', {})
                genre = premise_data.get('genre')

                # Infer genre from subgenre selections
                if not genre:
                    if 'fantasy_subgenre' in selections:
                        genre = 'fantasy'
                    elif 'mystery_subgenre' in selections:
                        genre = 'mystery'
                    elif 'romance_subgenre' in selections:
                        genre = 'romance'
                    elif 'scifi_subgenre' in selections:
                        genre = 'science-fiction'
                    elif 'horror_subgenre' in selections:
                        genre = 'horror'
                    elif 'literary_style' in selections:
                        genre = 'literary-fiction'
                    elif 'historical_period' in selections:
                        genre = 'historical-fiction'
                    elif 'thriller_subgenre' in selections:
                        genre = 'thriller'
                    else:
                        genre = 'general fiction'

                details['genre'] = genre

                # Extract themes
                themes = premise_data.get('themes', [])
                if isinstance(themes, list):
                    details['themes'] = ', '.join(themes) if themes else 'family, loyalty, courage'
                else:
                    details['themes'] = themes if themes else 'family, loyalty, courage'

                # Get hook for tone/setting hints
                details['hook'] = premise_data.get('hook', '')
                details['premise'] = premise_data.get('premise', '')

        # Fallback defaults
        if 'genre' not in details:
            details['genre'] = 'fiction'
        if 'themes' not in details:
            details['themes'] = 'family, loyalty, courage'
        if 'hook' not in details:
            details['hook'] = ''
        if 'premise' not in details:
            details['premise'] = ''

        return details

    def _get_genre_guidance(self, genre: str) -> str:
        """Get genre-specific writing guidance."""
        guidance_map = {
            'fantasy': """Genre guidance for FANTASY:
- Use epic, mythological tone celebrating wonder
- Reference wonder, journeys, magic, light, enchantment, imagination
- Metaphors: stars, ancient trees, illumination, sparks, forges of creation
- Tone: Grand but heartfelt, timeless, celebratory
- Examples: "wonder that sparks worlds," "forged in love's joy," "my guiding star\"""",

            'science-fiction': """Genre guidance for SCIENCE-FICTION:
- Future-oriented, celebrating discovery and possibility
- Reference discovery, exploration, innovation, potential, inspiration
- Metaphors: constellations, horizons, sparks, illumination, pathways
- Tone: Precise but emotional, philosophical, optimistic
- Examples: "spark of discovery," "boundless horizons," "constellations of possibility\"""",

            'mystery': """Genre guidance for MYSTERY:
- Sharp, observant language celebrating truth
- Reference truth, clarity, discovery, wonder, revelation
- Metaphors: illumination, discovery, clarity, insight
- Tone: Clear-eyed but warm, grateful, celebratory
- Examples: "truth that illuminates," "joy of discovery," "my cherished revelation\"""",

            'thriller': """Genre guidance for THRILLER:
- Passionate, heartfelt language celebrating courage
- Reference courage, excitement, triumph, passion, strength
- Metaphors: fire, warmth, celebration, inspiration
- Tone: Intense gratitude, celebrating courage and triumph
- Examples: "inspiration for courage," "fuel for passion," "celebration of triumph\"""",

            'horror': """Genre guidance for HORROR:
- Celebrate courage and imagination
- Reference courage, creativity, imagination, transcendence, warmth
- Metaphors: light, warmth, courage, creative fire
- Tone: Grateful for inspiration and creative courage
- Examples: "courage in every tale," "warmth of imagination," "love that transcends\"""",

            'romance': """Genre guidance for ROMANCE:
- Emotional, intimate language celebrating love
- Reference heart, soul, love, joy, connection
- Metaphors: heartbeats, home, belonging, celebration
- Tone: Deeply emotional, celebratory, joyful
- Examples: "love that taught me joy," "my heart and home," "reason love stories inspire\"""",

            'historical-fiction': """Genre guidance for HISTORICAL FICTION:
- Period-appropriate elevated language celebrating heritage
- Reference legacy, memory, heritage, generations, celebration
- Metaphors: heritage, legacy, threads through time, treasures
- Tone: Reverent, celebrating heritage and legacy
- Examples: "my living legacy," "heritage I celebrate," "treasures I cherish\"""",

            'literary-fiction': """Genre guidance for LITERARY FICTION:
- Lyrical, introspective language celebrating beauty
- Reference meaning, truth, beauty, depth, joy, richness
- Metaphors: beauty, truth, depth, illumination, richness of life
- Tone: Thoughtful, philosophical yet personal, celebratory
- Examples: "beauty in every truth," "depth that enriches," "joy that illuminates\"""",
        }

        return guidance_map.get(genre.lower(), f"""Genre guidance for {genre.upper()}:
- Match the tone and imagery of the book's world
- Use metaphors that fit the genre's conventions
- Balance genre flavor with heartfelt emotion
- Keep the core sentiment of family appreciation""")

    def _get_genre_example(self, genre: str) -> str:
        """Get example dedication tone for genre."""
        examples = {
            'fantasy': "To my family—the wonder that sparks every imagined world, the light that illuminates all my stories, and the magic that makes creation a joy.",

            'science-fiction': "To my family—my inspiration for every imagined future, the spark of curiosity that fuels discovery, and the reason I celebrate humanity's boundless potential.",

            'mystery': "To my family—the joy of discovery in every moment, the truth that love illuminates all mysteries, and my cherished companions in wonder.",

            'thriller': "To my family—my inspiration for every courageous character, the warmth that fuels my passion for storytelling, and the ones who celebrate every triumph with me.",

            'horror': "To my family—the courage that inspires every tale, the warmth that lights my imagination, and proof that love transcends all stories.",

            'romance': "To my family—the love that taught me how to write about love, my heart and home, and the inspiration beneath every word.",

            'historical-fiction': "To my family—my living legacy, the heritage I celebrate in every story, and the history I'm most proud to be part of.",

            'literary-fiction': "To my family—the beauty in every truth I explore, the depth of love that enriches life, and the joy that makes every story meaningful.",
        }

        return examples.get(genre.lower(), "To my family—my joy, my inspiration, and my celebration of love.")
