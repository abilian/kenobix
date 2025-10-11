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

# ODM is optional - only import if cattrs is available
try:
    from .odm import Document

    __all__ = ("Document", "KenobiX")
except ImportError:
    # cattrs not installed, ODM not available
    __all__ = ("KenobiX",)

__version__ = "5.0.0"
