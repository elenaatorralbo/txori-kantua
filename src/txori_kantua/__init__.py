"""Txori Kantua: IoT station for local recognition of bird songs.

This package only contains modules that already have a real implementation.
Empty subpackages are not created to reserve space: each directory appears
when its first implementation arrives, as agreed in ``CONTRIBUTING.md``.

Available subpackages:

``messaging``
    MQTT v1 contracts, validation, topic names and event construction.

``lcd``
    Hardware-independent text formatting and pagination for a 16x2 LCD.
"""

__all__ = ["__version__"]

#: Package version. It is not the project release version: ``v1.0.0`` is only
#: published after verified acceptance of the MVP (issue #32).
__version__ = "0.1.0.dev0"
