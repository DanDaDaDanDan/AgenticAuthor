"""Interactive taxonomy editor using prompt_toolkit."""

from typing import Dict, Any, List, Optional, Tuple
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.widgets import Frame
from rich.console import Console


class TaxonomyEditor:
    """Interactive taxonomy selection editor."""

    def __init__(
        self,
        taxonomy: Dict[str, Any],
        current_selections: Dict[str, Any],
        category_options: Dict[str, List[str]]
    ):
        """
        Initialize taxonomy editor.

        Args:
            taxonomy: Full taxonomy structure
            current_selections: Currently selected values
            category_options: Available options per category
        """
        self.taxonomy = taxonomy
        self.current_selections = current_selections.copy()
        self.category_options = category_options

        # Build category list
        self.categories = list(category_options.keys())
        self.current_category_index = 0
        self.current_option_index = 0

        # Track changes
        self.original_selections = current_selections.copy()
        self.changes_made = []

        self.console = Console()

    def get_current_category(self) -> str:
        """Get currently selected category."""
        if 0 <= self.current_category_index < len(self.categories):
            return self.categories[self.current_category_index]
        return ""

    def get_current_options(self) -> List[str]:
        """Get options for current category."""
        category = self.get_current_category()
        return self.category_options.get(category, [])

    def is_option_selected(self, option: str) -> bool:
        """Check if option is currently selected."""
        category = self.get_current_category()
        selected = self.current_selections.get(category, [])

        if isinstance(selected, list):
            return option in selected
        else:
            return str(selected) == option

    def toggle_option(self, option: str):
        """Toggle selection of an option."""
        category = self.get_current_category()
        current = self.current_selections.get(category, [])

        # Determine if multi-select or single-select
        # (Usually multi-select, but some categories might be single)
        if isinstance(current, list):
            # Multi-select
            if option in current:
                current.remove(option)
            else:
                current.append(option)
            self.current_selections[category] = current
        else:
            # Single-select
            self.current_selections[category] = [option]

    def get_display_text(self) -> FormattedText:
        """Generate formatted text for display."""
        lines = []

        # Header
        lines.append(("class:header", "═" * 80))
        lines.append(("class:header", " TAXONOMY EDITOR - Use ↑↓ to navigate, SPACE to toggle, TAB to switch category, ENTER to save"))
        lines.append(("class:header", "═" * 80))
        lines.append(("", "\n"))

        # Category tabs
        category_line = []
        for i, cat in enumerate(self.categories):
            display_name = cat.replace('_', ' ').title()
            if i == self.current_category_index:
                category_line.append(("class:category-selected", f" [{display_name}] "))
            else:
                category_line.append(("class:category", f"  {display_name}  "))

        lines.extend(category_line)
        lines.append(("", "\n\n"))

        # Current category options
        category = self.get_current_category()
        options = self.get_current_options()

        lines.append(("class:category-name", f"{category.replace('_', ' ').title()}:\n"))
        lines.append(("", "\n"))

        for i, option in enumerate(options):
            is_selected = self.is_option_selected(option)
            is_current = i == self.current_option_index

            # Build line
            if is_current:
                prefix = "class:option-cursor"
                marker = "→ "
            else:
                prefix = "class:option"
                marker = "  "

            if is_selected:
                checkbox = "[✓] "
                style = "class:option-selected" if not is_current else "class:option-cursor-selected"
            else:
                checkbox = "[ ] "
                style = prefix

            lines.append((style, f"{marker}{checkbox}{option}\n"))

        # Footer with help
        lines.append(("", "\n"))
        lines.append(("class:footer", "─" * 80))
        lines.append(("class:footer", "\n"))
        lines.append(("class:help", "↑/↓: Navigate  SPACE: Toggle  TAB: Next Category  SHIFT+TAB: Prev Category  ENTER: Save  ESC: Cancel"))

        return FormattedText(lines)

    def run(self) -> Optional[Dict[str, Any]]:
        """
        Run the interactive editor.

        Returns:
            Updated selections if saved, None if cancelled
        """
        kb = KeyBindings()

        # Navigation keys
        @kb.add('up')
        def move_up(event):
            if self.current_option_index > 0:
                self.current_option_index -= 1
            app.invalidate()

        @kb.add('down')
        def move_down(event):
            options = self.get_current_options()
            if self.current_option_index < len(options) - 1:
                self.current_option_index += 1
            app.invalidate()

        @kb.add('tab')
        def next_category(event):
            if self.current_category_index < len(self.categories) - 1:
                self.current_category_index += 1
                self.current_option_index = 0
            app.invalidate()

        @kb.add('s-tab')  # Shift+Tab
        def prev_category(event):
            if self.current_category_index > 0:
                self.current_category_index -= 1
                self.current_option_index = 0
            app.invalidate()

        # Toggle selection
        @kb.add('space')
        def toggle(event):
            options = self.get_current_options()
            if 0 <= self.current_option_index < len(options):
                option = options[self.current_option_index]
                self.toggle_option(option)
            app.invalidate()

        # Save and exit
        @kb.add('enter')
        def save_and_exit(event):
            event.app.exit(result=self.current_selections)

        # Cancel
        @kb.add('escape')
        @kb.add('c-c')
        def cancel(event):
            event.app.exit(result=None)

        # Create layout
        text_control = FormattedTextControl(
            text=self.get_display_text,
            focusable=True
        )

        window = Window(content=text_control)
        layout = Layout(window)

        # Create and run application
        app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=True,
            mouse_support=False
        )

        return app.run()


def run_taxonomy_editor(
    taxonomy: Dict[str, Any],
    current_selections: Dict[str, Any],
    category_options: Dict[str, List[str]]
) -> Optional[Dict[str, Any]]:
    """
    Run interactive taxonomy editor.

    Args:
        taxonomy: Full taxonomy structure
        current_selections: Current selections
        category_options: Available options per category

    Returns:
        Updated selections if saved, None if cancelled
    """
    editor = TaxonomyEditor(taxonomy, current_selections, category_options)
    return editor.run()
