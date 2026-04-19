# -*- coding: utf-8 -*-
"""
BACKWARD COMPATIBILITY SHIM — do not add logic here.

The OVS/TOK100 renderer has moved to:
    backend/engine/customers/ovs/tok100_renderer.py

This file re-exports everything from the new location so that any existing
code that still imports from backend.engine.tok100_label_builder continues
to work without modification.

New code should import directly from the renderer:
    from backend.engine.customers.ovs.tok100_renderer import build_label_pdf
Or use the generic dispatcher:
    from backend.engine.label_engine import get_renderer, build_labels
"""
from backend.engine.customers.ovs.tok100_renderer import *          # noqa: F401,F403
from backend.engine.customers.ovs.tok100_renderer import (          # noqa: F401
    build_label_pdf,
    build_label_png,
    build_label_thumbnail,
    _draw_front_panel,
    _draw_back_panel,
    OUTER_W, OUTER_H,
    INNER_X, INNER_Y, INNER_W, INNER_H,
    FB, FR,
    DARK, GREY, LGREY, NAVY, WHITE, BLACK, MAGENTA, GOLD, GREEN,
    TOK100_SIZES, SIZE_ROWS, CM_MAP,
)
