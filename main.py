import os
import io
import base64
import streamlit as st
from PIL import Image
from openai import OpenAI

# ============================================================
# 앱 설정
# ============================================================
st.set_page_config(
    page_title="🛣️ 고속도로 품질관리 보고서 생성기",
    page_icon="🛣️",
    layout="centered"
)

st.title("🛣️ 고속도로 품질관리 보고서 생성기")
st.caption("노면 사진 1장 업로드 → 결함 유형 판정 + 품질 등급 평가 + 보수 권고안 자동 작성 (OpenAI Vision API)")

# ============================================================
# API Key (Streamlit Secrets)
# ============================================================
api_key = st.secrets.get("OPENAI_API_KEY", None)
if not api_key:
    st.error("⚠️ OPENAI_API_KEY가 Streamlit Secrets에 설정되어 있지 않습니다.")
    st.info("Streamlit Cloud → 앱 설정 → Secrets 에 OPENAI_API_KEY = '...' 를 추가하세요.")
    st.stop()

client = OpenAI(api_key=api_key)

# ============================================================
# 시스템 프롬프트
# ============================================================
SYSTEM_PROMPT = """
너는 고속도로 품질관리 전문기관의 '노면 품질 평가 보고서' 작성 보조 전문가야.
입력된 사진과 사용자가 제공한 정보만을 근거로 보고서를 작성해.

핵심 규칙:
1) 사진으로 확정할 수 없는 내용은 단정하지 말고 '가능성 있음'으로 표현해.
2) 입력에 없는 정보는 '미상' 또는 '현장 정밀 조사 필요'로 표기해.
3) 품질 등급은 반드시 A(우수) / B(양호) / C(보통) / D(불량) / E(매우불량) 5단계로 판정해.
4) 과장 표현 금지. 객관적 기준에 따른 판단만 제시해.

반드시 아래 형식으로 출력해 (마크다운, 줄바꿈 유지):

## 1. 평가 개요
## 2. 노면 상태 관찰 (사진 기반)
## 3. 결함 유형 판정
> 균열 / 소성변형 / 포트홀 / 표면 마모 / 배수 불량 / 기타 중 해당 항목 명시
## 4. 품질 등급 평가 (A~E) + 판정 근거
## 5. 긴급 조치 필요 여부
## 6. 보수 공법 권고안 (단계별)
## 7. 추가 정밀 조사 체크리스트
## 8. 참고 및 면책 사항
""".strip()

# ============================================================
# 이미지 → base64 data URL 변환
# ============================================================
def to_data_url(uploaded_file, max_width=1280):
    img = Image.open(uploaded_file).convert("RGB")
    w, h = img.size
    if w > max_width:
        img = img.resize((max_width, int(h * max_width / w)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}", img

# ============================================================
# 입력 UI
# ============================================================
st.subheader("📥 평가 정보 입력")

col_a, col_b = st.columns(2)
with col_a:
    road_type = st.selectbox(
        "구간 유형",
        ["본선 차로 (주행)", "본선 차로 (추월)", "진출입 램프",
         "요금소 구간", "교량 위 노면", "터널 내 노면", "휴게소 접속도로", "기타"]
    )
with col_b:
    grade_criteria = st.selectbox(
        "평가 기준",
        ["국토교통부 PCI 기준", "한국도로공사 내부 기준", "AASHTO 기준", "기타/미상"]
    )

location = st.text_input("노선명 / 위치", placeholder="예) 경부고속도로 상행 142km, 천안IC~청주IC 구간")
inspect_date = st.text_input("조사 일시", placeholder="예) 2026-02-18 10:20")
traffic_info = st.text_input("교통량 / 차로 조건 (선택)", placeholder="예) 일 평균 45,000대, 4차로 중 2차로")
notes = st.text_area("현장 메모 (선택)", height=80,
                     placeholder="예) 소성변형 심화 구간, 동절기 동결융해 반복 이력, 야간 반사 저하 민원")

uploaded = st.file_uploader("📷 노면 사진 업로드 (jpg / png)", type=["jpg", "jpeg", "png"])

if uploaded:
    _, preview = to_data_url(uploaded)
    st.image(preview, caption="업로드된 노면 사진 미리보기", use_container_width=True)

# ============================================================
# 버튼
# ============================================================
col1, col2 = st.columns(2)
with col1:
    generate_btn = st.button("✨ 보고서 생성", type="primary", use_container_width=True)
with col2:
    if st.button("🧹 초기화", use_container_width=True):
        st.session_state["result"] = ""
        st.rerun()

if "result" not in st.session_state:
    st.session_state["result"] = ""

# ============================================================
# 보고서 생성 (API 호출)
# ============================================================
if generate_btn:
    if not uploaded:
        st.warning("⚠️ 노면 사진을 먼저 업로드해주세요.")
    else:
        def val(v):
            return v.strip() if v.strip() else "미상"

        user_prompt = f"""
[사용자 제공 정보]
- 구간 유형: {road_type}
- 평가 기준: {grade_criteria}
- 노선명/위치: {val(location)}
- 조사 일시: {val(inspect_date)}
- 교통량/차로: {val(traffic_info)}
- 현장 메모: {val(notes)}

요청:
위 정보와 업로드된 노면 사진을 바탕으로 지정 형식의 고속도로 품질관리 보고서를 작성해줘.
결함 유형은 가능한 한 구체적으로 분류하고, 불확실한 내용은 '현장 정밀 조사 필요'로 표기해줘.
""".strip()

        try:
            data_url, _ = to_data_url(uploaded)

            with st.spinner("🔍 AI가 노면 사진을 분석하고 있습니다..."):
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        },
                    ],
                    max_tokens=2000,
                    temperature=0.3,
                )

            st.session_state["result"] = resp.choices[0].message.content.strip()

        except Exception as e:
            st.error("❌ API 호출 중 오류가 발생했습니다.")
            st.code(str(e))

# ============================================================
# 결과 출력
# ============================================================
if st.session_state["result"]:
    st.divider()
    st.subheader("📄 고속도로 품질관리 보고서")
    st.markdown(st.session_state["result"])
    st.divider()
    st.download_button(
        label="📥 보고서 텍스트 저장 (.txt)",
        data=st.session_state["result"],
        file_name="highway_quality_report.txt",
        mime="text/plain",
        use_container_width=True
    )
