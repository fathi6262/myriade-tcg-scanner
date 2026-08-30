import base64
from datetime import datetime
import io
import json
import re
import urllib.parse
import requests

from google.oauth2.service_account import Credentials
import google.generativeai as genai
import gspread
import pandas as pd
from PIL import Image
import streamlit as st

# ---------------------------------------------------------
# 1. CONFIGURATION DE LA PAGE & STYLES CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Myriade Games — TCG Master Stock", page_icon="🔮", layout="wide"
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
        font-size: 0.8rem !important;
        color: #94a3b8 !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        margin-bottom: 4px !important;
    }

    .kpi-value {
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 2.2rem !important;
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
# 2. CONFIGURATION ET CACHE DES API
# ---------------------------------------------------------
SPREADSHEET_ID = "1rd14kfknX9z1P-72V_G2ITVBv2K1aMnLy5H_qt8c6eo"


@st.cache_resource
def get_gemini_model():
  genai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
  return genai.GenerativeModel("gemini-3.5-flash-lite") # Correction du modèle


@st.cache_resource
def get_google_sheet():
  scopes = ["https://www.googleapis.com/auth/spreadsheets"]
  creds = Credentials.from_service_account_info(
      st.secrets["gcp_service_account"], scopes=scopes
  )
  gc = gspread.authorize(creds)
  return gc.open_by_key(SPREADSHEET_ID).sheet1


gemini_model = get_gemini_model()
sheet = get_google_sheet()


# ---------------------------------------------------------
# 3. FONCTIONS UTILITAIRES ET ANALYSE GEMINI
# ---------------------------------------------------------
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
  clean_slug = slug.strip().split("/")[0] if slug else "Pokemon"
  clean_term = re.sub(r"[\-\/,\.:#]", " ", search_term)
  clean_term = " ".join(clean_term.split())
  search_query = urllib.parse.quote(clean_term)
  return f"https://www.cardmarket.com/fr/{clean_slug}/Products/Search?searchString={search_query}"


@st.cache_data(show_spinner=False)
def fetch_riftbound_card_from_riftcodex(card_name: str):
  """
  Interroge l'API publique REST de Riftcodex (api.riftcodex.com) 
  qui centralise les données officielles pour Riftbound.
  """
  if not card_name:
    return {}
  
  try:
    # L'API Riftcodex ne requiert pas d'authentification pour la lecture
    response = requests.get(
        "https://api.riftcodex.com/api/cards",
        params={"q": card_name, "limit": 5},
        timeout=8,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("items", [])
  except Exception:
    return {}

  if not results:
    return {}

  # Filtrage pour trouver la carte correspondante (insensible à la casse)
  card_name_lower = card_name.strip().lower()
  best_match = next(
      (c for c in results if c.get("name", "").strip().lower() == card_name_lower),
      results[0]
  )

  details = {}
  if "set" in best_match:
    details["set_name"] = str(best_match["set"])
  if "rarity" in best_match:
    details["rarity"] = str(best_match["rarity"]).capitalize()
  
  # Le coût peut varier selon le nom de la clé (cost ou energy_cost)
  if "cost" in best_match:
    details["play_cost"] = str(best_match["cost"])
  elif "energy_cost" in best_match:
    details["play_cost"] = str(best_match["energy_cost"])
    
  if "collector_number" in best_match:
    details["card_number"] = str(best_match["collector_number"])
  elif "number" in best_match:
    details["card_number"] = str(best_match["number"])
      
  return details


@st.cache_data(show_spinner=False)
def analyze_card_gemini_cached(image_bytes):
  pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

  prompt = """
    Tu es un expert mondial en identification de cartes TCG (Trading Card Games).
    Analyse cette photo de carte et extrait avec une précision exacte ses données officielles :

    1. "game_name" : Nom officiel du jeu (ex: "One Piece Card Game", "Riftbound", "Pokémon", "Magic: The Gathering", "Disney Lorcana", "Yu-Gi-Oh!").
    2. "card_name" : Nom de la carte. Si la carte est en japonais, donne le nom anglais/romaji officiel suivi du nom japonais entre parenthèses ou slashes (ex: "Monkey D. Luffy / モンキー・D・ルフィ").
    3. "set_name" : Nom ou code d'extension officiel (ex: "STARTER DECK EX -GEAR5- [ST-21]", "Vendetta", "ONE PIECE magazine Vol.20 Promo", "151").
    4. "card_number" : Numéro complet tel qu'imprimé (ex: "ST21-014", "156/166", "227/227", "OP01-120"). Ne trompe JAMAIS les chiffres "0" avec des lettres "O".
    5. "rarity" : Rareté officielle (ex: "Super Rare (SR)", "Rare (R)", "Épique", "Secret Rare (SEC)", "Commune (C)"). Attention : "DON!!" est le nom de la ressource, JAMAIS une rareté.
    6. "play_cost" : Le coût en mana/ressource/énergie (ex: 5, 1, 10).
    7. "language" : Code langue du texte de la carte ("JP", "EN", "FR", "DE").
    8. "cardmarket_slug" : Nom de la catégorie sur Cardmarket en 1 mot (ex: "OnePiece", "Riftbound", "Pokemon", "Magic", "Lorcana").
    9. "cardmarket_search_term" : Termes exacts pour chercher la carte sur Cardmarket (Nom anglais + Référence, ex: "Monkey D. Luffy ST21-014").

    Génère STRICTEMENT un objet JSON valide.
    """

  response = gemini_model.generate_content(
      [pil_image, prompt],
      generation_config=genai.GenerationConfig(
          response_mime_type="application/json", temperature=0.0
      ),
  )

  return json.loads(response.text)


# ---------------------------------------------------------
# 4. APPLICATION STREAMLIT
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📸 Scanner & Importer", "📦 Gestion du Stock"])

# --- ONGLET 1 : SCANNER ---
with tab1:
  scan_mode = st.radio(
      "Mode de traitement :",
      ["🎴 Unité (Caméra / Fichier)", "⚡ Scan en Lot (Multiple)"],
      horizontal=True,
  )

  if scan_mode == "🎴 Unité (Caméra / Fichier)":
    source_type = st.radio(
        "Source d'image :",
        ["💻 Fichier (PC / Galerie)", "📷 Caméra"],
        horizontal=True,
    )

    if source_type == "💻 Fichier (PC / Galerie)":
      image_input = st.file_uploader(
          "Dépose la photo de la carte", type=["jpg", "jpeg", "png", "webp"]
      )
    else:
      image_input = st.camera_input("Prendre la carte en photo")

    if image_input:
      img_byte_arr = io.BytesIO()
      Image.open(image_input).convert("RGB").save(img_byte_arr, format="JPEG")
      image_bytes = img_byte_arr.getvalue()

      try:
        with st.spinner("Analyse visuelle haute précision par Gemini..."):
          card = analyze_card_gemini_cached(image_bytes)

        # --- NOUVEAU : Interrogation de l'API Riftcodex ---
        if "riftbound" in card.get("game_name", "").lower():
          with st.spinner("Récupération des métadonnées sur Riftcodex..."):
            riftcodex_data = fetch_riftbound_card_from_riftcodex(card.get("card_name", ""))
            
            # On écrase les champs avec la vraie data de l'API
            card.update({k: v for k, v in riftcodex_data.items() if v})
            card["cardmarket_slug"] = "Riftbound"
            card["cardmarket_search_term"] = f"{card.get('card_name', '')} {card.get('card_number', '')}".strip()

        st.markdown("---")
        st.subheader("✏️ Vérifier et corriger les informations obtenues")

        with st.form("single_add_form"):
          col1, col2, col3 = st.columns(3)

          with col1:
            edit_game_name = st.text_input(
                "Jeu", value=card.get("game_name", "")
            )
            edit_card_name = st.text_input(
                "Nom de la carte", value=card.get("card_name", "")
            )
            edit_set_name = st.text_input(
                "Extension", value=card.get("set_name", "")
            )

          with col2:
            edit_card_number = st.text_input(
                "Numéro de carte (ex: ST21-014)",
                value=card.get("card_number", ""),
            )
            edit_rarity = st.text_input(
                "Rareté", value=card.get("rarity", "Super Rare (SR)")
            )
            edit_play_cost = st.text_input(
                "Coût (Mana/Ressource)", value=str(card.get("play_cost", ""))
            )

          with col3:
            edit_language = st.text_input(
                "Langue", value=card.get("language", "JP")
            )
            edit_emplacement = st.text_input(
                "Emplacement physique", value="Classeur 1"
            )
            edit_quantite = st.number_input(
                "Quantité", min_value=1, value=1, step=1
            )

          st.markdown("<br>", unsafe_allow_html=True)
          submit_button = st.form_submit_button("⚡ Ajouter au stock")

          if submit_button:
            cardmarket_url = build_cardmarket_url(
                card.get("cardmarket_slug", edit_game_name),
                card.get(
                    "cardmarket_search_term",
                    f"{edit_card_name} {edit_card_number}",
                ),
            )
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            sheet.append_row([
                date_str,
                edit_game_name,
                edit_card_name,
                edit_set_name,
                edit_card_number,
                edit_rarity,
                edit_play_cost,
                edit_language,
                edit_emplacement,
                edit_quantite,
                cardmarket_url,
            ])
            st.success(f"✅ {edit_card_name} enregistré avec succès !")

      except Exception as e:
        st.error(f"⚠️ Erreur d'analyse : {e}")

  else:
    uploaded_files = st.file_uploader(
        "Importe plusieurs images de cartes simultanément",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

    if uploaded_files:
      batch_loc = st.text_input(
          "Emplacement commun pour ce lot :", value="Boîte Arrivage"
      )

      if st.button(f"⚡ Analyser le lot ({len(uploaded_files)} images)"):
        progress_bar = st.progress(0)
        analyzed_cards = []

        for idx, file in enumerate(uploaded_files):
          img_byte_arr = io.BytesIO()
          Image.open(file).convert("RGB").save(img_byte_arr, format="JPEG")

          try:
            parsed_card = analyze_card_gemini_cached(img_byte_arr.getvalue())
            
            # --- NOUVEAU : Interrogation de l'API Riftcodex ---
            if "riftbound" in parsed_card.get("game_name", "").lower():
              riftcodex_data = fetch_riftbound_card_from_riftcodex(parsed_card.get("card_name", ""))
              parsed_card.update({k: v for k, v in riftcodex_data.items() if v})
              parsed_card["cardmarket_slug"] = "Riftbound"
              parsed_card["cardmarket_search_term"] = f"{parsed_card.get('card_name', '')} {parsed_card.get('card_number', '')}".strip()

            analyzed_cards.append(parsed_card)
          except Exception as e:
            st.warning(f"Impossible d'analyser l'image {file.name}: {e}")

          progress_bar.progress((idx + 1) / len(uploaded_files))

        st.session_state["batch_results"] = analyzed_cards
        st.success("Analyse du lot terminée !")

    if "batch_results" in st.session_state and st.session_state["batch_results"]:
      st.markdown(
          "### 📋 Récapitulatif du lot (Double-clique sur une case pour la"
          " modifier)"
      )

      batch_data = []
      for c in st.session_state["batch_results"]:
        batch_data.append({
            "Jeu": c.get("game_name", ""),
            "Nom": c.get("card_name", ""),
            "Extension": c.get("set_name", ""),
            "Numéro": c.get("card_number", ""),
            "Rareté": c.get("rarity", ""),
            "Coût": c.get("play_cost", ""),
            "Langue": c.get("language", "JP"),
            "Slug Cardmarket": c.get("cardmarket_slug", "OnePiece"),
            "Terme Recherche": c.get(
                "cardmarket_search_term", c.get("card_name", "")
            ),
        })

      batch_df = pd.DataFrame(batch_data)
      edited_df = st.data_editor(
          batch_df, use_container_width=True, num_rows="dynamic"
      )

      if st.button("💾 Tout valider dans Google Sheets"):
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        rows_to_add = []

        for _, row in edited_df.iterrows():
          url = build_cardmarket_url(
              row["Slug Cardmarket"], row["Terme Recherche"]
          )
          rows_to_add.append([
              date_str,
              row["Jeu"],
              row["Nom"],
              row["Extension"],
              row["Numéro"],
              row["Rareté"],
              row["Coût"],
              row["Langue"],
              batch_loc,
              1,
              url,
          ])

        sheet.append_rows(rows_to_add)
        st.success("✅ Lot ajouté au stock en une fraction de seconde !")
        del st.session_state["batch_results"]
        st.rerun()

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
            render_kpi("Références", str(len(df)), "🎴"), unsafe_allow_html=True
        )
      with col_m2:
        st.markdown(
            render_kpi(
                "Total Exemplaires", str(int(df["Quantité"].sum())), "📦"
            ),
            unsafe_allow_html=True,
        )
      with col_m3:
        st.markdown(
            render_kpi(
                "Jeux en Stock",
                str(df["Jeu"].nunique() if "Jeu" in df else 0),
                "🎮",
            ),
            unsafe_allow_html=True,
        )

      st.markdown("<br>", unsafe_allow_html=True)

      c_src, c_flt, c_exp = st.columns([2, 1, 1])
      with c_src:
        search_term = st.text_input(
            "🔍 Rechercher...", placeholder="Nom, numéro, emplacement..."
        )
      with c_flt:
        jeux_dispos = ["Tous les jeux"] + sorted(df["Jeu"].unique().tolist())
        selected_game = st.selectbox("🎮 Filtrer par jeu", jeux_dispos)
      with c_exp:
        st.markdown("<br>", unsafe_allow_html=True)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 Exporter Stock (CSV)",
            data=csv_buffer.getvalue(),
            file_name=f"Stock_Myriade_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

      filtered_df = df.copy()
      if selected_game != "Tous les jeux":
        filtered_df = filtered_df[filtered_df["Jeu"] == selected_game]
      if search_term:
        filtered_df = filtered_df[
            filtered_df["Nom"].str.contains(search_term, case=False, na=False)
            | filtered_df["Numéro"].str.contains(
                search_term, case=False, na=False
            )
            | filtered_df.get("Emplacement", "")
            .astype(str)
            .str.contains(search_term, case=False, na=False)
        ]

      st.markdown(f"**Cartes affichées ({len(filtered_df)})**")

      for idx, row in filtered_df.iterrows():
        with st.container():
          c_info, c_details, c_qty, c_actions, c_link = st.columns(
              [3.5, 2.5, 1.2, 2, 1]
          )

          with c_info:
            st.markdown(f"**{row['Nom']}** `{row['Numéro']}`")
            st.caption(f"{row['Jeu']} • {row['Extension']}")

          with c_details:
            st.markdown(
                f"📍 `{row.get('Emplacement', 'N/A')}` | Coût :"
                f" `{row.get('Coût', 'N/A')}`"
            )
            st.caption(
                f"Rareté : {row.get('Rareté', 'N/A')} •"
                f" {row.get('Langue', 'JP')}"
            )

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
                " Voir</a>",
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
