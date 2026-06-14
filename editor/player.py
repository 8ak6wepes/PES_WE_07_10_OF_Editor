from .edited_flags import EditedFlags
from .appearance import Appearance
from .special_abilities import SpecialAbilities
from .abilities import Abilities, Abilities_1_8
from .positions import Position
from .basic_settings import BasicSettings
from .pes_stat import Stat
from .utils.constants import *


class Player:

    # ── Fixed layout constants (same for all PS2 WE/PES titles) ──────────────
    # Full names are stored as UTF-16 LE (2 bytes per character, null-terminated).
    # 32 bytes = 16 wide characters maximum.
    # Shirt names are stored as single-byte ASCII (latin-1), 16 bytes.
    name_bytes_length       = 32       # bytes for full name field (16 UTF-16 LE chars)
    max_name_size           = 16       # max characters in the name
    shirt_name_bytes_length = 16       # bytes for shirt name (single-byte ASCII)
    name_encoding           = "utf-16-le"  # full name stored as wide chars
    shirt_encoding          = "latin-1"    # shirt name stored as single-byte ASCII

    # ── Config-injected class attributes ──────────────────────────────────────
    # Sentinel defaults only — real values are set by OptionFile.__init__ from
    # the active game YAML before any Player instance is created.
    # YAML keys are shown in comments; see also default.yaml for documentation.
    size                 = 124    # Player: Size
    start_address        = 0      # OF_BLOCK[4]
    start_address_edited = 0      # OF_BLOCK[3]
    total_edit           = 0      # derived: BS[3] / size
    total_players        = 0      # derived: BS[4] / size
    first_unused         = 0      # Player: First Unused
    first_edited_id      = 32768  # Player: First Edited Id
    total_ml_old         = 10     # Player: ML Legend Slots
    total_ml_youth       = 140    # Player: ML Youth Slots
    total_shop           = 160    # Player: Shop Slots
    total_ml_default     = 28     # Player: ML Default Slots
    first_ml_old         = 0      # derived: first_unused - total_ml_old
    first_ml_youth       = 0      # derived: first_ml_old - total_ml_youth
    first_shop           = 0      # derived: first_ml_youth - total_shop
    first_ml_default     = 0      # derived: first_shop - total_ml_default
    first_classic_player = 0      # derived from Team config
    last_classic_player  = 0      # derived from Team config

    def __init__(self, option_file, idx):
        self.idx = idx
        self.of = option_file
        # Roster membership — populated by OptionFile.set_free_agents()
        self.national_id     = None
        self.national_dorsal = None
        self.club_id         = None
        self.club_dorsal     = None
        self.free_agent      = None
        self.set_name_from_bytes()
        self.set_shirt_name_from_bytes()
        self.callname = Stat(self, 1, 0, 0xffff, "Callname")
        self.nation = Stat(self, 65, 0, 0xff, "Nationality", 1)

    def init_stats(self):
        self.basic_settings = BasicSettings(self)
        self.position = Position(self)
        self.appearance = Appearance(self)
        self.abilities = Abilities(self)
        self.abilities_1_8 = Abilities_1_8(self)
        self.special_abilities = SpecialAbilities(self)
        self.edited_flags = EditedFlags(self)

    @property
    def club_team_name(self):
        return "Free Agent" if self.club_id is None else self.of.teams_names[self.club_id]

    @property
    def national_team_name(self):
        return "Not Registered" if self.national_id is None else self.of.teams_names[self.national_id]

    @property
    def is_edit(self):
        """Return true if the player is an edit player."""
        return self.idx >= self.first_edited_id

    @property
    def is_unused(self):
        """Return true if the player is an unused player."""
        return self.idx >= self.first_unused

    @property
    def offset(self):
        """Return player offset."""
        return (
            self.idx * self.size
            if not self.is_edit
            else (self.idx - self.first_edited_id) * self.size
        )

    @property
    def address(self):
        """Return player address."""
        return (
            self.start_address + self.offset
            if not self.is_edit
            else self.start_address_edited + self.offset
        )

    @staticmethod
    def _decode_wide_name(data):
        """
        Decode a null-terminated UTF-16 LE string from a fixed-length byte field.
        Reads pairs of bytes until a 0x0000 wide-null or end of data.
        """
        result = []
        for i in range(0, len(data) - 1, 2):
            pair = data[i:i + 2]
            if pair == b'\x00\x00':
                break
            try:
                result.append(pair.decode('utf-16-le'))
            except Exception:
                break
        return ''.join(result)

    def set_name_from_bytes(self):
        """Set player name from relevant OF data bytes."""
        name = "???"
        if (
            self.idx > 0
            and (self.idx <= self.total_players or self.idx >= self.first_edited_id)
            and self.idx < self.first_edited_id + self.total_edit
        ):
            all_name_bytes = self.of.data[self.address: self.address + self.name_bytes_length]
            try:
                name = self._decode_wide_name(all_name_bytes)
            except Exception:
                name = f"Error (ID: {self.idx})"

            if not name:
                no_name_prefixes = {
                    self.first_edited_id: "Edited",
                    self.first_unused:    "Unused",
                    1:                    "Unknown",
                }
                for address, address_prefix in no_name_prefixes.items():
                    if self.idx >= address:
                        prefix = address_prefix
                        break
                name = f"{prefix} ({self.idx})"

        self.__name = name

    @property
    def name(self):
        """Return player name."""
        return self.__name

    @name.setter
    def name(self, name):
        """Update player name with the supplied value."""
        new_name = name[: self.max_name_size]
        if (
            new_name == f"Unknown ({self.idx})"
            or new_name == f"Edited ({self.idx})"
            or new_name == f"Unused ({self.idx})"
            or new_name == f"Error ({self.idx})"
            or new_name == ""
        ):
            player_name_bytes = [0] * self.name_bytes_length
        else:
            player_name_bytes = [0] * self.name_bytes_length
            new_name_bytes = new_name.encode(self.name_encoding, errors="replace")
            player_name_bytes[: len(new_name_bytes)] = new_name_bytes

        for i, byte in enumerate(player_name_bytes):
            self.of.data[self.address + i] = byte

        self.__name = new_name

    def set_shirt_name_from_bytes(self):
        """Set player shirt name from relevant OF data bytes."""
        shirt_name_address = self.address + 32
        name_byte_array = self.of.data[
            shirt_name_address: shirt_name_address + self.shirt_name_bytes_length
        ]
        self.__shirt_name = (
            name_byte_array.partition(b"\0")[0]
            .decode(encoding=self.shirt_encoding, errors="replace")
        )

    @property
    def shirt_name(self):
        """Return player shirt name."""
        return self.__shirt_name

    @shirt_name.setter
    def shirt_name(self, shirt_name: str):
        shirt_name_address = self.address + 32
        new_name = shirt_name[: self.max_name_size].upper()

        player_shirt_name_bytes = [0] * self.shirt_name_bytes_length
        new_name_bytes = str.encode(new_name, encoding=self.shirt_encoding, errors="replace")
        player_shirt_name_bytes[: len(new_name_bytes)] = new_name_bytes

        for i, byte in enumerate(player_shirt_name_bytes):
            self.of.data[shirt_name_address + i] = byte

        self.__shirt_name = new_name