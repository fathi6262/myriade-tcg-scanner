import base64
from datetime import datetime
import io
import json
import re
import urllib.parse

from google.oauth2.service_account import Credentials
from groq import Groq
import gspread
import pandas as pd
from PIL import Image
import requests
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
def get_groq_client():
  return Groq(api_key=st.secrets["GROQ_API_KEY"].strip())


@st.cache_resource
def get_google_sheet():
  scopes = ["https://www.googleapis.com/auth/spreadsheets"]
  creds = Credentials.from_service_account_info(
      st.secrets["gcp_service_account"], scopes=scopes
  )
  gc = gspread.authorize(creds)
  return gc.open_by_key(SPREADSHEET_ID).sheet1


groq_client = get_groq_client()
sheet = get_google_sheet()


# ---------------------------------------------------------
# 3. FONCTIONS UTILITAIRES ET SERVICES EXTERNES
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


def resize_image_for_api(
    pil_image: Image.Image, max_dimension: int = 1400
) -> Image.Image:
  width, height = pil_image.size
  if max(width, height) <= max_dimension:
    return pil_image
  scale = max_dimension / max(width, height)
  new_size = (int(width * scale), int(height * scale))
  return pil_image.resize(new_size, Image.LANCZOS)


def build_cardmarket_url(slug: str, search_term: str) -> str:
  clean_slug = slug.strip().split("/")[0] if slug else "Pokemon"
  clean_term = re.sub(r"[\-\/,\.:#]", " ", search_term)
  clean_term = " ".join(clean_term.split())
  search_query = urllib.parse.quote(clean_term)
  return f"https://www.cardmarket.com/fr/{clean_slug}/Products/Search?searchString={search_query}"


# STEP 1 : IDENTIFICATION NEUTRE MULTI-TCG SANS BIAIS
@st.cache_data(show_spinner=False)
def identify_card_visually(image_bytes):
  base64_image = base64.b64encode(image_bytes).decode("utf-8")

  prompt = """
    Exécute une analyse visuelle pour identifier la carte TCG :

    1. "game_name" : Identifie le jeu exact. Vérifie attentivement le copyright / éditeur au bas de la carte :
       - ©RGI / Riot Games / Kudos Productions -> Riftbound (ou League of Legends TCG)
       - ©Bandai -> One Piece Card Game / Dragon Ball Super Card Game
       - ©Pokémon / Nintendo / Creatures -> Pokémon
       - ©Disney / Ravensburger -> Lorcana
       - ©Wizards of the Coast -> Magic: The Gathering
       - ©Konami -> Yu-Gi-Oh!
    2. "card_name" : Nom exact de la carte (ex: "Lightning Rush", "Monkey D. Luffy", "Charizard").
    3. "play_cost" : Le chiffre du coût en mana/ressource/énergie (souvent en haut à gauche/droite dans un cercle ou symbole).
    4. "language" : Langue du texte de la carte ("EN", "FR", "JP", "DE").
    5. "printed_code_line" : Recopie INTÉGRALEMENT la ligne de référence imprimée en bas de carte (ex: "VEN 156/166 EN", "ST21-014", "SV03 199/165").

    Génère STRICTEMENT cet objet JSON :
    {
      "game_name": "",
      "card_name": "",
      "play_cost": "",
      "language": "EN",
      "printed_code_line": ""
    }
    """

  chat_completion = groq_client.chat.completions.create(
      messages=[
          {
              "role": "system",
              "content": (
                  "Tu es un moteur OCR TCG neutre et universel. Tu ne privilégies"
                  " aucun jeu par défaut. Tu lis les lignes de copyright et"
                  " d'éditeur avec précision. Tu réponds EXCLUSIVEMENT par un"
                  " objet JSON valide sans balise <think>."
              ),
          },
          {
              "role": "user",
              "content": [
                  {"type": "text", "text": prompt},
                  {
                      "type": "image_url",
                      "image_url": {
                          "url": f"data:image/jpeg;base64,{base64_image}"
                      },
                  },
              ],
          },
      ],
      model="qwen/qwen3.6-27b",
      max_tokens=512,
      temperature=0.0,
      reasoning_format="hidden",
      reasoning_effort="none",
  )

  raw_text = chat_completion.choices[0].message.content
  clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
  clean_text = re.sub(r"```json\s*", "", clean_text)
  clean_text = re.sub(r"```\s*", "", clean_text).strip()

  json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
  if json_match:
    try:
      return json.loads(json_match.group())
    except json.JSONDecodeError:
      pass

  raise ValueError(f"Identification visuelle impossible : {raw_text[:200]}")


# STEP 2A : BASE DE DONNÉES STRUCTURÉE JUSTTCG
@st.cache_data(show_spinner=False)
def fetch_card_details_from_justtcg(game_name: str, card_name: str):
  api_key = st.secrets.get("JUSTTCG_API_KEY")
  if not api_key or not card_name:
    return {}

  clean_search_name = card_name.split("/")[0].split("(")[0].strip()

  try:
    response = requests.get(
        "https://api.justtcg.com/v1/cards",
        headers={"x-api-key": api_key},
        params={"q": clean_search_name, "game": game_name, "limit": 5},
        timeout=8,
    )
    response.raise_for_status()
    results = response.json().get("data", [])
  except Exception:
    return {}

  if not results:
    return {}

  best_match = results[0]
  details = {}
  set_value = best_match.get("set_name") or best_match.get("set")
  if set_value:
    details["set_name"] = set_value
  if best_match.get("rarity"):
    details["rarity"] = best_match["rarity"]
  return details


# STEP 2B : RECHERCHE WEB CIBLÉE DUO GROQ / CARDMARKET
@st.cache_data(show_spinner=False)
def fetch_precise_card_details_from_web(
    game_name: str, card_name: str, printed_code_line: str = ""
):
  query = f"""Recherche sur le web et Cardmarket les métadonnées officielles exactes de cette carte :
Jeu : « {game_name} »
Nom de la carte : « {card_name} »
Code OCR imprimé : « {printed_code_line} »

CONSIGNES STRICTES :
1. Recherche uniquement pour le jeu « {game_name} ». Ne propose jamais une extension ou une référence appartenant à un autre TCG.
2. "card_number" : Numéro complet de la carte. Si le code contient une fraction (ex: 156/166, 227/227), CONSERVE IMPÉRATIVEMENT la fraction complète avec son total.
3. "set_name" : Code ou nom d'extension officiel correspondant (ex: "VEN" ou "Vendetta").
4. "rarity" : Rareté officielle.
5. "cardmarket_slug" : Nom de la catégorie sur Cardmarket en 1 mot sans espace (ex: Riftbound, Pokemon, Lorcana, OnePiece, Magic, YuGiOh).
6. "cardmarket_search_term" : Termes exacts pour chercher la carte sur Cardmarket (Nom + Référence).

Réponds UNIQUEMENT sous la forme d'un objet JSON strict :
{{"card_number": "", "set_name": "", "rarity": "", "cardmarket_slug": "", "cardmarket_search_term": ""}}"""

  try:
    completion = groq_client.chat.completions.create(
        model="groq/compound",
        messages=[{"role": "user", "content": query}],
        temperature=0.0,
        max_tokens=400,
    )
    raw_text = completion.choices[0].message.content.strip()
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if json_match:
      result = json.loads(json_match.group())
      return {k: str(v).strip() for k, v in result.items() if v}
  except Exception:
    pass
  return {}


# MOTEUR DE FUSION ET D'ENRICHISSEMENT
def process_full_card_data(image_bytes):
  # 1. Identification visuelle du nom, jeu et coût
  visual_info = identify_card_visually(image_bytes)

  game_name = visual_info.get("game_name", "")
  card_name = visual_info.get("card_name", "")
  play_cost = visual_info.get("play_cost", "")
  printed_code = visual_info.get("printed_code_line", "")

  # Extraction du numéro brut depuis la ligne visuelle si présente (ex: 156/166)
  extracted_number = ""
  num_match = re.search(r"([A-Z0-9\-\/]+\s*[\d]+[\/\-][\d]+)", printed_code)
  if num_match:
    extracted_number = num_match.group(1).strip()
  elif printed_code:
    extracted_number = printed_code.strip()

  # 2. Interrogation JustTCG
  justtcg_data = fetch_card_details_from_justtcg(game_name, card_name)

  # 3. Recherche Web
  web_data = fetch_precise_card_details_from_web(
      game_name, card_name, printed_code
  )

  # 4. Assemblage final
  card_number = web_data.get("card_number") or extracted_number or printed_code

  # Si la ligne visuelle contenait une fraction (ex: 156/166) et que la recherche a simplifié en VEN-156, on restaure la fraction
  if "/" in printed_code and "/" not in card_number:
    card_number = printed_code

  set_name = (
      web_data.get("set_name")
      or justtcg_data.get("set_name")
      or (printed_code.split()[0] if printed_code else "")
  )
  rarity = (
      web_data.get("rarity") or justtcg_data.get("rarity") or "Non spécifiée"
  )
  slug = web_data.get("cardmarket_slug") or game_name.replace(" ", "")
  search_term = web_data.get(
      "cardmarket_search_term", f"{card_name} {card_number}"
  )

  return {
      "game_name": game_name,
      "card_name": card_name,
      "set_name": set_name,
      "card_number": card_number,
      "rarity": rarity,
      "play_cost": play_cost,
      "language": visual_info.get("language", "EN"),
      "cardmarket_slug": slug,
      "cardmarket_search_term": search_term,
  }


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
      pil_image = Image.open(image_input).convert("RGB")
      pil_image = resize_image_for_api(pil_image)
      img_byte_arr = io.BytesIO()
      pil_image.save(img_byte_arr, format="JPEG", quality=92)
      image_bytes = img_byte_arr.getvalue()

      try:
        with st.spinner("Analyse visuelle & recherche des données..."):
          card = process_full_card_data(image_bytes)

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
                "Numéro de carte (ex: 156/166)",
                value=card.get("card_number", ""),
            )
            edit_rarity = st.text_input(
                "Rareté", value=card.get("rarity", "Commune")
            )
            edit_play_cost = st.text_input(
                "Coût (Mana/Ressource)", value=str(card.get("play_cost", ""))
            )

          with col3:
            edit_language = st.text_input(
                "Langue", value=card.get("language", "EN")
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
                f"{edit_card_name} {edit_card_number}",
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
          pil_img = Image.open(file).convert("RGB")
          pil_img = resize_image_for_api(pil_img)
          img_byte_arr = io.BytesIO()
          pil_img.save(img_byte_arr, format="JPEG", quality=92)

          try:
            parsed_card = process_full_card_data(img_byte_arr.getvalue())
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
            "Langue": c.get("language", "EN"),
            "Slug Cardmarket": c.get("cardmarket_slug", "Pokemon"),
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
                f" {row.get('Langue', 'EN')}"
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
