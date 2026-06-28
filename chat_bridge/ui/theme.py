"""
Translation Bridge — Color Theme (Graphite + Emerald)
"""


class C:
    """Application color palette — modern dark theme with proper elevation.

    Elevation goes page (darkest) → card → input (lighter), so surfaces read as
    stacked depth instead of flat. Emerald brand accent is kept from the logo.
    """
    BG         = "#0c0e10"   # Page background — deep near-black
    BG_CARD    = "#15181c"   # Elevated card — lighter than page = depth
    BG_INPUT   = "#1b1f24"   # Input / button surface — lighter still, tactile
    PRIMARY    = "#3ecf8e"   # Emerald brand (logo/banner green)
    PRIMARY_H  = "#34b87d"   # Hover — slightly deeper green
    ACCENT     = "#4ade94"   # Brighter emerald for accents/highlights on dark
    ACCENT_H   = "#34b87d"
    TEXT       = "#f2f4f5"   # Primary text — soft white
    TEXT_DIM   = "#8b9398"   # Secondary / muted text
    SUCCESS    = "#3ecf8e"   # Green
    ERROR      = "#ff6b6b"   # Error / warning red
    WARN       = "#ffd93d"   # Caution yellow
    BORDER     = "#262b30"   # Visible-but-subtle border on cards
    SEP        = "#1e2227"   # Hairline separator
