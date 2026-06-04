"""Backward-compatibility shim.

Prior to v0.1.0 this module was named `bonsai_room_with_miters` and lived
inside the (then-monolithic) `bonsai-walls` skill folder. v0.1.0 renamed
it to `bonsai_bim_helpers` to honestly reflect the scope (walls + slabs +
doors + windows + roofs + stairs + spaces + grids + project setup +
drawings helpers + audit + IDS).

This shim keeps `import bonsai_room_with_miters` working so older example
scripts and user-authored skills don't need to change. New code should
import the renamed module directly:

    import bonsai_bim_helpers as bw
"""
from bonsai_bim_helpers import *  # noqa: F401,F403
