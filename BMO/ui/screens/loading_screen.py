import tkinter as tk


class RecipeLoadingScreen:
    """Lightweight BMO-style loading screen for long recipe recommendations."""

    BG_COLOR = "#78CDAC"
    INK_COLOR = "#1A274D"
    PANEL_COLOR = "#D5ECFF"
    BAR_TRACK = "#5FB997"
    BAR_BLOCK = "#FDFDFD"

    def __init__(self, parent):
        self.parent = parent
        self.frame = None
        self.canvas = None
        self.after_id = None
        self.step = 0
        self.block_count = 4
        self.block_width = 16
        self.block_gap = 6
        self.frame_hold = 2
        self.track_left = 10
        self.track_right = 374
        self.track_top = 15
        self.track_bottom = 29

    def show(self):
        self.destroy()

        self.frame = tk.Frame(
            self.parent,
            bg=self.BG_COLOR,
            width=1280,
            height=720
        )
        self.frame.place(x=0, y=0, width=1280, height=720)
        self.frame.lift()

        tk.Label(
            self.frame,
            text="Bemore Recipe",
            font=("맑은 고딕", 30, "bold"),
            bg=self.BG_COLOR,
            fg=self.INK_COLOR
        ).place(relx=0.5, y=186, anchor="center")

        self._create_face()

        tk.Label(
            self.frame,
            text="가지고 있는 재료로 만들 수 있는 요리를 찾고 있어...",
            font=("맑은 고딕", 19),
            bg=self.BG_COLOR,
            fg=self.INK_COLOR
        ).place(relx=0.5, y=380, anchor="center")

        self._create_loading_bar()
        self.start_loading_animation()

    def destroy(self):
        self.stop_loading_animation()

        if self.frame is not None:
            self.frame.destroy()
            self.frame = None

        self.canvas = None
        self.step = 0

    def start_loading_animation(self):
        self.stop_loading_animation()
        self.step = 0
        self.animate_loading_bar()

    def stop_loading_animation(self):
        if self.after_id is not None and self.frame is not None:
            try:
                self.frame.after_cancel(self.after_id)
            except tk.TclError:
                pass
        self.after_id = None

    def _create_face(self):
        face = tk.Canvas(
            self.frame,
            width=170,
            height=112,
            bg=self.BG_COLOR,
            highlightthickness=0
        )
        face.place(relx=0.5, y=284, anchor="center")

        face.create_rectangle(
            18, 14, 152, 98,
            fill=self.PANEL_COLOR,
            outline=self.INK_COLOR,
            width=4
        )
        face.create_oval(54, 48, 72, 66, fill=self.INK_COLOR, outline="")
        face.create_oval(98, 48, 116, 66, fill=self.INK_COLOR, outline="")
        face.create_arc(
            69, 52, 101, 84,
            start=205,
            extent=130,
            style="arc",
            outline=self.INK_COLOR,
            width=4
        )

    def _create_loading_bar(self):
        self.canvas = tk.Canvas(
            self.frame,
            width=384,
            height=44,
            bg=self.BG_COLOR,
            highlightthickness=0
        )
        self.canvas.place(relx=0.5, y=472, anchor="center")

        self.canvas.create_rectangle(
            0, 8, 384, 36,
            fill=self.BAR_TRACK,
            outline=self.INK_COLOR,
            width=2
        )

    def animate_loading_bar(self):
        if self.frame is None or self.canvas is None:
            return

        self.canvas.delete("loading_block")

        pitch = self.block_width + self.block_gap
        slot_count = ((self.track_right - self.track_left - self.block_width) // pitch) + 1
        cycle_length = slot_count + self.block_count - 1
        head_slot = (self.step // self.frame_hold) % cycle_length

        visible_slots = []
        for index in range(self.block_count):
            slot = head_slot - index
            if 0 <= slot < slot_count:
                visible_slots.append(slot)

        for slot in sorted(visible_slots):
            x1 = self.track_left + slot * pitch
            self.canvas.create_rectangle(
                x1,
                self.track_top,
                x1 + self.block_width,
                self.track_bottom,
                fill=self.BAR_BLOCK,
                outline=self.PANEL_COLOR,
                width=1,
                tags="loading_block"
            )

        self.step += 1
        self.after_id = self.frame.after(110, self.animate_loading_bar)
