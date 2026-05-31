"""UnpackKindleS - .NET-independent Python port.

Converts DRM-free Kindle .azw3 / .azw.res files into EPUB, merging HD images.
"""

from .version import VERSION
from .errors import UnpackKindleSException
from .azw3 import Azw3File
from .azw6 import Azw6File
from .epub import Epub

__all__ = ["VERSION", "UnpackKindleSException", "Azw3File", "Azw6File", "Epub"]
__version__ = VERSION
