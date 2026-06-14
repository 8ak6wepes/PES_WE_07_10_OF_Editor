class Logo:

    # ── Fixed pixel-format constants (same for all PS2 WE/PES titles) ─────────
    header_size      = 32   # bytes of header before pixel data in each record
    width            = 32   # pixel width
    height           = 32   # pixel height
    bpp              = 4    # bits per pixel (16-colour indexed palette)
    palette_pes_size = 64   # palette bytes: 2^bpp colours × 4 bytes RGBA = 16×4
    #                         logo data layout: logo[:64] = palette, logo[64:] = pixels
    #                         pixel data = width×height×bpp/8 = 32×32×4/8 = 512 bytes
    #                         total logo field = header_size + palette + pixels = 608

    # ── Config-injected class attributes ──────────────────────────────────────
    # Sentinel defaults — real values set by OptionFile.__init__ from YAML.
    # Logo: Total and Logo: Size in the game YAML override these.
    start_address = 0    # set to Kits.end_address in OptionFile.__init__
    total         = 80   # Logo: Total
    size          = 608  # Logo: Size

    def __init__(self, option_file, idx):
        self.option_file = option_file
        self.idx = idx
        self.set_addresses()
        self.set_logo()
        self.set_pes_palette()
        self.set_pes_idat()

    def set_addresses(self):
        """
        Set the following logo addresses:

        - logo
        """
        self.header_address = self.start_address + (self.idx * self.size)
        self.logo_address = self.header_address + self.header_size

    def set_logo(self):
        """
        Generates a bytearray with the logo data
        """
        self.header = self.option_file.data[self.header_address : self.header_address + self.header_size]
        self.logo = self.option_file.data[self.logo_address : self.header_address + self.size]

    def set_pes_palette(self):
        """
        Set the "PES" palette which is a combination of rgb palette + transparency
        """
        self.pes_palette = self.logo[: self.palette_pes_size]

    def set_pes_idat(self):
        """
        Set the "PES" idat which is a png idat decompress
        """
        self.pes_idat = self.logo[self.palette_pes_size :]

    def enable_logo(self):
        """
        Enable logo in game, without this byte being 1 the logo wont be displayed
        """
        self.header[0] = 1

    def delete_logo(self):
        """
        Fill the logo with zeros, and option file data
        """
        self.header = bytearray(self.header_size)
        self.logo = bytearray(self.size - self.header_size)
        self.option_file.data[self.header_address : self.header_address + self.header_size] = self.header
        self.option_file.data[self.logo_address : self.header_address + self.size] = self.logo

    def update_logo(self, palette, idat):
        if len(palette) + len(idat) == len(self.logo):
            self.enable_logo()
            self.logo = palette + idat
            self.option_file.data[self.header_address : self.header_address + self.header_size] = self.header
            self.option_file.data[self.logo_address : self.header_address + self.size] = self.logo
            self.set_logo()
            self.set_pes_palette()
            self.set_pes_idat()
        else:
            raise ValueError("Image palette and idat size is not equals to the pes logo size")