import urllib.parse
from datetime import datetime
from google import genai
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
from PIL import Image
from pydantic import BaseModel
import streamlit as st

st.set_page_config(page_title="TCG Scanner & Stock", layout="wide")

# ---------------------------------------------------------
# 1. CONFIGURATION DES API ET ACCÈS
# ---------------------------------------------------------

# Initialisation du client Gemini
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# COLLE ICI L'ID DE TON GOOGLE SHEETS (trouvable dans l'URL entre /d/ et /edit)
SPREADSHEET_ID = "1rd14kfknX9z1P-72V_G2ITVBv2K1aMnLy5H_qt8c6eo"

# Connexion à Google Sheets via le compte de service
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scopes
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1


# ---------------------------------------------------------
# 2. SCHÉMA DE DONNÉES (PYDANTIC)
# ---------------------------------------------------------
class UniversalCard(BaseModel):
  game_name: str
  card_name: str
  set_name: str
  card_number: str
  cardmarket_slug: str


# ---------------------------------------------------------
# 3. INTERFACE UTILISATEUR (STREAMLIT)
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📸 Scanner", "📦 Mon Stock"])

# --- ONGLET 1 : SCANNER ---
with tab1:
  st.header("Ajouter une carte au stock")
  image_input = st.camera_input("Prendre une photo") or st.file_uploader(
      "Ou importer une image", type=["jpg", "png", "webp"]
  )

  if image_input:
    with st.spinner("Analyse visuelle par l'IA..."):
      # Conversion de l'image en objet PIL pour l'API Gemini
      pil_image = Image.open(image_input)

      prompt = (
          "Identifie cette carte TCG. Donne le slug exact de la catégorie"
          " Cardmarket dans 'cardmarket_slug' (ex: Magic, Pokemon, YuGiOh,"
          " Lorcana, OnePiece, DragonBallSuper)."
      )

      # Appel à Gemini 2.5 Flash
      response = client.models.generate_content(
          model="gemini-2.5-flash",
          contents=[pil_image, prompt],
          config={
              "response_mime_type": "application/json",
              "response_schema": UniversalCard,
          },
      )
      card = response.parsed

    # Affichage des métadonnées
    st.success(f"Carte détectée : **{card.card_name}**")

    col1, col2 = st.columns(2)
    with col1:
      st.write(f"**Jeu :** {card.game_name}")
      st.write(f"**Extension :** {card.set_name}")
    with col2:
      st.write(f"**Numéro :** {card.card_number}")

    # Génération du lien de recherche Cardmarket
    search_query = urllib.parse.quote(
        f"{card.card_name} {card.card_number}".strip()
    )
    cardmarket_url = f"https://www.cardmarket.com/fr/{card.cardmarket_slug}/Products/Search?searchString={search_query}"

    st.markdown(f"[👉 **Voir la fiche et les prix sur Cardmarket**]({cardmarket_url})")

    # Formulaire de sauvegarde dans Google Sheets
    with st.form("add_to_stock_form"):
      quantite = st.number_input(
          "Quantité à ajouter", min_value=1, value=1, step=1
      )
      submit_button = st.form_submit_button("Sauvegarder dans mon Stock")

      if submit_button:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet.append_row([
            date_str,
            card.game_name,
            card.card_name,
            card.set_name,
            card.card_number,
            quantite,
            cardmarket_url,
        ])
        st.success(
            f"{quantite}x {card.card_name} ajouté(s) avec succès dans Google"
            " Sheets !"
        )

# --- ONGLET 2 : INVENTAIRE ---
with tab2:
  st.header("Gestion du stock")

  if st.button("Rafraîchir les données"):
    st.rerun()

  try:
    records = sheet.get_all_records()
    if records:
      df = pd.DataFrame(records)

      col_m1, col_m2 = st.columns(2)
      col_m1.metric("Cartes uniques", len(df))
      col_m2.metric(
          "Total exemplaires",
          int(df["Quantité"].sum()) if "Quantité" in df else 0,
      )

      st.dataframe(
          df,
          use_container_width=True,
          column_config={
              "Lien Cardmarket": st.column_config.LinkColumn("Fiche Prix")
          },
      )
    else:
      st.info("Aucune carte dans l'inventaire pour le moment.")
  except Exception as e:
    st.error(f"Erreur lors de la récupération des données : {e}")
