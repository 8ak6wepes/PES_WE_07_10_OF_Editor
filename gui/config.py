import yaml
from pathlib import Path
import os
from editor import common_functions


_CONFIG_DEFAULTS = {
    "Gui": {
        "Game Name": "Unknown — select game version from Edit > Game Version",
    },
    "option_file_data": {
        "Game Identifier": [],
        "ENCRYPTED": True,
        "OF_BYTE_LENGTH": 0,
        "OF_BLOCK": [],
        "OF_BLOCK_SIZE": [],
    },
    "Player": {
        "First Unused": 0,
        "Size": 124,
        "First Edited Id": 32768,
        "ML Legend Slots": 10,
        "ML Youth Slots": 140,
        "Shop Slots": 160,
        "ML Default Slots": 28,
    },
    "Teams": {
        "Total Nations": 0,
        "Total Classic": 0,
        "Total J Nations": 0,
        "Total J Clubs": 0,
        "J League Extra Clubs": 0,
        "Max Players In Nations": 23,
        "Max Players In Clubs": 32,
        "Separator Size": 0,
    },
    "Club": {
        "Size": 88,
        "Max Abbr Name Size": 3,
        "First Emblem": 0,
        "First Club Emblem": 0,
    },
    "Stadiums": {
        "Total": 0,
        "Max Lenght": 61,
    },
    "Leagues": {
        "Total": 0,
    },
    "Kits": {
        "Nation Kit Data Size": 0,
        "Club Kit Data Size": 0,
        "Kit Data Size": 0,
    },
    "Shop": {
        "Points Offset": 0,
        "Unlock Offset Start": 0,
        "Unlock Offset End": 0,
    },
    "Logo": {
        "Total": 80,
        "Size": 608,
    },
    "Emblem": {
        "Total": 50,
        "Size 128": 5184,
        "Size 16": 2176,
    },
    "Formation": {
        "Size": 364,
        "Alt Size": 82,
    },
    "NATIONS": [],
    "CLASSIC TEAMS": [],
    "GROWTH TYPES": {
        "EARLY": [],
        "EARLY LASTING": [],
        "STANDARD": [],
        "STANDARD LASTING": [],
        "LATE": [],
        "LATE LASTING": [],
    },
}

_REQUIRED_KEYS = [
    ("option_file_data", "OF_BYTE_LENGTH",  "option file byte length"),
    ("option_file_data", "OF_BLOCK",        "block offset list"),
    ("option_file_data", "OF_BLOCK_SIZE",   "block size list"),
    ("Player",           "First Unused",    "first unused player index"),
    ("Stadiums",         "Total",           "total stadiums"),
    ("Leagues",          "Total",           "total leagues"),
    ("Kits",             "Kit Data Size",   "kit data size"),
]


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    current_dir = os.getcwd()
    config_dir = current_dir + "/" + "config"
    default_file = common_functions.resource_path("resources/default.yaml")
    is_default = False

    filelist = []
    games_config = []

    def __init__(self, file: str = None):
        self.filelist = []
        self.games_config = []
        self.validation_errors: list[str] = []

        self.get_config_files(self.config_dir)

        self.file_location = self._resolve_file(file)
        self.load_config()

    def load_config(self):
        try:
            with open(self.file_location, encoding="utf-8") as stream:
                raw = yaml.safe_load(stream) or {}
        except FileNotFoundError:
            raw = {}
            self.validation_errors.append(
                f"Config file not found: {self.file_location}"
            )
        except yaml.YAMLError as exc:
            raw = {}
            self.validation_errors.append(
                f"YAML parse error in {self.file_location}: {exc}"
            )

        self.file = _deep_merge(_CONFIG_DEFAULTS, raw)
        self._validate()

    def _resolve_file(self, file: str) -> str:
        if file is None:
            self.is_default = True
            return self._pick_default()
        self.is_default = False
        return file

    def _pick_default(self) -> str:
        if self.filelist:
            return self.filelist[0]
        return self.default_file

    def _validate(self):
        self.validation_errors = []

        for section, key, description in _REQUIRED_KEYS:
            value = self.file.get(section, {}).get(key)
            if value is None or value == 0 or value == []:
                self.validation_errors.append(
                    f"Missing or empty config value [{section}][{key}] "
                    f"({description}) in {self.file_location}"
                )

        block      = self.file["option_file_data"]["OF_BLOCK"]
        block_size = self.file["option_file_data"]["OF_BLOCK_SIZE"]
        if len(block) != len(block_size):
            self.validation_errors.append(
                f"OF_BLOCK has {len(block)} entries but OF_BLOCK_SIZE has "
                f"{len(block_size)} entries — they must match."
            )

        # Player.Size must divide OF_BLOCK_SIZE[4] evenly when both are set
        player_size = self.file["Player"]["Size"]
        if (
            len(block_size) > 4
            and block_size[4] > 0
            and player_size > 0
            and block_size[4] % player_size != 0
        ):
            self.validation_errors.append(
                f"Player Size {player_size} does not divide player block size "
                f"{block_size[4]} evenly (remainder {block_size[4] % player_size}). "
                f"Check Player.Size in {self.file_location}"
            )

        total_nations = self.file["Teams"]["Total Nations"]
        nations       = self.file["NATIONS"]
        if total_nations > 0 and not nations:
            self.validation_errors.append(
                f"Total Nations is {total_nations} but NATIONS list is empty."
            )

    def get_config_files(self, directory: str):
        if self.is_default:
            return
        try:
            for p in Path(directory).iterdir():
                if p.is_file() and p.suffix in (".yaml", ".yml"):
                    self.filelist.append(directory + "/" + p.name)
                    parent = p.parent
                    if parent.name != "config":
                        self.games_config.append(parent.name + ":" + p.stem)
                    else:
                        self.games_config.append(p.stem)
                elif p.is_dir():
                    self.get_config_files(directory + "/" + p.name)
        except Exception:
            self.filelist = []
            self.games_config = []