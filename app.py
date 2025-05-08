import io
import streamlit as st
import pandas as pd
import openai

# ─── CONFIGURE ────────────────────────────────────────────────────────────────
# Read your OpenAI key from Streamlit Cloud's Secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="Brand Name Corrector", layout="wide")
st.title("Excel Brand Name Spellchecker")

# ─── BRANDS & PROMPT ───────────────────────────────────────────────────────────
KNOWN_BRANDS = [
    "L'Oréal", "Maybelline", "Garnier", "NYX", "Essie",
    "Kiehl’s", "CeraVe", "Vichy", "Lancôme", "Urban Decay",
    "La Roche-Posay", "YSL"
]

PROMPT_TEMPLATE = """You are a brand name correction assistant. I will upload the contents of an Excel file that contains marketing brief information. The text may include misspelled brand names, and your job is to act like a brand name spellchecker.

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
{brands}

Here is the CSV content. Return only the CSV, nothing else:
```
{csv_input}
```"""

# ─── FILE UPLOAD & PROCESSING ─────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])

if uploaded_file:
    try:
        sheets = pd.read_excel(uploaded_file, sheet_name=None)
    except Exception as e:
        st.error(f"❌ Error reading Excel file: {e}")
        st.stop()

    corrected_sheets = {}

    for sheet_name, df in sheets.items():
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        csv_in = buf.getvalue()

        prompt = PROMPT_TEMPLATE.format(
            brands=", ".join(KNOWN_BRANDS),
            csv_input=csv_in
        )

        try:
            res = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            corrected_csv = res.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"❌ OpenAI API error: {e}")
            st.stop()

        # strip code fences if ChatGPT wrapped with ```
        lines = corrected_csv.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        corrected_csv_stripped = "\n".join(lines)

        try:
            corrected_df = pd.read_csv(io.StringIO(corrected_csv_stripped))
        except Exception as e:
            st.error(f"❌ Failed to parse corrected CSV: {e}")
            st.code(corrected_csv_stripped, language="csv")
            st.stop()

        corrected_sheets[sheet_name] = corrected_df

    out_buffer = io.BytesIO()
    with pd.ExcelWriter(out_buffer, engine="openpyxl") as writer:
        for name, cdf in corrected_sheets.items():
            cdf.to_excel(writer, sheet_name=name, index=False)
    out_buffer.seek(0)

    st.download_button(
        label="🚀 Download corrected Excel",
        data=out_buffer,
        file_name="corrected_brands.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
