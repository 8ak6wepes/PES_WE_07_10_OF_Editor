import os
import struct
from pathlib import Path

from editor.pes_stat import Stat

from .utils.constants import *

from .option_file_data import OF_KEY

from .club import Club
from .logo import Logo
from .player import Player
from .leagues import League
from .stadiums import Stadium
from .shop import Shop
from .teams import Team
from .images import PNG
from .kits import Kits
from .emblems import Emblem
from .formation import Formation
from .of_diagnostics import OFDiagnostics


_EDITED_TEAM_NAMES_STANDARD = [
    "<Edited> National 1",
    "<Edited> National 2",
    "<Edited> National 3",
    "<Edited> National 4",
    "<Edited> National 5",
    "<Edited> National 6",
    "<Edited> National 7",
    "<Edited>",
]

_EDITED_TEAM_NAMES_JL = [
    "<Edited> 1",
    "<Edited> 2",
    "<Edited> 3",
    "<Edited> 4",
    "<Edited> 5",
    "<Edited> 6",
    "<Edited> 7",
    "<Edited>",
]


def _edited_team_names(total_nations: int) -> list:
    return _EDITED_TEAM_NAMES_JL if total_nations == 0 else _EDITED_TEAM_NAMES_STANDARD


class OptionFile:
    of_key = OF_KEY

    def __init__(self, file_location, config):
        self.file_location = file_location
        self.data = bytearray()
        self.file_name = ""
        self.extension = ""
        self.header_data = bytearray()
        self.config = config
        self.diagnostics = OFDiagnostics(
            config,
            game_name=config.get("Gui", {}).get("Game Name", ""),
            filename=file_location,
        )
        self.encrypted = self.config['option_file_data']['ENCRYPTED']
        self.of_byte_length = self.config['option_file_data']['OF_BYTE_LENGTH']
        self.of_block = self.config['option_file_data']['OF_BLOCK']
        self.of_block_size = self.config['option_file_data']['OF_BLOCK_SIZE']
        self.nations = self.config['NATIONS']

        self.read_option_file()

        # ── Diagnostics: block layout ──────────────────────────────────────
        self.diagnostics.check_block_layout(
            self.of_block, self.of_block_size,
            self.of_byte_length, len(self.data),
        )

        # ------------------------------------------------------------------
        # Player class-level constants — set from config so they are correct
        # for every game version including J-League CC games where size != 124
        # ------------------------------------------------------------------
        Player.size = self.config['Player']['Size']
        Player.start_address = self.config['option_file_data']['OF_BLOCK'][4]
        Player.start_address_edited = self.config['option_file_data']['OF_BLOCK'][3]
        Player.total_edit = int(self.config['option_file_data']['OF_BLOCK_SIZE'][3] / Player.size)
        Player.total_players = int(self.config['option_file_data']['OF_BLOCK_SIZE'][4] / Player.size)
        Player.first_unused = (
            self.config['Player']['First Unused']
            if self.config['Player']['First Unused']
            else Player.total_players
        )

        # ML boundaries computed after YAML overrides — see below

        Club.start_address = self.config['option_file_data']['OF_BLOCK'][6]
        Club.size = self.config['Club']['Size']
        Club.total = int(self.config['option_file_data']['OF_BLOCK_SIZE'][6] / Club.size)
        Club.max_abbr_name_size = self.config['Club']['Max Abbr Name Size']
        Club.first_emblem = self.config['Club']['First Emblem']
        Club.first_club_emblem = self.config['Club']['First Club Emblem']
        Club.stadium_offset = Club.size - 7
        Club.color1_offset = Club.size - 16
        Club.emblem_offset = Club.size - 28
        Club.flag_style_offset = Club.size - 18
        Club.supp_color_offset = Club.size - 8

        Stadium.TOTAL = self.config['Stadiums']['Total']
        Stadium.MAX_LEN = self.config['Stadiums']['Max Lenght']
        Stadium.START_ADDRESS = self.config['option_file_data']['OF_BLOCK'][2]
        Stadium.SW_ADDR = Stadium.START_ADDRESS + (Stadium.MAX_LEN * Stadium.TOTAL)
        Stadium.END_ADDR = Stadium.SW_ADDR + Stadium.TOTAL

        League.TOTAL = self.config['Leagues']['Total']
        League.START_ADDRESS = Stadium.END_ADDR + Stadium.MAX_LEN + 1

        Team.total_nations = self.config['Teams']['Total Nations']
        Team.total_classic = self.config['Teams']['Total Classic']
        Team.total_clubs = Club.total - self.config['Teams']['J League Extra Clubs']
        Team.total_j_nations = self.config['Teams']['Total J Nations']
        Team.total_j_clubs = self.config['Teams']['Total J Clubs']
        Team.total_players_in_nations = self.config['Teams']['Max Players In Nations']
        Team.total_players_in_clubs = self.config['Teams']['Max Players In Clubs']
        Team.separator_size = self.config['Teams']['Separator Size']
        Team.total_ml_slots = self.config.get('Teams', {}).get('Total ML Slots', Team.total_ml_slots)
        Team.dorsal_start_address = self.config['option_file_data']['OF_BLOCK'][5]

        # ── Diagnostics: player records ────────────────────────────────────
        self.diagnostics.check_player_size(
            self.of_block_size[4], Player.size,
        )
        self.diagnostics.check_first_unused(
            Player.first_unused, Player.total_players,
            Player.size, self.data, Player.start_address,
        )
        self.diagnostics.check_player_stats(
            self.data, Player.start_address, Player.size,
        )
        self.diagnostics.check_club_size(
            self.of_block_size[6], Club.size,
        )

        Player.first_classic_player = (
            Team.total_players_in_nations * (Team.total_nations - Team.total_classic) + 1
        )
        Player.last_classic_player = (
            Player.first_classic_player + Team.total_players_in_nations * Team.total_classic
        )

        Kits.start_address = self.config['option_file_data']['OF_BLOCK'][7]
        Kits.size_nation = self.config['Kits']['Nation Kit Data Size']
        Kits.size_club = self.config['Kits']['Club Kit Data Size']
        Kits.kit_data_size = self.config["Kits"]["Kit Data Size"]
        Kits.total = Club.total + Team.total_nations + Team.total_classic
        Kits.start_address_club = Kits.start_address + (
            (Kits.total - Club.total) * Kits.size_nation
        )
        Kits.end_address = Kits.start_address_club + Team.total_clubs * Kits.size_club

        Stat.growth_types_early           = self.config["GROWTH TYPES"]["EARLY"]
        Stat.growth_types_early_lasting   = self.config["GROWTH TYPES"]["EARLY LASTING"]
        Stat.growth_types_standard        = self.config["GROWTH TYPES"]["STANDARD"]
        Stat.growth_types_standard_lasting = self.config["GROWTH TYPES"]["STANDARD LASTING"]
        Stat.growth_types_late            = self.config["GROWTH TYPES"]["LATE"]
        Stat.growth_types_late_lasting    = self.config["GROWTH TYPES"]["LATE LASTING"]

        Logo.start_address = Kits.end_address

        # ── Diagnostics: kits, logo, emblem ────────────────────────────────
        _B8 = self.of_block[8] if len(self.of_block) > 8 else 0
        _BS8 = self.of_block_size[8] if len(self.of_block_size) > 8 else 0

        # ------------------------------------------------------------------
        # Logo constants — loaded from YAML so they are correct per game.
        # Logo.total varies: EUR PES games have 80; some ASIA/JL games have 0.
        # Logo.size varies: standard is 608 bytes per record.
        # ------------------------------------------------------------------
        Logo.total = self.config.get('Logo', {}).get('Total', Logo.total)
        Logo.size  = self.config.get('Logo', {}).get('Size',  Logo.size)

        # ------------------------------------------------------------------
        # Emblem constants — loaded from YAML.
        # Emblem.total_128 varies: EUR games have 50; WE 2011 ASIA has 21.
        # Emblem.size_128 and size_16 may differ in older titles.
        # ------------------------------------------------------------------
        Emblem.total_128 = self.config.get('Emblem', {}).get('Total',    Emblem.total_128)
        Emblem.size_128  = self.config.get('Emblem', {}).get('Size 128', Emblem.size_128)
        Emblem.size_16   = self.config.get('Emblem', {}).get('Size 16',  Emblem.size_16)

        # ------------------------------------------------------------------
        # Formation constants — loaded from YAML.
        # Formation.size = 364 is the standard value; unconfirmed for all games.
        # Formation.alt_size = 82 bytes for the alternate formation record.
        # ------------------------------------------------------------------
        Formation.size     = self.config.get('Formation', {}).get('Size',     Formation.size)
        Formation.alt_size = self.config.get('Formation', {}).get('Alt Size', Formation.alt_size)

        # ------------------------------------------------------------------
        # Player ML/shop slot counts — loaded from YAML.
        # These determine where ML legend/youth/default/shop players are stored.
        # All vary between game generations.
        # ------------------------------------------------------------------
        Player.total_ml_old     = self.config.get('Player', {}).get('ML Legend Slots',  Player.total_ml_old)
        Player.total_ml_youth   = self.config.get('Player', {}).get('ML Youth Slots',   Player.total_ml_youth)
        Player.total_shop       = self.config.get('Player', {}).get('Shop Slots',       Player.total_shop)
        Player.total_ml_default = self.config.get('Player', {}).get('ML Default Slots', Player.total_ml_default)
        Player.first_edited_id  = self.config.get('Player', {}).get('First Edited Id',  Player.first_edited_id)

        # Recompute ML/shop player index boundaries now that YAML may have
        # overridden the slot counts above.
        Player.first_ml_old     = Player.first_unused - Player.total_ml_old
        Player.first_ml_youth   = Player.first_ml_old - Player.total_ml_youth
        Player.first_shop       = Player.first_ml_youth - Player.total_shop
        Player.first_ml_default = Player.first_shop - Player.total_ml_default

        # ------------------------------------------------------------------
        # Shop unlock byte range — loaded from YAML.
        # Defaults to B[1] start/end which is correct for most games.
        # ------------------------------------------------------------------
        Shop.POINTS_OFFSET_2        = self.config['Shop']['Points Offset']
        Shop.unlock_offset_start    = self.config.get('Shop', {}).get('Unlock Offset Start', self.of_block[1] if len(self.of_block) > 1 else 5144)
        Shop.unlock_offset_end      = self.config.get('Shop', {}).get('Unlock Offset End',   Shop.unlock_offset_start + 25)

        # ── Diagnostics: logo, emblem, shop, formation ────────────────────
        self.diagnostics.check_kits_and_logo(
            Club.start_address, Club.total, Club.size,
            Team.total_nations + Team.total_classic,
            Kits.size_nation, Kits.size_club,
            Team.total_clubs, _B8,
            Logo.total, Logo.size,
        )
        self.diagnostics.check_emblem_block(
            _BS8, Emblem.total_128, Emblem.size_128, Emblem.size_16,
        )
        self.diagnostics.check_shop_points(
            self.data, 52, Shop.POINTS_OFFSET_2,
        )

        self.load_of_data()
        self.diagnostics.flush()

    def load_of_data(self):
        self.set_clubs()
        self.set_logos()
        self.set_players()
        self.set_edited_players()
        self.set_teams()
        self.set_leagues()
        self.set_stadiums()
        self.set_shop()
        self.set_free_agents()

    @property
    def teams_names(self):
        if Team.total_classic == 0:
            classic_teams_names = []
        else:
            classic_teams_names = self.config['CLASSIC TEAMS']

        japan_n_team_names = [
            "<Japan National %d>" % (i + 1)
            for i in range(Team.total_j_nations)
        ]
        japan_c_team_names = [
            "<Japan Club %d>" % (i + 1)
            for i in range(Team.total_j_clubs)
        ]

        edited_names = _edited_team_names(Team.total_nations)

        return (
            self.nations[:Team.total_nations]
            + classic_teams_names
            + japan_n_team_names
            + edited_names
            + self.clubs_names[:Team.total_clubs]
            + japan_c_team_names
            + ML_TEAM_NAME
            + SHOP_TEAM_NAMES
            + ML_TEAM_NAMES_EXTRAS
        )

    def set_teams(self):
        self.teams = [Team(self, i) for i in range(Team.total_slots_cm())]

    def set_free_agents(self):
        first_club = (
            Team.total_nations
            + Team.total_j_nations
            + Team.total_classic
            + int(Player.total_edit / Team.total_players_in_nations)
        )
        last_club = first_club + Club.total

        for i, team in enumerate(self.teams):
            if team.is_national_team:
                for j, player in enumerate(team.players):
                    if player is not None:
                        player.free_agent = True
                    if player is not None and player.national_id is None and player.national_dorsal is None:
                        player.national_id = i
                        player.national_dorsal = team.dorsals[j]
            elif first_club <= team.idx < last_club:
                for j, player in enumerate(team.players):
                    if player is not None:
                        player.free_agent = False
                        player.club_id = i
                        player.club_dorsal = team.dorsals[j]
            else:
                for j, player in enumerate(team.players):
                    if player is not None:
                        player.free_agent = True
                    if player is not None and player.club_id is None and player.club_dorsal is None:
                        player.club_id = i
                        player.club_dorsal = team.dorsals[j]

    def read_option_file(self):
        of_file = open(self.file_location, "rb")
        file_name = Path(of_file.name).stem
        extension = Path(of_file.name).suffix
        folder = Path(of_file.name).resolve().parents[0]
        file_size = os.stat(of_file.name).st_size
        self.file_name = file_name
        self.extension = extension
        self.folder = folder
        file_contents = bytearray(of_file.read())
        of_file.close()

        if self.extension == ".psu":
            self.header_data, self.data = (
                file_contents[:file_size - self.of_byte_length],
                file_contents[file_size - self.of_byte_length:],
            )
            game_identifier = self.header_data[64:64 + 19].decode('utf-8')
        elif self.extension == ".xps":
            self.header_data, self.data = (
                file_contents[:file_size - self.of_byte_length - 4],
                file_contents[file_size - self.of_byte_length - 4:-4],
            )
            game_identifier = self.config['option_file_data']['Game Identifier']
        else:
            self.data = file_contents
            game_identifier = file_name

        if game_identifier not in self.config['option_file_data']['Game Identifier'] and self.extension == ".psu":
            raise ValueError("Invalid option file version")

        if self.of_byte_length != len(self.data):
            raise ValueError("Invalid option file, size doesn't match!")

        if self.encrypted:
            self.decrypt()
        self._compute_verified_blocks()

        return True

    def save_option_file(self, file_location=None):
        file_location = self.file_location = file_location or self.file_location

        if self.encrypted:
            self.encrypt()
            self.checksums()

        of_file = open(file_location, "wb")

        if self.extension == ".psu":
            of_file.write(self.header_data)
            of_file.write(self.data)
        elif self.extension == ".xps":
            of_file.write(self.header_data)
            of_file.write(self.data)
            of_file.write(bytearray(4))
        else:
            of_file.write(self.data)

        of_file.close()
        self.decrypt()
        return True

    def decrypt(self):
        total_keys = len(self.of_key)
        for i in range(1, len(self.of_block)):
            k = 0
            a = self.of_block[i]
            while True:
                if a + 4 > self.of_block[i] + self.of_block_size[i]:
                    break
                c = struct.unpack("<I", self.data[a: a + 4])[0]
                p = ((c - self.of_key[k]) + self.of_key[-1]) ^ self.of_key[-1]
                self.data[a: a + 4] = struct.pack("<I", p & 0xFFFFFFFF)
                k += 1
                if k == total_keys:
                    k = 0
                a += 4

    def encrypt(self):
        for i in range(1, len(self.of_block)):
            k = 0
            a = self.of_block[i]
            while True:
                if a + 4 > self.of_block[i] + self.of_block_size[i]:
                    break
                p = struct.unpack("<I", self.data[a: a + 4])[0]
                c = self.of_key[k] + ((p ^ self.of_key[-1]) - self.of_key[-1])
                self.data[a: a + 4] = struct.pack("<I", c & 0xFFFFFFFF)
                k += 1
                if k == len(self.of_key):
                    k = 0
                a += 4

    def _compute_verified_blocks(self):
        """Record which blocks have checksums matching our formula at load time.
        These are the blocks the PS2 game wrote correctly and verifies on load.
        Blocks where stored != computed are skipped in checksums() to preserve
        the PS2 game's original (non-standard) checksum value."""
        obl = self.of_byte_length
        blocks = self.of_block
        block_sizes = self.of_block_size
        last = len(blocks) - 1
        self._verified_blocks = set()
        for i in range(len(blocks)):
            end = obl if i == last else blocks[i] + block_sizes[i]
            checksum = 0
            for a in range(blocks[i], end, 4):
                if a + 4 <= len(self.data):
                    checksum += struct.unpack("<I", self.data[a: a + 4])[0]
            checksum &= 0xFFFFFFFF
            start = blocks[i] - 8
            stored = struct.unpack("<I", self.data[start: start + 4])[0]
            if stored == checksum:
                self._verified_blocks.add(i)

    def checksums(self):
        # PS2 checksum formula: sum(data[B[i] : B[i]+BS[i]]) for non-last blocks,
        # sum(data[B[i] : OF_BYTE_LENGTH]) for the last block.
        #
        # Some PS2 games write INCORRECT checksums for certain blocks (a game bug).
        # The PS2 loader skips verification for those blocks and expects the wrong
        # value to remain unchanged. We only update a block's checksum if the
        # original stored value matched our formula (i.e. PS2 wrote it correctly),
        # or if it's in the set of blocks we know the PS2 verifies.
        #
        # _verified_blocks is populated at load time: blocks where stored==computed.
        obl = self.of_byte_length
        blocks = self.of_block
        block_sizes = self.of_block_size
        last = len(blocks) - 1
        for i in range(0, len(blocks)):
            end = obl if i == last else blocks[i] + block_sizes[i]
            checksum = 0
            for a in range(blocks[i], end, 4):
                if a + 4 <= len(self.data):
                    checksum += struct.unpack("<I", self.data[a: a + 4])[0]
            checksum &= 0xFFFFFFFF
            start = blocks[i] - 8
            if i in self._verified_blocks:
                self.data[start: start + 4] = struct.pack('<I', checksum)

    def set_clubs(self):
        self.clubs = [Club(self, i) for i in range(Club.total)]
        self.clubs_names = [club.name for club in self.clubs]

    def set_logos(self):
        self.logos = [Logo(self, i) for i in range(Logo.total)]
        self.logos_png = [PNG(logo) for logo in self.logos]
        self.logos_tk = [png.png_bytes_to_tk_img() for png in self.logos_png]

    def set_players(self):
        self.players = [
            Player(self, i)
            for i in range(int(self.of_block_size[4] / Player.size))
        ]
        self.players_names = [player.name for player in self.players]

    def set_edited_players(self):
        self.edited_players = [
            Player(self, i)
            for i in range(Player.first_edited_id, Player.first_edited_id + Player.total_edit)
        ]
        self.edited_players_names = [ep.name for ep in self.edited_players]

    def set_players_names(self):
        self.players_names = [player.name for player in self.players]

    def set_edited_players_names(self):
        self.edited_players_names = [ep.name for ep in self.edited_players]

    def get_player_by_name(self, name: str):
        return (
            self.players[self.players_names.index(name)]
            if name in self.players_names
            else self.edited_players[self.edited_players_names.index(name)]
        )

    def get_player_by_idx(self, idx: int):
        if idx < Player.first_edited_id:
            if idx < len(self.players):
                return self.players[idx]
            return None  # idx out of regular player range — treat as empty slot
        else:
            edited_idx = idx - Player.first_edited_id
            if edited_idx < len(self.edited_players):
                return self.edited_players[edited_idx]
            return None  # idx out of edited player range — treat as empty slot

    def set_leagues(self):
        self.leagues = [League(self, i) for i in range(League.TOTAL)]
        self.leagues_names = [league.name for league in self.leagues]

    def set_stadiums(self):
        self.stadiums = [Stadium(self, i) for i in range(Stadium.TOTAL)]
        self.stadiums_names = [stadium.name for stadium in self.stadiums]

    def set_clubs_names(self):
        self.clubs_names = [club.name for club in self.clubs]

    def set_stadiums_names(self):
        self.stadiums_names = [stadium.name for stadium in self.stadiums]

    def set_leagues_names(self):
        self.leagues_names = [league.name for league in self.leagues]

    def set_shop(self):
        self.shop = Shop(self)