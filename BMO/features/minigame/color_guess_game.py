# features/minigame/color_guess_game.py
import random
from typing import List, Optional, Tuple


RGBColor = Tuple[int, int, int]


class ColorGuessGame:
    """
    색상 맞히기 미니게임의 순수 로직 클래스.

    역할:
    - 목표 색상 생성
    - 선택 가능한 그라데이션 색상 생성
    - 정답 위치 결정
    - 점수 관리
    - 점수에 따른 난이도 조절
    - 정답/오답 판정
    - 제한 시간 동안 점수 누적

    화면 출력과 클릭 좌표 처리는 ui/screens/minigame_screen.py에서 담당한다.
    """

    def __init__(self):
        # 기존 팀원 코드의 게임 상태값을 유지한다.
        self.COLOR_CELL_SIZE = 5
        self.DIFFICULTY_OFFSET = 400
        self.COLOR_MIN_DIFF = 80

        self.score = 0
        self.game_over = False

        self.answer_color: RGBColor = (0, 0, 0)
        self.answer_index = 0
        self.start_color: RGBColor = (0, 0, 0)
        self.end_color: RGBColor = (0, 0, 0)

        self.reset_game()

    def lerp_color(
        self,
        color_start: RGBColor,
        color_end: RGBColor,
        ratio: float
    ) -> RGBColor:
        """
        두 색상 사이의 중간 색상을 계산한다.
        기존 pygame 코드의 그라데이션 생성 알고리즘을 유지한다.
        """
        return (
            int(color_start[0] + (color_end[0] - color_start[0]) * ratio),
            int(color_start[1] + (color_end[1] - color_start[1]) * ratio),
            int(color_start[2] + (color_end[2] - color_start[2]) * ratio)
        )

    def pick_random_color(self) -> RGBColor:
        """
        목표 색상을 무작위로 생성한다.
        """
        return (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        )

    def get_natural_edge_colors(
        self,
        target_color: RGBColor,
        offset: int
    ) -> Tuple[RGBColor, RGBColor]:
        """
        목표 색상을 기준으로 양 끝에 배치할 색상 두 개를 만든다.

        기존 코드와 동일하게 목표 색상과 너무 비슷한 값은 제외한다.
        """

        def clamp(value: int) -> int:
            return max(0, min(255, value))

        while True:
            start_color = tuple(
                clamp(channel + random.randint(-offset, offset))
                for channel in target_color
            )

            end_color = tuple(
                clamp(channel + random.randint(-offset, offset))
                for channel in target_color
            )

            start_difference = sum(
                abs(start_color[index] - target_color[index])
                for index in range(3)
            )

            end_difference = sum(
                abs(end_color[index] - target_color[index])
                for index in range(3)
            )

            if (
                start_difference >= self.COLOR_MIN_DIFF
                and end_difference >= self.COLOR_MIN_DIFF
            ):
                return start_color, end_color

    def update_difficulty(self):
        """
        현재 점수에 따라 색상 칸 개수와 색상 차이를 조절한다.

        기존 팀원 코드의 난이도 상승 기준을 그대로 유지한다.
        """
        if self.score >= 20:
            self.COLOR_CELL_SIZE = 20
        elif self.score >= 15:
            self.COLOR_CELL_SIZE = 13
        elif self.score >= 5:
            self.COLOR_CELL_SIZE = 8
        else:
            self.COLOR_CELL_SIZE = 5

        if self.score >= 20:
            self.DIFFICULTY_OFFSET = 80
        else:
            self.DIFFICULTY_OFFSET = 300

    def reset_game(self):
        """
        현재 점수를 유지한 채 새로운 문제를 생성한다.
        """
        self.update_difficulty()

        self.answer_color = self.pick_random_color()
        self.answer_index = random.randint(0, self.COLOR_CELL_SIZE - 1)

        self.start_color, self.end_color = self.get_natural_edge_colors(
            self.answer_color,
            self.DIFFICULTY_OFFSET
        )

        self.game_over = False

    def restart_game(self):
        """
        점수를 초기화하고 게임을 처음부터 다시 시작한다.
        """
        self.score = 0
        self.reset_game()

    def get_choice_colors(self) -> List[RGBColor]:
        """
        사용자가 선택할 수 있는 색상 칸 목록을 반환한다.

        가운데 어딘가에 정답 색상이 포함되고,
        양 끝으로 자연스럽게 이어지는 그라데이션 구조를 만든다.
        """
        choice_colors: List[RGBColor] = []

        for index in range(self.COLOR_CELL_SIZE):
            if index < self.answer_index:
                ratio = (
                    index / self.answer_index
                    if self.answer_index > 0
                    else 0
                )

                draw_color = self.lerp_color(
                    self.start_color,
                    self.answer_color,
                    ratio
                )

            elif index == self.answer_index:
                draw_color = self.answer_color

            else:
                total_right_steps = (
                    self.COLOR_CELL_SIZE - 1
                ) - self.answer_index

                current_step = index - self.answer_index

                ratio = (
                    current_step / total_right_steps
                    if total_right_steps > 0
                    else 0
                )

                draw_color = self.lerp_color(
                    self.answer_color,
                    self.end_color,
                    ratio
                )

            choice_colors.append(draw_color)

        return choice_colors

    def select_color(self, selected_index: int) -> Optional[bool]:
        """
        사용자가 선택한 칸이 정답인지 판정한다.

        반환값:
        - True: 정답
        - False: 오답
        - None: 이미 게임 종료 상태이거나 잘못된 선택
        """
        if self.game_over:
            return None

        if not 0 <= selected_index < self.COLOR_CELL_SIZE:
            return None

        if selected_index == self.answer_index:
            self.score += 1
            self.reset_game()
            return True

        self.reset_game()
        return False
