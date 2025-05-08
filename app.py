import io
import streamlit as st
import pandas as pd
import openai
import requests
from bs4 import BeautifulSoup
from openpyxl.utils import get_column_letter

# ─── CONFIG ────────────────────────────────────────────────────────────────────
openai.api_key = st.secrets.get("OPENAI_API_KEY")
st.set_page_config(page_title="AI Assisted Brand Name Corrector", layout="wide")
st.title("AI Assisted Brand Name Corrector")

# ─── APP SUMMARY ───────────────────────────────────────────────────────────────
st.markdown(
    "Welcome to the AI-Assisted Brand Name Corrector! Simply upload your Excel file, and the app scrapes the web for known correct brand names and corrects any misspellings it finds."
)

# ─── FETCH SUPERDRUG BRANDS ─────────────────────────────────────────────────────
def fetch_superdrug_brands():
    """
    Scrapes the Superdrug A-Z Brands page and returns a list of brand names.
    """
    url = "https://www.superdrug.com/a-z-brands"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select("ul li a")
    return [a.get_text(strip=True) for a in links]

# ─── MANUAL + DYNAMIC BRAND LIST ────────────────────────────────────────────────
MANUAL_BRANDS = [
    "L'Oréal", "Maybelline", "Garnier", "NYX", "Essie",
    "Kiehl’s", "CeraVe", "Vichy", "Lancôme", "Urban Decay",
    "La Roche-Posay", "YSL", "Izzy Miyake", "Police", "Zadig and Voltaire",
    "Ghost", "John Paul Gaultier", "Playboy", "Hugo Boss", "Ted Baker",
    "Armani", "Giorgio Armani", "Misguided", "Sarah Jessica Parker",
    "Jennifer Lopez", "Ariana Grande", "Marc Jacobs", "Paco Rabanne",
    "Guess", "DKNY", "Ralph Lauren", "Longhorn", "Thierry Mugler",
    "David Beckham", "Calvin Klein",
    "Olay", "Nivea", "Dove", "Simple", "Neutrogena", "E45",
    "Johnson & Johnson", "No7", "Rimmel", "Revlon", "Essence",
    "Bourjois", "Max Factor", "Hawaiian Tropic", "Aveeno",
    "Clean & Clear", "NARS", "Clinique", "Bobbi Brown",
    "Estée Lauder", "Chanel", "Dior", "Gucci", "Versace",
    "Dolce & Gabbana", "Burberry", "Lacoste", "Schwarzkopf",
    "TRESemmé"
]
try:
    SUPERDRUG_BRANDS = fetch_superdrug_brands()
except Exception:
    SUPERDRUG_BRANDS = []
KNOWN_BRANDS = list(dict.fromkeys(MANUAL_BRANDS + SUPERDRUG_BRANDS))

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

# ─── FILE UPLOAD & PROCESSING ───────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
if not uploaded_file:
    st.info("Please upload an .xlsx file containing a 'brand' column.")
    st.stop()

try:
    sheets = pd.read_excel(uploaded_file, sheet_name=None)
except Exception as e:
    st.error(f"❌ Error reading Excel file: {e}")
    st.stop()

corrected_sheets = {}
processed_any = False

for sheet_name, df in sheets.items():
    brand_cols = [col for col in df.columns if col.lower() == 'brand']
    if not brand_cols:
        corrected_sheets[sheet_name] = df
        continue

    processed_any = True
    col = brand_cols[0]
    brands_series = df[col].astype(str)
    buf = io.StringIO()
    brands_series.to_csv(buf, index=False, header=True)
    csv_brands = buf.getvalue()

    prompt = PROMPT_TEMPLATE.format(
        brands=", ".join(KNOWN_BRANDS),
        csv_brands=csv_brands
    )
    with st.spinner(f"Correcting brands in '{sheet_name}'..."):
        try:
            res = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user",   "content": prompt}
                ],
                temperature=0
            )
        except Exception as e:
            st.error(f"🚫 OpenAI API error: {e}")
            st.stop()

    corrected_output = res.choices[0].message.content.strip()
    lines = [l for l in corrected_output.splitlines() if not l.strip().startswith("```")]
    corrected_csv = "\n".join(lines)

    try:
        corrected_df = pd.read_csv(io.StringIO(corrected_csv))
    except Exception as e:
        st.error(f"❌ Failed to parse corrected CSV: {e}")
        st.code(corrected_csv, language="csv")
        st.stop()

    df[col] = corrected_df['brand']
    corrected_sheets[sheet_name] = df

if not processed_any:
    st.error("No sheets had a 'brand' column. Nothing to correct.")
    st.stop()

# ─── EXPORT RESULTS ─────────────────────────────────────────────────────────────
out = io.BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as writer:
    for name, sheet in corrected_sheets.items():
        sheet.to_excel(writer, sheet_name=name, index=False)
        # auto-fit columns to content
        ws = writer.sheets[name]
        for idx, col in enumerate(sheet.columns, 1):
            max_length = max(
                sheet[col].astype(str).map(len).max(),
                len(col)
            )
            ws.column_dimensions[get_column_letter(idx)].width = max_length + 2
out.seek(0)

st.success("✅ Brand correction complete!")

st.download_button(
    label="🚀 Download corrected Excel",
    data=out,
    file_name="corrected_brands.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
