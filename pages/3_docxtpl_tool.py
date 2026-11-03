import streamlit as st
import io
try:
    from docxtpl import DocxTemplate
except ImportError:
    pass

st.set_page_config(page_title="Word 報告自動化", page_icon="📄")
st.title("📄 自動化 Word 報告產出")
st.markdown("這是一支獨立的程式，負責讀取 GitHub 上的 Word 模板並將下方數據填入匯出。")

st.subheader("1. 填寫報告變數")
project_name = st.text_input("專案名稱", "秀巒邊坡穩定性檢核報告")
report_date = st.date_input("報告日期")
spt_value = st.text_input("代表性 SPT-N60 值", "15")
q_ult_value = st.text_input("極限承載力 (kPa)", "250.5")
conclusion = st.text_area("工程結論與建議", "本區域發現 3 處顯著異常降雨熱區，建議加強傾斜管監測頻率。")

st.subheader("2. 生成與下載")
if st.button("產出 Word 報告"):
    try:
        # st.info 只是做邏輯展示，實務上你會解除下方註解來讀取真正的檔案
        st.info("💡 將字典內的變數寫入記憶體，準備觸發下載。")
        context = {
            'project_name': project_name,
            'date': str(report_date),
            'spt_n60': spt_value,
            'q_ult': q_ult_value,
            'conclusion': conclusion
        }
        st.json(context)
        
        # 實務上的運作邏輯如下：
        # doc = DocxTemplate("template_report.docx") 
        # doc.render(context)
        # bio = io.BytesIO()
        # doc.save(bio)
        # st.download_button("📥 下載 Word 報告", data=bio.getvalue(), file_name=f"{project_name}.docx")
        
    except Exception as e:
        st.error("生成失敗，請確認同層目錄是否有放置 template_report.docx 模板。")