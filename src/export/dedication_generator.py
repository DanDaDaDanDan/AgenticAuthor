"""Generate book-specific dedications based on premise and tone."""

from typing import Optional, Dict, Any
from pathlib import Path


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

        # Build prompt
        prompt = self._build_prompt(template_text, book_details)

        # Generate with LLM
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a literary editor crafting book dedications. Return only the dedication text, no explanations or quotes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
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
        premise_metadata_file = self.project.path / "premise_metadata.json"
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

    def _build_prompt(self, template_text: str, book_details: Dict[str, Any]) -> str:
        """Build the dedication generation prompt."""
        genre = book_details['genre']
        themes = book_details['themes']
        hook = book_details['hook']
        title = book_details['title']

        # Genre-specific guidance
        genre_guidance = self._get_genre_guidance(genre)

        prompt = f"""You are rewriting a book dedication to match this book's tone and genre.

BOOK DETAILS:
- Title: {title}
- Genre: {genre}
- Themes: {themes}
- Hook: {hook}

TEMPLATE DEDICATION:
{template_text}

TASK:
Rewrite the dedication with imagery and language that matches this book's style and genre.

Core sentiment to preserve:
- Family as anchors and constants
- Gratitude for unwavering support
- Love and connection as sources of strength
- Appreciation for being reasons to create

{genre_guidance}

IMPORTANT:
- Keep dedication to 2-4 sentences (similar length to template)
- Use literary, evocative language
- Make it feel specific to this book's world/tone
- Return ONLY the dedication text, no quotes, no explanations, no meta-commentary

Example tone for {genre}:
{self._get_genre_example(genre)}

Now write the dedication:"""

        return prompt

    def _get_genre_guidance(self, genre: str) -> str:
        """Get genre-specific writing guidance."""
        guidance_map = {
            'fantasy': """Genre guidance for FANTASY:
- Use epic, mythological tone
- Reference quests, journeys, magic, light/darkness
- Metaphors: shields, swords, ancient trees, stars, forges
- Tone: Grand but heartfelt, timeless
- Examples: "steadfast as ancient oak," "forged in love's fire," "my true north star\"""",

            'science-fiction': """Genre guidance for SCIENCE-FICTION:
- Future-oriented, technological metaphors
- Reference systems, networks, constants in flux, navigation
- Metaphors: beacons, algorithms, gravity, orbits, coordinates
- Tone: Precise but emotional, philosophical
- Examples: "my constant in shifting variables," "gravity that grounds," "beacons in the void\"""",

            'mystery': """Genre guidance for MYSTERY:
- Sharp, observant language
- Reference truth, clarity, patterns, answers
- Metaphors: clues, evidence, certainty, foundations
- Tone: Clear-eyed but warm, grateful
- Examples: "the truth I return to," "evidence of love's endurance," "my certain answer\"""",

            'thriller': """Genre guidance for THRILLER:
- Tense but heartfelt language
- Reference safety, refuge, trust, survival
- Metaphors: shelter, anchor, steady ground, safe harbor
- Tone: Intense gratitude, awareness of danger/safety contrast
- Examples: "my safe harbor," "the steady ground," "the ones who kept me human\"""",

            'horror': """Genre guidance for HORROR:
- Contrast darkness with light/hope
- Reference humanity, sanity, warmth in cold worlds
- Metaphors: light in darkness, warmth, tethers, humanity
- Tone: Grateful for preserving humanity/sanity
- Examples: "my tether to humanity," "light against the darkness," "warmth in endless night\"""",

            'romance': """Genre guidance for ROMANCE:
- Emotional, intimate language
- Reference heart, soul, love as foundation
- Metaphors: heartbeats, home, belonging, completion
- Tone: Deeply emotional, vulnerable
- Examples: "the love that taught me," "my home and heartbeat," "the reason love stories matter\"""",

            'historical-fiction': """Genre guidance for HISTORICAL FICTION:
- Period-appropriate elevated language
- Reference legacy, memory, roots, generations
- Metaphors: foundations, heritage, threads through time
- Tone: Reverent, aware of history's weight
- Examples: "my living legacy," "roots that anchor," "the heritage I cherish\"""",

            'literary-fiction': """Genre guidance for LITERARY FICTION:
- Lyrical, introspective language
- Reference meaning, truth, humanity, complexity
- Metaphors: mirrors, truth, depth, richness of life
- Tone: Thoughtful, philosophical yet personal
- Examples: "mirrors showing truth," "the meaning in chaos," "complexity made bearable\"""",
        }

        return guidance_map.get(genre.lower(), f"""Genre guidance for {genre.upper()}:
- Match the tone and imagery of the book's world
- Use metaphors that fit the genre's conventions
- Balance genre flavor with heartfelt emotion
- Keep the core sentiment of family appreciation""")

    def _get_genre_example(self, genre: str) -> str:
        """Get example dedication tone for genre."""
        examples = {
            'fantasy': "To my family—my steadfast companions through every quest, the light that guides me home from darkest realms, and the magic that makes all stories worth telling.",

            'science-fiction': "To my family—the constants in my ever-shifting variables, my gravity in the void, and the reason I believe in humanity's future.",

            'mystery': "To my family—the truth I return to when the world grows uncertain, my evidence that love endures, and my most reliable witnesses to life's mysteries.",

            'thriller': "To my family—my safe harbor in storms, the steady ground when everything shakes, and the ones who remind me what's worth fighting for.",

            'horror': "To my family—the light I carry against darkness, my tether to humanity when the world turns strange, and proof that love survives even horror.",

            'romance': "To my family—the love that taught me how to write about love, my home when I'm lost, and the heartbeat beneath every word.",

            'historical-fiction': "To my family—my living legacy, the roots that anchor me through changing times, and the history I'm most proud to be part of.",

            'literary-fiction': "To my family—the mirrors showing truth, the meaning I find in chaos, and the complexity of love that makes life bearable and beautiful.",
        }

        return examples.get(genre.lower(), "To my family—my constants, my anchors, and my inspiration.")
