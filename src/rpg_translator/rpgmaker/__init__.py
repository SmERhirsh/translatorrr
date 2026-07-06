"""RPG Maker MV/MZ project detection and data-file helpers."""

from rpg_translator.rpgmaker.detector import ProjectDetector, detect_project
from rpg_translator.rpgmaker.extractors import ExtractionResult, extract_project
from rpg_translator.rpgmaker.file_registry import DataFileRegistry, RPGMakerDataFileSpec
from rpg_translator.rpgmaker.json_loader import (
    LoadedDataFile,
    load_data_file,
    load_json_file,
    load_project_data_files,
)

__all__ = [
    "DataFileRegistry",
    "ExtractionResult",
    "LoadedDataFile",
    "ProjectDetector",
    "RPGMakerDataFileSpec",
    "detect_project",
    "extract_project",
    "load_data_file",
    "load_json_file",
    "load_project_data_files",
]
