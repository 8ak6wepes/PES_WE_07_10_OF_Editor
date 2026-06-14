import tkinter as tk
import os
import sys, traceback
from pathlib import Path
from tkinter import Tk, Menu, filedialog, messagebox
from tkinter.ttk import Notebook

import yaml

from editor import OptionFile, Team, Player, common_functions, load_csv
from editor.utils.constants import *

from gui import ClubTab, LogosTab, ShopTab, StadiumLeagueTab, PlayersTab, ImportTab, Config
from gui.export_to_csv_window import ExportToCSVWindow
from gui.face_hair_folder_window import FaceHairFolderWindow


class Gui(Tk):
    appname = "PES/WE OF Editor 2007-2010"
    report_callback_exception = common_functions.report_callback_exception
    last_working_dir = os.getcwd()
    current_exe_name = Path(sys.argv[0]).stem
    of = None

    def __init__(self):
        Tk.__init__(self)
        self.title(self.appname)
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws / 2) - (MAIN_WINDOW_W / 2)
        y = (hs / 2) - (MAIN_WINDOW_H / 2)
        self.geometry('%dx%d+%d+%d' % (MAIN_WINDOW_W, MAIN_WINDOW_H, x, y))
        self.iconbitmap(default=common_functions.resource_path("resources/img/pes_indie.ico"))
        load_defaults = False

        self.of2: OptionFile = None

        try:
            with open(os.getcwd() + "/" + self.current_exe_name + ".yaml") as stream:
                self.settings_file = yaml.safe_load(stream)
                self.last_working_dir = self.settings_file.get('Last Working Dir')
                self.my_config = Config(self.settings_file.get('Last Config File Used'))
                self._warn_config_errors()
        except Exception:
            load_defaults = True
            messagebox.showinfo(title=self.appname, message="No setting file found\nLoading default options")
        if load_defaults:
            try:
                self.my_config = Config()
                self._warn_config_errors()
            except Exception as e:
                messagebox.showerror(title=self.appname, message=f"No config files found: {e}")
                self.quit()
                self.destroy()

        self.my_menu = Menu(self.master)
        self.config(menu=self.my_menu)
        self.file_menu = Menu(self.my_menu, tearoff=0)
        self.edit_menu = Menu(self.my_menu, tearoff=0)
        self.help_menu = Menu(self.my_menu, tearoff=0)

        self.my_menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open", command=self.open)
        self.file_menu.add_command(label="Open OF2", command=self.open_of2)
        self.file_menu.add_command(label="Save", state='disabled', command=self.save_btn_action)
        self.file_menu.add_command(label="Save as...", state='disabled', command=self.save_as_btn_action)
        self.file_menu.add_command(label="Save as OF encrypted", state='disabled', command=self.save_of_encrypted_btn_action)
        self.file_menu.add_command(label="Save as OF decrypted", state='disabled', command=self.save_of_decrypted_btn_action)
        self.file_menu.add_command(label="Exit", command=lambda: self.stop())

        self.my_menu.add_cascade(label="Edit", menu=self.edit_menu)
        self.edit_menu.add_command(label="Export to CSV", state='disabled', command=self.export_to_csv)
        self.edit_menu.add_command(label="Import from CSV", state='disabled', command=self.import_from_csv)
        self.edit_menu.add_command(label="Select Face/Hair Folder", state='disabled', command=self.select_face_hair_folder)
        self.edit_submenu = Menu(self.my_menu, tearoff=0)

        dinamic_menues_val = {}
        for i in range(len(self.my_config.games_config)):
            game_name = self.my_config.games_config[i]
            if ":" in game_name:
                key = game_name.split(":")[0]
                entry = (i, game_name.split(":")[1])
                dinamic_menues_val.setdefault(key, []).append(entry)
            else:
                dinamic_menues_val[game_name] = [i, game_name]

        if dinamic_menues_val:
            for key in dinamic_menues_val.keys():
                if isinstance(dinamic_menues_val.get(key)[0], int):
                    self.edit_submenu.add_command(
                        label=dinamic_menues_val.get(key)[1],
                        command=lambda i=dinamic_menues_val.get(key)[0]: self.change_config(self.my_config.filelist[i])
                    )
                else:
                    dinamic_menu = Menu(self.my_menu, tearoff=0)
                    self.edit_submenu.add_cascade(label=key, menu=dinamic_menu)
                    for item in dinamic_menues_val.get(key):
                        dinamic_menu.add_command(
                            label=item[1],
                            command=lambda i=item[0]: self.change_config(self.my_config.filelist[i])
                        )

        self.edit_menu.add_cascade(label="Game Version", menu=self.edit_submenu)

        self.my_menu.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="Manual", command=self.manual)
        self.help_menu.add_command(label="About", command=self.about)

        game_ver = self.my_config.file["Gui"]["Game Name"]
        self.title(f"{self.appname} Version: {game_ver}")
        self.tabs_container = Notebook(self)
        self.protocol('WM_DELETE_WINDOW', self.stop)

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _warn_config_errors(self):
        if not self.my_config.validation_errors:
            return
        error_text = "\n".join(self.my_config.validation_errors)
        messagebox.showwarning(
            title=self.appname,
            message=(
                f"The config file at:\n{self.my_config.file_location}\n\n"
                f"has the following issues — default values will be used "
                f"for missing entries:\n\n{error_text}"
            ),
        )

    def create_config(self):
        self.my_config = Config()
        self._warn_config_errors()

    def change_config(self, file):
        self.my_config = Config(file)
        self._warn_config_errors()
        game_ver = self.my_config.file["Gui"]["Game Name"]
        self.title(f"{self.appname} Version: {game_ver}")
        self.tabs_container.destroy()
        self.of = None
        self.file_menu.entryconfig("Save", state="disabled")
        self.file_menu.entryconfig("Save as...", state="disabled")
        self.file_menu.entryconfig("Save as OF decrypted", state="disabled")
        self.edit_menu.entryconfig("Export to CSV", state="disabled")
        self.edit_menu.entryconfig("Import from CSV", state="disabled")
        self.edit_menu.entryconfig("Select Face/Hair Folder", state="disabled")
        self.tabs_container = Notebook(self)

    # ------------------------------------------------------------------
    # Game auto-detection
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_identifier(filename: str) -> str | None:
        """
        Read the minimum bytes needed to extract the game identifier string,
        using the same logic as OptionFile.read_option_file().

        .psu  — identifier is at header_data[64:83] (19 bytes).
                 header_data is everything before the last OF_BYTE_LENGTH bytes,
                 but the identifier is always within the first 128 bytes of the
                 file so we only read that far.
        .xps  — no embedded identifier; return file stem so caller can attempt
                 a name-based fallback.
        other — return file stem (used as game_identifier in read_option_file).
        """
        extension = Path(filename).suffix.lower()
        try:
            with open(filename, "rb") as f:
                if extension == ".psu":
                    header_start = f.read(128)
                    raw = header_start[64:83]
                    return raw.decode("utf-8", errors="ignore").rstrip("\x00")
                else:
                    return Path(filename).stem
        except OSError:
            return None

    def _find_matching_config(self, identifier: str) -> str | None:
        """
        Scan every YAML in self.my_config.filelist for one whose
        Game Identifier list contains *identifier*.
        Returns the file path of the first match, or None.
        """
        if not identifier:
            return None
        for config_path in self.my_config.filelist:
            try:
                with open(config_path, encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                identifiers = raw.get("option_file_data", {}).get("Game Identifier", [])
                if identifier in identifiers:
                    return config_path
            except Exception:
                continue
        return None

    def _auto_detect_and_switch(self, filename: str) -> bool:
        """
        Attempt to detect the game version from *filename* and switch the
        active config if a better match is found.

        Returns True if the config was switched, False otherwise.
        """
        identifier = self._extract_identifier(filename)
        if not identifier:
            return False

        # Already correct — identifier is in the current config's list
        current_ids = self.my_config.file["option_file_data"].get("Game Identifier", [])
        if identifier in current_ids:
            return False

        matched_path = self._find_matching_config(identifier)
        if not matched_path:
            return False

        new_config = Config(matched_path)
        game_name = new_config.file["Gui"]["Game Name"]
        self.my_config = new_config
        self._warn_config_errors()
        self.title(f"{self.appname} Version: {game_name}")
        messagebox.showinfo(
            title=self.appname,
            message=f"Game version detected: {game_name}\nConfig switched automatically.",
        )
        return True

    # ------------------------------------------------------------------
    # File-open helpers
    # ------------------------------------------------------------------

    def _open_file(self, attr: str):
        filetypes = [
            ('All files', '*.*'),
            ("PES/WE PS2 Option File", ".psu .xps"),
            ("PES/WE PSP Option File", ".bin"),
            ("PES/WE 3DS Option File", ".dat"),
        ]

        filename = filedialog.askopenfilename(
            title=f'{self.appname} Select your option file',
            initialdir=self.last_working_dir,
            filetypes=filetypes,
        )
        if not filename:
            return

        self.last_working_dir = str(Path(filename).parents[0])

        # Auto-detection only for the primary OF, not OF2.
        # OF2 is deliberately allowed to differ from the active config.
        if attr == 'of':
            self._auto_detect_and_switch(filename)

        current = getattr(self, attr)
        try:
            setattr(self, attr, OptionFile(filename, self.my_config.file))
        except Exception as e:
            if current is not None:
                setattr(self, attr, current)
            tb_str = traceback.format_exc()
            # Write full traceback to log file alongside the executable
            try:
                log_path = os.path.join(os.getcwd(), "of_editor_error.log")
                with open(log_path, "w") as log_f:
                    log_f.write(tb_str)
            except Exception:
                pass
            messagebox.showerror(
                self.appname,
                f"Failed to open option file:\n{e}\n\nFull traceback written to:\nof_editor_error.log",
            )
            return

        self.reload_gui_items()
        self._show_load_diagnostics(getattr(self, attr))

    def _show_load_diagnostics(self, of_obj):
        """
        After a successful load, check the diagnostics object on the
        OptionFile for any YAML or code issues and surface them to the user
        as a scrollable, non-blocking window.
        Issues are also always written to of_load_diagnostics.log.
        """
        if of_obj is None or not hasattr(of_obj, "diagnostics"):
            return
        diag = of_obj.diagnostics
        issues = diag.warnings
        if not issues:
            return

        yaml_issues = [(c, m) for c, m in issues if c == "YAML"]
        warn_issues = [(c, m) for c, m in issues if c == "WARN"]
        code_issues = [(c, m) for c, m in issues if c == "CODE"]

        # Build message
        lines = []
        if yaml_issues:
            lines.append(f"YAML CONFIG ISSUES ({len(yaml_issues)}) — update the game YAML:")
            for _, msg in yaml_issues:
                lines.append(f"  • {msg}")
        if code_issues:
            lines.append(f"\nCODE ISSUES ({len(code_issues)}):")
            for _, msg in code_issues:
                lines.append(f"  • {msg}")
        if warn_issues:
            lines.append(f"\nWARNINGS ({len(warn_issues)}) — may be expected for some saves:")
            for _, msg in warn_issues:
                lines.append(f"  • {msg}")
        lines.append("\nFull details: of_load_diagnostics.log")
        msg_text = "\n".join(lines)

        # Only show popup for YAML/CODE issues; warnings go to log only
        if not yaml_issues and not code_issues:
            return

        # Scrollable diagnostic window
        win = tk.Toplevel(self)
        game_name = getattr(of_obj, 'diagnostics', None) and of_obj.diagnostics.game_name
        win.title(f"{self.appname} — Load Diagnostics: {game_name or 'unknown game'}")
        win.resizable(True, True)
        win.geometry("640x380")
        win.grab_set()  # modal

        header_lbl = tk.Label(
            win,
            text="Issues detected while loading the option file.\n"
                 "The file loaded successfully but these items may need attention.",
            wraplength=600, justify="left", pady=6,
        )
        header_lbl.pack(fill="x", padx=10, pady=(10, 0))

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=6)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        txt = tk.Text(
            frame, wrap="word", yscrollcommand=scrollbar.set,
            font=("Courier", 9), relief="flat", bg="#f5f5f5",
        )
        txt.insert("1.0", msg_text)
        txt.config(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=txt.yview)

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(
            btn_frame, text="Open Log File",
            command=lambda: os.startfile("of_load_diagnostics.log")
            if hasattr(os, "startfile") else None,
        ).pack(side="left", padx=4)
        tk.Button(btn_frame, text="OK", command=win.destroy, width=10).pack(side="right", padx=4)

    def open(self):
        self._open_file('of')

    def open_of2(self):
        self._open_file('of2')

    # ------------------------------------------------------------------
    # GUI layout
    # ------------------------------------------------------------------

    def publish(self):
        self.players_tab.publish()
        self.players_tab.load_faces_hairs()
        self.clubs_tab.publish()
        self.stadium_league_tab.publish()
        self.shop_tab.publish()
        self.import_tab.publish()

        self.tabs_container.pack()
        self.tabs_container.add(self.players_tab, text="Players & Teams")
        self.tabs_container.add(self.clubs_tab, text="Clubs")
        self.tabs_container.add(self.stadium_league_tab, text="Stadiums & Leagues")
        self.tabs_container.add(self.logos_tab, text="Logos")
        self.tabs_container.add(self.import_tab, text="Import From OF2")
        self.tabs_container.bind('<<NotebookTabChanged>>', self.on_tab_change)

    def on_tab_change(self, event):
        tab = event.widget.tab('current')['text']
        if tab == 'Clubs':
            self.clubs_tab.refresh_gui()
        if tab == 'Players & Teams':
            self.players_tab.update_teams_cmb_values()

    def reload_gui_items(self, args={}):
        self.file_menu.entryconfig("Save", state="normal")
        self.file_menu.entryconfig("Save as...", state="normal")
        self.file_menu.entryconfig("Save as OF decrypted", state="normal")
        self.edit_menu.entryconfig("Export to CSV", state="normal")
        self.edit_menu.entryconfig("Import from CSV", state="normal")
        self.edit_menu.entryconfig("Select Face/Hair Folder", state="normal")
        prev_selection = self.tabs_container.select()
        current_index = -1
        if prev_selection:
            current_index = self.tabs_container.index("current")
        self.tabs_container.destroy()
        self.tabs_container = Notebook(self)
        self.players_tab = PlayersTab(self.tabs_container, self.of, MAIN_WINDOW_W, MAIN_WINDOW_H, self.appname)
        self.clubs_tab = ClubTab(self.tabs_container, self.of, MAIN_WINDOW_W, MAIN_WINDOW_H, self.appname)
        self.stadium_league_tab = StadiumLeagueTab(self.tabs_container, self.of, MAIN_WINDOW_W, MAIN_WINDOW_H, self.appname)
        self.logos_tab = LogosTab(self.tabs_container, self.of, MAIN_WINDOW_W, MAIN_WINDOW_H, self.appname)
        self.shop_tab = ShopTab(self.tabs_container, self.of, MAIN_WINDOW_W, MAIN_WINDOW_H, self.appname)
        self.import_tab = ImportTab(self.tabs_container, self.of, self.of2, MAIN_WINDOW_W, MAIN_WINDOW_H, self.appname)
        self.import_tab.bind("<<ReloadRequest>>", self.reload_gui_items)
        self.publish()
        if prev_selection and current_index >= 0:
            self.tabs_container.select(current_index)

    # ------------------------------------------------------------------
    # Save helpers
    # ------------------------------------------------------------------

    def save_btn_action(self):
        try:
            self.of.save_option_file()
            messagebox.showinfo(title=self.appname, message=f"All changes saved at {self.of.file_location}")
        except Exception as e:
            messagebox.showerror(title=self.appname, message=f"Error while saving, error type={e}, try running as admin")

    def test_save_btn_action(self):
        try:
            with open("", "rb") as dec_of:
                self.of.data = bytearray(dec_of.read())
            self.of.save_option_file()
            messagebox.showinfo(title=self.appname, message=f"All changes saved at {self.of.file_location}")
        except Exception as e:
            messagebox.showerror(title=self.appname, message=f"Error while saving, error type={e}, try running as admin")

    def save_as_btn_action(self):
        try:
            new_location = filedialog.asksaveasfile(
                initialdir=self.last_working_dir, title=self.appname, mode='wb',
                filetypes=([("All files", "*")]), defaultextension=f"{self.of.extension}",
            )
            if not new_location:
                return
            self.of.save_option_file(new_location.name)
            messagebox.showinfo(title=self.appname, message=f"All changes saved at {self.of.file_location}")
        except Exception as e:
            messagebox.showerror(title=self.appname, message=f"Error while saving, error type={e}, try running as admin or saving into another location")

    def _save_of(self, encrypted: bool):
        try:
            new_location = filedialog.asksaveasfile(
                initialdir=self.last_working_dir, title=self.appname, mode='wb',
                filetypes=([("All files", "*")]), defaultextension=f"{self.of.extension}",
            )
            if not new_location:
                return
            self.of.encrypted = encrypted
            self.of.save_option_file(new_location.name)
            self.of.encrypted = self.my_config.file['option_file_data']['ENCRYPTED']
            messagebox.showinfo(title=self.appname, message=f"All changes saved at {self.of.file_location}")
        except Exception as e:
            messagebox.showerror(title=self.appname, message=f"Error while saving, error type={e}, try running as admin or saving into another location")

    def save_of_decrypted_btn_action(self):
        self._save_of(encrypted=False)

    def save_of_encrypted_btn_action(self):
        self._save_of(encrypted=True)

    def convert_of_to_db(self):
        try:
            folder_selected = filedialog.askdirectory(initialdir=self.last_working_dir, title=self.appname)
            if not folder_selected:
                return
            players_file = open(folder_selected + "/db.bin_000", "wb")
            for i in range(Player.first_unused):
                players_file.write(self.of.data[self.of.players[i].address: self.of.players[i].address + Player.size])
            players_file.close()

            national_relink = open(folder_selected + "/db.bin_001", "wb")
            temp_team = Team(self.of, 0)
            national_relink.write(self.of.data[temp_team.dorsal_start_address: temp_team.dorsal_start_address + temp_team.first_club_slot])
            national_relink.close()

            messagebox.showinfo(title=self.appname, message=f"All changes saved at {folder_selected}")
        except Exception as e:
            messagebox.showerror(title=self.appname, message=f"Error while saving, error type={e}, try running as admin or saving into another location")

    def export_to_csv(self):
        csv_window = ExportToCSVWindow(self, self.of)
        csv_window.mainloop()

    def import_from_csv(self):
        try:
            filetypes = [
                ("CSV Files", ".csv"),
                ('All files', '*.*'),
            ]
            filename = filedialog.askopenfilename(
                initialdir=self.last_working_dir,
                title="Select your CSV file",
                filetypes=filetypes,
            )
            if not filename:
                return
            self.last_working_dir = str(Path(filename).parents[0])
            load_csv(filename, self.of)
            self.players_tab.apply_player_filter()
            messagebox.showinfo(title=self.appname, message="CSV file imported")
        except Exception as e:
            tb_str = traceback.format_exc()
            messagebox.showerror(title=self.appname, message="%s\n%s" % (e, tb_str))

    def select_face_hair_folder(self):
        new_window = FaceHairFolderWindow(self)
        new_window.mainloop()
        self.players_tab.load_faces_hairs()

    def about(self):
        messagebox.showinfo(title=self.appname, message=
            """Thanks to PeterC10 for python de/encrypt code for OF and growth type values map,
Yerry11 for png import/export
""")

    def manual(self):
        messagebox.showinfo(title=self.appname, message=
            r"""Maybe in the future there'll be one
""")

    def save_settings(self):
        settings_file_name = os.getcwd() + "/" + self.current_exe_name + ".yaml"
        dict_file = {
            'Last Config File Used': self.my_config.file_location,
            'Last Working Dir': self.last_working_dir,
        }
        settings_file = open(settings_file_name, "w")
        yaml.dump(dict_file, settings_file)
        settings_file.close()

    def start(self):
        self.resizable(False, False)
        self.mainloop()

    def stop(self):
        self.save_settings()
        self.quit()
        self.destroy()