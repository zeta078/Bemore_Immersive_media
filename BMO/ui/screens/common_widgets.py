import tkinter as tk

from PIL import Image, ImageTk

from ui.asset_paths import ICON_IMAGES_DIR


def create_back_button(parent, command, x=45, y=42, width=140, height=52):
    icon_path = ICON_IMAGES_DIR / "back.png"
    parent_bg = parent.cget("bg")

    button_options = {
        "bg": parent_bg,
        "activebackground": parent_bg,
        "relief": "flat",
        "bd": 0,
        "highlightthickness": 0,
        "cursor": "hand2",
        "command": command,
        "takefocus": False,
    }

    try:
        image = Image.open(icon_path).resize((42, 42))
        button_image = ImageTk.PhotoImage(image)
        back_button = tk.Button(parent, image=button_image, **button_options)
        back_button.image = button_image
    except Exception as error:
        print(f"[ERROR] 뒤로가기 이미지 로드 실패: {error}")
        print(f"[CHECK] 이미지 파일 경로 확인: {icon_path}")
        back_button = tk.Button(
            parent,
            text="돌아가기",
            font=("맑은 고딕", 15, "bold"),
            fg="#1A274D",
            activeforeground="#1A274D",
            **button_options
        )

    back_button.place(x=x, y=y, width=width, height=height)
    return back_button
