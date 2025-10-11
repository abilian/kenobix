"""
KenobiX - High-Performance Document Database

Based on KenobiDB by Harrison Erd
Enhanced with SQLite3 JSON optimizations for 15-665x faster operations.

.. py:data:: __all__
   :type: tuple[str]
   :value: ("KenobiX",)

   Package exports
"""

from .kenobix import KenobiX

__all__ = ("KenobiX",)
__version__ = "5.0.0"
