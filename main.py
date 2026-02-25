import io, os
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

# 프롬프트(아주 간단)
PROMPT = """
사진을 보고 고속도로 시설물 점검 보고서를 작성해줘.
손상 여부, 손상 유형, 위험도(낮음/중간/높음), 조치/보수 권고, 추가 점검 항목을 포함해.
확실하지 않으면 '현장 확인 필요'라고 써.
""".strip()

st.title("🛣️ 시설물 점검 보고서(무료 시도)")

# Streamlit Cloud Secrets 또는 환경변수에서 키 읽기
api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error('Secrets에 GEMINI_API_KEY를 넣어주세요. 예: GEMINI_API_KEY="..."')
    st.stop()

img_file = st.file_uploader("점검 사진 1장 업로드", type=["jpg", "jpeg", "png"])
if not img_file:
    st.stop()

img_bytes = img_file.getvalue()
st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)

if st.button("보고서 생성"):
    try:
        client = genai.Client(api_key=api_key)

        # 이미지 안전 전달(바이트+mime)
        img_part = types.Part.from_bytes(
            data=img_bytes,
            mime_type=img_file.type or "image/jpeg",
        )

        resp = client.models.generate_content(
            model="gemini-2.0-flash",  # 모델 고정
            contents=[PROMPT, img_part],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=800,
            ),
        )

        st.markdown((resp.text or "").strip() or "응답이 비어 있습니다.")

    except Exception as e:
        msg = str(e)
        # 무료 막힘/쿼터 이슈를 사용자에게 짧게 안내
        if ("429" in msg) or ("RESOURCE_EXHAUSTED" in msg) or ("limit: 0" in msg):
            st.error("무료 쿼터가 막혀서 호출이 안 됩니다(429/limit:0). 다른 키/프로젝트 또는 Billing이 필요할 수 있어요.")
        elif "404" in msg and "not found" in msg.lower():
            st.error("현재 키/환경에서 이 모델을 찾을 수 없습니다(404).")
        else:
            st.error(f"오류: {e}")
