# ui/screens/recipe_screen.py
import threading
import tkinter as tk

from features.recipe.recipe_service import RecipeService
from ui.screens.common_widgets import create_back_button
from ui.screens.loading_screen import RecipeLoadingScreen


class RecipeScreen:
    """
    추천 레시피 목록과 상세 팝업 화면 UI.

    - 목록: RecipeService.get_recommended_recipes() — 백엔드 Gemini 추천
    - 조리순서: RecipeService.get_recipe_steps() — 백엔드 Gemini 생성
    UI는 화면 구성과 버튼 이벤트만 담당한다.
    """

    def __init__(self, parent, on_back, recipe_service=None):
        self.parent = parent
        self.on_back = on_back
        self.recipe_service = recipe_service or RecipeService()

        self.frame = None
        self.popup_overlay = None
        self.loading_screen = None
        self.recipes = []
        self.mock_recipes = self.recipes
        self._direct_entry = False  # 선택 레시피로 바로 진입했는지 여부

    def show(self):
        self.frame = tk.Frame(
            self.parent,
            bg="#78CDAC",
            width=1280,
            height=720
        )
        self.frame.place(x=0, y=0, width=1280, height=720)
        self.frame.lift()

        self._create_back_button()

        # 선택한 레시피가 있으면 바로 조리 화면으로
        from features.recipe.recipe_service import load_selected_recipe
        selected = load_selected_recipe()
        if selected:
            self._direct_entry = True
            self.frame.after(0, lambda: self._open_cooking_popup_from_cache(selected))
        else:
            self._direct_entry = False
            self._show_loading()
            threading.Thread(target=self._load_recipes, daemon=True).start()

    def _show_loading(self):
        if self.frame is None:
            return
        self.loading_screen = RecipeLoadingScreen(self.frame)
        self.loading_screen.show()
        create_back_button(self.loading_screen.frame, self.on_back)

    def _load_recipes(self):
        from features.recipe.recipe_service import load_cached_recipes
        cached = load_cached_recipes()
        if cached:
            self.recipes = cached
        else:
            self.recipes = self.recipe_service.get_recommended_recipes()
        self.mock_recipes = self.recipes
        if self.frame is not None:
            self.frame.after(0, self._on_loaded)

    def _on_loaded(self):
        if self.frame is None:
            return
        if self.loading_screen is not None:
            self.loading_screen.destroy()
            self.loading_screen = None
        self._create_title()
        self._create_recipe_list()
        self._create_bottom_note()

    def destroy(self):
        self._close_recipe_popup()
        if self.loading_screen is not None:
            self.loading_screen.destroy()
            self.loading_screen = None
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None

    def _create_title(self):
        tk.Label(
            self.frame,
            text="추천 레시피",
            font=("맑은 고딕", 28, "bold"),
            bg="#78CDAC",
            fg="#1A274D"
        ).pack(pady=(42, 8))

        if self.recipes:
            subtitle = f"지금 만들 수 있는 레시피 {len(self.recipes)}개"
        else:
            subtitle = "추천 레시피를 불러오지 못했어요"

        tk.Label(
            self.frame,
            text=subtitle,
            font=("맑은 고딕", 14),
            bg="#78CDAC",
            fg="#1A274D"
        ).pack()

    def _create_back_button(self):
        create_back_button(self.frame, self.on_back)

    def _create_recipe_list(self):
        list_area = tk.Frame(self.frame, bg="#78CDAC")
        list_area.place(x=295, y=178, width=690, height=405)

        if not self.recipes:
            tk.Label(
                list_area,
                text="냉장고 재료를 등록하거나 잠시 후 다시 시도해 주세요.",
                font=("맑은 고딕", 14),
                bg="#78CDAC",
                fg="#1A274D"
            ).pack(pady=120)
            return

        for index, recipe in enumerate(self.recipes, start=1):
            self._create_recipe_button(list_area, index, recipe)

    def _create_recipe_button(self, parent, number, recipe):
        button_frame = tk.Frame(
            parent,
            bg="#FDFDFD",
            highlightbackground="#D5ECFF",
            highlightthickness=2,
            cursor="hand2"
        )
        button_frame.pack(fill="x", pady=(0, 18))
        button_frame.configure(height=112)
        button_frame.pack_propagate(False)

        number_label = tk.Label(
            button_frame,
            text=str(number),
            font=("맑은 고딕", 20, "bold"),
            bg="#78CDAC",
            fg="#FDFDFD",
            width=3,
            height=1
        )
        number_label.place(x=30, y=31, width=54, height=50)

        recipe_name_label = tk.Label(
            button_frame,
            text=recipe["recipe_name"],
            font=("맑은 고딕", 20, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        )
        recipe_name_label.place(x=115, y=22, width=415, height=38)

        recipe_info_label = tk.Label(
            button_frame,
            text=f"조리 시간 {recipe['cook_time']}  /  난이도 {recipe['difficulty']}",
            font=("맑은 고딕", 12),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        )
        recipe_info_label.place(x=117, y=66, width=400, height=25)

        arrow_label = tk.Label(
            button_frame,
            text=">",
            font=("맑은 고딕", 34, "bold"),
            bg="#FDFDFD",
            fg="#1A274D"
        )
        arrow_label.place(x=615, y=29, width=38, height=48)

        for widget in [button_frame, number_label, recipe_name_label,
                       recipe_info_label, arrow_label]:
            widget.bind(
                "<Button-1>",
                lambda event, r=recipe: self._open_recipe_popup(r)
            )

    def _create_bottom_note(self):
        tk.Label(
            self.frame,
            text="레시피를 선택하면 필요한 재료와 조리 순서를 확인할 수 있어요.",
            font=("맑은 고딕", 13),
            bg="#78CDAC",
            fg="#1A274D"
        ).place(relx=0.5, y=628, anchor="center")

    # ──────────────────────────────────────────────────────────────────
    #  첫 번째 팝업: 재료 확인 + 선택하기
    # ──────────────────────────────────────────────────────────────────

    def _open_recipe_popup(self, recipe):
        selected = self.recipe_service.select_recipe(recipe)
        if selected is None:
            return

        self._close_recipe_popup()

        self.popup_overlay = tk.Frame(
            self.frame,
            bg="#63B497",
            width=1280,
            height=720
        )
        self.popup_overlay.place(x=0, y=0, width=1280, height=720)
        self.popup_overlay.lift()

        popup_card = tk.Frame(
            self.popup_overlay,
            bg="#FDFDFD",
            highlightbackground="#1A274D",
            highlightthickness=2
        )
        popup_card.place(x=210, y=68, width=860, height=530)

        self._create_popup_header(popup_card, selected)
        self._create_popup_summary(popup_card, selected)
        self._create_popup_body(popup_card, selected)
        self._create_popup_select_button(popup_card, selected)

    def _create_popup_header(self, parent, recipe):
        tk.Label(
            parent,
            text=recipe["recipe_name"],
            font=("맑은 고딕", 25, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=38, y=26, width=640, height=42)

        tk.Button(
            parent,
            text="×",
            font=("맑은 고딕", 22, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            activebackground="#D5ECFF",
            activeforeground="#1A274D",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._close_recipe_popup
        ).place(x=785, y=20, width=42, height=42)

    def _create_popup_summary(self, parent, recipe):
        tk.Label(
            parent,
            text=recipe.get("description", ""),
            font=("맑은 고딕", 13),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="nw",
            justify="left",
            wraplength=760
        ).place(x=42, y=75, width=760, height=60)

    def _create_popup_body(self, parent, recipe):
        """재료 박스(560px) + 오른쪽 조리시간/난이도 뱃지."""
        ingredient_frame = tk.Frame(
            parent,
            bg="#FDFDFD",
            highlightbackground="#D5ECFF",
            highlightthickness=2
        )
        ingredient_frame.place(x=42, y=155, width=560, height=280)

        tk.Label(
            ingredient_frame,
            text="재료",
            font=("맑은 고딕", 16, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=18, y=15, width=150, height=30)

        tk.Label(
            ingredient_frame,
            text="사용 가능 재료",
            font=("맑은 고딕", 12, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=18, y=60, width=200, height=25)

        available_text = (
            ", ".join(recipe.get("available_ingredients", []))
            or "없음"
        )
        tk.Label(
            ingredient_frame,
            text=available_text,
            font=("맑은 고딕", 12),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="nw",
            justify="left",
            wraplength=510
        ).place(x=18, y=90, width=510, height=60)

        tk.Label(
            ingredient_frame,
            text="부족한 재료",
            font=("맑은 고딕", 12, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=18, y=165, width=200, height=25)

        missing_text = (
            ", ".join(recipe.get("missing_ingredients", []))
            or "없음"
        )
        tk.Label(
            ingredient_frame,
            text=missing_text,
            font=("맑은 고딕", 12),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="nw",
            justify="left",
            wraplength=510
        ).place(x=18, y=195, width=510, height=60)

        # 오른쪽 뱃지
        info_x = 630
        tk.Label(
            parent,
            text="조리 시간",
            font=("맑은 고딕", 12, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=info_x, y=155, width=190, height=28)

        tk.Label(
            parent,
            text=recipe.get("cook_time", "-"),
            font=("맑은 고딕", 14),
            bg="#D5ECFF",
            fg="#1A274D"
        ).place(x=info_x, y=188, width=190, height=44)

        tk.Label(
            parent,
            text="난이도",
            font=("맑은 고딕", 12, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=info_x, y=250, width=190, height=28)

        tk.Label(
            parent,
            text=recipe.get("difficulty", "-"),
            font=("맑은 고딕", 14),
            bg="#FFF4C2",
            fg="#1A274D"
        ).place(x=info_x, y=283, width=190, height=44)

    def _create_popup_select_button(self, parent, recipe):
        tk.Button(
            parent,
            text="선택하기",
            font=("맑은 고딕", 15, "bold"),
            bg="#FFE275",
            fg="#1A274D",
            activebackground="#FFF4C2",
            activeforeground="#1A274D",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self._open_cooking_popup(recipe)
        ).place(x=324, y=450, width=212, height=58)

    def _close_recipe_popup(self):
        if self.popup_overlay is not None:
            self.popup_overlay.destroy()
            self.popup_overlay = None

    def _close_recipe_popup_silent(self):
        """팝업만 닫고 on_back은 호출하지 않는다."""
        if self.popup_overlay is not None:
            self.popup_overlay.destroy()
            self.popup_overlay = None

    # ──────────────────────────────────────────────────────────────────
    #  두 번째 팝업: 조리 순서 (백엔드에서 Gemini로 실시간 생성)
    # ──────────────────────────────────────────────────────────────────

    def _open_cooking_popup_from_cache(self, recipe):
        """레시피 버튼 재진입 시: 저장은 이미 완료됐으므로 팝업만 띄운다."""
        self._open_cooking_popup(recipe, skip_save=True)

    def _open_cooking_popup(self, recipe, skip_save=False):
        """선택하기 클릭 → 조리 순서 팝업 (로딩 상태로 시작, 백그라운드 요청)."""
        # 선택한 레시피 DB 저장 + 영양소 저장 (백그라운드) — 캐시 재진입 시 생략
        import threading as _t
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        if not skip_save:
            def _save():
                try:
                    import sys as _sys, os as _os
                    _bmo_root = _os.path.normpath(
                        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..")
                    )
                    if _bmo_root not in _sys.path:
                        _sys.path.insert(0, _bmo_root)
                    from db_bridge import save_consumed_recipe, add_daily_nutrition, deduct_recipe_ingredients
                    from features.recipe.recipe_service import save_selected_recipe
                    recipe_name = recipe.get("recipe_name", "")

                    # 선택한 레시피 저장 (레시피 버튼 재진입 시 재사용)
                    save_selected_recipe(recipe)

                    # 사용한 재료 Inventory에서 차감
                    available = recipe.get("available_ingredients", [])
                    if available:
                        deducted = deduct_recipe_ingredients(available)
                        print(f"[RECIPE SCREEN] 재료 차감 완료: {deducted}개 ({available})")
                    else:
                        print(f"[RECIPE SCREEN] 차감할 재료 없음 (available_ingredients 비어있음)")

                    # ConsumedRecipe DB 저장 + 영양소 조회 후 저장 (backend_client 사용)
                    try:
                        from backend_client import BackendClient
                        client = BackendClient()
                        nutrition_resp = client.get_nutrition(recipe_name)
                        nutrition = nutrition_resp if (nutrition_resp and nutrition_resp.get("calories", 0) > 0) else None

                        save_consumed_recipe(recipe_name, nutrition)

                        if nutrition:
                            add_daily_nutrition(nutrition)
                            print(f"[RECIPE SCREEN] 영양소 저장 완료: {recipe_name}")
                        else:
                            print(f"[RECIPE SCREEN] 영양소 정보 없음 또는 0kcal: {recipe_name}")
                    except Exception as e:
                        print(f"[RECIPE SCREEN] 영양소 저장 실패: {e}")
                        save_consumed_recipe(recipe_name)
                except Exception as e:
                    print(f"[RECIPE SCREEN] 저장 실패: {e}")
            _t.Thread(target=_save, daemon=True).start()

        self._close_recipe_popup()

        self.popup_overlay = tk.Frame(
            self.frame,
            bg="#63B497",
            width=1280,
            height=720
        )
        self.popup_overlay.place(x=0, y=0, width=1280, height=720)
        self.popup_overlay.lift()

        popup_card = tk.Frame(
            self.popup_overlay,
            bg="#FDFDFD",
            highlightbackground="#1A274D",
            highlightthickness=2
        )
        popup_card.place(x=210, y=68, width=860, height=580)

        # 헤더
        tk.Label(
            popup_card,
            text=recipe["recipe_name"],
            font=("맑은 고딕", 25, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=38, y=26, width=680, height=42)

        # X 버튼: direct_entry면 메인화면으로, 아니면 목록으로
        def _on_cooking_popup_close():
            self._close_recipe_popup_silent()
            if self._direct_entry:
                self._direct_entry = False
                self.on_back()
            else:
                # 목록 화면으로 돌아감 (이미 frame이 떠 있음)
                pass

        tk.Button(
            popup_card,
            text="×",
            font=("맑은 고딕", 22, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            activebackground="#D5ECFF",
            activeforeground="#1A274D",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=_on_cooking_popup_close
        ).place(x=785, y=20, width=42, height=42)

        # 설명
        tk.Label(
            popup_card,
            text=recipe.get("description", ""),
            font=("맑은 고딕", 13),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="nw",
            justify="left",
            wraplength=760
        ).place(x=42, y=75, width=760, height=50)

        # 요리 시간
        tk.Label(
            popup_card,
            text="요리 시간:",
            font=("맑은 고딕", 13, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=42, y=138, width=80, height=26)

        tk.Label(
            popup_card,
            text=recipe.get("cook_time", "-"),
            font=("맑은 고딕", 13),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=125, y=138, width=600, height=26)

        # 재료 한 줄 요약
        tk.Label(
            popup_card,
            text="재료:",
            font=("맑은 고딕", 13, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=42, y=172, width=50, height=26)

        all_ingr = (
            recipe.get("available_ingredients", []) +
            recipe.get("missing_ingredients", [])
        )
        tk.Label(
            popup_card,
            text=", ".join(all_ingr) if all_ingr else "-",
            font=("맑은 고딕", 13),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="nw",
            justify="left",
            wraplength=680
        ).place(x=96, y=172, width=680, height=26)

        # 조리 순서 제목
        tk.Label(
            popup_card,
            text="조리 순서",
            font=("맑은 고딕", 14, "bold"),
            bg="#FDFDFD",
            fg="#1A274D",
            anchor="w"
        ).place(x=42, y=210, width=760, height=30)

        # 조리 순서 텍스트 박스
        steps_text = tk.Text(
            popup_card,
            font=("맑은 고딕", 12),
            bg="#FDFDFD",
            fg="#1A274D",
            relief="solid",
            bd=1,
            wrap="word",
            state="normal",
            highlightbackground="#D5ECFF",
            highlightthickness=1
        )
        steps_scrollbar = tk.Scrollbar(
            popup_card,
            orient="vertical",
            command=steps_text.yview
        )
        steps_text.configure(yscrollcommand=steps_scrollbar.set)
        steps_text.place(x=42, y=248, width=756, height=290)
        steps_scrollbar.place(x=798, y=248, width=18, height=290)
        steps_text.bind(
            "<MouseWheel>",
            lambda e: steps_text.yview_scroll(int(-1 * (e.delta / 120)), "units")
        )

        # 로딩 메시지 표시
        steps_text.insert("1.0", "Gemini가 조리 순서를 생성 중이에요...\n잠시만 기다려 주세요.")
        steps_text.configure(state="disabled")

        # 레퍼런스 저장 (업데이트용)
        self._steps_text_widget = steps_text

        print(self.recipe_service.build_selected_recipe_log(recipe))

        # 백그라운드에서 백엔드 호출
        threading.Thread(
            target=self._fetch_and_update_steps,
            args=(recipe,),
            daemon=True
        ).start()

    def _fetch_and_update_steps(self, recipe):
        """백그라운드: 이미 받은 steps 사용, 없으면 /select-recipe 호출."""
        import re as _re
        steps = recipe.get("steps", [])
        raw_text = ""
        if not steps:
            steps, raw_text = self.recipe_service.get_recipe_steps(
                recipe["recipe_name"]
            )
        # 번호를 1. 2. 3. ... 으로 재정렬 (예: "3-1. ..." -> "1. ...")
        renumbered = []
        for i, step in enumerate(steps, start=1):
            clean = _re.sub(r"^\d+[-]?\d*[.)]\s*", "", step).strip()
            renumbered.append(f"{i}. {clean}")
        if self.frame:
            self.frame.after(0, lambda: self._update_steps_widget(renumbered, raw_text))

    def _update_steps_widget(self, steps: list, raw_text: str):
        """메인 스레드: 조리 순서 텍스트 박스를 실제 내용으로 교체."""
        widget = getattr(self, "_steps_text_widget", None)
        if widget is None:
            return
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return

        if steps:
            content = "\n\n".join(steps)
        elif raw_text:
            content = raw_text
        else:
            content = "조리 순서 정보를 가져오지 못했어요."

        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.configure(state="disabled")

    def mock_recipe_speak(self, recipe):
        print(self.recipe_service.build_selected_recipe_log(recipe))
