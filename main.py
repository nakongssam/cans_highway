import streamlit as st
import google.generativeai as genai
from PIL import Image

# 1. 페이지 설정
st.set_page_config(page_title="고속도로 시설물 점검 보고서 AI", layout="wide")

# 2. API 키 설정 (Secrets에서 불러오기)
# Streamlit Cloud의 Settings > Secrets에 저장한 'GEMINI_API_KEY'를 가져옵니다.
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    # 무료 티어에서 가장 효율적인 gemini-2.0-flash 사용
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    st.error("⚠️ Streamlit Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.")
    st.stop() # 키가 없으면 앱 중단

# 3. 앱 제목 및 UI 구성
st.title("🚧 고속도로 시설물 유지관리 AI 점검 시스템")
st.info("비공개 API 키를 통해 보안 연결이 활성화되었습니다.")

# 파일 업로더
uploaded_file = st.file_uploader("시설물 점검 사진을 업로드하세요 (JPG, PNG)", type=["jpg", "png", "jpeg"])

# 프롬프트 설정 (사용자 요청 내용 반영)
SYSTEM_PROMPT = """
너는 고속도로 운영기관의 시설물 유지관리 담당 기술자다.
입력되는 시설물 점검 사진 1장을 바탕으로 현장 점검 보고서 초안을 작성한다.

[작성 절차 및 원칙]
1. 외관 상태 관찰 (손상, 변형, 오염, 파손 등)
2. 손상 유형 판정 (균열, 박리, 부식, 침하, 탈락 등)
3. 위험도 평가 (낮음/중간/높음) 및 근거 제시
4. 긴급 안전 위험 시 즉시 조치 사항 제시
5. 단계별 보수 및 정비 권고안 작성
6. 추가 점검 필요 항목 체크리스트 작성

* 사진에 기반하지 않은 정보 생성 금지
* 확정 어려운 내용은 '현장 확인 필요' 명시
* 기술 보고서 문체 유지

보고서 형식:
[1. 점검 개요]
[2. 관찰 내용 (사진 기반)]
[3. 손상/이상 유형 판정 (가능성 포함)]
[4. 위험도 평가 (낮음/중간/높음) 및 근거]
[5. 즉시 조치 권고 (필요 시)]
[6. 보수/정비 권고안 (단계별)]
[7. 추가 점검/확인 항목 (체크리스트)]
[8. 참고/주의 (면책 문구)]
"""

if uploaded_file:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.image(image, caption="현장 점검 사진", use_container_width=True)
    
    with col2:
        if st.button("AI 보고서 생성"):
            try:
                with st.spinner("이미지를 분석하여 전문 보고서를 작성 중입니다..."):
                    # API 호출
                    response = model.generate_content([SYSTEM_PROMPT, image])
                    
                    st.subheader("📋 분석 결과")
                    st.markdown(response.text)
                    
                    # 다운로드 기능
                    st.download_button(
                        label="📄 보고서 텍스트로 저장",
                        data=response.text,
                        file_name="highway_report.txt",
                        mime="text/plain"
                    )
            except Exception as e:
                st.error(f"분석 중 오류 발생: {e}")
