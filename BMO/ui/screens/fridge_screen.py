# ui/screens/fridge_screen.py
import tkinter as tk

from features.fridge.fridge_service import FridgeService
from ui.screens.common_widgets import create_back_button


class FridgeScreen:
    """
    냉장고 보유 식재료 목록 화면 UI.

    데이터 조회와 가공은 FridgeService가 담당하고, 이 클래스는 화면
    구성과 이벤트 연결만 담당한다.
    """

    def __init__(self, parent, on_back, fridge_service=None):
        self.parent = parent
        self.on_back = on_back
        self.fridge_service = fridge_service or FridgeService()
        self.frame = None
        self.ingredient_items = []

    def show(self):
        self.ingredient_items = self.fridge_service.get_ingredient_items()

        self.frame = tk.Frame(
            self.parent,
            bg="#78CDAC",
            width=1280,
            height=720
        )
        self.frame.place(x=0, y=0, width=1280, height=720)
        self.frame.lift()

        self._create_title()
        self._create_back_button()
        self._create_ingredient_list()
        self._create_bottom_note()

    def destroy(self):
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None

    def _create_title(self):
        title_label = tk.Label(
            self.frame,
            text="냉장고",
            font=("맑은 고딕", 28, "bold"),
            bg="#78CDAC",
            fg="#1A274D"
        )
        title_label.pack(pady=(45, 8))

        subtitle_label = tk.Label(
            self.frame,
            text="현재 냉장고에 등록된 재료 목록입니다.",
            font=("맑은 고딕", 14),
            bg="#78CDAC",
            fg="#1A274D"
        )
        subtitle_label.pack()

    def _create_back_button(self):
        create_back_button(self.frame, self.on_back)

    def _create_ingredient_list(self):
        list_area = tk.Frame(
            self.frame,
            bg="#FDFDFD",
            highlightbackground="#1A274D",
            highlightthickness=2
        )
        list_area.place(x=255, y=155, width=770, height=410)

        header = tk.Frame(
            list_area,
            bg="#D5ECFF",
            height=62
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        self._create_column_text(
            parent=header,
            text="식재료명",
            x=55,
            font_size=16,
            bold=True,
            bg="#D5ECFF"
        )
        self._create_column_text(
            parent=header,
            text="수량",
            x=330,
            font_size=16,
            bold=True,
            bg="#D5ECFF"
        )
        self._create_column_text(
            parent=header,
            text="등록 방식",
            x=520,
            font_size=16,
            bold=True,
            bg="#D5ECFF"
        )

        body_canvas = tk.Canvas(
            list_area,
            bg="#FDFDFD",
            highlightthickness=0,
            bd=0
        )
        scrollbar = tk.Scrollbar(
            list_area,
            orient="vertical",
            command=body_canvas.yview
        )
        rows_frame = tk.Frame(body_canvas, bg="#FDFDFD")

        rows_window = body_canvas.create_window(
            (0, 0),
            window=rows_frame,
            anchor="nw"
        )
        body_canvas.configure(yscrollcommand=scrollbar.set)

        body_canvas.pack(side="left", fill="both", expand=True, padx=(0, 0))
        scrollbar.pack(side="right", fill="y")

        def update_scroll_region(event=None):
            body_canvas.configure(scrollregion=body_canvas.bbox("all"))
            body_canvas.itemconfigure(rows_window, width=body_canvas.winfo_width())

        rows_frame.bind("<Configure>", update_scroll_region)
        body_canvas.bind("<Configure>", update_scroll_region)
        body_canvas.bind(
            "<MouseWheel>",
            lambda event: body_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        )
        rows_frame.bind(
            "<MouseWheel>",
            lambda event: body_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        )

        for item in self.ingredient_items:
            self._create_item_row(
                rows_frame,
                item["name"],
                item["quantity"],
                item["source"],
                body_canvas
            )

    def _create_item_row(self, parent, name, quantity, source, scroll_target=None):
        row = tk.Frame(
            parent,
            bg="#FDFDFD",
            height=72
        )
        row.pack(fill="x", padx=2, pady=2)
        row.pack_propagate(False)

        name_label = self._create_column_text(
            parent=row,
            text=name,
            x=55,
            font_size=15,
            bg="#FDFDFD"
        )
        quantity_label = self._create_column_text(
            parent=row,
            text=quantity,
            x=330,
            font_size=15,
            bg="#FDFDFD"
        )
        source_label = self._create_column_text(
            parent=row,
            text=source,
            x=520,
            font_size=15,
            bg="#FDFDFD"
        )

        if scroll_target is not None:
            widgets = [row, name_label, quantity_label, source_label]
            for widget in widgets:
                widget.bind(
                    "<MouseWheel>",
                    lambda event: scroll_target.yview_scroll(int(-1 * (event.delta / 120)), "units")
                )

    def _create_column_text(
        self,
        parent,
        text,
        x,
        font_size,
        bg,
        bold=False
    ):
        font_weight = "bold" if bold else "normal"

        label = tk.Label(
            parent,
            text=text,
            font=("맑은 고딕", font_size, font_weight),
            bg=bg,
            fg="#1A274D",
            anchor="w"
        )
        label.place(x=x, rely=0.5, anchor="w")
        return label

    def _create_bottom_note(self):
        note = tk.Label(
            self.frame,
            text="재료 정보는 냉장고 서비스에서 조회한 결과입니다.",
            font=("맑은 고딕", 13),
            bg="#78CDAC",
            fg="#1A274D"
        )
        note.place(relx=0.5, y=600, anchor="center")
