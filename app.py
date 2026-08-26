import urllib.parse
from datetime import datetime
from google import genai
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
from pydantic import BaseModel
import streamlit as st

st.set_page_config(page_title="TCG Scanner & Stock", layout="wide")

# Initialisation de Gemini
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


class UniversalCard(BaseModel):
  game_name: str
  card_name: str
  set_name: str
  card_number: str
  cardmarket_slug: str


# Connexion Google Sheets
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scopes
)
gc = gspread.authorize(creds)
sheet = gc.open("Stock_Cartes_TCG").sheet1

# Interface
tab1, tab2 = st.tabs(["📸 Scanner", "📦 Stock"])

with tab1:
  st.header("Ajouter une carte")
  img = st.camera_input("Prendre une photo") or st.file_uploader(
      "Ou importer une image", type=["jpg", "png", "webp"]
  )

  if img:
    with st.spinner("Analyse par l'IA..."):
      prompt = "Identifie cette carte TCG. Donne le slug exact de la catégorie Cardmarket dans 'cardmarket_slug' (ex: Magic, Pokemon, YuGiOh, Lorcana, OnePiece, DragonBallSuper)."
      res = client.models.generate_content(
          model="gemini-2.5-flash",
          contents=[{"mime_type": "image/jpeg", "data": img.getvalue()}, prompt],
          config={
              "response_mime_type": "application/json",
              "response_schema": UniversalCard,
          },
      )
      card = res.parsed

    st.success(f"Détecté : {card.card_name}")
    st.write(
        f"**Jeu :** {card.game_name} | **Extension :** {card.set_name} |"
        f" **Numéro :** {card.card_number}"
    )

    query = urllib.parse.quote(f"{card.card_name} {card.card_number}".strip())
    cardmarket_url = f"https://www.cardmarket.com/fr/{card.cardmarket_slug}/Products/Search?searchString={query}"

    with st.form("add_form"):
      qty = st.number_input("Quantité", min_value=1, value=1)
      if st.form_submit_button("Sauvegarder dans le stock"):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet.append_row([
            now,
            card.game_name,
            card.card_name,
            card.set_name,
            card.card_number,
            qty,
            cardmarket_url,
        ])
        st.success("Carte enregistrée dans Google Sheets !")

with tab2:
  st.header("Mon Inventaire")
  if st.button("Rafraîchir les données"):
    st.rerun()

  records = sheet.get_all_records()
  if records:
    df = pd.DataFrame(records)
    col1, col2 = st.columns(2)
    col1.metric("Cartes uniques", len(df))
    col2.metric("Total exemplaires", df["Quantité"].sum())

    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Lien Cardmarket": st.column_config.LinkColumn("Fiche Prix")
        },
    )
  else:
    st.info("Aucune carte scannée pour l'instant.")
