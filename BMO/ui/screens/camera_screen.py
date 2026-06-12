# ui/screens/camera_screen.py
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from features.camera.camera_service import (
    CameraError,
    create_camera_service,
    create_capture_path,
)
from features.camera.camera_config import (
    CAMERA_BACKEND,
    CAMERA_CAPTURE_SIZE,
    CAMERA_INDEX,
    CAMERA_PREVIEW_SIZE,
    CAPTURE_SAVE_DIR,
)
from ui.screens.common_widgets import create_back_button


class CameraScreen:
    """
    카메라 기능 화면 UI.

    - PC에서는 OpenCV 웹캠 사용
    - Raspberry Pi에서는 Picamera2 카메라 모듈 사용
    - 촬영한 사진은 파일로 저장
    - 백엔드 이미지 분석 요청은 이후 연결
    """

    PREVIEW_DELAY_MS = 80  # 약 12fps 수준의 가벼운 미리보기 갱신
    INACTIVITY_TIMEOUT_MS = 60000

    def __init__(self, parent, on_back):
        self.parent = parent
        self.on_back = on_back

        self.frame = None
        self.preview_label = None
        self.status_label = None

        self.capture_button = None
        self.retake_button = None
        self.analyze_button = None

        self.camera = None
        self.preview_job = None
        self.inactivity_job = None
        self.preview_image = None

        self.captured_path = None
        self.is_preview_running = False

    # ==================================================
    # 화면 생성 / 종료
    # ==================================================
    def show(self):
        """
        카메라 화면을 생성하고, 실제 카메라 미리보기를 시작한다.
        """
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
        self._create_preview_area()
        self._create_status_label()
        self._create_capture_button()

        self.start_camera_preview()
        self.reset_inactivity_timer()

    def destroy(self):
        """
        카메라 화면 종료 시 미리보기 반복 작업과 카메라 장치를 정리한다.
        """
        self.cancel_inactivity_timer()
        self.stop_camera_preview()

        if self.frame is not None:
            self.frame.destroy()
            self.frame = None

        self.preview_label = None
        self.status_label = None
        self.capture_button = None
        self.retake_button = None
        self.analyze_button = None
        self.preview_image = None
        self.inactivity_job = None

    def go_back(self):
        """
        돌아가기 버튼 처리.
        부모 화면으로 복귀하기 전에 카메라 자원을 먼저 정리한다.
        """
        self.cancel_inactivity_timer()
        self.stop_camera_preview()
        self.on_back()

    def reset_inactivity_timer(self):
        """
        카메라 화면에서 사용자 조작이 있을 때 자동 복귀 타이머를 1분으로 되돌린다.
        """
        self.cancel_inactivity_timer()

        if self.frame is None:
            return

        self.inactivity_job = self.parent.after(
            self.INACTIVITY_TIMEOUT_MS,
            self.auto_return_to_main
        )

    def cancel_inactivity_timer(self):
        if self.inactivity_job is None:
            return

        try:
            self.parent.after_cancel(self.inactivity_job)
        except Exception:
            pass

        self.inactivity_job = None

    def auto_return_to_main(self):
        """
        1분 동안 카메라 화면에서 조작이 없으면 메인 화면으로 복귀한다.
        """
        self.inactivity_job = None

        if self.frame is None:
            return

        print("[CAMERA UI] 1분 동안 조작이 없어 메인 화면으로 돌아갑니다.")
        self.go_back()

    # ==================================================
    # 기본 UI 구성
    # ==================================================
    def _create_title(self):
        title_label = tk.Label(
            self.frame,
            text="카메라",
            font=("맑은 고딕", 28, "bold"),
            bg="#78CDAC",
            fg="#1A274D"
        )
        title_label.pack(pady=(35, 5))

        subtitle_label = tk.Label(
            self.frame,
            text="영수증 또는 식재료 사진을 촬영해 주세요.",
            font=("맑은 고딕", 14),
            bg="#78CDAC",
            fg="#1A274D"
        )
        subtitle_label.pack()

    def _create_back_button(self):
        create_back_button(self.frame, self.go_back, y=35)

    def _create_preview_area(self):
        preview_area = tk.Frame(
            self.frame,
            bg="#D5ECFF",
            width=720,
            height=400,
            highlightbackground="#1A274D",
            highlightthickness=2
        )
        preview_area.place(x=280, y=130, width=720, height=400)

        self.preview_label = tk.Label(
            preview_area,
            text="카메라를 준비하고 있어요...",
            font=("맑은 고딕", 18, "bold"),
            bg="#D5ECFF",
            fg="#1A274D",
            justify="center"
        )
        self.preview_label.place(x=0, y=0, width=716, height=396)

    def _create_status_label(self):
        self.status_label = tk.Label(
            self.frame,
            text="",
            font=("맑은 고딕", 13),
            bg="#78CDAC",
            fg="#1A274D"
        )
        self.status_label.place(relx=0.5, y=552, anchor="center")

    def _create_capture_button(self):
        self.capture_button = tk.Button(
            self.frame,
            text="촬영하기",
            font=("맑은 고딕", 15, "bold"),
            bg="#FFE275",
            fg="#1A274D",
            activebackground="#FFF4C2",
            activeforeground="#1A274D",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.capture_photo
        )
        self.capture_button.place(x=565, y=590, width=150, height=55)

    # ==================================================
    # 카메라 실행 / 실시간 미리보기
    # ==================================================
    def start_camera_preview(self):
        """
        config.py 설정값에 맞는 카메라를 생성하고 미리보기를 시작한다.
        """
        try:
            self.stop_camera_preview()

            self.camera = create_camera_service(
                backend=CAMERA_BACKEND,
                preview_size=CAMERA_PREVIEW_SIZE,
                capture_size=CAMERA_CAPTURE_SIZE,
                camera_index=CAMERA_INDEX
            )
            self.camera.start()

            self.is_preview_running = True
            self.status_label.config(text="촬영할 대상을 화면 안에 맞춰 주세요.")

            print(f"[CAMERA UI] 미리보기 시작: backend={CAMERA_BACKEND}")

            self.update_preview_frame()

        except CameraError as error:
            self.is_preview_running = False
            self.camera = None

            self.preview_label.config(
                image="",
                text=f"카메라를 실행할 수 없습니다.\n\n{error}"
            )
            self.status_label.config(text="카메라 연결 상태를 확인해 주세요.")

            print(f"[CAMERA ERROR] {error}")

        except Exception as error:
            self.is_preview_running = False
            self.camera = None

            self.preview_label.config(
                image="",
                text=f"카메라 화면 오류가 발생했습니다.\n\n{error}"
            )
            self.status_label.config(text="오류 로그를 확인해 주세요.")

            print(f"[CAMERA ERROR] 예상하지 못한 오류: {error}")

    def update_preview_frame(self):
        """
        카메라에서 프레임을 읽어 Tkinter 미리보기 영역에 반복 출력한다.
        """
        if not self.is_preview_running or self.camera is None:
            return

        if self.frame is None or not self.frame.winfo_exists():
            return

        try:
            frame_array = self.camera.get_preview_frame()

            image = Image.fromarray(frame_array)
            image = image.resize(CAMERA_PREVIEW_SIZE)

            self.preview_image = ImageTk.PhotoImage(image)

            self.preview_label.config(
                image=self.preview_image,
                text=""
            )

            self.preview_job = self.parent.after(
                self.PREVIEW_DELAY_MS,
                self.update_preview_frame
            )

        except CameraError as error:
            self.stop_camera_preview()

            self.preview_label.config(
                image="",
                text=f"미리보기 중 오류가 발생했습니다.\n\n{error}"
            )
            self.status_label.config(text="카메라 미리보기를 다시 확인해 주세요.")

            print(f"[CAMERA ERROR] {error}")

    def stop_camera_preview(self):
        """
        Tkinter 예약 작업과 카메라 장치를 안전하게 종료한다.
        """
        self.is_preview_running = False

        if self.preview_job is not None:
            try:
                self.parent.after_cancel(self.preview_job)
            except Exception:
                pass
            self.preview_job = None

        if self.camera is not None:
            try:
                self.camera.stop()
            except Exception as error:
                print(f"[CAMERA WARN] 카메라 종료 중 경고: {error}")

            self.camera = None

    # ==================================================
    # 촬영 / 확인 / 분석 요청 UI
    # ==================================================
    def capture_photo(self):
        """
        현재 카메라 화면을 이미지 파일로 저장한다.
        촬영 후에는 실시간 미리보기를 멈추고 확인 버튼을 표시한다.
        """
        self.reset_inactivity_timer()

        if self.camera is None or not self.is_preview_running:
            self.status_label.config(text="현재 촬영 가능한 카메라가 없습니다.")
            return

        try:
            save_path = create_capture_path(
                save_dir=CAPTURE_SAVE_DIR,
                prefix="camera"
            )

            self.captured_path = self.camera.capture(save_path)

            self.stop_camera_preview()

            self.status_label.config(
                text=f"촬영 완료: {Path(self.captured_path).name}"
            )

            self.capture_button.place_forget()
            self._create_confirm_buttons()

            print(f"[CAMERA UI] 촬영 이미지 저장 완료: {self.captured_path}")

        except CameraError as error:
            self.status_label.config(text="사진 촬영에 실패했습니다.")
            print(f"[CAMERA ERROR] 촬영 실패: {error}")

    def _create_confirm_buttons(self):
        """
        촬영 후 다시 찍기와 분석 요청하기 버튼을 표시한다.
        """
        if self.retake_button is None:
            self.retake_button = tk.Button(
                self.frame,
                text="다시 찍기",
                font=("맑은 고딕", 15, "bold"),
                bg="#FDFDFD",
                fg="#1A274D",
                activebackground="#D5ECFF",
                activeforeground="#1A274D",
                relief="flat",
                bd=0,
                cursor="hand2",
                command=self.retake_photo
            )

        if self.analyze_button is None:
            self.analyze_button = tk.Button(
                self.frame,
                text="분석 요청하기",
                font=("맑은 고딕", 15, "bold"),
                bg="#FFE275",
                fg="#1A274D",
                activebackground="#FFF4C2",
                activeforeground="#1A274D",
                relief="flat",
                bd=0,
                cursor="hand2",
                command=self.request_analysis
            )

        self.retake_button.place(x=470, y=590, width=150, height=55)
        self.analyze_button.place(x=655, y=590, width=175, height=55)

    def retake_photo(self):
        """
        방금 촬영한 사진을 삭제하고 다시 실시간 미리보기를 시작한다.
        """
        self.reset_inactivity_timer()

        if self.captured_path:
            try:
                captured_file = Path(self.captured_path)

                if captured_file.exists():
                    captured_file.unlink()

                print(f"[CAMERA UI] 재촬영으로 기존 이미지 삭제: {self.captured_path}")

            except Exception as error:
                print(f"[CAMERA WARN] 기존 촬영 이미지 삭제 실패: {error}")

        self.captured_path = None

        if self.retake_button is not None:
            self.retake_button.place_forget()

        if self.analyze_button is not None:
            self.analyze_button.place_forget()

        self.capture_button.place(x=565, y=590, width=150, height=55)

        self.preview_label.config(
            image="",
            text="카메라를 다시 준비하고 있어요..."
        )

        self.start_camera_preview()

    def request_analysis(self):
        """
        촬영 이미지를 백엔드 /upload-camera 로 전송한다.
        - 영수증이면 재료를 추출해 DB에 저장
        - 일반 사진이면 설명 텍스트를 상태 라벨에 표시
        """
        self.reset_inactivity_timer()

        if not self.captured_path:
            self.status_label.config(text="먼저 사진을 촬영해 주세요.")
            return

        print("[CAMERA UI] 분석 요청 버튼 선택")
        print(f"[CAMERA UI] 백엔드 전달 예정 이미지: {self.captured_path}")

        # 버튼 비활성화 (중복 요청 방지)
        if self.analyze_button:
            self.analyze_button.config(state="disabled", text="분석 중...")
        self.status_label.config(text="이미지를 분석하고 있어요...")

        import threading
        threading.Thread(target=self._do_analysis, daemon=True).start()

    def _do_analysis(self):
        """백그라운드: 백엔드 /upload-camera 호출 → 결과 처리."""
        import os, sys
        try:
            # BackendClient import
            # camera_screen.py 위치: BMO/ui/screens/ → 두 번 올라가면 BMO/
            bmo_root = os.path.normpath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
            )
            print(f"[CAMERA DEBUG] bmo_root={bmo_root}")
            if bmo_root not in sys.path:
                sys.path.insert(0, bmo_root)
            from backend_client import BackendClient
            import requests

            client = BackendClient()

            with open(self.captured_path, "rb") as img_file:
                resp = requests.post(
                    f"{client.base_url}/upload-camera",
                    files={"file": img_file},
                    timeout=60
                )
            resp.raise_for_status()
            data = resp.json()

            image_type = data.get("type", "image")
            result_text = data.get("result", "")
            items = data.get("items", [])

            print(f"[CAMERA UI] 분석 완료: type={image_type}, items={len(items)}")

            # 영수증 → DB 재료 저장
            if image_type == "receipt" and items:
                self._save_receipt_items(items, bmo_root)

            # UI 업데이트는 메인 스레드에서
            if self.frame and self.frame.winfo_exists():
                self.frame.after(0, lambda: self._on_analysis_done(image_type, result_text, items))

        except Exception as e:
            print(f"[CAMERA ERROR] 분석 요청 실패: {e}")
            if self.frame and self.frame.winfo_exists():
                self.frame.after(0, lambda: self._on_analysis_error(str(e)))

    def _save_receipt_items(self, items: list, bmo_root: str):
        """영수증 재료 목록을 DB에 저장한다. db_bridge.save_ingredient_items() 사용."""
        import sys
        try:
            if bmo_root not in sys.path:
                sys.path.insert(0, bmo_root)
            from db_bridge import save_ingredient_items
            saved = save_ingredient_items(items)
            print(f"[CAMERA UI] 재료 {saved}개 DB 저장 완료")
        except Exception as e:
            import traceback
            print(f"[CAMERA ERROR] 재료 DB 저장 실패: {e}")
            traceback.print_exc()

    def _on_analysis_done(self, image_type: str, result_text: str, items: list):
        """메인 스레드: 분석 결과를 UI에 반영한다."""
        if self.analyze_button:
            self.analyze_button.config(state="normal", text="분석 요청하기")

        if image_type == "receipt" and items:
            names = ", ".join(
                item.get("ingredient_name") or item.get("name", "")
                for item in items
                if item.get("ingredient_name") or item.get("name")
            )
            self.status_label.config(
                text=f"영수증 인식 완료! 냉장고에 추가됨: {names}"
            )
        else:
            # 너무 길면 앞 60자만 표시
            short = result_text[:60] + ("..." if len(result_text) > 60 else "")
            self.status_label.config(text=short or "분석 완료")

    def _on_analysis_error(self, error_msg: str):
        """메인 스레드: 분석 실패 시 UI를 복구한다."""
        if self.analyze_button:
            self.analyze_button.config(state="normal", text="분석 요청하기")
        self.status_label.config(text="분석 요청 중 문제가 생겼어. 다시 시도해줘.")
        print(f"[CAMERA ERROR] {error_msg}")