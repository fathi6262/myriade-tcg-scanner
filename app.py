import urllib.parse
from datetime import datetime
from google import genai
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
from PIL import Image
from pydantic import BaseModel
import streamlit as st

# ---------------------------------------------------------
# 1. CONFIGURATION DE LA PAGE & STYLES CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Myriade Games — TCG Scanner", page_icon="🔮", layout="wide"
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=Inter:wght@400;600&display=swap');

    .stApp {
        background: radial-gradient(circle at 50% 0%, #1a0b2e 0%, #080b11 70%) !important;
        color: #f1f5f9;
        font-family: 'Inter', sans-serif;
    }

    .brand-title {
        font-family: 'Rajdhani', sans-serif;
        font-size: 3rem;
        font-weight: 700;
        text-align: center;
        background: linear-gradient(90deg, #a855f7 0%, #00f0ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    .brand-subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 0.95rem;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 2rem;
    }

    div[data-testid="stForm"], div[data-testid="stMetric"], .stDataFrame, div[data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.65) !important;
        border: 1px solid rgba(0, 240, 255, 0.2) !important;
        border-radius: 12px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(10px);
    }

    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #94a3b8 !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }
    
    button[aria-selected="true"] {
        background: linear-gradient(90deg, rgba(168, 85, 247, 0.25), rgba(0, 240, 255, 0.25)) !important;
        color: #00f0ff !important;
        border: 1px solid #00f0ff !important;
        box-shadow: 0 0 15px rgba(0, 240, 255, 0.3);
    }

    .stButton > button, div[data-testid="stForm"] button {
        background: linear-gradient(90deg, #7c3aed 0%, #0284c7 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        box-shadow: 0 0 15px rgba(0, 240, 255, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover, div[data-testid="stForm"] button:hover {
        box-shadow: 0 0 25px rgba(168, 85, 247, 0.8) !important;
        transform: translateY(-2px);
    }

    a {
        color: #00f0ff !important;
        text-decoration: none !important;
        font-weight: 600;
    }

    div[data-testid="stMetricValue"] {
        color: #00f0ff !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 2.2rem !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# En-tête
st.markdown(
    '<div class="brand-title">✨ Myriade Games</div>', unsafe_allow_html=True
)
st.markdown(
    '<div class="brand-subtitle">Une multitude d\'univers, une seule'
    " communauté</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 2. CONFIGURATION DES API ET ACCÈS
# ---------------------------------------------------------
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

SPREADSHEET_ID = "1rd14kfknX9z1P-72V_G2ITVBv2K1aMnLy5H_qt8c6eo"

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scopes
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1


# ---------------------------------------------------------
# 3. SCHÉMA DE DONNÉES
# ---------------------------------------------------------
class UniversalCard(BaseModel):
  game_name: str
  card_name: str
  set_name: str
  card_number: str
  cardmarket_slug: str


# ---------------------------------------------------------
# 4. APPLICATION STREAMLIT
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📸 Scanner une carte", "📦 Gestion du Stock"])

# --- ONGLET 1 : SCANNER ---
with tab1:
  source_type = st.radio(
      "Source de l'image :",
      ["💻 Fichier (PC / Galerie)", "📷 Caméra"],
      horizontal=True,
  )

  if source_type == "💻 Fichier (PC / Galerie)":
    image_input = st.file_uploader(
        "Dépose l'image de la carte ici", type=["jpg", "jpeg", "png", "webp"]
    )
  else:
    image_input = st.camera_input("Prendre une photo de la carte")

  if image_input:
    with st.spinner("Analyse visuelle en cours par l'IA..."):
      pil_image = Image.open(image_input).convert("RGB")

      prompt = (
          "Identifie cette carte TCG. Donne le slug exact de la catégorie"
          " Cardmarket dans 'cardmarket_slug' (ex: Magic, Pokemon, YuGiOh,"
          " Lorcana, OnePiece, DragonBallSuper, FleshAndBlood)."
      )

      response = client.models.generate_content(
          model="gemini-3.6-flash",
          contents=[pil_image, prompt],
          config={
              "response_mime_type": "application/json",
              "response_schema": UniversalCard,
          },
      )
      card = response.parsed

    st.markdown("---")
    st.subheader(f"🔮 {card.card_name}")

    col1, col2 = st.columns(2)
    with col1:
      st.markdown(f"**Jeu :** `{card.game_name}`")
      st.markdown(f"**Extension :** {card.set_name}")
    with col2:
      st.markdown(f"**Numéro :** {card.card_number}")

    search_query = urllib.parse.quote(
        f"{card.card_name} {card.card_number}".strip()
    )
    cardmarket_url = f"https://www.cardmarket.com/fr/{card.cardmarket_slug}/Products/Search?searchString={search_query}"

    st.markdown(
        f'<p style="margin-top: 10px;"><a href="{cardmarket_url}"'
        ' target="_blank">↗ Consulter la cote en direct sur'
        " Cardmarket</a></p>",
        unsafe_allow_html=True,
    )

    with st.form("add_to_stock_form"):
      quantite = st.number_input(
          "Quantité à ajouter au stock", min_value=1, value=1, step=1
      )
      submit_button = st.form_submit_button("⚡ Enregistrer dans l'inventaire")

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
            f"✅ {quantite}x {card.card_name} ajouté(s) à la base de données !"
        )

# --- ONGLET 2 : OUTIL DE GESTION DE STOCK ---
with tab2:
  try:
    records = sheet.get_all_records()

    if records:
      df = pd.DataFrame(records)

      df["Quantité"] = (
          pd.to_numeric(df["Quantité"], errors="coerce").fillna(1).astype(int)
      )

      # Metrics
      col_m1, col_m2, col_m3 = st.columns(3)
      col_m1.metric("Références uniques", len(df))
      col_m2.metric("Total exemplaires", int(df["Quantité"].sum()))
      col_m3.metric("Jeux en stock", df["Jeu"].nunique() if "Jeu" in df else 0)

      st.markdown("---")

      # --- SECTION 1 : AJUSTEMENT RAPIDE ---
      with st.expander(
          "⚡ **Ajustement Rapide (Ajouter / Retirer / Supprimer)**",
          expanded=True,
      ):
        df["label_select"] = (
            df["Jeu"]
            + " — "
            + df["Nom"]
            + " ("
            + df["Numéro"]
            + ") [Stock: "
            + df["Quantité"].astype(str)
            + "]"
        )
        selected_label = st.selectbox(
            "Rechercher et sélectionner une carte à modifier :",
            df["label_select"].tolist(),
        )

        if selected_label:
          selected_idx = df[df["label_select"] == selected_label].index[0]
          current_qty = int(df.loc[selected_idx, "Quantité"])
          card_title = df.loc[selected_idx, "Nom"]

          col_b1, col_b2, col_b3, col_b4 = st.columns(4)

          if col_b1.button("➕ Ajouter (+1)"):
            df.loc[selected_idx, "Quantité"] += 1
            df_to_save = df.drop(columns=["label_select"])
            sheet.clear()
            sheet.update(
                [df_to_save.columns.values.tolist()]
                + df_to_save.astype(str).values.tolist()
            )
            st.toast(f"+1 {card_title} (Nouveau stock : {current_qty + 1})")
            st.rerun()

          if col_b2.button("➖ Retirer (-1)"):
            if current_qty > 1:
              df.loc[selected_idx, "Quantité"] -= 1
              df_to_save = df.drop(columns=["label_select"])
              sheet.clear()
              sheet.update(
                  [df_to_save.columns.values.tolist()]
                  + df_to_save.astype(str).values.tolist()
              )
              st.toast(f"-1 {card_title} (Nouveau stock : {current_qty - 1})")
            else:
              df = df.drop(selected_idx)
              df_to_save = df.drop(columns=["label_select"])
              sheet.clear()
              if not df_to_save.empty:
                sheet.update(
                    [df_to_save.columns.values.tolist()]
                    + df_to_save.astype(str).values.tolist()
                )
              st.toast(f"🗑️ {card_title} retiré du stock (Quantité = 0)")
            st.rerun()

          if col_b3.button("🗑️ Supprimer l'entrée"):
            df = df.drop(selected_idx)
            df_to_save = df.drop(columns=["label_select"])
            sheet.clear()
            if not df_to_save.empty:
              sheet.update(
                  [df_to_save.columns.values.tolist()]
                  + df_to_save.astype(str).values.tolist()
              )
            st.toast(f"🗑️ {card_title} supprimé de la base.")
            st.rerun()

          if col_b4.button("🔄 Rafraîchir"):
            st.rerun()

      df = df.drop(columns=["label_select"])

      # --- SECTION 2 : ÉDITEUR EN GRILLE DE MASSE ---
      st.markdown("### ✏️ Éditeur de masse (Format Tableur)")
      st.caption(
          "Modifie directement la colonne **Quantité** ci-dessous, puis clique"
          " sur **Sauvegarder**."
      )

      edited_df = st.data_editor(
          df,
          use_container_width=True,
          num_rows="dynamic",
          disabled=[
              "Date",
              "Jeu",
              "Nom",
              "Extension",
              "Numéro",
              "Lien Cardmarket",
          ],
          column_config={
              "Lien Cardmarket": st.column_config.LinkColumn("Fiche Prix"),
              "Date": st.column_config.TextColumn("Date d'ajout"),
              "Quantité": st.column_config.NumberColumn(
                  "Quantité", min_value=0, step=1, required=True
              ),
          },
          hide_index=True,
      )

      if st.button("💾 Sauvegarder les modifications de la grille"):
        edited_df["Quantité"] = pd.to_numeric(
            edited_df["Quantité"], errors="coerce"
        ).fillna(0)
        final_df = edited_df[edited_df["Quantité"] > 0]

        sheet.clear()
        sheet.update(
            [final_df.columns.values.tolist()]
            + final_df.astype(str).values.tolist()
        )
        st.success("✅ Stock mis à jour avec succès sur Google Sheets !")
        st.rerun()

    else:
      st.info(
          "L'inventaire est actuellement vide. Scanne une carte pour commencer !"
      )

  except Exception as e:
    st.error(f"Erreur d'accès à la base de données : {e}")
