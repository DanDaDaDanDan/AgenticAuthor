"""Interactive model selector with fuzzy search."""

from typing import List, Optional, Tuple
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.widgets import TextArea


class ModelSelector:
    """Interactive model selection with fuzzy search."""

    def __init__(self, models: List[any], current_model: str):
        """
        Initialize model selector.

        Args:
            models: List of Model objects from API
            current_model: Currently selected model ID
        """
        self.models = models
        self.current_model = current_model
        self.search_text = ""
        self.selected_index = 0
        self.filtered_models = models.copy()

        # Pre-calculate display info
        self.model_info = []
        for model in models:
            provider = model.id.split('/')[0] if '/' in model.id else 'other'
            name = model.id.split('/', 1)[1] if '/' in model.id else model.id

            # Price info
            if model.is_free:
                price = "Free"
            else:
                price = f"${model.cost_per_1k_tokens * 1000:.4f}/1M"

            self.model_info.append({
                'model': model,
                'provider': provider,
                'name': name,
                'price': price,
                'display': f"{model.id} [{price}]"
            })

        self._update_filter()

    def _update_filter(self):
        """Update filtered models based on search text."""
        if not self.search_text:
            self.filtered_models = self.models.copy()
        else:
            search_lower = self.search_text.lower()
            matches = []

            for i, info in enumerate(self.model_info):
                model_id_lower = info['model'].id.lower()

                # Check if search term matches
                if search_lower in model_id_lower:
                    # Calculate relevance score
                    score = 0
                    if model_id_lower.startswith(search_lower):
                        score = 3
                    elif '/' + search_lower in model_id_lower:
                        score = 2
                    else:
                        score = 1

                    matches.append((self.models[i], score))

            # Sort by score (descending) then alphabetically
            matches.sort(key=lambda x: (-x[1], x[0].id.lower()))
            self.filtered_models = [m[0] for m in matches]

        # Reset selection if out of bounds
        if self.selected_index >= len(self.filtered_models):
            self.selected_index = max(0, len(self.filtered_models) - 1)

    def get_display_text(self) -> FormattedText:
        """Generate formatted text for display."""
        lines = []

        # Header
        lines.append(("class:header", "═" * 100))
        lines.append(("class:header", " MODEL SELECTOR - Type to filter, ↑↓ to navigate, ENTER to select, ESC to cancel"))
        lines.append(("class:header", "═" * 100))
        lines.append(("", "\n"))

        # Search box
        lines.append(("class:label", "Search: "))
        lines.append(("class:search", self.search_text))
        lines.append(("class:cursor", "▋"))
        lines.append(("", "\n\n"))

        # Results count
        total = len(self.models)
        filtered = len(self.filtered_models)
        if self.search_text:
            lines.append(("class:info", f"Showing {filtered} of {total} models\n\n"))
        else:
            lines.append(("class:info", f"Showing all {total} models\n\n"))

        # Model list (show up to 15)
        display_models = self.filtered_models[:15]

        for i, model in enumerate(display_models):
            info = next((inf for inf in self.model_info if inf['model'].id == model.id), None)
            if not info:
                continue

            is_selected = i == self.selected_index
            is_current = model.id == self.current_model

            # Build line
            if is_selected:
                prefix = "→ "
                style = "class:selected"
            else:
                prefix = "  "
                style = "class:normal"

            # Model ID with highlighting
            model_display = info['display']

            if is_current:
                model_display += " ← current"
                if is_selected:
                    style = "class:selected-current"
                else:
                    style = "class:current"

            lines.append((style, f"{prefix}{model_display}\n"))

        if filtered > 15:
            lines.append(("class:info", f"\n... and {filtered - 15} more (refine search to see)\n"))

        # Footer
        lines.append(("", "\n"))
        lines.append(("class:footer", "─" * 100))
        lines.append(("class:footer", "\n"))
        lines.append(("class:help", "Type: Filter  ↑↓: Navigate  ENTER: Select  ESC: Cancel  BACKSPACE: Clear char"))

        return FormattedText(lines)

    def run(self) -> Optional[str]:
        """
        Run the interactive selector.

        Returns:
            Selected model ID if chosen, None if cancelled
        """
        kb = KeyBindings()

        # Navigation
        @kb.add('up')
        def move_up(event):
            if self.selected_index > 0:
                self.selected_index -= 1
            app.invalidate()

        @kb.add('down')
        def move_down(event):
            if self.selected_index < min(len(self.filtered_models) - 1, 14):
                self.selected_index += 1
            app.invalidate()

        # Text input
        @kb.add('<any>')
        def add_char(event):
            # Add character to search
            if event.data and len(event.data) == 1 and event.data.isprintable():
                self.search_text += event.data
                self._update_filter()
                self.selected_index = 0
                app.invalidate()

        # Backspace
        @kb.add('backspace')
        def delete_char(event):
            if self.search_text:
                self.search_text = self.search_text[:-1]
                self._update_filter()
                self.selected_index = 0
                app.invalidate()

        # Select
        @kb.add('enter')
        def select(event):
            if self.filtered_models and 0 <= self.selected_index < len(self.filtered_models):
                event.app.exit(result=self.filtered_models[self.selected_index].id)
            else:
                event.app.exit(result=None)

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


def select_model_interactive(
    models: List[any],
    current_model: str
) -> Optional[str]:
    """
    Run interactive model selector.

    Args:
        models: List of Model objects
        current_model: Currently selected model ID

    Returns:
        Selected model ID if chosen, None if cancelled
    """
    selector = ModelSelector(models, current_model)
    return selector.run()
