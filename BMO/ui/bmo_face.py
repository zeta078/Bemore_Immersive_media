# ui/bmo_face.py
import itertools
import random
import re
import time
import tkinter as tk

from PIL import Image, ImageTk

from ui.asset_paths import FACE_IMAGES_DIR, ICON_IMAGES_DIR
from ui.screens.camera_screen import CameraScreen
from ui.screens.fridge_screen import FridgeScreen
from ui.screens.recipe_screen import RecipeScreen
from ui.screens.minigame_screen import MiniGameScreen
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = PROJECT_ROOT / "assets" / "images"
FACE_IMAGES_DIR = IMAGES_DIR / "faces"
ICON_IMAGES_DIR = IMAGES_DIR / "icons"


class BMOFace:
    EXIT_ONLY_SCREENS = {"camera", "minigame"}
    CONTEXT_CHAT_SCREENS = {"fridge", "recipe"}
    PERSISTENT_MIC_SCREENS = {"fridge", "recipe"}
    FUNCTION_MENU_TIMEOUT_MS = 5000

    def __init__(
        self,
        on_sleep_touch=None,
        on_screen_narrate=None,
        on_return_narrate=None
    ):
        self.root = tk.Tk()
        self.root.title("BMO")
        self.root.geometry("1280x720")  # 원본 해상도: 1280x720
        self.root.resizable(False, False)
        self.root.attributes("-fullscreen", True)
        self.on_sleep_touch = on_sleep_touch
        self.on_screen_narrate = on_screen_narrate
        self.on_return_narrate = on_return_narrate

        # -----------------------------
        # 현재 표시 중인 화면
        # face / camera / fridge / recipe / minigame
        # -----------------------------
        self.current_screen = "face"
        self.active_screen = None
        self.active_screen_name = None

        # -----------------------------
        # 기존 얼굴 이미지 출력 영역
        # -----------------------------
        self.label = tk.Label(self.root, bg="black")
        self.label.pack(expand=True, fill="both")

        self.current_image = None
        self.state = None
        self.current_path = None
        self.image_cycle = None
        self.idle_base_file = None
        self.idle_blink_files = []
        self.idle_blink_sequence = []
        self.next_idle_blink_at = time.monotonic()
        self._image_cache: dict = {}   # path → ImageTk.PhotoImage
        self._last_img_path = None

        # -----------------------------
        # 마이크 UI 상태값
        # manual_mute: 사용자가 직접 선택한 수동 음소거
        # screen_input_block: 기능 화면 진입에 따른 자동 입력 차단
        # -----------------------------
        self.manual_mute = False
        self.screen_input_block = False
        self.controls_visible = False
        self.is_function_menu_visible = False
        self.controls_hide_job = None
        self.weather_overlay = None
        self.weather_overlay_image = None
        self.weather_overlay_job = None
        self.function_menu_panel = tk.Frame(
            self.root,
            bg="#D5ECFF",
            bd=0,
            highlightthickness=0
        )

        # -----------------------------
        # 마이크 버튼 이미지 불러오기
        # 경로: assets/images/icons/mic.png, assets/images/icons/mute.png
        # -----------------------------
        self.load_mic_images()

        # -----------------------------
        # 마이크 이미지 버튼
        # 얼굴 화면을 터치했을 때만 표시
        # -----------------------------
        self.mic_button = tk.Button(
            self.root,
            image=self.mic_on_image,
            bg="#78CDAC",
            activebackground="#78CDAC",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.toggle_mic_button
        )

        # -----------------------------
        # 음소거 상태 유지 표시
        # 버튼이 숨겨진 상태에서 음소거 중이면 작은 아이콘 표시
        # -----------------------------
        self.muted_indicator = tk.Label(
            self.root,
            image=self.muted_indicator_image,
            bg="#78CDAC",
            bd=0,
            highlightthickness=0,
            cursor="hand2"
        )

        # -----------------------------
        # 하단 기능 버튼
        # 현재는 화면 전환 테스트를 위해 항상 표시
        # -----------------------------
        self.feature_buttons = []
        self.feature_button_images = []
        self.create_feature_buttons()
        self.hide_controls()

        # 얼굴 화면 클릭/터치 시 상태에 따라 wake 또는 기능 메뉴 표시
        self.label.bind("<Button-1>", self.on_screen_touch)

        # 작은 음소거 아이콘 클릭은 화면 전체 터치와 분리해서 처리
        self.muted_indicator.bind("<Button-1>", self.on_mic_indicator_touch)

        # 애니메이션 루프 시작
        self.root.after(0, self.animate)

    # ==================================================
    # 마이크 이미지 불러오기
    # ==================================================
    def load_mic_images(self):
        mic_image_path = ICON_IMAGES_DIR / "mic.png"
        mute_image_path = ICON_IMAGES_DIR / "mute.png"

        try:
            mic_image = Image.open(mic_image_path).resize((72, 72))
            mute_image = Image.open(mute_image_path).resize((72, 72))
            muted_indicator_image = Image.open(mute_image_path).resize((48, 48))

            self.mic_on_image = ImageTk.PhotoImage(mic_image)
            self.mic_off_image = ImageTk.PhotoImage(mute_image)
            self.muted_indicator_image = ImageTk.PhotoImage(
                muted_indicator_image
            )

        except Exception as e:
            print(f"[ERROR] 마이크 UI 이미지 로드 실패: {e}")
            print(f"[CHECK] 이미지 폴더 경로 확인: {ICON_IMAGES_DIR}")

            # 이미지 문제가 생겨도 프로그램 자체는 종료되지 않도록 처리
            self.mic_on_image = None
            self.mic_off_image = None
            self.muted_indicator_image = None

    # ==================================================
    # 기존 얼굴 상태 및 애니메이션 처리
    # ==================================================
    def set_state(self, state):
        if state in ["happy", "sad", "angry"]:
            path = FACE_IMAGES_DIR / "emotion" / state
        else:
            path = FACE_IMAGES_DIR / state

        if not path.exists():
            print(f"[ERROR] 폴더 없음: {path}")
            return

        files = sorted([
            file.name for file in path.iterdir()
            if file.is_file()
            and file.suffix.lower() in (".png", ".jpg", ".jpeg")
        ])

        if not files:
            print(f"[ERROR] 이미지 없음: {path}")
            return

        self.state = state
        self.current_path = path
        self._last_img_path = None
        self.reset_idle_blink(files if state == "idle" else None)
        self.apply_state_controls(state)

        # speak 상태는 입 열림 → 닫힘 왕복 느낌으로 재생
        if state == "speak" and len(files) > 1:
            sequence = files + files[::-1][1:-1]
        else:
            sequence = files

        self.image_cycle = itertools.cycle(sequence)

    def reset_idle_blink(self, files):
        self.idle_base_file = None
        self.idle_blink_files = []
        self.idle_blink_sequence = []

        if not files:
            return

        numbered_idle_files = [
            file for file in files
            if self.get_idle_file_number(file) is not None
        ]
        numbered_idle_files.sort(key=self.get_idle_file_number)

        if len(numbered_idle_files) >= 2:
            self.idle_base_file = numbered_idle_files[0]
            self.idle_blink_files = numbered_idle_files[1:]
        elif "idle.png" in files and "idle2.png" in files:
            self.idle_base_file = "idle.png"
            self.idle_blink_files = ["idle2.png"]
        elif len(files) >= 2:
            self.idle_base_file = files[0]
            self.idle_blink_files = [files[1]]

        self.schedule_next_idle_blink()

    def get_idle_file_number(self, file):
        match = re.match(r"^idle_?(\d+)", file)
        if match is None:
            return None

        return int(match.group(1))

    def schedule_next_idle_blink(self):
        self.next_idle_blink_at = time.monotonic() + random.uniform(1.5, 3.5)

    def get_idle_frame(self):
        if not self.idle_base_file or not self.idle_blink_files:
            return None, None

        if self.idle_blink_sequence:
            file, delay = self.idle_blink_sequence.pop(0)
            if not self.idle_blink_sequence:
                self.schedule_next_idle_blink()
            return file, delay

        if time.monotonic() >= self.next_idle_blink_at:
            if random.random() < 0.25:
                self.idle_blink_sequence = self.build_idle_blink_sequence()
                self.idle_blink_sequence.append((self.idle_base_file, 80))
                self.idle_blink_sequence.extend(
                    self.build_idle_blink_sequence(include_base=False)
                )
                self.idle_blink_sequence.append((self.idle_base_file, 300))
            else:
                self.idle_blink_sequence = self.build_idle_blink_sequence()

            return self.idle_blink_sequence.pop(0)

        return self.idle_base_file, 300

    def build_idle_blink_sequence(self, include_base=True):
        closed_frame_index = len(self.idle_blink_files) // 2
        closing_frame_count = max(closed_frame_index, 1)
        opening_frame_count = max(
            len(self.idle_blink_files) - closed_frame_index - 1,
            1
        )
        closing_delay = max(8, int(100 / closing_frame_count))
        opening_delay = max(10, int(170 / opening_frame_count))
        sequence = []

        for index, file in enumerate(self.idle_blink_files):
            if index < closed_frame_index:
                delay = closing_delay
            elif index == closed_frame_index:
                delay = 35
            else:
                delay = opening_delay

            sequence.append((file, delay))

        if include_base:
            sequence.append((self.idle_base_file, 300))

        return sequence

    def animate(self):
        """
        얼굴 화면일 때만 표정 이미지를 갱신한다.
        기능 화면을 보고 있는 동안에는 불필요한 얼굴 이미지 로딩을 멈춘다.
        """
        idle_delay = None

        if self.current_screen == "face":
            if self.image_cycle and self.current_path:
                if self.state == "idle":
                    file, idle_delay = self.get_idle_frame()
                    if file is None:
                        file = next(self.image_cycle)
                else:
                    file = next(self.image_cycle)
                img_path = self.current_path / file

                try:
                    if img_path != self._last_img_path:
                        if img_path not in self._image_cache:
                            image = Image.open(img_path).resize((1280, 720))
                            self._image_cache[img_path] = ImageTk.PhotoImage(image)
                            if len(self._image_cache) > 30:
                                oldest = next(iter(self._image_cache))
                                del self._image_cache[oldest]
                        self.current_image = self._image_cache[img_path]
                        self.label.config(image=self.current_image)
                        self._last_img_path = img_path

                        # 이미지 변경 시에만 lift — 매 프레임 호출 시 X11 expose 이벤트로 깜빡임 발생
                        if self.mic_button.winfo_ismapped():
                            self.mic_button.lift()
                        elif self.manual_mute:
                            self.muted_indicator.lift()
                        self.lift_feature_buttons()
                        self.lift_weather_overlay()

                except Exception as e:
                    print(f"[ERROR] 이미지 로드 실패: {e}")

        delay_map = {
            "sleep": 400,
            "wake": 200,
            "idle": 300,
            "listen": 220,
            "think": 500,
            "speak": 160,
            "happy": 300,
            "sad": 400,
            "angry": 200,
        }

        delay = idle_delay or delay_map.get(self.state, 250)
        self.root.after(delay, self.animate)

    # ==================================================
    # 마이크 이미지 버튼 처리
    # ==================================================
    def on_screen_touch(self, event=None):
        """
        얼굴 화면에서만 상태별 터치 동작을 처리한다.
        """
        if self.current_screen != "face":
            return

        if event is not None and event.widget in (self.mic_button, self.muted_indicator):
            return "break"

        if self.state == "sleep":
            self.hide_controls()

            if self.on_sleep_touch is not None:
                self.on_sleep_touch()

            return "break"

        if self.state == "idle":
            self.show_controls()
            return "break"

        return "break"

    def on_mic_indicator_touch(self, event=None):
        self.show_face_mic_button()
        return "break"

    def schedule_controls_auto_hide(self):
        if self.controls_hide_job is not None:
            self.root.after_cancel(self.controls_hide_job)

        self.controls_hide_job = self.root.after(
            self.FUNCTION_MENU_TIMEOUT_MS,
            self.auto_hide_controls
        )

    def cancel_controls_auto_hide(self):
        if self.controls_hide_job is None:
            return

        self.root.after_cancel(self.controls_hide_job)
        self.controls_hide_job = None

    def auto_hide_controls(self):
        self.controls_hide_job = None
        self.hide_controls()

    def show_controls(self):
        if self.current_screen != "face" or self.state != "idle":
            return

        self.controls_visible = True
        self.is_function_menu_visible = True
        self.show_feature_buttons()
        self.show_face_mic_button()
        self.schedule_controls_auto_hide()

    def hide_controls(self):
        self.cancel_controls_auto_hide()
        self.controls_visible = False
        self.is_function_menu_visible = False
        self.function_menu_panel.place_forget()
        self.hide_feature_buttons()
        self.mic_button.place_forget()

        self.update_mic_indicator()

    def show_face_mic_button(self):
        if self.current_screen != "face":
            return

        self.mic_button.place(
            relx=0.975,
            rely=0.035,
            anchor="ne"
        )
        self.mic_button.lift()
        self.muted_indicator.place_forget()

    def toggle_mic_button(self):
        """
        수동 음소거 상태를 변경한다.
        TTS 출력은 막지 않고, 새 음성 입력/STT 시작 여부에만 사용한다.
        """
        self.set_mic_muted(not self.manual_mute)

    def set_mic_muted(self, muted):
        """
        음성 명령이나 UI 버튼에서 수동 음소거 상태를 명시적으로 설정한다.
        """
        self.manual_mute = bool(muted)

        if not self.manual_mute:
            self.mic_button.config(image=self.mic_on_image)
            print("[MIC UI] 마이크 ON 선택")
        else:
            self.mic_button.config(image=self.mic_off_image)
            print("[MIC UI] 음소거 선택")

        if self.controls_visible:
            self.schedule_controls_auto_hide()
        else:
            if self.current_screen in self.PERSISTENT_MIC_SCREENS:
                self.show_persistent_mic_button()
            self.update_mic_indicator()

    def update_mic_indicator(self):
        """
        얼굴 화면에서 버튼이 숨겨져 있고 음소거 상태일 때만
        작은 mute 아이콘을 표시한다.
        """
        if self.current_screen != "face":
            self.muted_indicator.place_forget()
            return

        if self.mic_button.winfo_ismapped():
            self.muted_indicator.place_forget()
            return

        if not self.manual_mute:
            self.muted_indicator.place_forget()
        else:
            self.muted_indicator.place(
                relx=0.975,
                rely=0.035,
                anchor="ne"
            )
            self.muted_indicator.lift()

    def is_voice_input_enabled(self):
        return self.get_voice_mode() != "muted"

    def get_voice_mode(self):
        if self.manual_mute:
            return "muted"

        if self.current_screen in self.EXIT_ONLY_SCREENS:
            return "exit_only"

        if self.current_screen in self.CONTEXT_CHAT_SCREENS:
            return "context_chat"

        return "full_chat"

    def apply_state_controls(self, state):
        if self.current_screen != "face":
            return

        if state == "idle":
            self.hide_controls()
            self.show_face_mic_button()
            return

        if state == "sleep":
            self.hide_controls()
            self.mic_button.place_forget()
            self.muted_indicator.place_forget()
            return

        if state in {"wake", "listen", "think", "speak"}:
            self.hide_controls()
            self.show_face_mic_button()

    def show_persistent_mic_button(self):
        if self.current_screen not in self.PERSISTENT_MIC_SCREENS:
            return

        self.controls_visible = False
        self.muted_indicator.place_forget()
        self.mic_button.place(
            relx=0.975,
            rely=0.035,
            anchor="ne"
        )
        self.mic_button.lift()

    # ==================================================
    # 하단 기능 버튼 처리
    # ==================================================
    def load_feature_button_image(self, icon_name):
        icon_path = ICON_IMAGES_DIR / icon_name

        try:
            image = Image.open(icon_path).resize((42, 42))
            return ImageTk.PhotoImage(image)
        except Exception as e:
            print(f"[ERROR] 기능 버튼 이미지 로드 실패: {e}")
            print(f"[CHECK] 이미지 파일 경로 확인: {icon_path}")
            return None

    def create_feature_buttons(self):
        button_specs = [
            ("camera.png", "카메라", "camera"),
            ("fridge.png", "냉장고", "fridge"),
            ("recipe.png", "레시피", "recipe"),
            ("minigame.png", "미니게임", "minigame"),
        ]

        start_x = 312
        button_width = 145
        gap = 25
        button_y = 610

        for index, (icon_name, label, screen_name) in enumerate(button_specs):
            button_image = self.load_feature_button_image(icon_name)
            self.feature_button_images.append(button_image)

            button = tk.Button(
                self.root,
                image=button_image,
                bg="#FDFDFD",
                activebackground="#D5ECFF",
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda name=screen_name: self.select_feature(name),
                takefocus=False
            )

            if button_image is None:
                button.config(
                    text=label,
                    font=("맑은 고딕", 14, "bold"),
                    fg="#1A274D",
                    activeforeground="#1A274D"
                )

            x = start_x + (button_width + gap) * index
            button.place(
                x=x,
                y=button_y,
                width=button_width,
                height=64
            )

            self.feature_buttons.append(button)

    def select_feature(self, screen_name):
        self.hide_controls()
        self.open_feature_screen(screen_name)

    def open_feature_screen(self, screen_name):
        screen_handlers = {
            "face": self.show_face_screen,
            "home": self.show_face_screen,
            "camera": self.show_camera_screen,
            "fridge": self.show_fridge_screen,
            "recipe": self.show_recipe_screen,
            "minigame": self.show_minigame_screen,
        }

        handler = screen_handlers.get(screen_name)
        if handler is None:
            print(f"[SCREEN WARN] 알 수 없는 기능 화면: {screen_name}")
            return False

        handler()
        return True

    def get_return_message(self, screen_name):
        messages = {
            "camera": "카메라 화면을 닫았어.",
            "fridge": "냉장고 화면을 닫았어.",
            "recipe": "레시피 화면을 닫았어.",
            "minigame": "미니게임 화면을 닫았어.",
        }
        return messages.get(screen_name, "")

    def go_back_from_feature(self, screen_name):
        self.show_face_screen()

        if self.on_return_narrate is not None:
            self.on_return_narrate(self.get_return_message(screen_name))

    def close_current_feature_screen(self):
        if self.current_screen == "face":
            return

        self.go_back_from_feature(self.current_screen)

    def narrate_screen_entry(self, text):
        if text and self.on_screen_narrate is not None:
            self.on_screen_narrate(text)

    def build_recipe_entry_message(self):
        recipes = getattr(self.active_screen, "mock_recipes", [])
        recipe_names = [
            recipe.get("recipe_name", "")
            for recipe in recipes
            if recipe.get("recipe_name")
        ]

        if not recipe_names:
            return ""

        return f"추천 레시피로는 {', '.join(recipe_names)}가 있어."

    def show_feature_buttons(self):
        if self.current_screen != "face":
            return

        start_x = 312
        button_width = 145
        gap = 25
        button_y = 610

        self.function_menu_panel.place(x=302, y=596, width=678, height=94)
        self.function_menu_panel.lift()

        for index, button in enumerate(self.feature_buttons):
            x = start_x + (button_width + gap) * index
            button.place(
                x=x,
                y=button_y,
                width=button_width,
                height=64
            )
            button.lift()

    def hide_feature_buttons(self):
        self.function_menu_panel.place_forget()

        for button in self.feature_buttons:
            button.place_forget()

    def lift_feature_buttons(self):
        if self.current_screen == "face" and self.is_function_menu_visible:
            self.function_menu_panel.lift()
            for button in self.feature_buttons:
                button.lift()

    # ==================================================
    # 날씨 아이콘 오버레이
    # ==================================================
    def show_weather_icon(self, icon_name, duration_ms=10000):
        if self.current_screen != "face" or not icon_name:
            return

        icon_path = ICON_IMAGES_DIR / icon_name
        if not icon_path.exists():
            print(f"[WEATHER UI] 날씨 아이콘 없음: {icon_path}")
            return

        if self.weather_overlay_job is not None:
            self.root.after_cancel(self.weather_overlay_job)
            self.weather_overlay_job = None

        try:
            image = Image.open(icon_path).resize((72, 72))
            self.weather_overlay_image = ImageTk.PhotoImage(image)
        except Exception as e:
            print(f"[WEATHER UI ERROR] 날씨 아이콘 로드 실패: {e}")
            return

        if self.weather_overlay is None:
            self.weather_overlay = tk.Label(
                self.root,
                bg="#78CDAC",
                bd=0,
                highlightthickness=0
            )

        self.weather_overlay.config(image=self.weather_overlay_image)
        self.weather_overlay.place(x=265, y=145, width=72, height=72)
        self.weather_overlay.lift()

        self.weather_overlay_job = self.root.after(
            duration_ms,
            self.hide_weather_icon
        )

    def hide_weather_icon(self):
        if self.weather_overlay_job is not None:
            try:
                self.root.after_cancel(self.weather_overlay_job)
            except Exception:
                pass
            self.weather_overlay_job = None

        if self.weather_overlay is not None:
            self.weather_overlay.place_forget()

    def lift_weather_overlay(self):
        if self.current_screen == "face" and self.weather_overlay is not None:
            self.weather_overlay.lift()

    # ==================================================
    # 화면 전환 공통 처리
    # ==================================================
    def prepare_feature_screen(self, screen_name):
        """
        기능 화면을 표시하기 전에 얼굴 화면 위의 조작 UI를 정리한다.
        """
        self.current_screen = screen_name
        self.active_screen_name = screen_name

        self.screen_input_block = False
        self.cancel_controls_auto_hide()
        self.controls_visible = False
        self.is_function_menu_visible = False
        self.mic_button.place_forget()
        self.muted_indicator.place_forget()
        self.function_menu_panel.place_forget()
        self.hide_weather_icon()
        self.hide_feature_buttons()

        if self.active_screen is not None:
            self.active_screen.destroy()
            self.active_screen = None

    def show_face_screen(self):
        """
        현재 기능 화면을 닫고 기본 비모 얼굴 화면으로 복귀한다.
        마이크 ON/OFF UI 상태값은 그대로 유지한다.
        """
        if self.active_screen is not None:
            self.active_screen.destroy()
            self.active_screen = None

        self.current_screen = "face"
        self.active_screen_name = None
        self.screen_input_block = False
        self.controls_visible = False
        self.is_function_menu_visible = False

        self.hide_controls()
        self.set_state("idle")
        self.show_face_mic_button()

        print("[SCREEN] -> face")

    # ==================================================
    # 기능 화면 호출
    # ==================================================
    def show_camera_screen(self):
        self.prepare_feature_screen("camera")

        self.active_screen = CameraScreen(
            parent=self.root,
            on_back=lambda: self.go_back_from_feature("camera")
        )
        self.active_screen.show()

        print("[SCREEN] -> camera")

    def show_fridge_screen(self):
        self.prepare_feature_screen("fridge")

        self.active_screen = FridgeScreen(
            parent=self.root,
            on_back=lambda: self.go_back_from_feature("fridge")
        )
        self.active_screen.show()
        self.show_persistent_mic_button()
        self.narrate_screen_entry("현재 냉장고에는 이런 재료들이 있어.")

        print("[SCREEN] -> fridge")

    def show_recipe_screen(self):
        self.prepare_feature_screen("recipe")

        self.active_screen = RecipeScreen(
            parent=self.root,
            on_back=lambda: self.go_back_from_feature("recipe")
        )
        self.active_screen.show()
        self.show_persistent_mic_button()
        self.narrate_screen_entry(self.build_recipe_entry_message())

        print("[SCREEN] -> recipe")

    def show_minigame_screen(self):
        self.prepare_feature_screen("minigame")

        self.active_screen = MiniGameScreen(
            parent=self.root,
            on_back=lambda: self.go_back_from_feature("minigame")
        )
        self.active_screen.show()

        print("[SCREEN] -> minigame")

    # ==================================================
    # 프로그램 실행
    # ==================================================
    def run(self):
        self.root.mainloop()
