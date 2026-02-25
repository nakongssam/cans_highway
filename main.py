import io
import os
import re
import time
from datetime import datetime

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types


SYSTEM_PROMPT = """
너는 고속도로 운영기관의 시설물 유지관리 담당 기술자다.

입력되는 시설물 점검 사진 1장을 바탕으로
현장 점검 보고서 초안을 작성하는 업무를 수행한다.

다음의 절차에 따라 분석을 수행할 것:

1. 사진에 나타난 시설물의 외관 상태를 관찰하여
   손상, 변형, 오염, 파손 등의 이상 여부를 식별한다.

2. 식별된 이상 현상이 있을 경우,
   해당 손상의 유형을 기술적으로 판정한다.
   (예: 균열, 박리, 부식, 침하, 탈락 등)

3. 해당 이상이 시설물의 기능 또는 안전성에 미칠 수 있는
   잠재적 영향을 고려하여 위험도를 다음 중 하나로 평가한다.
   - 낮음
   - 중간
   - 높음

4. 긴급한 안전 위험이 예상되는 경우에만
   즉시 조치 필요 사항을 제시한다.

5. 중장기 유지관리를 위한
   단계별 보수 및 정비 권고안을 작성한다.

6. 사진만으로 판단이 어려운 경우,
   추가 점검이 필요한 항목을 체크리스트 형태로 제시한다.

다음 작성 원칙을 반드시 준수할 것:

- 사진에 기반하지 않은 정보는 임의로 생성하지 말 것
- 확정이 어려운 내용은 '현장 확인 필요'로 명시할 것
- 과장된 표현 또는 추정성 판단을 단정적으로 서술하지 말 것
- 기술 보고서 문체를 유지할 것

보고서는 반드시 아래 형식으로 작성할 것:

[1. 점검 개요]
[2. 관찰 내용 (사진 기반)]
[3. 손상/이상 유형 판정 (가능성 포함)]
[4. 위험도 평가 (낮음/중간/높음) 및 근거]
[5. 즉시 조치 권고 (필요 시)]
[6. 보수/정비 권고안 (단계별)]
[7. 추가 점검/확인 항목 (체크리스트)]
[8. 참고/주의 (면책 문구)]
""".strip()


def get_api_key() -> str | None:
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


@st.cache_resource
def get_client(api_key: str):
    return genai.Client(api_key=api_key)


def call_with_retry(fn, max_retries=3):
    """429/RESOURCE_EXHAUSTED가 뜰 때 짧게 재시도. (무료 쿼터 0이면 오래 기다려도 소용없어서 짧게)"""
    base_sleep = 2.0
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            is_rate = ("429" in msg) or ("RESOURCE_EXHAUSTED" in msg) or ("TooManyRequests" in msg)
            if not is_rate:
                raise
            # limit: 0이면 즉시 중단(기다려도 해결 안 되는 경우가 많음)
            if "limit: 0" in msg:
                raise RuntimeError(
                    "현재 키/프로젝트에서 Free tier 쿼터가 0으로 표시됩니다(요청이 차단된 상태).\n"
                    "다른 모델/프로젝트를 시도하거나, 필요 시 Billing 연결이 필요할 수 있습니다."
                ) from e

            m = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", msg, re.IGNORECASE)
            sleep_s = float(m.group(1)) if m else base_sleep * (2 ** attempt)

            if attempt >= max_retries:
                raise RuntimeError(
                    "요청 제한(429)에 걸렸습니다. 잠시 후 다시 시도해 주세요."
                ) from e

            time.sleep(min(sleep_s, 8.0))


@st.cache_data(ttl=600)
def list_available_models(api_key: str) -> list[str]:
    """내 API 키에서 실제로 보이는 모델만 목록으로 제공(404 방지)."""
    client = get_client(api_key)

    def _list():
        # python-genai는 Developer API/Vertex 모두 지원하지만,
        # 여기서는 Developer API 기준으로 '보이는 모델'을 그대로 보여주는 전략
        models = client.models.list()
        names = []
        for m in models:
            # name은 보통 "models/xxx" 형태
            if getattr(m, "name", None):
                names.append(m.name.replace("models/", ""))
        # 중복 제거
        return sorted(list(set(names)))

    return call_with_retry(_list, max_retries=2)


def main():
    st.set_page_config(page_title="시설물 점검 보고서(무료 가능 모델 자동)", layout="wide")
    st.title("🛣️ 시설물 점검 보고서 생성 (이미지 → Gemini)")

    api_key = get_api_key()
    if not api_key:
        st.error(
            "API Key가 없습니다.\n\n"
            "Streamlit Cloud → App settings → Secrets에 아래처럼 추가하세요:\n"
            'GEMINI_API_KEY = "YOUR_KEY"'
        )
        st.stop()

    # 모델 목록 가져오기(가능한 모델만 보여줌)
    try:
        model_list = list_available_models(api_key)
    except Exception as e:
        st.warning(f"모델 목록을 불러오지 못했습니다: {e}")
        model_list = []

    with st.sidebar:
        st.subheader("설정")
        if model_list:
            model = st.selectbox("model (내 키에서 사용 가능한 모델)", model_list, index=0)
        else:
            # 목록 실패 시 수동 입력 fallback
            model = st.text_input("model (수동 입력)", value="gemini-2.0-flash")

        temperature = st.slider("temperature", 0.0, 1.0, 0.2, 0.05)
        max_tokens = st.number_input("max_output_tokens", 256, 4096, 1024, step=256)
        concise = st.toggle("간단 모드(토큰 절약)", value=True)

        st.caption("무료 티어는 모델/계정에 따라 limit:0이 뜰 수 있어요.")

    uploaded = st.file_uploader("점검 사진 1장 업로드 (JPG/PNG)", type=["jpg", "jpeg", "png"])
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("입력 이미지")
        if uploaded:
            img_bytes = uploaded.getvalue()
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            st.image(img, use_container_width=True)
        else:
            st.info("사진을 업로드하세요.")

    with col2:
        st.subheader("보고서")
        if not uploaded:
            return

        img_bytes = uploaded.getvalue()
        mime = uploaded.type or "image/jpeg"
        img_part = types.Part.from_bytes(data=img_bytes, mime_type=mime)

        user_prompt = (
            "첨부된 시설물 점검 사진 1장을 바탕으로 시스템 지침(규칙/형식)을 엄격히 준수하여 보고서를 작성하라.\n"
            "- 사진만으로 확정할 수 없는 내용은 반드시 '현장 확인 필요'로 표기하라.\n"
            "- 입력되지 않은 정보는 임의로 생성하지 말라.\n"
        )
        if concise:
            user_prompt += (
                "\n[출력 분량 지침]\n"
                "- 각 섹션은 2~5문장 이내로 간결하게 작성하라.\n"
                "- 체크리스트는 핵심 5~8개 항목으로 제한하라.\n"
            )

        if st.button("보고서 생성", type="primary", use_container_width=True):
            client = get_client(api_key)

            def _gen():
                return client.models.generate_content(
                    model=model,
                    contents=[user_prompt, img_part],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=float(temperature),
                        max_output_tokens=int(max_tokens),
                    ),
                )

            with st.spinner("Gemini가 보고서를 작성 중입니다..."):
                try:
                    resp = call_with_retry(_gen, max_retries=2)
                except Exception as e:
                    st.error(str(e))
                    st.stop()

            text = (resp.text or "").strip()
            if not text:
                st.warning("응답이 비어 있습니다.")
                return

            st.markdown(text)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "다운로드(MD)",
                data=text.encode("utf-8"),
                file_name=f"inspection_report_{ts}.md",
                mime="text/markdown",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
