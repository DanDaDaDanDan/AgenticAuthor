"""KDP metadata generator for book publishing."""

from typing import Dict, List, Optional, Any
from pathlib import Path

from ..prompts import get_prompt_loader


class KDPMetadataGenerator:
    """Generate Amazon KDP metadata from book content."""

    def __init__(self, client, project, model: str):
        """
        Initialize KDP metadata generator.

        Args:
            client: OpenRouter API client
            project: Project to generate metadata for
            model: Model to use for generation
        """
        self.client = client
        self.project = project
        self.model = model
        self.prompt_loader = get_prompt_loader()

    async def generate_all_metadata(self) -> Dict[str, Any]:
        """
        Generate all KDP metadata in one comprehensive call.

        Returns:
            Dict with all metadata fields
        """
        # Build comprehensive context
        context = self._build_context()

        # Generate all metadata
        prompt = self._build_comprehensive_prompt(context)

        response = await self.client.completion(
            model=self.model,
            prompt=prompt,
            temperature=0.7,
            display=False
        )

        # Parse response
        metadata = self._parse_metadata_response(response)

        return metadata

    async def generate_description(self) -> str:
        """
        Generate compelling book description (100-150 words).

        Returns:
            HTML-formatted book description
        """
        try:
            context = self._build_context()

            # Render prompt from template
            prompts = self.prompt_loader.render(
                "kdp/description",
                context=context
            )

            if not prompts or not isinstance(prompts, dict):
                raise Exception(f"Prompt rendering failed: prompts={prompts}")

            if 'user' not in prompts or 'system' not in prompts:
                raise Exception(f"Prompt missing required keys: {list(prompts.keys())}")

            # Get temperature from config
            temperature = self.prompt_loader.get_temperature("kdp/description", default=0.7)

            response = await self.client.completion(
                model=self.model,
                prompt=prompts['user'],
                system_prompt=prompts['system'],
                temperature=temperature,
                display=False
            )

            if not response:
                raise Exception("API returned None/empty response")

            return response.strip()

        except Exception as e:
            raise Exception(f"Description generation failed at: {type(e).__name__}: {str(e)}")

    async def generate_keywords(self) -> List[str]:
        """
        Generate 7 keyword boxes optimized for Amazon search.

        Returns:
            List of 7 keyword strings (50 characters max each)
        """
        context = self._build_context()

        # Render prompt from template
        prompts = self.prompt_loader.render(
            "kdp/keywords",
            context=context
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature("kdp/keywords", default=0.7)

        response = await self.client.completion(
            model=self.model,
            prompt=prompts['user'],
            system_prompt=prompts['system'],
            temperature=temperature,
            display=False
        )

        # Parse keywords
        keywords = [line.strip() for line in response.strip().split('\n') if line.strip()]
        keywords = keywords[:7]  # Ensure exactly 7

        # Truncate to 50 characters
        keywords = [kw[:50] if len(kw) > 50 else kw for kw in keywords]

        # Pad if less than 7
        while len(keywords) < 7:
            keywords.append("")

        return keywords

    async def generate_categories(self) -> List[Dict[str, str]]:
        """
        Recommend 3 optimal Amazon categories.

        Returns:
            List of 3 category dicts with path and reasoning
        """
        context = self._build_context()

        prompt = f"""You are an expert in Amazon KDP category selection.

Based on the book content below, recommend 3 optimal categories for maximum visibility and sales.

REQUIREMENTS:
- Be as SPECIFIC as possible (subcategories, not broad categories)
- Balance: some reach + some niche for "bestseller" badges
- Must accurately reflect book content
- Format: Books > [Genre] > [Subgenre] > [Specific]
- Consider competition (niche categories easier to rank)

BOOK CONTENT:
{context}

For each category, provide:
1. Category path (e.g., "Books > Science Fiction > Space Opera")
2. Brief reasoning (why this category?)

Format:
CATEGORY 1: [path]
REASON: [one sentence]

CATEGORY 2: [path]
REASON: [one sentence]

CATEGORY 3: [path]
REASON: [one sentence]"""

        response = await self.client.completion(
            model=self.model,
            prompt=prompt,
            temperature=0.7,
            display=False
        )

        # Parse categories
        categories = self._parse_categories(response)

        return categories

    async def generate_author_bio(self, author_info: Optional[str] = None) -> str:
        """
        Generate author bio (100-200 words).

        Args:
            author_info: Optional additional info about author

        Returns:
            Author bio in third person
        """
        context = self._build_context()

        author_name = self.project.get_book_metadata('author', 'the author')

        additional_info = ""
        if author_info:
            additional_info = f"\n\nADDITIONAL AUTHOR INFO:\n{author_info}"

        # Render prompt from template
        prompts = self.prompt_loader.render(
            "kdp/author_bio",
            author_name=author_name,
            context=context,
            additional_info=additional_info
        )

        # Get temperature from config
        temperature = self.prompt_loader.get_temperature("kdp/author_bio", default=0.7)

        response = await self.client.completion(
            model=self.model,
            prompt=prompts['user'],
            system_prompt=prompts['system'],
            temperature=temperature,
            display=False
        )

        return response.strip()

    async def suggest_comp_titles(self) -> List[Dict[str, str]]:
        """
        Suggest 3 comparable titles (comp titles).

        Returns:
            List of 3 comp title suggestions with reasoning
        """
        context = self._build_context()

        prompt = f"""You are an expert in book positioning and comparable titles (comp titles).

Based on the book content below, suggest 3 comp titles - similar books published in the last 3-5 years.

REQUIREMENTS:
- Recent books (2020-2025 preferred)
- Similar in: tone, themes, target audience, genre
- Successful but NOT mega-bestsellers (avoid Harry Potter, Twilight, etc.)
- Genuinely similar, not just popular
- Include why they're comparable

BOOK CONTENT:
{context}

For each comp title, provide:
1. Title and author
2. Why it's comparable (tone, themes, audience)
3. How to use it ("Perfect for fans of [Title]")

Format:
COMP 1: [Title] by [Author]
WHY: [one sentence]
USE: [suggestion]

COMP 2: [Title] by [Author]
WHY: [one sentence]
USE: [suggestion]

COMP 3: [Title] by [Author]
WHY: [one sentence]
USE: [suggestion]"""

        response = await self.client.completion(
            model=self.model,
            prompt=prompt,
            temperature=0.7,
            display=False
        )

        # Parse comp titles
        comp_titles = self._parse_comp_titles(response)

        return comp_titles

    def _build_context(self) -> str:
        """Build comprehensive context from book content."""
        parts = []

        # Book metadata
        title = self.project.get_book_metadata('title', 'Untitled')
        author = self.project.get_book_metadata('author', 'Unknown')
        parts.append(f"TITLE: {title}")
        parts.append(f"AUTHOR: {author}\n")

        # Premise
        premise = self.project.get_premise()
        if premise:
            parts.append("PREMISE:")
            parts.append(premise)
            parts.append("")

        # Treatment (first 2000 words for context)
        treatment = self.project.get_treatment()
        if treatment:
            parts.append("TREATMENT (excerpt):")
            words = treatment.split()[:2000]
            parts.append(' '.join(words))
            if len(treatment.split()) > 2000:
                parts.append("[...truncated]")
            parts.append("")

        # Chapters metadata (from chapters.yaml)
        chapters_yaml = self.project.get_chapters_yaml()
        if chapters_yaml:
            # Extract key metadata
            metadata = chapters_yaml.get('metadata', {})
            if metadata:
                parts.append("GENRE & METADATA:")
                parts.append(f"Genre: {metadata.get('genre', 'Unknown')}")
                parts.append(f"Subgenre: {metadata.get('subgenre', '')}")
                parts.append(f"Tone: {metadata.get('tone', '')}")
                parts.append(f"Themes: {', '.join(metadata.get('themes', []))}")
                parts.append(f"Tropes: {', '.join(metadata.get('tropes', []))}")
                parts.append("")

            # Characters summary
            characters = chapters_yaml.get('characters', [])
            if characters:
                parts.append("MAIN CHARACTERS:")
                for char in characters[:3]:  # Top 3 characters
                    description = char.get('description') or char.get('background', '')
                    # Handle None values explicitly
                    description = description[:100] if description else ''
                    parts.append(f"- {char.get('name', 'Unknown')}: {char.get('role', '')} - {description}")
                parts.append("")

            # Chapter outlines (summary)
            chapters = chapters_yaml.get('chapters', [])
            if chapters:
                parts.append(f"STORY STRUCTURE: {len(chapters)} chapters")
                parts.append("Chapter highlights:")
                for ch in chapters[:3]:  # First 3 chapters
                    summary = ch.get('summary', '') or ''  # Handle explicit None
                    summary_excerpt = summary[:100] if summary else ''
                    parts.append(f"- Ch{ch.get('number', '?')}: {ch.get('title', 'Untitled')} - {summary_excerpt}")
                if len(chapters) > 3:
                    parts.append(f"[...and {len(chapters) - 3} more chapters]")
                parts.append("")

        # Sample of actual prose (first chapter excerpt)
        chapter_files = list(self.project.list_chapters())
        if chapter_files:
            first_chapter = min(chapter_files, key=lambda f: f.name)
            prose = first_chapter.read_text(encoding='utf-8')
            words = prose.split()[:500]
            parts.append("PROSE SAMPLE (Chapter 1 excerpt):")
            parts.append(' '.join(words))
            if len(prose.split()) > 500:
                parts.append("[...truncated]")
            parts.append("")

        return '\n'.join(parts)

    def _build_comprehensive_prompt(self, context: str) -> str:
        """Build comprehensive prompt for all metadata generation."""
        return f"""You are an expert Amazon KDP metadata specialist and book marketer.

Based on the book content below, generate ALL metadata needed for a successful KDP launch.

Generate the following in this EXACT format:

DESCRIPTION:
[100-150 word HTML-formatted book description with <b>, <i>, <br> tags]

KEYWORDS:
[7 keyword phrases, one per line, max 50 chars each]

CATEGORIES:
Category 1: [path]
Reason: [why]
Category 2: [path]
Reason: [why]
Category 3: [path]
Reason: [why]

COMP TITLES:
1. [Title] by [Author] - [why comparable]
2. [Title] by [Author] - [why comparable]
3. [Title] by [Author] - [why comparable]

AUTHOR BIO:
[100-200 word bio in third person]

BOOK CONTENT:
{context}

Generate all metadata now:"""

    def _parse_metadata_response(self, response: str) -> Dict[str, Any]:
        """Parse comprehensive metadata response."""
        metadata = {
            'description': '',
            'keywords': [],
            'categories': [],
            'comp_titles': [],
            'author_bio': ''
        }

        # Split by sections
        sections = response.split('\n\n')

        current_section = None
        for section in sections:
            section = section.strip()

            if section.startswith('DESCRIPTION:'):
                current_section = 'description'
                metadata['description'] = section.replace('DESCRIPTION:', '').strip()
            elif section.startswith('KEYWORDS:'):
                current_section = 'keywords'
            elif section.startswith('CATEGORIES:'):
                current_section = 'categories'
            elif section.startswith('COMP TITLES:'):
                current_section = 'comp_titles'
            elif section.startswith('AUTHOR BIO:'):
                current_section = 'author_bio'
                metadata['author_bio'] = section.replace('AUTHOR BIO:', '').strip()
            elif current_section == 'description' and section:
                metadata['description'] += '\n\n' + section
            elif current_section == 'keywords' and section and not section.startswith('CATEGORIES:'):
                keywords = [line.strip() for line in section.split('\n') if line.strip()]
                metadata['keywords'].extend(keywords[:7])
            elif current_section == 'author_bio' and section:
                metadata['author_bio'] += '\n\n' + section

        # Ensure 7 keywords
        while len(metadata['keywords']) < 7:
            metadata['keywords'].append("")

        return metadata

    def _parse_categories(self, response: str) -> List[Dict[str, str]]:
        """Parse category recommendations."""
        categories = []

        lines = response.strip().split('\n')
        current_cat = {}

        for line in lines:
            line = line.strip()

            if line.startswith('CATEGORY'):
                if current_cat:
                    categories.append(current_cat)
                current_cat = {}
                # Extract path
                if ':' in line:
                    path = line.split(':', 1)[1].strip()
                    current_cat['path'] = path
            elif line.startswith('REASON:'):
                reason = line.replace('REASON:', '').strip()
                current_cat['reason'] = reason

        if current_cat:
            categories.append(current_cat)

        return categories[:3]

    def _parse_comp_titles(self, response: str) -> List[Dict[str, str]]:
        """Parse comp title suggestions."""
        comp_titles = []

        lines = response.strip().split('\n')
        current_comp = {}

        for line in lines:
            line = line.strip()

            if line.startswith('COMP'):
                if current_comp:
                    comp_titles.append(current_comp)
                current_comp = {}
                # Extract title info
                if ':' in line:
                    info = line.split(':', 1)[1].strip()
                    current_comp['info'] = info
            elif line.startswith('WHY:'):
                why = line.replace('WHY:', '').strip()
                current_comp['why'] = why
            elif line.startswith('USE:'):
                use = line.replace('USE:', '').strip()
                current_comp['use'] = use

        if current_comp:
            comp_titles.append(current_comp)

        return comp_titles[:3]

    def save_metadata_file(self, metadata: Dict[str, Any], output_path: Optional[Path] = None):
        """
        Save metadata to publishing-metadata.md file.

        Args:
            metadata: Generated metadata dict
            output_path: Optional custom path
        """
        if output_path is None:
            # Ensure exports directory exists
            self.project.exports_dir.mkdir(exist_ok=True)
            output_path = self.project.publishing_metadata_file

        # Load template
        template_path = Path(__file__).parent.parent.parent / 'docs' / 'PUBLISHING_METADATA_TEMPLATE.md'

        if template_path.exists():
            template = template_path.read_text(encoding='utf-8')
        else:
            # Fallback to basic format
            template = self._get_basic_template()

        # Replace placeholders
        title = self.project.get_book_metadata('title', 'Untitled')
        author = self.project.get_book_metadata('author', 'Unknown')
        from datetime import datetime
        year = self.project.get_book_metadata('copyright_year', datetime.now().year)

        content = template.replace('{{title}}', title)
        content = content.replace('{{author}}', author)
        content = content.replace('{{copyright_year}}', str(year))
        content = content.replace('{{date}}', datetime.now().strftime('%Y-%m-%d'))

        # Insert generated metadata
        if metadata.get('description'):
            content = self._insert_section(content, '## Book Description', metadata['description'])

        if metadata.get('keywords'):
            for i, keyword in enumerate(metadata['keywords'], 1):
                content = content.replace(f'### Keyword Box {i} (50 char max):\n```\n\n```',
                                         f'### Keyword Box {i} (50 char max):\n```\n{keyword}\n```')

        # Note: Author bio is NOT auto-generated (users should write their own)

        # Write to file
        output_path.write_text(content, encoding='utf-8')

    def _insert_section(self, content: str, section_header: str, new_text: str) -> str:
        """Insert generated text into a section."""
        # For Book Description section, replace the placeholder in the code block
        if section_header == '## Book Description':
            placeholder = '[Generated description will appear here]'
            if placeholder in content:
                content = content.replace(placeholder, new_text)
            return content

        # Find the section for other headers
        if section_header in content:
            # Find next section or end
            start = content.find(section_header)
            next_section = content.find('\n## ', start + len(section_header))

            if next_section == -1:
                # Last section
                before = content[:start]
                return before + section_header + '\n\n' + new_text + '\n\n'
            else:
                before = content[:start]
                after = content[next_section:]
                return before + section_header + '\n\n' + new_text + '\n\n' + after

        return content

    def _get_basic_template(self) -> str:
        """Get basic template if file doesn't exist."""
        return """# Publishing Metadata

**Book**: {{title}}
**Author**: {{author}}
**Generated**: {{date}}

---

## Book Description

```
[Generated description will appear here]
```

---

## Keywords (7 Search Terms)

### Keyword Box 1 (50 char max):
```

```

### Keyword Box 2 (50 char max):
```

```

### Keyword Box 3 (50 char max):
```

```

### Keyword Box 4 (50 char max):
```

```

### Keyword Box 5 (50 char max):
```

```

### Keyword Box 6 (50 char max):
```

```

### Keyword Box 7 (50 char max):
```

```
"""
