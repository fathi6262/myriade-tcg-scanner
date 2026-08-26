from datetime import datetime
import io
import re
import urllib.parse
from google import genai
from google.genai import types
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
        font-size: 2.8rem;
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
        font-size: 0.85rem;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 1.5rem;
    }

    div[data-testid="stForm"], .stDataFrame {
        background: rgba(15, 23, 42, 0.65) !important;
        border: 1px solid rgba(0, 240, 255, 0.2) !important;
        border-radius: 12px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(10px);
    }

    .kpi-card {
        background: rgba(15, 23, 42, 0.7) !important;
        border: 1px solid rgba(0, 240, 255, 0.3) !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        text-align: center !important;
        box-shadow: 0 0 15px rgba(0, 240, 255, 0.08) !important;
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    .kpi-card:hover {
        border-color: #a855f7 !important;
        transform: translateY(-2px);
    }

    .kpi-label {
        font-size: 0.85rem !important;
        color: #94a3b8 !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        margin-bottom: 4px !important;
    }

    .kpi-value {
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 2.4rem !important;
        font-weight: 700 !important;
        background: linear-gradient(90deg, #00f0ff 0%, #a855f7 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        line-height: 1.1 !important;
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
        font-size: 1rem !important;
        font-weight: 700 !important;
        box-shadow: 0 0 12px rgba(0, 240, 255, 0.2) !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover, div[data-testid="stForm"] button:hover {
        box-shadow: 0 0 20px rgba(168, 85, 247, 0.8) !important;
        transform: translateY(-1px);
    }

    a {
        color: #00f0ff !important;
        text-decoration: none !important;
        font-weight: 600;
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
api_key = st.secrets["GEMINI_API_KEY"].strip()
client = genai.Client(api_key=api_key)

SPREADSHEET_ID = "1rd14kfknX9z1P-72V_G2ITVBv2K1aMnLy5H_qt8c6eo"

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scopes
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1


# ---------------------------------------------------------
# 3. SCHÉMA DE DONNÉES & FONCTIONS
# ---------------------------------------------------------
class UniversalCard(BaseModel):
  game_name: str
  card_name: str
  set_name: str
  card_number: str
  cardmarket_slug: str
  cardmarket_search_term: str


def update_sheet_data(dataframe):
  sheet.clear()
  sheet.update(
      [dataframe.columns.values.tolist()] + dataframe.astype(str).values.tolist()
  )


def render_kpi(label: str, value: str, icon: str = ""):
  return f"""
    <div class="kpi-card">
        <div class="kpi-label">{icon} {label}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """


def build_cardmarket_url(slug: str, search_term: str) -> str:
  clean_slug = slug.strip().split("/")[0]
  clean_term = re.sub(r"[\-\/,\.:#]", " ", search_term)
  clean_term = " ".join(clean_term.split())
  search_query = urllib.parse.quote(clean_term)
  return f"https://www.cardmarket.com/fr/{clean_slug}/Products/Search?searchString={search_query}"


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
      # Conversion de l'image PIL en octets JPEG
      pil_image = Image.open(image_input).convert("RGB")
      img_byte_arr = io.BytesIO()
      pil_image.save(img_byte_arr, format="JPEG")
      image_bytes = img_byte_arr.getvalue()

      image_part = types.Part.from_bytes(
          data=image_bytes, mime_type="image/jpeg"
      )

      prompt = """
      Identifie cette carte TCG.
      - Dans 'cardmarket_slug', donne STRICTEMENT la catégorie principale Cardmarket en UN SEUL MOT (ex: Pokemon, Magic, YuGiOh, Lorcana, OnePiece, DragonBallSuper, Riftbound). NE METS JAMAIS de sous-dossier ou de slash.
      - Dans 'cardmarket_search_term', COMBINE le NOM DE LA CARTE et le NOM DE L'EXTENSION (ou code d'extension).
        RÈGLES STRICTES : RETIRE TOUS les slashes (/), les tirets (-) et les numéros de collection sous forme de fraction.
        Exemple 1 : Carte "Dracaufeu", Extension "Set de Base", Numéro "4/102" -> "Dracaufeu Set de Base"
        Exemple 2 : Carte "Ahri - Inquisitive", Extension "Riftbound" -> "Ahri Inquisitive Riftbound"
        Exemple 3 : Carte "Charizard ex", Extension "151", Numéro "199/165" -> "Charizard ex 151"
      """

      try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=UniversalCard,
            ),
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

        cardmarket_url = build_cardmarket_url(
            card.cardmarket_slug, card.cardmarket_search_term
        )

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
          submit_button = st.form_submit_button(
              "⚡ Enregistrer dans l'inventaire"
          )

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
                f"✅ {quantite}x {card.card_name} ajouté(s) à la base de"
                " données !"
            )

      except Exception as e:
        st.error(
            "❌ Erreur lors de l'appel à l'API Google : Vérifie que la clé n'est"
            f" pas restreinte dans Google Cloud.\nDétail de l'erreur : {e}"
        )

# --- ONGLET 2 : INVENTAIRE ---
with tab2:
  try:
    records = sheet.get_all_records()

    if records:
      df = pd.DataFrame(records)
      df["Quantité"] = (
          pd.to_numeric(df["Quantité"], errors="coerce").fillna(1).astype(int)
      )

      col_m1, col_m2, col_m3 = st.columns(3)

      with col_m1:
        st.markdown(
            render_kpi("Références uniques", str(len(df)), "🎴"),
            unsafe_allow_html=True,
        )
      with col_m2:
        st.markdown(
            render_kpi(
                "Total exemplaires", str(int(df["Quantité"].sum())), "📦"
            ),
            unsafe_allow_html=True,
        )
      with col_m3:
        st.markdown(
            render_kpi(
                "Jeux en stock",
                str(df["Jeu"].nunique() if "Jeu" in df else 0),
                "🎮",
            ),
            unsafe_allow_html=True,
        )

      st.markdown("<br>", unsafe_allow_html=True)

      col_search, col_filter = st.columns([2, 1])
      with col_search:
        search_term = st.text_input(
            "🔍 Rechercher une carte...",
            placeholder="Nom de la carte, numéro...",
        )
      with col_filter:
        jeux_dispos = ["Tous les jeux"] + sorted(df["Jeu"].unique().tolist())
        selected_game = st.selectbox("🎮 Filtrer par jeu", jeux_dispos)

      filtered_df = df.copy()
      if selected_game != "Tous les jeux":
        filtered_df = filtered_df[filtered_df["Jeu"] == selected_game]
      if search_term:
        filtered_df = filtered_df[
            filtered_df["Nom"].str.contains(search_term, case=False, na=False)
            | filtered_df["Numéro"].str.contains(
                search_term, case=False, na=False
            )
        ]

      st.markdown(f"**Cartes affichées ({len(filtered_df)})**")

      for idx, row in filtered_df.iterrows():
        with st.container():
          c_info, c_qty, c_actions, c_link = st.columns([4, 1.5, 2.5, 1.5])

          with c_info:
            st.markdown(f"**{row['Nom']}** `{row['Numéro']}`")
            st.caption(f"{row['Jeu']} • {row['Extension']}")

          with c_qty:
            st.markdown(f"### {row['Quantité']} ex.")

          with c_actions:
            b1, b2, b3 = st.columns(3)
            if b1.button("➕", key=f"add_{idx}"):
              df.loc[idx, "Quantité"] += 1
              update_sheet_data(df)
              st.rerun()

            if b2.button("➖", key=f"sub_{idx}"):
              if df.loc[idx, "Quantité"] > 1:
                df.loc[idx, "Quantité"] -= 1
              else:
                df = df.drop(idx)
              update_sheet_data(df)
              st.rerun()

            if b3.button("🗑️", key=f"del_{idx}"):
              df = df.drop(idx)
              update_sheet_data(df)
              st.rerun()

          with c_link:
            st.markdown(
                f"<br><a href='{row['Lien Cardmarket']}' target='_blank'>↗"
                " Prix</a>",
                unsafe_allow_html=True,
            )

          st.markdown(
              "<hr style='margin: 8px 0; opacity: 0.15;'>",
              unsafe_allow_html=True,
          )

    else:
      st.info(
          "L'inventaire est actuellement vide. Scanne une carte pour commencer !"
      )

  except Exception as e:
    st.error(f"Erreur lors du chargement du stock : {e}")
