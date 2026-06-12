# ui/screens/minigame_screen.py
import tkinter as tk

from features.minigame.color_guess_game import ColorGuessGame, RGBColor
from ui.screens.common_widgets import create_back_button


class MiniGameScreen:
    """
    BMO 화면 내부에서 실행되는 색상 맞히기 미니게임 UI.

    게임 규칙과 상태 계산은 ColorGuessGame이 담당하고,
    이 클래스는 Tkinter 화면 출력과 사용자 입력 연결만 담당한다.
    """

    BACKGROUND_COLOR = "#78CDAC"
    NAVY_COLOR = "#1A274D"
    SOFT_BLUE_COLOR = "#D5ECFF"
    YELLOW_COLOR = "#FFE275"
    LIGHT_YELLOW_COLOR = "#FFF4C2"
    WHITE_COLOR = "#FDFDFD"
    GAME_OVER_COLOR = "#F6C6C6"
    WARNING_RED_COLOR = "#D62828"

    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 720
    GAME_TIME_LIMIT_SECONDS = 60
    TIMER_WARNING_SECONDS = 10

    def __init__(self, parent, on_back):
        self.parent = parent
        self.on_back = on_back

        self.frame = None
        self.content_frame = None
        self.canvas = None
        self.timer_text_id = None
        self.remaining_seconds = self.GAME_TIME_LIMIT_SECONDS
        self.timer_job = None
        self.game_over_reason = None

        self.game = ColorGuessGame()

    def show(self):
        """
        미니게임 첫 화면을 생성하고 표시한다.
        """
        if self.frame is not None:
            self.destroy()

        self.frame = tk.Frame(
            self.parent,
            bg=self.BACKGROUND_COLOR,
            width=self.WINDOW_WIDTH,
            height=self.WINDOW_HEIGHT
        )

        self.frame.place(
            x=0,
            y=0,
            width=self.WINDOW_WIDTH,
            height=self.WINDOW_HEIGHT
        )
        self.frame.lift()

        self._create_title()
        self._create_back_button()
        self._create_content_frame()
        self._show_intro_screen()

        print("[GAME UI] 미니게임 화면을 열었어.")

    def destroy(self):
        """
        미니게임 화면을 종료한다.

        별도의 반복 작업이나 프로세스를 만들지 않으므로,
        현재 프레임만 안전하게 제거하면 된다.
        """
        self._cancel_timer()

        if self.frame is not None:
            self.frame.destroy()
            self.frame = None
            self.content_frame = None
            self.canvas = None
            self.timer_text_id = None

        print("[GAME UI] 미니게임 화면을 닫았어.")

    def _create_title(self):
        """
        화면 상단 제목 영역을 만든다.
        """
        title_label = tk.Label(
            self.frame,
            text="색상 맞히기",
            font=("맑은 고딕", 28, "bold"),
            bg=self.BACKGROUND_COLOR,
            fg=self.NAVY_COLOR
        )
        title_label.pack(pady=(38, 4))

        subtitle_label = tk.Label(
            self.frame,
            text="같은 색의 칸을 빠르게 찾아봐!",
            font=("맑은 고딕", 14),
            bg=self.BACKGROUND_COLOR,
            fg=self.NAVY_COLOR
        )
        subtitle_label.pack()

    def _create_back_button(self):
        """
        기존 비모 화면으로 돌아가는 버튼을 만든다.
        """
        create_back_button(self.frame, self.on_back)

    def _create_content_frame(self):
        """
        시작 화면, 게임 화면, 게임 종료 화면이 표시될 본문 영역을 만든다.
        """
        self.content_frame = tk.Frame(
            self.frame,
            bg=self.BACKGROUND_COLOR,
            width=1160,
            height=560
        )
        self.content_frame.place(x=60, y=130, width=1160, height=560)

    def _clear_content(self):
        """
        본문 영역의 기존 위젯을 모두 제거한다.
        """
        if self.content_frame is None:
            return

        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.canvas = None
        self.timer_text_id = None

    def _show_intro_screen(self):
        """
        게임 시작 전 안내 화면을 표시한다.
        """
        self._cancel_timer()
        self._clear_content()

        preview_card = tk.Frame(
            self.content_frame,
            bg=self.WHITE_COLOR,
            highlightbackground=self.SOFT_BLUE_COLOR,
            highlightthickness=2
        )
        preview_card.place(x=295, y=28, width=570, height=390)

        preview_title = tk.Label(
            preview_card,
            text="위에 표시된 색과 같은 칸을 찾아봐!",
            font=("맑은 고딕", 15, "bold"),
            bg=self.WHITE_COLOR,
            fg=self.NAVY_COLOR
        )
        preview_title.place(x=0, y=22, width=570, height=30)

        target_preview = tk.Frame(
            preview_card,
            bg="#FFE275",
            highlightbackground=self.NAVY_COLOR,
            highlightthickness=3
        )
        target_preview.place(x=215, y=66, width=140, height=126)

        choice_guide = tk.Label(
            preview_card,
            text="아래 색상 중 하나를 선택",
            font=("맑은 고딕", 13, "bold"),
            bg=self.WHITE_COLOR,
            fg=self.NAVY_COLOR
        )
        choice_guide.place(x=0, y=212, width=570, height=28)

        preview_colors = [
            "#B8E986",
            "#55CFA8",
            "#7DD3C7",
            "#FFE275",
            "#39B8B0"
        ]

        for index, color in enumerate(preview_colors):
            color_cell = tk.Frame(
                preview_card,
                bg=color,
                highlightbackground=self.NAVY_COLOR if color == "#FFE275" else "#D5ECFF",
                highlightthickness=2
            )
            color_cell.place(
                x=40 + (index * 100),
                y=264,
                width=82,
                height=72
            )

        guide_label = tk.Label(
            self.content_frame,
            text="목표 색상과 같은 칸을 누르면 점수를 얻어요!",
            font=("맑은 고딕", 17, "bold"),
            bg=self.BACKGROUND_COLOR,
            fg=self.NAVY_COLOR
        )
        guide_label.place(x=0, y=432, width=1160, height=32)

        sub_guide_label = tk.Label(
            self.content_frame,
            text="60초 동안 최대한 많은 점수에 도전해봐!",
            font=("맑은 고딕", 13),
            bg=self.BACKGROUND_COLOR,
            fg=self.NAVY_COLOR,
            anchor="center"
        )
        sub_guide_label.place(x=0, y=464, width=1160, height=24)

        start_button = tk.Button(
            self.content_frame,
            text="게임 시작",
            font=("맑은 고딕", 18, "bold"),
            bg=self.YELLOW_COLOR,
            fg=self.NAVY_COLOR,
            activebackground=self.LIGHT_YELLOW_COLOR,
            activeforeground=self.NAVY_COLOR,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.start_game
        )
        start_button.place(x=480, y=506, width=200, height=64)

    def start_game(self):
        """
        점수를 초기화하고 새 게임을 시작한다.
        """
        self._cancel_timer()
        self.remaining_seconds = self.GAME_TIME_LIMIT_SECONDS
        self.game_over_reason = None
        self.game.restart_game()
        self._render_game()
        self._schedule_timer_tick()

        print("[GAME] 색상 맞히기 게임을 시작")

    def _render_game(self):
        """
        현재 게임 상태를 기반으로 목표 색상과 선택 칸들을 표시한다.
        """
        self._clear_content()

        self.canvas = tk.Canvas(
            self.content_frame,
            width=1160,
            height=550,
            bg=self.BACKGROUND_COLOR,
            highlightthickness=0
        )
        self.canvas.place(x=0, y=0, width=1160, height=550)

        self._draw_score()
        self._draw_target_color()
        self._draw_choice_colors()

    def _draw_score(self):
        """
        현재 점수를 화면에 표시한다.
        """
        if self.canvas is None:
            return

        self.canvas.create_text(
            1080,
            30,
            text=f"점수: {self.game.score}",
            font=("맑은 고딕", 18, "bold"),
            fill=self.NAVY_COLOR,
            anchor="e"
        )

        self.timer_text_id = self.canvas.create_text(
            80,
            30,
            text=self._format_timer_text(),
            font=("맑은 고딕", 18, "bold"),
            fill=self._get_timer_color(),
            anchor="w"
        )

    def _format_timer_text(self):
        return f"남은 시간: {self.remaining_seconds}초"

    def _get_timer_color(self):
        if self.remaining_seconds <= self.TIMER_WARNING_SECONDS:
            return self.WARNING_RED_COLOR

        return self.NAVY_COLOR

    def _schedule_timer_tick(self):
        if self.timer_job is not None or self.frame is None:
            return

        self.timer_job = self.frame.after(1000, self._tick_timer)

    def _cancel_timer(self):
        if self.timer_job is None:
            return

        try:
            if self.frame is not None:
                self.frame.after_cancel(self.timer_job)
        except tk.TclError:
            pass

        self.timer_job = None

    def _tick_timer(self):
        self.timer_job = None

        if self.frame is None or self.game.game_over:
            return

        self.remaining_seconds -= 1
        self._update_timer_display()

        if self.remaining_seconds <= 0:
            self.remaining_seconds = 0
            self.game.game_over = True
            self.game_over_reason = "timeout"
            print(f"[GAME] 시간 초과. 최종 점수: {self.game.score}")
            self._show_game_over_screen()
            return

        self._schedule_timer_tick()

    def _update_timer_display(self):
        if self.canvas is None or self.timer_text_id is None:
            return

        self.canvas.itemconfigure(
            self.timer_text_id,
            text=self._format_timer_text(),
            fill=self._get_timer_color()
        )

    def _draw_target_color(self):
        """
        사용자가 맞혀야 하는 목표 색상 사각형을 표시한다.
        """
        if self.canvas is None:
            return

        target_hex = self._rgb_to_hex(self.game.answer_color)

        self.canvas.create_text(
            580,
            28,
            text="해당 색과 같은 칸을 찾는 게임입니다!",
            font=("맑은 고딕", 17, "bold"),
            fill=self.NAVY_COLOR
        )

        target_left = 465
        target_top = 68
        target_right = 695
        target_bottom = 270

        self.canvas.create_rectangle(
            target_left,
            target_top,
            target_right,
            target_bottom,
            fill=target_hex,
            outline=self.NAVY_COLOR,
            width=3
        )

    def _draw_choice_colors(self):
        """
        클릭 가능한 색상 선택 칸들을 화면 아래쪽에 표시한다.
        """
        if self.canvas is None:
            return

        choice_colors = self.game.get_choice_colors()

        area_left = 35
        area_right = 1125
        area_top = 350
        area_bottom = 505

        total_width = area_right - area_left
        cell_width = total_width / len(choice_colors)

        self.canvas.create_text(
            580,
            322,
            text="아래 색상 중 하나를 선택",
            font=("맑은 고딕", 15, "bold"),
            fill=self.NAVY_COLOR
        )

        for index, color in enumerate(choice_colors):
            left = area_left + (cell_width * index)
            right = area_left + (cell_width * (index + 1))
            color_hex = self._rgb_to_hex(color)

            tag_name = f"choice_{index}"

            self.canvas.create_rectangle(
                left,
                area_top,
                right,
                area_bottom,
                fill=color_hex,
                outline=self.NAVY_COLOR,
                width=2,
                tags=(tag_name,)
            )

            self.canvas.tag_bind(
                tag_name,
                "<Button-1>",
                lambda event, selected_index=index: self._select_color(
                    selected_index
                )
            )

            self.canvas.tag_bind(
                tag_name,
                "<Enter>",
                lambda event: self.canvas.config(cursor="hand2")
            )

            self.canvas.tag_bind(
                tag_name,
                "<Leave>",
                lambda event: self.canvas.config(cursor="")
            )

    def _select_color(self, selected_index: int):
        """
        선택된 색상 칸을 게임 로직에 전달하고 결과에 따라 화면을 갱신한다.
        """
        result = self.game.select_color(selected_index)

        if result is True:
            print(f"[GAME] 정답이야. 현재 점수: {self.game.score}")
            self._render_game()
            return

        if result is False:
            print(f"[GAME] 오답이야. 현재 점수: {self.game.score}")
            self._render_game()

    def _show_game_over_screen(self):
        """
        제한 시간이 끝난 뒤 게임 종료 화면을 표시한다.
        """
        self._cancel_timer()
        self._clear_content()

        game_over_panel = tk.Frame(
            self.content_frame,
            bg=self.GAME_OVER_COLOR,
            highlightbackground=self.NAVY_COLOR,
            highlightthickness=2
        )
        game_over_panel.place(x=245, y=55, width=670, height=330)

        game_over_title = tk.Label(
            game_over_panel,
            text="TIME OUT!",
            font=("맑은 고딕", 34, "bold"),
            bg=self.GAME_OVER_COLOR,
            fg=self.WARNING_RED_COLOR
        )
        game_over_title.pack(pady=(68, 16))

        score_label = tk.Label(
            game_over_panel,
            text=f"최종 점수: {self.game.score}",
            font=("맑은 고딕", 22, "bold"),
            bg=self.GAME_OVER_COLOR,
            fg=self.NAVY_COLOR
        )
        score_label.pack()

        restart_button = tk.Button(
            self.content_frame,
            text="다시 시작",
            font=("맑은 고딕", 16, "bold"),
            bg=self.YELLOW_COLOR,
            fg=self.NAVY_COLOR,
            activebackground=self.LIGHT_YELLOW_COLOR,
            activeforeground=self.NAVY_COLOR,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.start_game
        )
        restart_button.place(x=405, y=445, width=160, height=58)

        create_back_button(
            self.content_frame,
            self.on_back,
            x=595,
            y=445,
            width=160,
            height=58
        )

    def _rgb_to_hex(self, color: RGBColor) -> str:
        """
        RGB 튜플 값을 Tkinter가 사용할 수 있는 HEX 문자열로 변환한다.
        """
        return "#{:02x}{:02x}{:02x}".format(
            color[0],
            color[1],
            color[2]
        )
