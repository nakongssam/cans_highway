import os
import io
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
    # Streamlit Cloud: Secrets에 GEMINI_API_KEY를 넣는 걸 권장
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


@st.cache_resource
def get_client(api_key: str):
    # 키를 명시적으로 넣어두면 환경변수/시크릿 설정이 헷갈려도 안전
    return genai.Client(api_key=api_key)


def to_pil_image(uploaded_file) -> Image.Image:
    data = uploaded_file.read()
    return Image.open(io.BytesIO(data)).convert("RGB")


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
        max_tokens = st.number_input("max_output_tokens", min_value=256, max_value=8192, value=2048, step=256)
        st.divider()
        st.caption("업무 보고서 안정성은 temperature 낮게(0.0~0.3) 추천")

    uploaded = st.file_uploader("점검 사진 1장을 업로드하세요 (JPG/PNG)", type=["jpg", "jpeg", "png"])

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("입력 이미지")
        if uploaded:
            img = to_pil_image(uploaded)
            st.image(img, use_container_width=True)
        else:
            st.info("사진을 업로드하면 보고서 생성이 가능합니다.")

    with col2:
        st.subheader("생성 결과")
        if not uploaded:
            st.empty()
            return

        # 업로드 파일은 read()가 한 번 소비되므로, 버튼 클릭 때 다시 읽기 위해
        # Streamlit이 제공하는 uploaded.getvalue()를 사용해 안전하게 처리
        img_bytes = uploaded.getvalue()
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # (선택) 점검 개요에 넣을 수 있는 “사용자 입력” — 없으면 모델이 임의 생성하면 안 되니, 여기서 받는 게 안정적
        with st.expander("점검 정보 입력(선택)", expanded=False):
            facility_name = st.text_input("시설물 명/구간(선택)", value="")
            inspection_date = st.date_input("점검일(선택)", value=None)
            inspector = st.text_input("점검자(선택)", value="")
            extra_notes = st.text_area("추가 메모(선택)", value="", height=80)

        user_context_lines = []
        if facility_name:
            user_context_lines.append(f"- 시설물/구간: {facility_name}")
        if inspection_date:
            user_context_lines.append(f"- 점검일: {inspection_date.isoformat()}")
        if inspector:
            user_context_lines.append(f"- 점검자: {inspector}")
        if extra_notes.strip():
            user_context_lines.append(f"- 메모: {extra_notes.strip()}")

        user_context = "\n".join(user_context_lines).strip()

        if st.button("보고서 생성", type="primary", use_container_width=True):
            client = get_client(api_key)

            user_prompt = (
                "첨부된 시설물 점검 사진 1장을 바탕으로, 위 기준과 형식을 엄격히 준수하여 보고서를 작성하라.\n"
                "사진만으로 확정할 수 없는 내용은 반드시 '현장 확인 필요'로 표기하라.\n"
            )
            if user_context:
                user_prompt += "\n[사용자 제공 점검 정보]\n" + user_context + "\n"

            with st.spinner("Gemini가 보고서를 작성 중입니다..."):
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=[user_prompt, img],
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=float(temperature),
                            max_output_tokens=int(max_tokens),
                        ),
                    )
                except Exception as e:
                    st.error(f"Gemini 호출 중 오류: {e}")
                    st.stop()

            report = (resp.text or "").strip()
            if not report:
                st.warning("응답 텍스트가 비어 있습니다. (안전필터/모델 응답 이슈 가능)")
                return

            st.markdown(report)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="보고서 다운로드 (Markdown)",
                data=report.encode("utf-8"),
                file_name=f"inspection_report_{ts}.md",
                mime="text/markdown",
                use_container_width=True,
            )

            st.download_button(
                label="보고서 다운로드 (TXT)",
                data=report.encode("utf-8"),
                file_name=f"inspection_report_{ts}.txt",
                mime="text/plain",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
