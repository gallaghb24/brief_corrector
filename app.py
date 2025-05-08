import io
import streamlit as st
import pandas as pd
import openai

# ─── CONFIGURE ────────────────────────────────────────────────────────────────
openai.api_key = st.secrets["OPENAI_API_KEY"]
st.set_page_config(page_title="Brand Name Corrector", layout="wide")
st.title("Excel Brand Name Spellchecker")

# ─── KNOWN BRANDS ─────────────────────────────────────────────────────────────
KNOWN_BRANDS = [
    "L'Oréal", "Maybelline", "Garnier", "NYX", "Essie",
    "Kiehl’s", "CeraVe", "Vichy", "Lancôme", "Urban Decay",
    "La Roche-Posay", "YSL", "Izzy Miyake", "Police", "Zadig and Voltaire",
    "Ghost", "John Paul Gaultier", "Playboy", "Hugo Boss", "Ted Baker",
    "Armani", "Giorgio Armani", "Misguided", "Sarah Jessica Parker",
    "Jennifer Lopez", "Ariana Grande", "Marc Jacobs", "Paco Rabanne",
    "Guess", "DKNY", "Ralph Lauren", "Longhorn", "Thierry Mugler",
    "David Beckham", "Calvin Klein"
]

# ─── PROMPT TEMPLATE ──────────────────────────────────────────────────────────
PROMPT_TEMPLATE = """
You are a brand name correction assistant. I will provide the list of values from the 'brand' column of an Excel sheet. Your job is to correct any misspelled or abbreviated brand names, using only the known correct names below.

Task:
- Read each brand value exactly as given.
- If it is misspelled, correct it to one of the known brands.
- If it is an abbreviation (e.g. SJP, JPG, JLO, CK), expand it to the proper full brand name.
- If it is not a brand, or already correct, leave it unchanged.
- If you encounter an unfamiliar acronym or abbreviation that could plausibly map to one of the known brands, attempt to expand it.

Known correct brand names:
{brands}

Known abbreviations:
SJP -> Sarah Jessica Parker
JPG -> John Paul Gaultier
JLO -> Jennifer Lopez
CK  -> Calvin Klein

Return only the corrected values in CSV format with header 'brand' and rows in the same order. Do not include any extra text or formatting.
```
{csv_brands}
```"""

# ─── FILE UPLOAD & PROCESSING ─────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
if not uploaded_file:
    st.info("Please upload an .xlsx file with a 'brand' column.")
    st.stop()

try:
    sheets = pd.read_excel(uploaded_file, sheet_name=None)
except Exception as e:
    st.error(f"❌ Error reading Excel file: {e}")
    st.stop()

corrected_sheets = {}
for sheet_name, df in sheets.items():
    if 'brand' not in df.columns:
        corrected_sheets[sheet_name] = df
        continue

    # extract only the brand column
    brands_series = df['brand'].astype(str)
    buf = io.StringIO()
    brands_series.to_csv(buf, index=False, header=True)
    csv_brands = buf.getvalue()

    # call ChatGPT for corrections
    prompt = PROMPT_TEMPLATE.format(
        brands=", ".join(KNOWN_BRANDS),
        csv_brands=csv_brands
    )
    try:
        res = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0
        )
        corrected_output = res.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"❌ OpenAI API error: {e}")
        st.stop()

    # remove any code fences
    lines = corrected_output.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    corrected_csv = "\n".join(lines)

    # parse corrected CSV and replace column
    try:
        corrected_df = pd.read_csv(io.StringIO(corrected_csv))
    except Exception as e:
        st.error(f"❌ Failed to parse corrected CSV: {e}")
        st.code(corrected_csv, language="csv")
        st.stop()

    df['brand'] = corrected_df['brand']
    corrected_sheets[sheet_name] = df

# ─── EXPORT RESULTS ─────────────────────────────────────────────────────────────
out = io.BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as writer:
    for name, sheet in corrected_sheets.items():
        sheet.to_excel(writer, sheet_name=name, index=False)
out.seek(0)

st.download_button(
    label="🚀 Download corrected Excel",
    data=out,
    file_name="corrected_brands.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
