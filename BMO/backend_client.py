# backend/backend_client.py
import os
from typing import Any, Dict, Optional

import requests


class BackendClient:
    """
    BMO 프론트엔드와 백엔드 서버의 HTTP 통신을 담당하는 클래스.

    - 일반 대화 및 음식 추천 요청: /ask
    - 냉장고 이미지 분석: /upload-image
    - 영수증 OCR 분석: /upload-receipt
    - 음식 영양 분석: /nutrition
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30
    ):
        self.base_url = (
            base_url
            or os.getenv("BMO_BACKEND_URL", "http://175.202.111.234:5000")

        ).rstrip("/")

        self.timeout = timeout

    def health_check(self) -> bool:
        """
        백엔드 서버가 실행 중인지 확인한다.

        데이터 명세서 기준:
        GET /
        응답 예시:
        {
            "message": "BMO Backend Running!"
        }
        """
        try:
            response = requests.get(
                f"{self.base_url}/",
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            print(f"[BACKEND] 서버 연결 확인: {data.get('message', '응답 수신')}")
            return True

        except requests.RequestException as e:
            print(f"[BACKEND WARN] 서버 연결 실패: {e}")
            return False

        except ValueError:
            print("[BACKEND WARN] 서버 응답이 JSON 형식이 아님")
            return False

    def ask(
        self,
        text: str,
        profile: Optional[Dict[str, Any]] = None,
        ingredients: Optional[list] = None,
        today_nutrition: Optional[Dict[str, Any]] = None,
        last_recommendations: str = "",
        recent_meals: Optional[list] = None,
        recipes: Optional[list] = None
    ) -> Optional[Dict[str, Any]]:
        """
        사용자 발화를 백엔드에 전달한다.

        사용 예:
        - 일반 대화
        - 음식 추천
        - 레시피 선택
        - 재료 추가/삭제 액션 처리
        """
        payload = {
            "text": text,
            "profile": profile or {},
            "ingredients": ingredients or [],
            "recipes": recipes or [],
            "today_nutrition": today_nutrition or {},
            "last_recommendations": last_recommendations,
            "recent_meals": recent_meals or []
        }

        try:
            response = requests.post(
                f"{self.base_url}/ask",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            result = data.get("result", {})

            print("[BACKEND] /ask 응답 수신")
            return result

        except requests.RequestException as e:
            print(f"[BACKEND WARN] /ask 요청 실패: {e}")
            return None

        except ValueError:
            print("[BACKEND WARN] /ask 응답이 JSON 형식이 아님")
            return None

    def upload_image(self, image_path: str) -> Optional[str]:
        """
        냉장고 또는 식재료 이미지를 서버에 전송해 설명 결과를 받는다.

        데이터 명세서 기준:
        POST /upload-image
        """
        try:
            with open(image_path, "rb") as image_file:
                files = {
                    "file": image_file
                }

                response = requests.post(
                    f"{self.base_url}/upload-image",
                    files=files,
                    timeout=self.timeout
                )

            response.raise_for_status()
            data = response.json()

            result = data.get("result", "")
            print(f"[BACKEND] 이미지 분석 결과: {result}")
            return result

        except FileNotFoundError:
            print(f"[BACKEND WARN] 이미지 파일을 찾을 수 없음: {image_path}")
            return None

        except requests.RequestException as e:
            print(f"[BACKEND WARN] 이미지 업로드 실패: {e}")
            return None

        except ValueError:
            print("[BACKEND WARN] 이미지 분석 응답이 JSON 형식이 아님")
            return None

    def upload_receipt(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        영수증 이미지를 서버에 전송해 추출된 재료 목록을 받는다.

        데이터 명세서 기준:
        POST /upload-receipt
        """
        try:
            with open(image_path, "rb") as image_file:
                files = {
                    "file": image_file
                }

                response = requests.post(
                    f"{self.base_url}/upload-receipt",
                    files=files,
                    timeout=self.timeout
                )

            response.raise_for_status()
            data = response.json()

            print(f"[BACKEND] 영수증 분석 결과: {data.get('result', '')}")
            return data

        except FileNotFoundError:
            print(f"[BACKEND WARN] 영수증 이미지 파일을 찾을 수 없음: {image_path}")
            return None

        except requests.RequestException as e:
            print(f"[BACKEND WARN] 영수증 업로드 실패: {e}")
            return None

        except ValueError:
            print("[BACKEND WARN] 영수증 분석 응답이 JSON 형식이 아님")
            return None

    def get_nutrition(self, recipe_name: str) -> Optional[Dict[str, Any]]:
        """
        선택된 음식의 영양 정보를 조회한다.

        데이터 명세서 기준:
        POST /nutrition
        """
        payload = {
            "recipe_name": recipe_name
        }

        try:
            response = requests.post(
                f"{self.base_url}/nutrition",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            print(f"[BACKEND] 영양 분석 결과 수신: {recipe_name}")
            return data

        except requests.RequestException as e:
            print(f"[BACKEND WARN] 영양 분석 요청 실패: {e}")
            return None

        except ValueError:
            print("[BACKEND WARN] 영양 분석 응답이 JSON 형식이 아님")
            return None

    def select_recipe(self, recipe_name: str) -> Optional[str]:
        """
        레시피 이름으로 조리 방법을 받아온다.

        POST /select-recipe
        응답: {"result": "조리 단계 텍스트", "saved_meal": recipe_name}
        """
        payload = {"recipe_name": recipe_name}

        try:
            response = requests.post(
                f"{self.base_url}/select-recipe",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            print(f"[BACKEND] 조리 방법 수신: {recipe_name}")
            return data.get("result", "")

        except requests.RequestException as e:
            print(f"[BACKEND WARN] 조리 방법 요청 실패: {e}")
            return None

        except ValueError:
            print("[BACKEND WARN] 조리 방법 응답이 JSON 형식이 아님")
            return None