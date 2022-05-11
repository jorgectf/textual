from __future__ import annotations

from typing import Iterable, Iterator, TYPE_CHECKING

import rich.repr
from rich.highlighter import ReprHighlighter
from rich.pretty import Pretty
from rich.style import Style
from rich.text import Text
from rich.tree import Tree

from ._node_list import NodeList
from .color import Color
from .css._error_tools import friendly_list
from .css.constants import VALID_DISPLAY, VALID_VISIBILITY
from .css.errors import StyleValueError
from .css.parse import parse_declarations
from .css.styles import Styles, RenderStyles
from .css.query import NoMatchingNodesError
from .message_pump import MessagePump

if TYPE_CHECKING:
    from .app import App
    from .css.query import DOMQuery
    from .screen import Screen


class NoParent(Exception):
    pass


@rich.repr.auto
class DOMNode(MessagePump):
    """A node in a hierarchy of things forming the UI.

    Nodes are mountable and may be styled with CSS.

    """

    DEFAULT_STYLES = ""
    INLINE_STYLES = ""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self._name = name
        self._id = id
        self._classes: set[str] = set() if classes is None else set(classes.split())
        self.children = NodeList()
        self._css_styles: Styles = Styles(self)
        self._inline_styles: Styles = Styles.parse(
            self.INLINE_STYLES, repr(self), node=self
        )
        self.styles = RenderStyles(self, self._css_styles, self._inline_styles)
        self._default_styles = Styles()
        self._default_rules = self._default_styles.extract_rules((0, 0, 0))
        super().__init__()

    def on_register(self, app: App) -> None:
        """Called when the widget is registered

        Args:
            app (App): Parent application.
        """

    def __rich_repr__(self) -> rich.repr.Result:
        yield "name", self._name, None
        yield "id", self._id, None
        if self._classes:
            yield "classes", " ".join(self._classes)

    @property
    def parent(self) -> DOMNode | None:
        """Get the parent node.

        Returns:
            DOMNode: The node which is the direct parent of this node.
        """
        return self._parent

    @property
    def screen(self) -> "Screen":
        """Get the screen that this node is contained within. Note that this may not be the currently active screen within the app."""
        # Get the node by looking up a chain of parents
        # Note that self.screen may not be the same as self.app.screen
        from .screen import Screen

        node = self
        while node and not isinstance(node, Screen):
            node = node._parent
        assert isinstance(node, Screen)
        return node

    @property
    def id(self) -> str | None:
        """The ID of this node, or None if the node has no ID.

        Returns:
            (str | None): A Node ID or None.
        """
        return self._id

    @id.setter
    def id(self, new_id: str) -> str:
        """Sets the ID (may only be done once).

        Args:
            new_id (str): ID for this node.

        Raises:
            ValueError: If the ID has already been set.

        """
        if self._id is not None:
            raise ValueError(
                f"Node 'id' attribute may not be changed once set (current id={self._id!r})"
            )
        self._id = new_id
        return new_id

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def css_identifier(self) -> str:
        """A CSS selector that identifies this DOM node."""
        tokens = [self.__class__.__name__]
        if self.id is not None:
            tokens.append(f"#{self.id}")
        return "".join(tokens)

    @property
    def css_identifier_styled(self) -> Text:
        """A stylized CSS identifier."""
        tokens = Text.styled(self.__class__.__name__)
        if self.id is not None:
            tokens.append(f"#{self.id}", style="bold")
        if self.classes:
            tokens.append(".")
            tokens.append(".".join(class_name for class_name in self.classes), "italic")
        if self.name:
            tokens.append(f"[name={self.name}]", style="underline")
        return tokens

    @property
    def classes(self) -> frozenset[str]:
        return frozenset(self._classes)

    @property
    def pseudo_classes(self) -> frozenset[str]:
        """Get a set of all pseudo classes"""
        pseudo_classes = frozenset({*self.get_pseudo_classes()})
        return pseudo_classes

    @property
    def css_type(self) -> str:
        """Gets the CSS type, used by the CSS.

        Returns:
            str: A type used in CSS (lower cased class name).
        """
        return self.__class__.__name__.lower()

    @property
    def css_path_nodes(self) -> list[DOMNode]:
        """A list of nodes from the root to this node, forming a "path".

        Returns:
            list[DOMNode]: List of Nodes, starting with the root and ending with this node.
        """
        result: list[DOMNode] = [self]
        append = result.append

        node: DOMNode = self
        while isinstance(node._parent, DOMNode):
            node = node._parent
            append(node)
        return result[::-1]

    @property
    def display(self) -> bool:
        """
        Returns: ``True`` if this DOMNode is displayed (``display != "none"``), ``False`` otherwise.
        """
        return self.styles.display != "none"

    @display.setter
    def display(self, new_val: bool | str) -> None:
        """
        Args:
            new_val (bool | str): Shortcut to set the ``display`` CSS property.
                ``False`` will set ``display: none``. ``True`` will set ``display: block``.
                A ``False`` value will prevent the DOMNode from consuming space in the layout.
        """
        # TODO: This will forget what the original "display" value was, so if a user
        #  toggles to False then True, we'll reset to the default "block", rather than
        #  what the user initially specified.
        if isinstance(new_val, bool):
            self.styles.display = "block" if new_val else "none"
        elif new_val in VALID_DISPLAY:
            self.styles.display = new_val
        else:
            raise StyleValueError(
                f"invalid value for display (received {new_val!r}, "
                f"expected {friendly_list(VALID_DISPLAY)})",
            )

    @property
    def visible(self) -> bool:
        return self.styles.visibility != "hidden"

    @visible.setter
    def visible(self, new_value: bool) -> None:
        if isinstance(new_value, bool):
            self.styles.visibility = "visible" if new_value else "hidden"
        elif new_value in VALID_VISIBILITY:
            self.styles.visibility = new_value
        else:
            raise StyleValueError(
                f"invalid value for visibility (received {new_value!r}, "
                f"expected {friendly_list(VALID_VISIBILITY)})"
            )

    @property
    def tree(self) -> Tree:
        """Get a Rich tree object which will recursively render the structure of the node tree.

        Returns:
            Tree: A Rich object which may be printed.
        """
        from rich.columns import Columns
        from rich.console import Group
        from rich.panel import Panel

        highlighter = ReprHighlighter()
        tree = Tree(highlighter(repr(self)))

        def add_children(tree, node):
            for child in node.children:
                info = Columns(
                    [
                        Pretty(child),
                        highlighter(f"region={child.region!r}"),
                        highlighter(
                            f"virtual_size={child.virtual_size!r}",
                        ),
                    ]
                )
                css = child.styles.css
                if css:
                    info = Group(
                        info,
                        Panel.fit(
                            Text(child.styles.css),
                            border_style="dim",
                            title="css",
                            title_align="left",
                        ),
                    )
                branch = tree.add(info)
                if tree.children:
                    add_children(branch, child)

        add_children(tree, self)
        return tree

    @property
    def rich_text_style(self) -> Style:
        """Get the text style object.

        A widget's style is influenced by its parent. For instance if a widgets background has an alpha,
        then its parent's background color will show through. Additionally, widgets will inherit their
        parent's text style (i.e. bold, italic etc).

        Returns:
            Style: Rich Style object.
        """

        # TODO: Feels like there may be opportunity for caching here.

        background = Color(0, 0, 0, 0)
        color = Color(255, 255, 255, 0)
        style = Style()
        for node in reversed(self.ancestors):
            styles = node.styles
            if styles.has_rule("background"):
                background += styles.background
            if styles.has_rule("color"):
                color = styles.color
            style += styles.text_style

        style = Style(bgcolor=background.rich_color, color=color.rich_color) + style
        return style

    @property
    def ancestors(self) -> list[DOMNode]:
        """Get a list of Nodes by tracing ancestors all the way back to App."""

        nodes: list[DOMNode] = [self]
        add_node = nodes.append
        node = self
        while True:
            node = node.parent
            if node is None:
                break
            add_node(node)
        return nodes

    @property
    def displayed_children(self) -> list[DOMNode]:
        """The children which don't have display: none set."""
        return [child for child in self.children if child.display]

    @property
    def focusable_children(self) -> list[DOMNode]:
        """Get the children which may be focused."""
        # TODO: This may be the place to define order, other focus related rules
        return [child for child in self.children if child.display and child.visible]

    def get_pseudo_classes(self) -> Iterable[str]:
        """Get any pseudo classes applicable to this Node, e.g. hover, focus.

        Returns:
            Iterable[str]: Iterable of strings, such as a generator.
        """
        return ()

    def reset_styles(self) -> None:
        from .widget import Widget

        for node in self.walk_children():
            node._css_styles.reset()
            if isinstance(node, Widget):
                node.set_dirty()
                node._layout_required = True

    def on_style_change(self) -> None:
        pass

    def add_child(self, node: DOMNode) -> None:
        """Add a new child node.

        Args:
            node (DOMNode): A DOM node.
        """
        self.children._append(node)
        node.set_parent(self)

    def add_children(self, *nodes: DOMNode, **named_nodes: DOMNode) -> None:
        """Add multiple children to this node.

        Args:
            *nodes (DOMNode): Positional args should be new DOM nodes.
            **named_nodes (DOMNode): Keyword args will be assigned the argument name as an ID.
        """
        _append = self.children._append
        for node in nodes:
            _append(node)
        for node_id, node in named_nodes.items():
            _append(node)
            node.id = node_id

    def walk_children(self, with_self: bool = True) -> Iterable[DOMNode]:
        """Generate all descendents of this node.

        Args:
            with_self (bool, optional): Also include self in the results. Defaults to True.

        """

        stack: list[Iterator[DOMNode]] = [iter(self.children)]
        pop = stack.pop
        push = stack.append

        if with_self:
            yield self

        while stack:
            node = next(stack[-1], None)
            if node is None:
                pop()
            else:
                yield node
                if node.children:
                    push(iter(node.children))

    def get_child(self, id: str) -> DOMNode:
        """Return the first child (immediate descendent) of this node with the given ID.

        Args:
            id (str): The ID of the child.

        Returns:
            DOMNode: The first child of this node with the ID.

        Raises:
            NoMatchingNodesError: if no children could be found for this ID
        """
        for child in self.children:
            if child.id == id:
                return child
        raise NoMatchingNodesError(f"No child found with id={id!r}")

    def query(self, selector: str | None = None) -> DOMQuery:
        """Get a DOM query.

        Args:
            selector (str, optional): A CSS selector or `None` for all nodes. Defaults to None.

        Returns:
            DOMQuery: A query object.
        """
        from .css.query import DOMQuery

        return DOMQuery(self, selector)

    def set_styles(self, css: str | None = None, **styles) -> None:
        """Set custom styles on this object."""
        # TODO: This can be done more efficiently
        kwarg_css = "\n".join(
            f"{key.replace('_', '-')}: {value}" for key, value in styles.items()
        )
        apply_css = f"{css or ''}\n{kwarg_css}\n"
        new_styles = parse_declarations(apply_css, f"<custom styles for ${self!r}>")
        self.styles.merge(new_styles)
        self.refresh()

    def has_class(self, *class_names: str) -> bool:
        """Check if the Node has all the given class names.

        Args:
            *class_names (str): CSS class names to check.

        Returns:
            bool: ``True`` if the node has all the given class names, otherwise ``False``.
        """
        return self._classes.issuperset(class_names)

    def add_class(self, *class_names: str) -> None:
        """Add class names to this Node.

        Args:
            *class_names (str): CSS class names to add.

        """
        self._classes.update(class_names)
        try:
            self.app.stylesheet.update(self.app, animate=True)
            self.refresh()
        except LookupError:
            pass

    def remove_class(self, *class_names: str) -> None:
        """Remove class names from this Node.

        Args:
            *class_names (str): CSS class names to remove.

        """
        self._classes.difference_update(class_names)
        try:
            self.app.stylesheet.update(self.app, animate=True)
            self.refresh()
        except LookupError:
            pass

    def toggle_class(self, *class_names: str) -> None:
        """Toggle class names on this Node.

        Args:
            *class_names (str): CSS class names to toggle.

        """
        self._classes.symmetric_difference_update(class_names)
        try:
            self.app.stylesheet.update(self.app, animate=True)
            self.refresh()
        except LookupError:
            pass

    def has_pseudo_class(self, *class_names: str) -> bool:
        """Check for pseudo class (such as hover, focus etc)"""
        has_pseudo_classes = self.pseudo_classes.issuperset(class_names)
        return has_pseudo_classes

    def refresh(self, *, repaint: bool = True, layout: bool = False) -> None:
        pass