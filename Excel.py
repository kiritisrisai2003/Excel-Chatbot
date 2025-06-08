# excel_chatbot_app.py
import streamlit as st
import pandas as pd
from io import BytesIO
import os
import google.generativeai as genai
import tempfile
import importlib
import subprocess
import sys
import matplotlib.pyplot as plt
import pyttsx3
from dotenv import load_dotenv  # ✅ Important for .env support

# STEP 1: Load env vars early
load_dotenv()

# STEP 2: Configure Gemini
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
try:
    import xlsxwriter
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "xlsxwriter"])
    import xlsxwriter

# STEP 3: Initialize TTS after env loaded
tts_engine = pyttsx3.init()
def speak_text(text):
    tts_engine.say(text)
    tts_engine.runAndWait()

def load_excel(file):
    return pd.read_excel(file)

def normalize_percentages(df, column_name):
    if column_name in df.columns:
        df[column_name] = df[column_name] * 100
    return df

def delete_first_last_lines(filepath):
    try:
        with open(filepath, 'r') as f_in:
            lines = f_in.readlines()
        if len(lines) > 2:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f_out:
                f_out.writelines(lines[1:-1])
            os.replace(f_out.name, filepath)
        elif len(lines) > 0:
            with open(filepath, 'w') as f:
                f.write("")
    except FileNotFoundError:
        print(f"File not found: {filepath}")
    except Exception as e:
        print(f"Error: {e}")

def generate_python_code(user_query, df_columns):
    prompt = f"""
    You are a Python data analysis and visualization expert. Your task is to generate Python code that processes a Pandas DataFrame based on a user's natural language query. The generated function should:

    1. Be named process_dataframe_query.
    2. Accept two arguments:
       - df: A Pandas DataFrame containing the data.
       - query: A string containing the user's query.
    3. Perform operations or visualizations as described in the query.
    4. Return one of the following based on the query:
       - A new Pandas DataFrame (e.g., after filtering, sorting, or grouping).
       - A summary statistic (e.g., total, mean, or count).
       - A Matplotlib figure for visualizations (e.g., bar chart, pie chart, or scatter plot).

    Important:  
    - Do NOT call plt.show() or any display function inside the generated code.  
    - Just create and return the Matplotlib figure object if visualization is requested.
    - When filtering task names or other string fields, do case-insensitive matching (e.g., use .str.lower()).

    
    # rest of your function code



Guidelines:
- For visualization queries, create the appropriate chart and return the Matplotlib figure object.
- For data transformations (e.g., filtering or sorting), return a new DataFrame.
- If the query is unclear or unsupported, return an error message as a string.

Examples:
1. Query: "Show me the progress in a pie chart"
   - Output: A pie chart visualizing the "Progress" column's percentage distribution.

2. Query: "Filter tasks with progress less than 50% and show them"
   - Output: A DataFrame filtered where "Progress" is less than 50%.

3. Query: "What is the average progress across all projects?"
   - Output: A number representing the average progress.

DataFrame Schema:
- Assume the DataFrame has the following columns: {', '.join(df_columns)}. These column names are case-sensitive.

User Query: {user_query}
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    code = response.text.strip()
    return code

def execute_code_query(df, user_query):
    code = generate_python_code(user_query, df.columns)
    file_path = "generated_code.py"
    try:
        with open(file_path, "w") as f:
            f.write(code)
        delete_first_last_lines(file_path)

        spec = importlib.util.spec_from_file_location("generated_module", file_path)
        generated_module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(generated_module)
        except ModuleNotFoundError as e:
            missing = str(e).split("'")[1]
            subprocess.check_call([sys.executable, "-m", "pip", "install", missing])
            spec.loader.exec_module(generated_module)

        result = generated_module.process_dataframe_query(df, user_query)
        os.remove(file_path)
        return result

    except Exception as e:
        return f"Error executing generated code: {e}"

def save_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output

def main():
    st.set_page_config(page_title="Excel Mate - Your Data Assistant", layout="wide")
    st.title("Excel Mate")

    # Create two clean columns
    col1, col2 = st.columns([1, 2], gap="large")

    with col1:
        st.subheader("1️⃣ Upload Your Excel File")
        uploaded_file = st.file_uploader("Upload a .xlsx file", type="xlsx")

        if uploaded_file:
            df = load_excel(uploaded_file)
            df = normalize_percentages(df, "Progress")
            st.session_state["df"] = df

            st.markdown("---")
            with st.expander("Preview Uploaded Data", expanded=False):
                st.dataframe(df.head(10), use_container_width=True)

            st.download_button(
                label="Download Cleaned Excel File",
                data=save_to_excel(df),
                file_name="updated_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Upload an Excel file to start using Excel Mate.")

    with col2:
        st.subheader("2️⃣ Want to know some thing about your data")

        if "df" in st.session_state:
            with st.form("query_form"):
                user_query = st.text_input(" Let's explore your excel", placeholder="Type your query here...")
                submitted = st.form_submit_button("Submit")

            if submitted and user_query:
                with st.spinner("Analyzing your data..."):
                    result = execute_code_query(st.session_state["df"], user_query)

                st.markdown("#### Result")
                if isinstance(result, pd.DataFrame):
                    st.dataframe(result, use_container_width=True)
                    st.download_button(
                        label="Download Result as Excel",
                        data=save_to_excel(result),
                        file_name="filtered_result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    tts_text = "Here is the filtered data displayed on screen."
                elif isinstance(result, plt.Figure):
                    st.pyplot(result)
                    tts_text = "Here is the chart you requested."
                elif isinstance(result, (int, float, str)):
                    st.success(f"{result}")
                    tts_text = str(result)
                else:
                    st.warning("Sorry, I couldn’t understand that output.")
                    tts_text = "Sorry, I couldn't understand that output."

                # Speak the answer aloud
                speak_text(tts_text)
        else:
            st.warning("Please upload a file first to ask questions.")


if __name__ == "__main__":
    main()
