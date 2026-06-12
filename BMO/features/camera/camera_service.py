# camera/camera_service.py
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import importlib.util
import os
import platform


class CameraError(RuntimeError):
    """카메라 시작, 미리보기 또는 촬영 과정에서 발생하는 오류."""
    pass


def is_raspberry_pi() -> bool:
    """
    현재 실행 환경이 Raspberry Pi인지 확인한다.

    PC 개발 환경에서는 False가 되고,
    Raspberry Pi OS에서는 /proc/device-tree/model 정보를 통해 확인한다.
    """
    model_path = "/proc/device-tree/model"

    if not os.path.exists(model_path):
        return False

    try:
        with open(model_path, "r", encoding="utf-8") as file:
            model_name = file.read()
        return "Raspberry Pi" in model_name
    except Exception:
        return False


def create_capture_path(
    save_dir: str = "captured_images",
    prefix: str = "capture"
) -> str:
    """
    촬영 이미지가 저장될 경로를 생성한다.

    예:
    captured_images/receipt_20260522_214530.jpg
    """
    directory = Path(save_dir)
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.jpg"

    return str(directory / filename)


class BaseCamera(ABC):
    """
    CameraScreen이 PC 웹캠인지 Raspberry Pi 카메라인지
    신경 쓰지 않고 동일한 방식으로 사용하기 위한 공통 인터페이스.
    """

    def __init__(
        self,
        preview_size: tuple[int, int] = (720, 400),
        capture_size: tuple[int, int] = (1920, 1080),
        camera_index: int = 0
    ):
        self.preview_size = preview_size
        self.capture_size = capture_size
        self.camera_index = camera_index
        self.started = False

    @abstractmethod
    def start(self) -> None:
        """카메라 장치를 시작한다."""
        raise NotImplementedError

    @abstractmethod
    def get_preview_frame(self):
        """
        GUI 미리보기용 RGB 이미지 배열을 반환한다.
        반환 형식은 Pillow Image.fromarray()에 전달할 수 있는 numpy 배열이다.
        """
        raise NotImplementedError

    @abstractmethod
    def capture(self, save_path: str) -> str:
        """현재 장면을 이미지 파일로 저장하고 저장 경로를 반환한다."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """카메라 장치와 자원을 정리한다."""
        raise NotImplementedError


class OpenCVCamera(BaseCamera):
    """
    PC 내장 웹캠 또는 USB 웹캠용 카메라 처리 클래스.

    Windows PC에서 VS Code로 개발할 때 기본적으로 이 클래스를 사용한다.
    """

    def __init__(
        self,
        preview_size: tuple[int, int] = (720, 400),
        capture_size: tuple[int, int] = (1920, 1080),
        camera_index: int = 0
    ):
        super().__init__(preview_size, capture_size, camera_index)
        self.cv2 = None
        self.capture_device = None
        self.last_full_frame = None

    def start(self) -> None:
        try:
            import cv2
        except ImportError as error:
            raise CameraError(
                "OpenCV가 설치되어 있지 않습니다. "
                "PC에서 `pip install opencv-python`을 실행해 주세요."
            ) from error

        self.cv2 = cv2

        # Windows에서는 DirectShow를 우선 사용하면 웹캠 시작 지연이 줄어드는 경우가 있다.
        if platform.system() == "Windows":
            self.capture_device = cv2.VideoCapture(
                self.camera_index,
                cv2.CAP_DSHOW
            )
        else:
            self.capture_device = cv2.VideoCapture(self.camera_index)

        if not self.capture_device.isOpened():
            self.capture_device.release()
            self.capture_device = None
            raise CameraError(
                f"웹캠을 열 수 없습니다. camera_index={self.camera_index}"
            )

        # 저장용 프레임은 OCR 분석을 고려해 비교적 높은 해상도로 요청한다.
        self.capture_device.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            self.capture_size[0]
        )
        self.capture_device.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            self.capture_size[1]
        )

        self.started = True
        print("[CAMERA] OpenCV 웹캠 시작")

    def get_preview_frame(self):
        if not self.started or self.capture_device is None:
            raise CameraError("웹캠이 시작되지 않았습니다.")

        success, frame_bgr = self.capture_device.read()

        if not success or frame_bgr is None:
            raise CameraError("웹캠 프레임을 읽지 못했습니다.")

        # 촬영 시에는 리사이즈 전 원본 프레임을 저장한다.
        self.last_full_frame = frame_bgr.copy()

        frame_rgb = self.cv2.cvtColor(frame_bgr, self.cv2.COLOR_BGR2RGB)
        frame_rgb = self.cv2.resize(frame_rgb, self.preview_size)

        return frame_rgb

    def capture(self, save_path: str) -> str:
        if not self.started or self.capture_device is None:
            raise CameraError("웹캠이 시작되지 않았습니다.")

        # 아직 미리보기 프레임이 한 번도 생성되지 않았다면 즉시 한 장 읽는다.
        if self.last_full_frame is None:
            success, frame_bgr = self.capture_device.read()

            if not success or frame_bgr is None:
                raise CameraError("촬영할 웹캠 이미지를 읽지 못했습니다.")

            self.last_full_frame = frame_bgr

        output_path = Path(save_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        success = self.cv2.imwrite(
            str(output_path),
            self.last_full_frame
        )

        if not success:
            raise CameraError(f"이미지 저장에 실패했습니다: {output_path}")

        print(f"[CAMERA] 웹캠 이미지 저장 완료: {output_path}")
        return str(output_path)

    def stop(self) -> None:
        if self.capture_device is not None:
            self.capture_device.release()
            self.capture_device = None

        self.last_full_frame = None
        self.started = False

        print("[CAMERA] OpenCV 웹캠 종료")


class Picamera2Camera(BaseCamera):
    """
    Raspberry Pi 카메라 모듈용 처리 클래스.

    최종 Raspberry Pi 5 장비에서는 이 클래스를 사용한다.
    """

    def __init__(
        self,
        preview_size: tuple[int, int] = (720, 400),
        capture_size: tuple[int, int] = (1920, 1080),
        camera_index: int = 0
    ):
        super().__init__(preview_size, capture_size, camera_index)
        self.picam2 = None

    def start(self) -> None:
        try:
            from picamera2 import Picamera2
        except ImportError as error:
            raise CameraError(
                "Picamera2를 불러오지 못했습니다. "
                "Raspberry Pi에서 `sudo apt install python3-picamera2`를 "
                "확인해 주세요."
            ) from error

        try:
            self.picam2 = Picamera2(self.camera_index)

            # main: 촬영 저장용 고해상도 스트림
            # lores: GUI 미리보기용 저해상도 스트림
            camera_config = self.picam2.create_preview_configuration(
                main={
                    "size": self.capture_size,
                    "format": "RGB888"
                },
                lores={
                    "size": self.preview_size,
                    "format": "RGB888"
                }
            )

            self.picam2.configure(camera_config)
            self.picam2.start()

            # 연속 오토포커스 (AfMode 2 = Continuous)
            try:
                self.picam2.set_controls({"AfMode": 2, "AfTrigger": 0})
                print("[CAMERA] 오토포커스 활성화")
            except Exception as af_error:
                print(f"[CAMERA] 오토포커스 미지원: {af_error}")

            self.started = True
            print("[CAMERA] Picamera2 카메라 모듈 시작")

        except Exception as error:
            self.stop()
            raise CameraError(
                f"Raspberry Pi 카메라 시작 실패: {error}"
            ) from error

    def get_preview_frame(self):
        if not self.started or self.picam2 is None:
            raise CameraError("Raspberry Pi 카메라가 시작되지 않았습니다.")

        try:
            frame = self.picam2.capture_array("lores")
            return frame[:, :, ::-1]  # BGR → RGB
        except Exception as error:
            raise CameraError(
                f"카메라 미리보기 프레임 읽기 실패: {error}"
            ) from error

    def capture(self, save_path: str) -> str:
        if not self.started or self.picam2 is None:
            raise CameraError("Raspberry Pi 카메라가 시작되지 않았습니다.")

        output_path = Path(save_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 저장 이미지는 main 고해상도 스트림에서 캡처한다.
            self.picam2.capture_file(str(output_path), name="main")
            print(f"[CAMERA] Picamera2 이미지 저장 완료: {output_path}")
            return str(output_path)

        except Exception as error:
            raise CameraError(
                f"Raspberry Pi 이미지 저장 실패: {error}"
            ) from error

    def stop(self) -> None:
        if self.picam2 is not None:
            try:
                self.picam2.stop()
            except Exception:
                pass

            try:
                self.picam2.close()
            except Exception:
                pass

            self.picam2 = None

        self.started = False
        print("[CAMERA] Picamera2 카메라 모듈 종료")


def create_camera_service(
    backend: str = "auto",
    preview_size: tuple[int, int] = (720, 400),
    capture_size: tuple[int, int] = (1920, 1080),
    camera_index: int = 0
) -> BaseCamera:
    """
    설정값에 따라 사용할 카메라 처리 객체를 생성한다.

    backend:
    - "auto"      : Raspberry Pi + Picamera2 사용 가능 시 카메라 모듈,
                    그 외에는 OpenCV 웹캠 사용
    - "opencv"    : PC 웹캠 또는 USB 웹캠 강제 사용
    - "picamera2" : Raspberry Pi 카메라 모듈 강제 사용
    """
    selected_backend = backend.lower().strip()

    if selected_backend not in {"auto", "opencv", "picamera2"}:
        raise ValueError(
            "CAMERA_BACKEND는 'auto', 'opencv', 'picamera2' 중 하나여야 합니다."
        )

    if selected_backend == "auto":
        picamera2_available = importlib.util.find_spec("picamera2") is not None

        if is_raspberry_pi() and picamera2_available:
            selected_backend = "picamera2"
        else:
            selected_backend = "opencv"

    print(f"[CAMERA] 선택된 카메라 백엔드: {selected_backend}")

    if selected_backend == "picamera2":
        return Picamera2Camera(
            preview_size=preview_size,
            capture_size=capture_size,
            camera_index=camera_index
        )

    return OpenCVCamera(
        preview_size=preview_size,
        capture_size=capture_size,
        camera_index=camera_index
    )