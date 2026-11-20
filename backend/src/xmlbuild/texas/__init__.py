"""Texas Ethics Commission (``texas_tec``) jurisdiction plugin package."""

from src.xmlbuild.texas.errors import SpecMissingError
from src.xmlbuild.texas.mapping import MAPPING_TABLE, TBD, mapping_rows
from src.xmlbuild.texas.plugin import (
    SPEC_SECTION5_ITEMS,
    TexasTecPlugin,
    missing_spec_items,
    plugin,
    required_spec_file_paths,
)

__all__ = [
    "MAPPING_TABLE",
    "SPEC_SECTION5_ITEMS",
    "SpecMissingError",
    "TBD",
    "TexasTecPlugin",
    "mapping_rows",
    "missing_spec_items",
    "plugin",
    "required_spec_file_paths",
]
