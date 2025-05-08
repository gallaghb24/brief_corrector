from dotenv import load_dotenv
import os

load_dotenv()  
openai.api_key = os.getenv("OPENAI_API_KEY")

import os
import io
import streamlit as st
import pandas as pd
import openai

# Configuration
API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = API_KEY

st.set_page_config(page_title="Brand Name Corrector", layout="wide")
st.title("Excel Brand Name Spellchecker")

# Known brand list
KNOWN_BRANDS = [
    "L'Oréal", "Maybelline", "Garnier", "NYX", "Essie",
    "Kiehl’s", "CeraVe", "Vichy", "Lancôme", "Urban Decay",
    "La Roche-Posay", "YSL"
]

PROMPT_TEMPLATE = '''You are a brand name correction assistant. I will upload the contents of an Excel file that contains marketing brief information. The text may include misspelled brand names, and your job is to act like a brand name spellchecker.

Your task is to:
- Read the text exactly as it appears in the Excel cells.
- Identify any brand names mentioned, even if they are misspelled.
- Correct the brand names to their proper spelling, based on the known list below.
- Return the corrected content in CSV format with the same shape, row and column order preserved.

Important:
- Do not rephrase or summarise anything.
- Only correct brand names.
- Preserve line breaks, punctuation, and all non-brand content exactly as it was.
- If no brand name is misspelled, return the text unchanged.

Known correct brand names:
'''+ ", ".join(KNOWN_BRANDS) + '''

Here is the CSV content. Return only the CSV, nothing else:
```
{csv_input}
```'''

# File upload
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])

if uploaded_file:
    # Read into DataFrame
    try:
        df = pd.read_excel(uploaded_file, sheet_name=None)
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        st.stop()

    all_sheets = {}
    for sheet_name, sheet_df in df.items():
        # Convert each sheet to CSV
        csv_buf = io.StringIO()
        sheet_df.to_csv(csv_buf, index=False)
        csv_input = csv_buf.getvalue()

        # Construct prompt
        prompt = PROMPT_TEMPLATE.format(csv_input=csv_input)

        # Call OpenAI API
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            corrected_csv = response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

        # Parse corrected CSV back to DataFrame
        try:
            corrected_df = pd.read_csv(io.StringIO(corrected_csv))
        except Exception as e:
            st.error(f"Failed to parse corrected CSV: {e}")
            st.text_area("Corrected CSV output", corrected_csv)
            st.stop()

        all_sheets[sheet_name] = corrected_df

    # Prepare output Excel
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
        for sheet_name, sheet_df in all_sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
    output_buffer.seek(0)

    # Download button
    st.download_button(
        label="Download corrected Excel",
        data=output_buffer,
        file_name="corrected_brands.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
