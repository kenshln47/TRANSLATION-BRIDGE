"""Translation Bridge visual system.

The product deliberately uses quiet, low-contrast surfaces with one restrained
forest-green accent. It stays legible next to a game without becoming another
neon game HUD.
"""


class C:
    """Calm, practical palette shared by every application surface."""

    BG          = "#101512"  # Ink green-black, easy on the eyes beside a game
    BG_CARD     = "#192019"  # Main paper-like surface
    BG_INPUT    = "#222B23"  # Controls are tactile, not glossy
    BG_RAISED   = "#2A342B"  # Slightly elevated utility surface
    PRIMARY     = "#9CCF78"  # Muted leaf green; the only brand colour
    PRIMARY_H   = "#B4DD91"
    ACCENT      = "#C9E7A9"
    ACCENT_H    = "#D9F2BF"
    PRIMARY_DIM = "#30482E"
    TEXT        = "#F3F0E8"  # Warm white avoids a sterile pure-white screen
    TEXT_DIM    = "#AAB2A8"
    TEXT_SOFT   = "#D3D8CF"
    SUCCESS     = "#9CCF78"
    ERROR       = "#E58B7A"
    WARN        = "#E6C777"
    BORDER      = "#344037"
    SEP         = "#29332B"
