# excel_chatbot_app.py
import streamlit as st
import pandas as pd
from io import BytesIO
import os
import google.generativeai as genai
import tempfile
import importlib.util
import subprocess
import sys
import matplotlib.pyplot as plt
from gtts import gTTS


genai.configure(api_key="AIzaSyD4o3gh3V8VQ4UBOlgY5Bo-Jcq_lFCF-vk")

# STEP 2: Streamlit-safe Text-to-Speech using gTTS
def speak_text(text):
    try:
        tts = gTTS(text)
        filename = f"audio_{uuid.uuid4()}.mp3"
        tts.save(filename)
        audio_file = open(filename, 'rb')
        st.audio(audio_file.read(), format='audio/mp3')
        audio_file.close()
        os.remove(filename)
    except:
        st.warning("Audio generation failed.")

# STEP 3: Detect actual header row in Excel
def detect_actual_header_row(df_raw):
    max_unique = 0
    best_row_idx = 0
    for i in range(min(len(df_raw), 20)):
        unique_count = df_raw.iloc[i].nunique()
        non_empty_count = df_raw.iloc[i].notna().sum()
        if non_empty_count >= 3 and unique_count >= 3:
            if unique_count > max_unique:
                max_unique = unique_count
                best_row_idx = i
    return best_row_idx

# STEP 4: Load Excel file intelligently
def load_excel(file):
    df_raw = pd.read_excel(file, header=None)
    header_row_idx = detect_actual_header_row(df_raw)
    df = pd.read_excel(file, header=header_row_idx)
    df.columns = [str(col).strip() for col in df.columns]
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df = df.dropna(how="all").reset_index(drop=True)
    return df

# STEP 5: Generate code from Gemini
def generate_python_code(user_query, df_columns):
    prompt = f"""
You are a Python data analyst. Write Python code for the following query:
- Wrap everything inside: def process_dataframe_query(df, query):
- Return result
- Handle DataFrame queries: sum, filter, count, plot (matplotlib)
- DataFrame columns: {', '.join(df_columns)}
- Query: {user_query}
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text

# STEP 6: Execute generated code safely
def execute_code_query(df, user_query):
    code = generate_python_code(user_query, df.columns)
    code_block = code.split("```python")[-1].split("```")[0].strip()

    with open("generated_code.py", "w") as f:
        f.write(code_block)

    try:
        spec = importlib.util.spec_from_file_location("gen_code", "generated_code.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.process_dataframe_query(df, user_query)
        return result
    except Exception as e:
        return f"Error executing generated code: {e}"

# STEP 7: Save result as Excel
def save_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output

# STEP 8: Main Streamlit app
def main():
    st.set_page_config(page_title="Excel Mate", layout="wide")
    st.title("📊 Excel Mate - Your AI-Powered Excel Assistant")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📂 Upload Excel File")
        file = st.file_uploader("Upload .xlsx file", type="xlsx")
        if file:
            df = load_excel(file)
            st.session_state["df"] = df

            st.success("✅ File uploaded and cleaned.")
            st.dataframe(df.head(10), use_container_width=True)

            st.download_button(
                label="⬇ Download Cleaned Excel",
                data=save_to_excel(df),
                file_name="cleaned_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col2:
        st.subheader("💬 Ask a Question")
        if "df" in st.session_state:
            with st.form("query_form"):
                user_query = st.text_input("Ask something about your data:")
                submitted = st.form_submit_button("Submit")

            if submitted and user_query:
                with st.spinner("🔍 Analyzing..."):
                    result = execute_code_query(st.session_state["df"], user_query)

                st.markdown("### 📌 Result")
                if isinstance(result, pd.DataFrame):
                    st.dataframe(result)
                    speak_text("Here is your data.")
                elif isinstance(result, plt.Figure):
                    st.pyplot(result)
                    speak_text("Here is the chart you requested.")
                elif isinstance(result, (int, float, str)):
                    st.success(result)
                    speak_text(str(result))
                elif isinstance(result, list):
                    st.write(result)
                    speak_text("Here is the list.")
                else:
                    st.warning("❌ I couldn’t process that request.")
                    st.code(str(result))
                    speak_text("Sorry, I couldn’t process that.")
        else:
            st.info("📎 Please upload a file to begin.")

if __name__ == "__main__":
    main()
