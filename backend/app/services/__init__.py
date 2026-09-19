"""Services for the Menu AI application."""


def parse_menu_image(*args, **kwargs):
    """Lazy import wrapper to avoid importing heavy deps at module load."""
    from app.services.vision_parser import parse_menu_image as _parse_menu_image
    return _parse_menu_image(*args, **kwargs)


__all__ = ["parse_menu_image"]
