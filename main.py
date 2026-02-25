import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# 페이지 설정
st.set_page_config(page_title="고속도로 시설물 점검 보고서 생성기", layout="wide")

# 사이드바에서 API 키 설정 (Streamlit Secrets 사용 권장)
with st.sidebar:
    st.title("설정")
    api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    st.info("API 키는 [Google AI Studio](https://aistudio.google.com/)에서 발급받을 수 있습니다.")

# API 연결 설정
if api_key:
    genai.configure(api_key=api_key)
    # 무료 티어에서 성능과 속도가 가장 균형 잡힌 flash 모델 사용
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    st.warning("먼저 사이드바에 API 키를 입력해 주세요.")

# 앱 제목 및 설명
st.title("🚧 고속도로 시설물 유지관리 AI 점검 시스템")
st.write("시설물 점검 사진을 업로드하면 AI 기술자가 기술 보고서 초안을 작성합니다.")

# 파일 업로더
uploaded_file = st.file_uploader("점검 사진 업로드 (JPG, PNG, JPEG)", type=["jpg", "png", "jpeg"])

# 사용자가 제공한 프롬프트 설정
SYSTEM_PROMPT = """
너는 고속도로 운영기관의 시설물 유지관리 담당 기술자다.
입력되는 시설물 점검 사진 1장을 바탕으로 현장 점검 보고서 초안을 작성하는 업무를 수행한다.

다음의 절차에 따라 분석을 수행할 것:
1. 사진에 나타난 시설물의 외관 상태를 관찰하여 손상, 변형, 오염, 파손 등의 이상 여부를 식별한다.
2. 식별된 이상 현상이 있을 경우, 해당 손상의 유형을 기술적으로 판정한다. (예: 균열, 박리, 부식, 침하, 탈락 등)
3. 해당 이상이 시설물의 기능 또는 안전성에 미칠 수 있는 잠재적 영향을 고려하여 위험도를 다음 중 하나로 평가한다. (낮음, 중간, 높음)
4. 긴급한 안전 위험이 예상되는 경우에만 즉시 조치 필요 사항을 제시한다.
5. 중장기 유지관리를 위한 단계별 보수 및 정비 권고안을 작성한다.
6. 사진만으로 판단이 어려운 경우, 추가 점검이 필요한 항목을 체크리스트 형태로 제시한다.

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
"""

if uploaded_file is not None:
    # 이미지 표시
    image = Image.open(uploaded_file)
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.image(image, caption="업로드된 점검 사진", use_container_width=True)
    
    with col2:
        if st.button("보고서 생성 시작"):
            if not api_key:
                st.error("API 키가 필요합니다.")
            else:
                try:
                    with st.spinner("AI 기술자가 사진을 분석 중입니다..."):
                        # Gemini API 호출 (이미지와 프롬프트 전달)
                        response = model.generate_content([SYSTEM_PROMPT, image])
                        
                        st.subheader("📋 생성된 점검 보고서 초안")
                        st.markdown(response.text)
                        
                        # 결과 다운로드 버튼
                        st.download_button(
                            label="보고서 텍스트 다운로드",
                            data=response.text,
                            file_name="inspection_report.txt",
                            mime="text/plain"
                        )
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")
