"""Unit tests for data models."""
import pytest
from pathlib import Path

from src.models import (
    Project, ProjectMetadata,
    Story, Chapter, ChapterOutline,
    Taxonomy, GenreElement
)


class TestProject:
    """Test Project model."""

    def test_create_project(self, temp_dir):
        """Test creating a new project."""
        project = Project.create(
            temp_dir / "test_book",
            name="Test Book",
            genre="fantasy",
            author="Test Author"
        )

        assert project.is_valid
        assert project.metadata.name == "Test Book"
        assert project.metadata.genre == "fantasy"
        assert project.metadata.author == "Test Author"
        assert project.project_file.exists()
        assert project.chapters_dir.exists()
        assert project.analysis_dir.exists()

    def test_save_and_load_premise(self, temp_dir):
        """Test saving and loading premise."""
        project = Project.create(temp_dir / "test")

        premise = "This is a test premise for the story."
        project.save_premise(premise)

        loaded = project.get_premise()
        assert loaded == premise
        assert project.premise_file.exists()

    def test_save_and_load_chapter(self, temp_dir):
        """Test saving and loading chapters."""
        project = Project.create(temp_dir / "test")

        chapter_content = "# Chapter 1\n\nThis is chapter 1 content."
        project.save_chapter(1, chapter_content)

        loaded = project.get_chapter(1)
        assert loaded == chapter_content
        assert (project.chapters_dir / "chapter-01.md").exists()

    def test_word_count_update(self, temp_dir):
        """Test word count updates when saving chapters."""
        project = Project.create(temp_dir / "test")

        project.save_chapter(1, "This is a test chapter with some words.")
        project.save_chapter(2, "Another chapter with more words here.")

        # Word count should be updated
        assert project.metadata.word_count > 0


class TestStory:
    """Test Story model."""

    def test_story_initialization(self):
        """Test story model initialization."""
        story = Story()

        assert story.premise is None
        assert story.treatment is None
        assert len(story.chapter_outlines) == 0
        assert len(story.chapters) == 0

    def test_add_chapter_outline(self):
        """Test adding chapter outlines."""
        story = Story()

        outline = ChapterOutline(
            number=1,
            title="The Beginning",
            summary="Chapter 1 summary"
        )
        story.chapter_outlines.append(outline)

        assert len(story.chapter_outlines) == 1
        assert story.get_chapter_outline(1) == outline
        assert story.get_chapter_outline(2) is None

    def test_add_chapter(self):
        """Test adding full chapters."""
        story = Story()

        chapter = Chapter(
            number=1,
            title="Chapter One",
            content="Full chapter content...",
            word_count=100
        )
        story.add_chapter(chapter)

        assert len(story.chapters) == 1
        assert story.get_chapter(1) == chapter
        assert story.total_word_count == 100

    def test_story_completeness(self):
        """Test checking if story is complete."""
        story = Story()

        # Add outlines
        for i in range(1, 4):
            outline = ChapterOutline(
                number=i,
                title=f"Chapter {i}",
                summary=f"Summary {i}"
            )
            story.chapter_outlines.append(outline)

        assert not story.is_complete

        # Add all chapters
        for i in range(1, 4):
            chapter = Chapter(
                number=i,
                title=f"Chapter {i}",
                content=f"Content {i}",
                word_count=100
            )
            story.add_chapter(chapter)

        assert story.is_complete


class TestTaxonomy:
    """Test Taxonomy model."""

    def test_taxonomy_creation(self):
        """Test creating a taxonomy."""
        taxonomy = Taxonomy(
            name="Fantasy",
            description="Fantasy genre taxonomy",
            genre="fantasy",
            subgenres=["high fantasy", "urban fantasy"],
            themes=[
                GenreElement(name="Good vs Evil", description="Classic conflict"),
                GenreElement(name="Hero's Journey", description="Campbell's monomyth")
            ]
        )

        assert taxonomy.name == "Fantasy"
        assert len(taxonomy.themes) == 2
        assert taxonomy.themes[0].name == "Good vs Evil"

    def test_taxonomy_to_prompt_context(self):
        """Test converting taxonomy to prompt context."""
        taxonomy = Taxonomy(
            name="SciFi",
            description="Science Fiction",
            genre="scifi",
            themes=[
                GenreElement(name="AI", description="Artificial Intelligence"),
                GenreElement(name="Space", description="Space exploration")
            ],
            target_audience="Adult readers"
        )

        context = taxonomy.to_prompt_context()

        assert "Genre: scifi" in context
        assert "Description: Science Fiction" in context
        assert "Key Themes: AI, Space" in context
        assert "Target Audience: Adult readers" in context

    def test_taxonomy_serialization(self):
        """Test taxonomy dict conversion."""
        taxonomy = Taxonomy(
            name="Test",
            description="Test taxonomy",
            genre="test",
            themes=[GenreElement(name="Theme1", description="Desc1")]
        )

        data = taxonomy.to_dict()
        assert data['name'] == "Test"
        assert len(data['themes']) == 1
        assert data['themes'][0]['name'] == "Theme1"

        # Test round trip
        restored = Taxonomy.from_dict(data)
        assert restored.name == taxonomy.name
        assert len(restored.themes) == len(taxonomy.themes)