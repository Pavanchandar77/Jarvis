"""UI-ish components for twin extraction."""


class ItemListComponent:
    """Renders a list of items."""

    def render(self, items):
        return "".join(f"<li>{item['name']}</li>" for item in items)


class ItemPage:
    """Page shell for the catalog."""

    def __init__(self):
        self.list = ItemListComponent()

    def render(self, items):
        return f"<ul>{self.list.render(items)}</ul>"
