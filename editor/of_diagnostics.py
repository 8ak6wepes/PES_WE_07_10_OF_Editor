"""
editor/of_diagnostics.py
========================
Diagnostic logging for option file loading.

Imported by option_file.py and called at each load stage.
Results are written to of_load_diagnostics.log in the working directory
and surfaced to the GUI as structured warnings after a successful load,
or as detailed error context when loading fails.

Usage (inside OptionFile.__init__):
    from .of_diagnostics import OFDiagnostics
    self.diagnostics = OFDiagnostics(config, of_byte_length)
    self.diagnostics.check_block_layout(of_block, of_block_size)
    ...
    self.diagnostics.flush()          # write log
    warnings = self.diagnostics.warnings   # list of (category, message) tuples
"""

import struct
import traceback
from datetime import datetime
from pathlib import Path


# ── Categories ─────────────────────────────────────────────────────────────────
YAML  = "YAML"    # wrong value in game config — fix the YAML
CODE  = "CODE"    # unexpected code-level issue
WARN  = "WARN"    # investigate but not necessarily broken
INFO  = "INFO"    # informational — no action needed


class OFDiagnostics:
    """
    Collects diagnostic results during option file loading.
    Each check appends to self.log_lines and self.issues.
    Call flush() to write the log file.
    """

    LOG_PATH = Path("of_load_diagnostics.log")

    def __init__(self, config: dict, game_name: str = "", filename: str = ""):
        self.config    = config
        self.game_name = game_name
        self.filename  = filename
        self.issues    = []   # list of (category, short_message)
        self.log_lines = []
        self._section_open = False

        self._head(f"OF Load Diagnostics — {datetime.now():%Y-%m-%d %H:%M:%S}")
        self._head(f"Game:   {game_name or 'unknown'}")
        self._head(f"File:   {filename or 'unknown'}")
        self._head("=" * 72)

    # ── internal logging ───────────────────────────────────────────────────────

    def _head(self, msg):
        self.log_lines.append(msg)

    def _section(self, title):
        bar = "─" * max(0, 68 - len(title))
        self.log_lines.append(f"\n── {title} {bar}")

    def _ok(self, msg):
        self.log_lines.append(f"  ✓ {msg}")

    def _warn(self, msg, category=WARN, issue_msg=None):
        self.log_lines.append(f"  ⚠ {msg}")
        self.issues.append((category, issue_msg or msg))

    def _fail(self, msg, category=YAML, issue_msg=None):
        self.log_lines.append(f"  ✗ {msg}")
        self.issues.append((category, issue_msg or msg))

    def _info(self, msg):
        self.log_lines.append(f"    {msg}")

    # ── public checks ──────────────────────────────────────────────────────────

    def check_block_layout(self, B, BS, obl, actual_len):
        """Verify block list lengths, OBL, and all blocks fit within OF data."""
        self._section("Block Layout")

        # OBL match
        if actual_len != obl:
            self._fail(
                f"OF data length {actual_len} ≠ OF_BYTE_LENGTH {obl} in YAML",
                YAML,
                f"OF_BYTE_LENGTH wrong: YAML={obl}, actual={actual_len}"
            )
        else:
            self._ok(f"OF_BYTE_LENGTH matches actual file data: {obl:,} bytes")

        # Block/size list parity
        if len(B) != len(BS):
            self._fail(
                f"OF_BLOCK has {len(B)} entries, OF_BLOCK_SIZE has {len(BS)} — must match",
                YAML, "OF_BLOCK and OF_BLOCK_SIZE list lengths differ"
            )
        else:
            self._ok(f"OF_BLOCK and OF_BLOCK_SIZE both have {len(B)} entries")

        # All blocks in range
        out_of_range = []
        for i, (b, bs) in enumerate(zip(B, BS)):
            if b + bs > actual_len:
                out_of_range.append(i)
                self._fail(
                    f"B[{i}] at {b}+{bs}={b+bs} exceeds OF length {actual_len}",
                    YAML, f"OF_BLOCK[{i}] or OF_BLOCK_SIZE[{i}] out of range"
                )
        if not out_of_range:
            self._ok(f"All {len(B)} blocks fit within OF data")

    def check_player_size(self, BS4, player_size):
        """Verify Player.size divides BS[4] exactly."""
        self._section("Player Record Size")
        if player_size == 0:
            self._fail("Player.size is 0 — not set in YAML", YAML, "Player:Size is 0")
            return
        if BS4 % player_size != 0:
            rem = BS4 % player_size
            self._fail(
                f"BS[4]={BS4} not divisible by Player.size={player_size} (rem={rem})",
                YAML, f"Player:Size {player_size} wrong — BS[4]={BS4} rem={rem}"
            )
            # Suggest correct values
            for alt in [112, 116, 120, 124, 128, 132]:
                if BS4 % alt == 0:
                    self._info(f"→ Player.size={alt} divides BS[4] exactly ({BS4//alt} slots)")
        else:
            slots = BS4 // player_size
            self._ok(f"BS[4]/{player_size} = {slots} player slots (exact)")

    def check_player_stats(self, data, p0_addr, player_size, stat_start=48):
        """Spot-check ability stats on player 0 to verify decrypt and addresses."""
        self._section("Player Stats (Decrypt Verification)")
        stat_fields = [
            ("attack",      7), ("defence",     8), ("body_balance", 9),
            ("stamina",    10), ("top_speed",   11), ("acceleration", 12),
            ("response",   13), ("agility",     14),
        ]
        valid = 0
        for name, off in stat_fields:
            addr = p0_addr + stat_start + off
            if addr >= len(data) or addr - 1 < 0:
                continue
            hi = data[addr]; lo = data[addr - 1]
            raw = ((hi << 8) | lo) & 127
            if 1 <= raw <= 126:
                valid += 1
        if valid < 6:
            self._warn(
                f"Player 0 stats: only {valid}/8 in valid range 1–126",
                WARN,
                f"Player stats {valid}/8 valid — check Player:Size or OF_BLOCK[4] or decrypt"
            )
            self._info("→ If 0/8: decryption failed or wrong OF_BLOCK[4]")
            self._info("→ If some valid: Player.size may be slightly wrong")
        else:
            self._ok(f"Player 0 stats: {valid}/8 valid (decrypt and address confirmed)")

    def check_club_size(self, BS6, club_size):
        """Verify Club.size divides BS[6] exactly."""
        self._section("Club Record Size")
        if club_size == 0:
            self._fail("Club.size is 0 — not set in YAML", YAML, "Club:Size is 0")
            return
        if BS6 % club_size != 0:
            rem = BS6 % club_size
            self._fail(
                f"BS[6]={BS6} not divisible by Club.size={club_size} (rem={rem})",
                YAML, f"Club:Size {club_size} wrong — BS[6]={BS6} rem={rem}"
            )
            for alt in [80, 84, 88, 92, 96, 100, 104, 108, 112, 116, 120, 124, 128, 138]:
                if BS6 % alt == 0:
                    self._info(f"→ Club.size={alt} divides BS[6] exactly ({BS6//alt} clubs)")
        else:
            self._ok(f"BS[6]/{club_size} = {BS6//club_size} clubs (exact)")

    def check_kits_and_logo(self, B6, CT, CS, nat_slots, KSN, KSC,
                             total_clubs, B8, logo_total, logo_size):
        """Verify kits_end < B[8] and logo block fits."""
        self._section("Kits & Logo Block")
        kits_end = B6 + CT * CS + nat_slots * KSN + total_clubs * KSC
        logo_space = B8 - kits_end - 8
        self._info(f"kits_end = B[6]+CT*CS+nat*KSN+clubs*KSC = {kits_end}")
        self._info(f"B[8] (emblems) = {B8}, logo_space = B8-kits_end-8 = {logo_space}")

        if logo_space < 0:
            overshoot = -logo_space
            self._fail(
                f"kits_end overshoots B[8] by {overshoot} bytes — kit sizes too large",
                YAML, f"Kits:Club Kit Data Size too large — kits_end exceeds B[8] by {overshoot}B"
            )
            # Suggest a smaller KSC
            for alt_KSC in sorted(set([KSC - 104, KSC - 96, KSC - 88, KSC - 80, 544, 456])):
                if alt_KSC <= 0: continue
                alt_end = B6 + CT * CS + nat_slots * KSN + total_clubs * alt_KSC
                alt_space = B8 - alt_end - 8
                if alt_space > 0 and logo_size and alt_space % logo_size == 0:
                    n = alt_space // logo_size
                    if 20 <= n <= 120:
                        self._info(f"→ KSC={alt_KSC} gives {n} logos×{logo_size}B exactly")
        elif logo_total == 0:
            implied = logo_space // logo_size if logo_size else 0
            self._warn(
                f"Logo.total=0 in YAML but {logo_space}B gap available (~{implied} logos)",
                WARN, f"Logo:Total not set — gap implies {implied} logos at {logo_size}B each"
            )
        elif logo_size and logo_space % logo_size != 0:
            implied = logo_space // logo_size
            self._warn(
                f"Logo gap {logo_space}B ÷ {logo_size} = {logo_space/logo_size:.2f} "
                f"(YAML says {logo_total} logos, expected {logo_total*logo_size}B)",
                WARN, f"Logo:Total or Logo:Size may be wrong — gap={logo_space} ÷ {logo_size} = {logo_space/logo_size:.2f}"
            )
        else:
            self._ok(f"Logo block: {logo_total} logos × {logo_size}B = {logo_space}B ✓")

    def check_emblem_block(self, BS8, emb_total, emb_128, emb_16):
        """Verify emblem slot size divides BS[8] to give expected count."""
        self._section("Emblem Block")
        slot = emb_128 + emb_16
        if slot == 0:
            self._fail("Emblem slot size is 0 — check Emblem:Size 128 and Size 16", YAML)
            return
        implied = BS8 // slot
        rem = BS8 % slot
        self._info(f"BS[8]={BS8}, slot={emb_128}+{emb_16}={slot}, implied total={implied} (rem={rem})")
        if implied != emb_total:
            self._fail(
                f"Emblem.total {emb_total} in YAML ≠ BS[8]/{slot} = {implied}",
                YAML, f"Emblem:Total {emb_total} wrong — BS[8] implies {implied}"
            )
            self._info(f"→ Set Emblem:Total: {implied} in YAML")
        else:
            self._ok(f"Emblem.total={emb_total} confirmed by BS[8]/{slot}")

    def check_formation_address(self, f0_addr, data_len, form_size):
        """Verify computed formation 0 address is within data."""
        self._section("Formation Block")
        if f0_addr < 0 or f0_addr >= data_len:
            self._fail(
                f"Formation 0 address {f0_addr} out of OF data range (len={data_len})",
                YAML, "Formation address out of range — check OF_BLOCK[5] or Teams config"
            )
        else:
            self._ok(f"Formation 0 address {f0_addr} within OF data")
            if f0_addr + form_size < data_len:
                self._ok(f"Formation.size={form_size} fits within OF data")

    def check_shop_points(self, data, spo1, spo2):
        """Read and validate both shop points copies."""
        self._section("Shop Points")
        # Copy 1 — unencrypted B[0]
        if spo1 + 4 <= len(data):
            gp1 = struct.unpack_from("<I", data, spo1)[0]
            ok1 = 0 <= gp1 <= 9_999_999
            self._ok(f"GP copy 1 @ offset {spo1}: {gp1:,} GP") if ok1 else             self._warn(f"GP copy 1 @ offset {spo1}: {gp1} — out of 0–9,999,999 range",
                       WARN, f"Shop points copy 1 @ {spo1} = {gp1} — implausible")
        else:
            self._fail(f"Shop points offset 1 ({spo1}) out of data range", YAML)

        # Copy 2 — encrypted block (value only trustworthy if GP=0 on EUR)
        if spo2 and spo2 + 4 <= len(data):
            gp2 = struct.unpack_from("<I", data, spo2)[0]
            ok2 = 0 <= gp2 <= 9_999_999
            self._ok(f"GP copy 2 @ offset {spo2}: {gp2:,} GP") if ok2 else             self._info(f"GP copy 2 @ offset {spo2}: {gp2} — encrypted block, "
                       "value only verifiable with known GP balance")
        elif spo2 == 0:
            self._warn("Shop:Points Offset is 0 — not configured in YAML",
                       WARN, "Shop:Points Offset not set in YAML")

    def check_first_unused(self, FU, total_slots, player_size, data, p0_addr):
        """Verify First Unused is within range and the slot looks empty."""
        self._section("First Unused Player")
        if FU == 0:
            self._warn("Player:First Unused is 0 — may default to total slots",
                       WARN, "Player:First Unused not set in YAML")
            return
        if FU > total_slots:
            self._fail(
                f"First Unused {FU} > total player slots {total_slots}",
                YAML, f"Player:First Unused {FU} exceeds total slots {total_slots}"
            )
            return
        self._ok(f"First Unused {FU} within total slots {total_slots}")

        # Optionally peek at the slot
        addr = p0_addr + FU * player_size
        if addr + 4 <= len(data):
            v = struct.unpack_from("<I", data, addr)[0]
            zero_bytes = sum(1 for b in data[addr:addr+32] if b == 0) if addr + 32 <= len(data) else 0
            if zero_bytes >= 28:
                self._ok(f"Slot at First Unused appears empty ({zero_bytes}/32 zero bytes)")
            else:
                self._warn(
                    f"Slot at First Unused ({FU}) has only {zero_bytes}/32 zero bytes "
                    f"— official save or First Unused may be wrong",
                    WARN, f"Player:First Unused slot {FU} not empty ({32-zero_bytes} non-zero bytes)"
                )

    # ── summary & flush ────────────────────────────────────────────────────────

    @property
    def warnings(self):
        """Return list of (category, message) for non-INFO issues."""
        return [(cat, msg) for cat, msg in self.issues]

    @property
    def yaml_issues(self):
        return [(cat, msg) for cat, msg in self.issues if cat == YAML]

    @property
    def has_critical(self):
        return any(cat in (YAML, CODE) for cat, _ in self.issues)

    def summary(self):
        """Append a summary section to the log."""
        self._section("SUMMARY")
        self._info(f"Game: {self.game_name or 'unknown'}")
        self._info(f"File: {self.filename or 'unknown'}")
        yaml_i = [(c,m) for c,m in self.issues if c == YAML]
        code_i = [(c,m) for c,m in self.issues if c == CODE]
        warn_i = [(c,m) for c,m in self.issues if c == WARN]

        if not self.issues:
            self._ok("All checks passed — no issues found")
        if yaml_i:
            self.log_lines.append(f"\n  YAML CONFIG ISSUES ({len(yaml_i)}) — fix the game YAML:")
            for _, msg in yaml_i:
                self.log_lines.append(f"    • {msg}")
        if code_i:
            self.log_lines.append(f"\n  CODE ISSUES ({len(code_i)}):")
            for _, msg in code_i:
                self.log_lines.append(f"    • {msg}")
        if warn_i:
            self.log_lines.append(f"\n  WARNINGS ({len(warn_i)}) — investigate:")
            for _, msg in warn_i:
                self.log_lines.append(f"    • {msg}")

    def flush(self, log_path=None):
        """Write log to disk."""
        self.summary()
        target = Path(log_path) if log_path else self.LOG_PATH
        try:
            target.write_text("\n".join(self.log_lines) + "\n", encoding="utf-8")
        except Exception:
            pass  # never let logging crash the editor