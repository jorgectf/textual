from __future__ import annotations

from functools import partial

import rich.repr
from rich.text import Text, TextType
from typing_extensions import Literal, Self

from .. import events
from ..binding import Binding
from ..css._error_tools import friendly_list
from ..message import Message
from ..reactive import reactive
from ..widgets import Static

ButtonVariant = Literal["default", "primary", "success", "warning", "error"]
"""The names of the valid button variants.

These are the variants that can be used with a [`Button`][textual.widgets.Button].
"""

_VALID_BUTTON_VARIANTS = {"default", "primary", "success", "warning", "error"}


class InvalidButtonVariant(Exception):
    """Exception raised if an invalid button variant is used."""


class Button(Static, can_focus=True):
    """A simple clickable button."""

    DEFAULT_CSS = """
    Button {
        width: auto;
        min-width: 16;
        height: 3;
        background: $boost;
        color: $text;
        border: tall $background;

        content-align: center middle;
        text-style: bold;
    }

    App.-dark-mode Button:disabled {
        border: tall transparent;
    }

    Button:focus {
        text-style: bold reverse;
    }

    Button:hover {
        border: tall $accent 60%;
    }

    Button.-active {
        opacity: 0.5;
    }

    App.-light-mode Button.-default {
        border: tall $foreground;
    }

    App.-light-mode Button.-default:hover {
        border: tall $accent;
    }


    /* Primary variant */
    Button.-primary {
        background: $primary;
        color: $text;
    }

    App.-light-mode Button.-primary {
        background: $primary;
        color: $text;
    }

    Button.-primary:hover {
        background: $primary-darken-1;
    }

    App.-light-mode Button.-primary:hover {
        border: tall $foreground;
        background: $primary-lighten-1;
    }


    /* Success variant */
    Button.-success {
        color: $success 90%;
        background: $success 20%;
    }

    Button.-success.-active {

    }

    Button.-success:hover {
        border: tall $success 60%;
    }

    App.-light-mode Button.-success {
        background: $success 80%;
        color: $text;
    }

    App.-light-mode Button.-success:hover {
        border: tall $foreground;
    }

    /* Warning variant */
    Button.-warning {
        background: $warning 15%;
        color: $warning 90%;

    }

    Button.-warning:hover {
        border: tall $warning 60%;
    }

    App.-light-mode Button.-warning {
        background: $warning 80%;
        color: $text;
    }

    App.-light-mode Button.-warning:hover {
        border: tall $foreground;
    }


    /* Error variant */
    Button.-error {
        background: $error 20%;
        color: $error 90%;
    }

    Button.-error:hover {
       border: tall $error 60%;
    }

    App.-light-mode Button.-error {
        background: $error;
        color: $text;
    }

    App.-light-mode Button.-error:hover {
        border: tall $foreground;
    }




    """

    BINDINGS = [Binding("enter", "press", "Press Button", show=False)]

    ACTIVE_EFFECT_DURATION = 0.3
    """When buttons are clicked they get the `-active` class for this duration (in seconds)"""

    label: reactive[TextType] = reactive[TextType]("")
    """The text label that appears within the button."""

    variant = reactive("default")
    """The variant name for the button."""

    class Pressed(Message, bubble=True):
        """Event sent when a `Button` is pressed.

        Can be handled using `on_button_pressed` in a subclass of
        [`Button`][textual.widgets.Button] or in a parent widget in the DOM.
        """

        def __init__(self, button: Button) -> None:
            self.button: Button = button
            """The button that was pressed."""
            super().__init__()

        @property
        def control(self) -> Button:
            """An alias for [Pressed.button][textual.widgets.Button.Pressed.button].

            This will be the same value as [Pressed.button][textual.widgets.Button.Pressed.button].
            """
            return self.button

    def __init__(
        self,
        label: TextType | None = None,
        variant: ButtonVariant = "default",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        """Create a Button widget.

        Args:
            label: The text that appears within the button.
            variant: The variant of the button.
            name: The name of the button.
            id: The ID of the button in the DOM.
            classes: The CSS classes of the button.
            disabled: Whether the button is disabled or not.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        if label is None:
            label = self.css_identifier_styled

        self.label = self.validate_label(label)

        self.variant = self.validate_variant(variant)

    def __rich_repr__(self) -> rich.repr.Result:
        yield from super().__rich_repr__()
        yield "variant", self.variant, "default"

    def validate_variant(self, variant: str) -> str:
        if variant not in _VALID_BUTTON_VARIANTS:
            raise InvalidButtonVariant(
                f"Valid button variants are {friendly_list(_VALID_BUTTON_VARIANTS)}"
            )
        return variant

    def watch_variant(self, old_variant: str, variant: str):
        self.remove_class(f"-{old_variant}")
        self.add_class(f"-{variant}")

    def validate_label(self, label: TextType) -> TextType:
        """Parse markup for self.label"""
        if isinstance(label, str):
            return Text.from_markup(label)
        return label

    def render(self) -> TextType:
        label = Text.assemble(" ", self.label, " ")
        label.stylize(self.text_style)
        return label

    async def _on_click(self, event: events.Click) -> None:
        event.stop()
        self.press()

    def press(self) -> Self:
        """Respond to a button press.

        Returns:
            The button instance."""
        if self.disabled or not self.display:
            return self
        # Manage the "active" effect:
        self._start_active_affect()
        # ...and let other components know that we've just been clicked:
        self.post_message(Button.Pressed(self))
        return self

    def _start_active_affect(self) -> None:
        """Start a small animation to show the button was clicked."""
        self.add_class("-active")
        self.set_timer(
            self.ACTIVE_EFFECT_DURATION, partial(self.remove_class, "-active")
        )

    def action_press(self) -> None:
        """Activate a press of the button."""
        self.press()

    @classmethod
    def success(
        cls,
        label: TextType | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> Button:
        """Utility constructor for creating a success Button variant.

        Args:
            label: The text that appears within the button.
            disabled: Whether the button is disabled or not.
            name: The name of the button.
            id: The ID of the button in the DOM.
            classes: The CSS classes of the button.
            disabled: Whether the button is disabled or not.

        Returns:
            A [`Button`][textual.widgets.Button] widget of the 'success'
                [variant][textual.widgets.button.ButtonVariant].
        """
        return Button(
            label=label,
            variant="success",
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )

    @classmethod
    def warning(
        cls,
        label: TextType | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> Button:
        """Utility constructor for creating a warning Button variant.

        Args:
            label: The text that appears within the button.
            disabled: Whether the button is disabled or not.
            name: The name of the button.
            id: The ID of the button in the DOM.
            classes: The CSS classes of the button.
            disabled: Whether the button is disabled or not.

        Returns:
            A [`Button`][textual.widgets.Button] widget of the 'warning'
                [variant][textual.widgets.button.ButtonVariant].
        """
        return Button(
            label=label,
            variant="warning",
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )

    @classmethod
    def error(
        cls,
        label: TextType | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> Button:
        """Utility constructor for creating an error Button variant.

        Args:
            label: The text that appears within the button.
            disabled: Whether the button is disabled or not.
            name: The name of the button.
            id: The ID of the button in the DOM.
            classes: The CSS classes of the button.
            disabled: Whether the button is disabled or not.

        Returns:
            A [`Button`][textual.widgets.Button] widget of the 'error'
                [variant][textual.widgets.button.ButtonVariant].
        """
        return Button(
            label=label,
            variant="error",
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
