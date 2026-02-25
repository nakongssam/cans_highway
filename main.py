import base64
import mimetypes
from typing import Optional

import streamlit as st
from openai import OpenAI


# ----------------------------
# Helpers
# ----------------------------
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_EXTS = ["png", "jpg", "jpeg", "webp"]


def get_mime_type(file_name: str) -> str:
    """
    Guess MIME type from file name. Fallback to application/octet-stream.
    For jpg/jpeg, mimetypes returns image/jpeg (good).
    """
    mime, _ = mimetypes.guess_type(file_name)
    return mime or "application/octet-stream"


def file_to_data_url(uploaded_file) -> str:
    """
    Convert uploaded image to base64 data URL: data:<mime>;base64,<...>
    """
    raw = uploaded_file.getvalue()
    mime = get_mime_type(uploaded_file.name)

    # Streamlit uploader may provide jpg/jpeg; ensure mime is acceptable
    # If guessing failed but content type exists, try that
    if mime == "application/octet-stream" and getattr(uploaded_file, "type", None):
        mime = uploaded_file.type

    if mime not in ALLOWED_MIME:
        # Allow jpeg even if uploader gives image/jpg (rare)
        if mime == "image/jpg":
            mime = "image/jpeg"
        else:
            raise ValueError(f"지원하지 않는 이미지 형식입니다: {mime}")

    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def extract_text_from_response(resp) -> str:
    """
    Responses API 결과에서 텍스트를 최대한 안전하게 추출.
    SDK 버전에 따라 output_text 속성이 있거나, output 구조를 파싱해야 할 수 있음.
    """
    # 1) 가장 간단한 경로(지원되는 경우)
    text = getattr(resp, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    # 2) output 구조를 순회하며 text content 수집
    try:
        chunks = []
        for item in (resp.output or []):
            for content in (getattr(item, "content", None) or []):
                ctype = getattr(content, "type", None)
                if ctype in ("output_text", "text"):
                    t = getattr(content, "text", None)
                    if t:
                        chunks.append(t)
        joined = "\n".join(chunks).strip()
        if joined:
            return joined
    except Exception:
        pass

    # 3) 최후의 보루
    return "⚠️ 응답에서 텍스트를 추출하지 못했습니다. 다시 시도해 주세요."


def build_prompt(
    project_name: str,
    road_name: str,
    inspector: str,
    weather: str,
    notes: str,
) -> str:
    return f"""
당신은 '고속도로 시설물 점검' 분야의 품질관리(QC) 보고서를 작성하는 전문가입니다.
사용자가 제공한 점검 사진 1장을 바탕으로 **품질관리 보고서(Markdown)** 를 작성하세요.

# 작성 원칙
- 반드시 한국어로 작성
- 과장 금지: 사진에서 확인 가능한 내용과 합리적 추정은 구분
- 확인 불가한 내용은 "확인 필요"로 표기
- 표/체크리스트를 적극 활용
- 안전/품질/환경/교통관리 관점 포함
- 마지막에 '조치 우선순위'와 '후속 점검 계획'을 제시

# 보고서에 포함할 섹션(순서 고정)
1. 개요 (프로젝트/노선/점검자/날씨/비고)
2. 사진 기반 관찰 요약 (핵심 5줄 내)
3. 결함/이상 징후 추정 및 근거 (표로: 항목, 관찰근거, 심각도(상/중/하), 확인필요 여부)
4. 품질 기준 관점 체크리스트 (표로: 포장/배수/균열/표지/시설물/안전, 적합/주의/부적합, 메모)
5. 즉시 조치 사항 (불릿)
6. 보수·보강 권고 (불릿, 공법은 일반적 수준에서 제안)
7. 위험요인 및 안전관리(작업자/운전자) (불릿)
8. 조치 우선순위 (1~5, 근거 포함)
9. 후속 점검 계획 (일정 예시 포함)
10. 부록: 사진 판독 한계 및 추가 필요 자료

# 입력 메타정보
- 프로젝트명: {project_name or "미입력"}
- 노선/구간: {road_name or "미입력"}
- 점검자: {inspector or "미입력"}
- 날씨/환경: {weather or "미입력"}
- 비고: {notes or "미입력"}

이제 사진을 분석해 보고서를 작성하세요.
""".strip()


# ----------------------------
# Streamlit App
# ----------------------------
st.set_page_config(page_title="고속도로 점검 보고서 생성기", page_icon="🛣️", layout="wide")

st.title("🛣️ 고속도로 점검 이미지 → 품질관리 보고서 생성기")
st.caption("이미지를 업로드하면 OpenAI 비전 모델로 QC 보고서(Markdown)를 자동 생성합니다. (Streamlit Community Cloud 배포용)")

# Secrets 체크
api_key: Optional[str] = None
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except Exception:
    api_key = None

if not api_key:
    st.error(
        "❌ OpenAI API Key를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 **Settings → Secrets** 에 다음처럼 등록해 주세요:\n"
        "- `OPENAI_API_KEY = \"your_key_here\"`\n\n"
        "키가 등록되면 새로고침 후 다시 시도해 주세요."
    )
    st.stop()

client = OpenAI(api_key=api_key)

with st.sidebar:
    st.header("⚙️ 보고서 설정")
    model = st.selectbox(
        "사용 모델",
        options=[
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-4o-mini",
            "gpt-4o",
        ],
        index=0,
        help="계정/권한에 따라 사용 가능한 모델이 다를 수 있습니다.",
    )

    st.subheader("🧾 메타정보(선택)")
    project_name = st.text_input("프로젝트명", value="")
    road_name = st.text_input("노선/구간", value="")
    inspector = st.text_input("점검자", value="")
    weather = st.text_input("날씨/환경", value="")
    notes = st.text_area("비고", value="", height=120)

    st.divider()
    st.subheader("🧠 생성 옵션(선택)")
    max_output_tokens = st.slider("최대 출력 토큰", min_value=300, max_value=2500, value=1200, step=50)
    temperature = st.slider("창의성(temperature)", min_value=0.0, max_value=1.2, value=0.3, step=0.1)

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("1) 점검 이미지 업로드")
    uploaded = st.file_uploader(
        "PNG/JPG/JPEG/WEBP 파일만 업로드 가능",
        type=ALLOWED_EXTS,
        accept_multiple_files=False,
        help="현장 점검 사진(포장, 균열, 배수, 표지, 시설물 등)을 업로드하세요.",
    )

    if uploaded is not None:
        st.image(uploaded, caption=f"업로드 이미지: {uploaded.name}", use_container_width=True)

with col_right:
    st.subheader("2) 보고서 생성 및 다운로드")

    if "report_md" not in st.session_state:
        st.session_state.report_md = ""

    generate = st.button("🧾 보고서 생성하기", type="primary", use_container_width=True, disabled=(uploaded is None))

    if generate:
        if uploaded is None:
            st.warning("이미지를 먼저 업로드해 주세요.")
        else:
            try:
                with st.spinner("이미지를 분석하고 보고서를 작성하는 중입니다..."):
                    data_url = file_to_data_url(uploaded)
                    prompt = build_prompt(project_name, road_name, inspector, weather, notes)

                    resp = client.responses.create(
                        model=model,
                        input=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "input_text", "text": prompt},
                                    {"type": "input_image", "image_url": data_url},
                                ],
                            }
                        ],
                        max_output_tokens=int(max_output_tokens),
                        temperature=float(temperature),
                    )

                    md = extract_text_from_response(resp)

                    # 보고서 상단에 간단 메타 헤더 추가(사용자 편의)
                    header = f"""# 고속도로 점검 품질관리 보고서

- 생성일시: {st.session_state.get("generated_at", "")}
- 파일명: {uploaded.name}

---
"""
                    # generated_at 세팅 (한번만)
                    if not st.session_state.get("generated_at"):
                        from datetime import datetime, timezone, timedelta

                        kst = timezone(timedelta(hours=9))
                        st.session_state.generated_at = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S (KST)")

                        header = f"""# 고속도로 점검 품질관리 보고서

- 생성일시: {st.session_state.generated_at}
- 파일명: {uploaded.name}

---
"""

                    st.session_state.report_md = header + "\n" + md

            except ValueError as ve:
                st.error(f"❌ 업로드 파일 처리 중 오류가 발생했습니다: {ve}")
            except Exception as e:
                st.error(
                    "❌ OpenAI API 호출 중 문제가 발생했습니다.\n\n"
                    "가능한 원인:\n"
                    "- API 키/권한 문제\n"
                    "- 모델 사용 불가 또는 한도 초과\n"
                    "- 네트워크 일시 오류\n\n"
                    f"오류 상세: {type(e).__name__}: {e}"
                )

    if st.session_state.report_md:
        st.success("✅ 보고서가 생성되었습니다!")
        st.markdown(st.session_state.report_md)

        st.download_button(
            label="⬇️ 보고서 .md 다운로드",
            data=st.session_state.report_md.encode("utf-8"),
            file_name="highway_qc_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    else:
        st.info("오른쪽 상단의 **보고서 생성하기** 버튼을 누르면 결과가 여기 표시됩니다.")

st.divider()
with st.expander("🔐 Streamlit Secrets 설정 방법", expanded=False):
    st.markdown(
        """
Streamlit Community Cloud에서 아래처럼 Secrets를 등록하세요.

- 앱 대시보드 → **Settings** → **Secrets**
- 다음을 추가:

```toml
OPENAI_API_KEY = "sk-..."
