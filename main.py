import os
import io
import re
import time
from datetime import datetime, date

import streamlit as st
from PIL import Image

from google import genai
from google.genai import types


# =========================
# 1) SYSTEM PROMPT (사용자 제공)
# =========================
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


# =========================
# 2) 유틸
# =========================
def get_api_key() -> str | None:
    # Streamlit Cloud: Secrets에 GEMINI_API_KEY 추천
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


@st.cache_resource
def get_client(api_key: str):
    # 키를 명시적으로 넣어두면 환경변수 인식 문제를 줄일 수 있음
    return genai.Client(api_key=api_key)


def bytes_to_pil_image(img_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def build_user_prompt(
    facility_name: str,
    inspection_date: date | None,
    inspector: str,
    extra_notes: str,
    concise_mode: bool,
) -> str:
    """
    user_prompt는 '요청'을 짧고 명확하게.
    - concise_mode면 출력 분량을 명시적으로 줄여 토큰 절약
    """
    base = (
        "첨부된 시설물 점검 사진 1장을 바탕으로, "
        "시스템 지침(규칙/형식)을 엄격히 준수하여 보고서를 작성하라.\n"
        "- 사진만으로 확정할 수 없는 내용은 반드시 '현장 확인 필요'로 표기하라.\n"
        "- 입력되지 않은 정보는 임의로 생성하지 말라.\n"
    )

    if concise_mode:
        base += (
            "\n[출력 분량 지침]\n"
            "- 각 섹션은 2~5문장 이내로 간결하게 작성하라.\n"
            "- 체크리스트는 핵심 5~8개 항목으로 제한하라.\n"
        )

    ctx_lines = []
    if facility_name.strip():
        ctx_lines.append(f"- 시설물/구간: {facility_name.strip()}")
    if inspection_date:
        ctx_lines.append(f"- 점검일: {inspection_date.isoformat()}")
    if inspector.strip():
        ctx_lines.append(f"- 점검자: {inspector.strip()}")
    if extra_notes.strip():
        ctx_lines.append(f"- 메모: {extra_notes.strip()}")

    if ctx_lines:
        base += "\n[사용자 제공 점검 정보]\n" + "\n".join(ctx_lines) + "\n"

    return base.strip()


def call_gemini_with_retry(client, *, model: str, contents, config, max_retries: int = 4):
    """
    429(RESOURCE_EXHAUSTED / TooManyRequests) 발생 시 재시도.
    에러 메시지에 'retry in XXs'가 있으면 그 시간만큼 대기.
    없으면 지수 백오프.
    """
    base_sleep = 2.0

    for attempt in range(max_retries + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            msg = str(e)

            # 재시도 대상인지 판단
            is_rate_limited = ("429" in msg) or ("RESOURCE_EXHAUSTED" in msg) or ("TooManyRequests" in msg)
            if not is_rate_limited:
                raise

            # retry in XXs 힌트가 있으면 우선 사용
            m = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", msg, re.IGNORECASE)
            if m:
                sleep_s = float(m.group(1))
            else:
                sleep_s = base_sleep * (2 ** attempt)  # 2,4,8,16...

            if attempt >= max_retries:
                raise RuntimeError(
                    "Gemini API 호출 제한(429)에 걸렸습니다.\n"
                    "- 잠시 후 다시 시도하거나\n"
                    "- AI Studio에서 Billing/쿼터(무료 티어) 상태를 확인해 주세요.\n\n"
                    f"원문 에러: {msg[:600]}"
                ) from e

            time.sleep(sleep_s)


# =========================
# 3) Streamlit UI
# =========================
def main():
    st.set_page_config(page_title="시설물 점검 보고서 생성기", layout="wide")
    st.title("🛣️ 시설물 점검 보고서 생성 (이미지 → Gemini)")

    api_key = get_api_key()
    if not api_key:
        st.error(
            "Gemini API Key가 설정되지 않았습니다.\n\n"
            "Streamlit Cloud → App settings → Secrets에 아래처럼 추가하세요:\n"
            'GEMINI_API_KEY = "YOUR_KEY"\n'
        )
        st.stop()

    with st.sidebar:
        st.subheader("모델/출력 설정")
        model = st.text_input("model", value="gemini-2.0-flash")
        temperature = st.slider("temperature", 0.0, 1.0, 0.2, 0.05)

        # 토큰 절약용 기본값: 1024
        max_tokens = st.number_input("max_output_tokens", 256, 8192, 1024, step=256)

        concise_mode = st.toggle("간단 모드(토큰 절약)", value=True)
        st.caption("간단 모드: 섹션/체크리스트 분량을 제한하여 비용/쿼터 소모를 줄입니다.")

        st.divider()
        st.caption("※ 429가 잦으면 Billing 연결이 가장 안정적입니다.")

    uploaded = st.file_uploader("점검 사진 1장을 업로드하세요 (JPG/PNG)", type=["jpg", "jpeg", "png"])

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("입력 이미지")
        if uploaded:
            img_bytes = uploaded.getvalue()
            img_preview = bytes_to_pil_image(img_bytes)
            st.image(img_preview, use_container_width=True)
        else:
            st.info("사진을 업로드하면 보고서 생성 버튼이 활성화됩니다.")

    with col2:
        st.subheader("보고서")
        if not uploaded:
            st.empty()
            return

        # 업로드 파일 read() 문제 방지: getvalue()로 bytes 확보
        img_bytes = uploaded.getvalue()
        img = bytes_to_pil_image(img_bytes)

        with st.expander("점검 정보 입력(선택)", expanded=False):
            facility_name = st.text_input("시설물 명/구간(선택)", value="")
            inspection_date = st.date_input("점검일(선택)", value=None)
            inspector = st.text_input("점검자(선택)", value="")
            extra_notes = st.text_area("추가 메모(선택)", value="", height=80)

        if st.button("보고서 생성", type="primary", use_container_width=True):
            client = get_client(api_key)

            user_prompt = build_user_prompt(
                facility_name=facility_name,
                inspection_date=inspection_date,
                inspector=inspector,
                extra_notes=extra_notes,
                concise_mode=concise_mode,
            )

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=float(temperature),
                max_output_tokens=int(max_tokens),
            )

            with st.spinner("Gemini가 보고서를 작성 중입니다..."):
                resp = call_gemini_with_retry(
                    client,
                    model=model,
                    contents=[user_prompt, img],
                    config=config,
                    max_retries=4,
                )

            report = (resp.text or "").strip()
            if not report:
                st.warning("응답 텍스트가 비어 있습니다. (안전필터/모델 응답 이슈 가능)")
                return

            st.markdown(report)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "보고서 다운로드 (MD)",
                data=report.encode("utf-8"),
                file_name=f"inspection_report_{ts}.md",
                mime="text/markdown",
                use_container_width=True,
            )
            st.download_button(
                "보고서 다운로드 (TXT)",
                data=report.encode("utf-8"),
                file_name=f"inspection_report_{ts}.txt",
                mime="text/plain",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
