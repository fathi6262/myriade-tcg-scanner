import io
import json
import re
import urllib.parse
from datetime import datetime

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
st.markdown('<div class="brand-title">✨ Myriade Games</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="brand-subtitle">Une multitude d\'univers, une seule'
    " communauté</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 2. CONFIGURATION ET CACHE DES API
# ---------------------------------------------------------
SPREADSHEET_ID = "1rd14kfknX9z1P-72V_G2ITVBv2K1aMnLy5H_qt8c6eo"
QTY_COL_LETTER = "J"  # colonne "Quantité" dans le Google Sheet (à ajuster si besoin)


@st.cache_resource
def get_gemini_model():
  genai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
  return genai.GenerativeModel("gemini-3.5-flash-lite")


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
# 3. FONCTIONS UTILITAIRES ET API TIERCES
# ---------------------------------------------------------
@st.cache_data(ttl=20, show_spinner=False)
def load_stock_records():
  """Lecture cachée du stock (évite un appel API à chaque interaction)."""
  return sheet.get_all_records()


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


def sheet_row_index(pandas_idx: int) -> int:
  """Convertit un index pandas (0-based, sans en-tête) en index de ligne gspread (1-based, +1 pour l'en-tête)."""
  return pandas_idx + 2


def update_qty_cell(pandas_idx: int, new_qty: int):
  row = sheet_row_index(pandas_idx)
  sheet.update_acell(f"{QTY_COL_LETTER}{row}", new_qty)
  load_stock_records.clear()


def delete_sheet_row(pandas_idx: int):
  row = sheet_row_index(pandas_idx)
  sheet.delete_rows(row)
  load_stock_records.clear()


# ================== FONCTIONS API TIERCES (métadonnées par jeu) ==================

def _normalize_card_text(text: str) -> str:
  """Normalise un nom de carte pour comparaison (ponctuation, espaces, casse)."""
  text = text.strip().lower()
  text = re.sub(r"[,\-–—'’\.]", " ", text)
  text = re.sub(r"\s+", " ", text)
  return text.strip()


def _normalize_card_number(number: str) -> str:
  """Isole la partie numérique d'un numéro de carte (ex: '113/166' -> '113', 'VEN 113' -> '113')."""
  match = re.search(r"\d+", number or "")
  return match.group(0) if match else ""


@st.cache_data(show_spinner=False)
def fetch_riftbound_card_from_riftcodex(card_name: str, card_number: str = ""):
  """API publique pour Riftbound (api.riftcodex.com).

  Le matching se fait EN PRIORITÉ sur le numéro de carte (identifiant fiable
  et sans ambiguïté), car le nom extrait par Gemini peut différer légèrement
  du nom exact en base (ponctuation, sous-titre, casse...). Sans match fiable
  (numéro ou nom exact/normalisé), on ne renvoie rien plutôt que de deviner
  avec le premier résultat de la recherche — un mauvais matching peut faire
  remonter la rareté, le coût ou le numéro d'une carte totalement différente.
  """
  if not card_name:
    return {}
  try:
    response = requests.get(
        "https://api.riftcodex.com/api/cards",
        params={"q": card_name, "limit": 10},
        timeout=8,
    )
    response.raise_for_status()
    results = response.json().get("items", [])
    if not results:
      return {}

    best_match = None

    # 1. Match par numéro de carte (le plus fiable)
    target_number = _normalize_card_number(card_number)
    if target_number:
      for c in results:
        candidate_number = _normalize_card_number(
            str(c.get("collector_number") or c.get("number") or "")
        )
        if candidate_number and candidate_number == target_number:
          best_match = c
          break

    # 2. Sinon, match par nom exact normalisé
    if best_match is None:
      target_name = _normalize_card_text(card_name)
      for c in results:
        if _normalize_card_text(c.get("name", "")) == target_name:
          best_match = c
          break

    # 3. Aucun match fiable : on ne renvoie rien (pas de fallback au hasard)
    if best_match is None:
      return {}

    details = {}
    if "name" in best_match:
      details["card_name"] = str(best_match["name"])
    if "set" in best_match:
      details["set_name"] = str(best_match["set"])
    if "rarity" in best_match:
      details["rarity"] = str(best_match["rarity"]).capitalize()
    if "cost" in best_match:
      details["play_cost"] = str(best_match["cost"])
    elif "energy_cost" in best_match:
      details["play_cost"] = str(best_match["energy_cost"])
    if "collector_number" in best_match:
      details["card_number"] = str(best_match["collector_number"])
    elif "number" in best_match:
      details["card_number"] = str(best_match["number"])
    return details
  except Exception:
    return {}


@st.cache_data(show_spinner=False)
def fetch_onepiece_card_from_optcgapi(card_id: str):
  """API publique communautaire pour One Piece Card Game (optcgapi.com)."""
  if not card_id:
    return {}
  card_id = card_id.upper().strip().split()[0]
  if card_id.startswith("ST"):
    url = f"https://optcgapi.com/api/decks/card/{card_id}/"
  elif card_id.startswith("P"):
    url = f"https://optcgapi.com/api/promos/card/{card_id}/"
  else:
    url = f"https://optcgapi.com/api/sets/card/{card_id}/"

  try:
    response = requests.get(url, timeout=8)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list) and len(data) > 0:
      best_match = data[0]
    elif isinstance(data, dict):
      best_match = data
    else:
      return {}

    details = {}
    if "name" in best_match:
      details["card_name"] = str(best_match["name"])
    if "set_name" in best_match:
      details["set_name"] = str(best_match["set_name"])
    if "rarity" in best_match:
      details["rarity"] = str(best_match["rarity"])
    if "cost" in best_match:
      details["play_cost"] = str(best_match["cost"])
    return details
  except Exception:
    return {}


@st.cache_data(show_spinner=False)
def fetch_pokemon_card_from_pokemontcgio(card_name: str, card_number: str):
  """API publique pour Pokémon TCG."""
  if not card_name:
    return {}
  try:
    clean_name = card_name.split()[0].replace("é", "e").strip()
    response = requests.get(
        "https://api.pokemontcg.io/v2/cards",
        params={"q": f'name:"{clean_name}"'},
        timeout=8,
    )
    response.raise_for_status()
    results = response.json().get("data", [])
    if not results:
      return {}

    best_match = results[0]
    if card_number:
      num_only = card_number.split("/")[0].strip()
      for r in results:
        if str(r.get("number")).lower() == num_only.lower():
          best_match = r
          break

    details = {}
    if "name" in best_match:
      details["card_name"] = str(best_match["name"])
    if "set" in best_match and "name" in best_match["set"]:
      details["set_name"] = str(best_match["set"]["name"])
    if "rarity" in best_match:
      details["rarity"] = str(best_match["rarity"])
    return details
  except Exception:
    return {}


@st.cache_data(show_spinner=False)
def fetch_lorcana_card_from_api(card_name: str):
  """API publique communautaire pour Disney Lorcana."""
  if not card_name:
    return {}
  try:
    clean_name = card_name.split("-")[0].strip()
    response = requests.get(
        f"https://api.lorcana-api.com/cards/fetch?search=name~{clean_name}", timeout=8
    )
    response.raise_for_status()
    results = response.json()
    if not results or not isinstance(results, list):
      return {}

    best_match = results[0]
    details = {}
    full_name = str(best_match.get("Name", ""))
    if best_match.get("Subtitle"):
      full_name += f" - {best_match['Subtitle']}"
    if full_name:
      details["card_name"] = full_name

    if best_match.get("Set_Name"):
      details["set_name"] = str(best_match["Set_Name"])
    if best_match.get("Rarity"):
      details["rarity"] = str(best_match["Rarity"])
    if best_match.get("Cost"):
      details["play_cost"] = str(best_match["Cost"])
    if best_match.get("Card_Num"):
      details["card_number"] = str(best_match["Card_Num"])
    return details
  except Exception:
    return {}


def enrich_card_data(card: dict) -> dict:
  """Complète les données extraites par Gemini avec les API tierces spécifiques au jeu."""
  game_lower = card.get("game_name", "").lower()

  if "riftbound" in game_lower:
    riftcodex_data = fetch_riftbound_card_from_riftcodex(
        card.get("card_name", ""), card.get("card_number", "")
    )
    # La rareté Riftbound provient exclusivement de l'API Riftcodex, jamais
    # de l'estimation visuelle de Gemini (symbole en bas de carte). Si l'API
    # ne trouve pas de correspondance fiable, on laisse la rareté vide plutôt
    # que d'afficher une valeur potentiellement fausse.
    card["rarity"] = riftcodex_data.get("rarity", "")
    card.update({k: v for k, v in riftcodex_data.items() if v and k != "rarity"})
    card["cardmarket_slug"] = "Riftbound"
    card["cardmarket_search_term"] = f"{card.get('card_name', '')} {card.get('card_number', '')}".strip()

  elif "one piece" in game_lower:
    optcg_data = fetch_onepiece_card_from_optcgapi(card.get("card_number", ""))
    card.update({k: v for k, v in optcg_data.items() if v})
    card["cardmarket_slug"] = "OnePiece"
    card["cardmarket_search_term"] = f"{card.get('card_name', '')} {card.get('card_number', '')}".strip()

  elif "pok" in game_lower:
    pkmn_data = fetch_pokemon_card_from_pokemontcgio(card.get("card_name", ""), card.get("card_number", ""))
    card.update({k: v for k, v in pkmn_data.items() if v})
    card["cardmarket_slug"] = "Pokemon"
    card["cardmarket_search_term"] = f"{card.get('card_name', '')} {card.get('card_number', '')}".strip()

  elif "lorcana" in game_lower:
    lorcana_data = fetch_lorcana_card_from_api(card.get("card_name", ""))
    card.update({k: v for k, v in lorcana_data.items() if v})
    card["cardmarket_slug"] = "Lorcana"
    card["cardmarket_search_term"] = card.get("card_name", "").replace(" - ", " ")

  elif "palworld" in game_lower:
    card["cardmarket_slug"] = "Palworld"
    card["cardmarket_search_term"] = f"{card.get('card_name', '')} {card.get('card_number', '')}".strip()

  return card


# ================== MOTEUR IA ==================

@st.cache_data(show_spinner=False)
def analyze_card_gemini_cached(image_bytes):
  pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

  prompt = """
    Tu es un expert mondial en identification de cartes TCG (Trading Card Games).
    Analyse cette photo de carte et extrait avec une précision exacte ses données officielles :

    1. "game_name" : Nom officiel du jeu (ex: "One Piece Card Game", "Riftbound", "Pokémon", "Magic: The Gathering", "Disney Lorcana", "Palworld TCG", "Yu-Gi-Oh!").
    2. "card_name" : Nom COMPLET de la carte (titre principal + sous-titre).
    3. "set_name" : Nom ou code d'extension officiel imprimé.
    4. "card_number" : Numéro complet tel qu'imprimé (ex: "ST21-014", "156/166", "227/227"). Ne trompe JAMAIS les chiffres "0" avec des lettres "O".
    5. "rarity" : Rareté officielle exacte.
       - Pour RIFTBOUND : Regarde TOUT EN BAS DE LA CARTE, AU MILIEU. Tu y verras un petit symbole géométrique :
         * Boule blanche/grise = Common
         * Triangle vert = Uncommon
         * Losange rose = Rare
         * Pentagone orange = Epic
         * Hexagone jaune = Overnumbered / Alternate Art
       - Pour ONE PIECE : C, UC, R, SR, SEC, P (attention : "DON!!" est la ressource, JAMAIS la rareté).
       - Pour d'autres jeux : Commune, Peu Commune, Rare, Épique, Légendaire, Secret Rare, Promo.
    6. "play_cost" : Le coût en mana/ressource/énergie (ex: 5, 1, 10).
    7. "language" : Code langue du texte de la carte ("JP", "EN", "FR", "DE").
    8. "cardmarket_slug" : Nom de la catégorie sur Cardmarket en 1 mot (ex: "OnePiece", "Riftbound", "Pokemon", "Magic", "Lorcana", "Palworld").
    9. "cardmarket_search_term" : Termes exacts pour chercher la carte sur Cardmarket (Nom anglais + Référence).

    Génère STRICTEMENT un objet JSON valide, sans formatage markdown additionnel.
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
  source_type = st.radio(
      "Source de l'image :",
      ["📷 Appareil photo", "💻 PC"],
      horizontal=True,
      index=0,  # Appareil photo sélectionné par défaut
  )

  if source_type == "💻 PC":
    image_input = st.file_uploader(
        "Dépose la photo de la carte", type=["jpg", "jpeg", "png", "webp"]
    )
  else:
    # NOTE : st.camera_input ne permet pas de forcer nativement la caméra
    # arrière depuis le code Python — voir le message après le code pour
    # le détail de cette limitation et une piste de contournement.
    image_input = st.camera_input("Prendre la carte en photo")

  if image_input:
    img_byte_arr = io.BytesIO()
    Image.open(image_input).convert("RGB").save(img_byte_arr, format="JPEG")
    image_bytes = img_byte_arr.getvalue()

    try:
      with st.spinner("Analyse visuelle haute précision par Gemini..."):
        card = analyze_card_gemini_cached(image_bytes)

      with st.spinner("Récupération des métadonnées complémentaires..."):
        card = enrich_card_data(card)

      st.markdown("---")
      st.subheader("✏️ Vérifier et corriger les informations obtenues")

      with st.form("single_add_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
          edit_game_name = st.text_input("Jeu", value=card.get("game_name", ""))
          edit_card_name = st.text_input("Nom de la carte", value=card.get("card_name", ""))
          edit_set_name = st.text_input("Extension", value=card.get("set_name", ""))

        with col2:
          edit_card_number = st.text_input("Numéro de carte", value=card.get("card_number", ""))
          edit_rarity = st.text_input("Rareté", value=card.get("rarity", ""))
          edit_play_cost = st.text_input("Coût (Mana/Ressource)", value=str(card.get("play_cost", "")))

        with col3:
          edit_language = st.text_input("Langue", value=card.get("language", "FR"))
          edit_emplacement = st.text_input("Emplacement physique", value="Classeur 1")
          edit_quantite = st.number_input("Quantité", min_value=1, value=1, step=1)

        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button("⚡ Ajouter au stock")

        if submit_button:
          cardmarket_url = build_cardmarket_url(
              card.get("cardmarket_slug", edit_game_name),
              card.get("cardmarket_search_term", f"{edit_card_name} {edit_card_number}"),
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
          load_stock_records.clear()
          st.success(f"✅ {edit_card_name} enregistré avec succès !")

    except Exception as e:
      st.error(f"⚠️ Erreur d'analyse : {e}")

# --- ONGLET 2 : INVENTAIRE ---
with tab2:
  try:
    records = load_stock_records()

    if records:
      df = pd.DataFrame(records)
      df["Quantité"] = pd.to_numeric(df["Quantité"], errors="coerce").fillna(1).astype(int)

      col_m1, col_m2, col_m3 = st.columns(3)
      with col_m1:
        st.markdown(render_kpi("Références", str(len(df)), "🎴"), unsafe_allow_html=True)
      with col_m2:
        st.markdown(
            render_kpi("Total Exemplaires", str(int(df["Quantité"].sum())), "📦"),
            unsafe_allow_html=True,
        )
      with col_m3:
        st.markdown(
            render_kpi("Jeux en Stock", str(df["Jeu"].nunique() if "Jeu" in df else 0), "🎮"),
            unsafe_allow_html=True,
        )

      st.markdown("<br>", unsafe_allow_html=True)

      c_src, c_flt, c_exp = st.columns([2, 1, 1])
      with c_src:
        search_term = st.text_input("🔍 Rechercher...", placeholder="Nom, numéro, emplacement...")
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
            | filtered_df["Numéro"].astype(str).str.contains(search_term, case=False, na=False)
            | filtered_df.get("Emplacement", "").astype(str).str.contains(search_term, case=False, na=False)
        ]

      st.markdown(f"**Cartes affichées ({len(filtered_df)})**")

      for idx, row in filtered_df.iterrows():
        with st.container():
          c_info, c_details, c_qty, c_actions, c_link = st.columns([3.5, 2.5, 1.2, 2, 1])

          with c_info:
            st.markdown(f"**{row['Nom']}** `{row['Numéro']}`")
            st.caption(f"{row['Jeu']} • {row['Extension']}")

          with c_details:
            st.markdown(f"📍 `{row.get('Emplacement', 'N/A')}` | Coût : `{row.get('Coût', 'N/A')}`")
            st.caption(f"Rareté : {row.get('Rareté', 'N/A')} • {row.get('Langue', 'FR')}")

          with c_qty:
            st.markdown(f"### {row['Quantité']} ex.")

          with c_actions:
            b1, b2, b3 = st.columns(3)
            if b1.button("➕", key=f"add_{idx}"):
              update_qty_cell(idx, row["Quantité"] + 1)
              st.rerun()

            if b2.button("➖", key=f"sub_{idx}"):
              if row["Quantité"] > 1:
                update_qty_cell(idx, row["Quantité"] - 1)
              else:
                delete_sheet_row(idx)
              st.rerun()

            if b3.button("🗑️", key=f"del_{idx}"):
              delete_sheet_row(idx)
              st.rerun()

          with c_link:
            st.markdown(
                f"<br><a href='{row['Lien Cardmarket']}' target='_blank'>↗ Voir</a>",
                unsafe_allow_html=True,
            )

          st.markdown("<hr style='margin: 8px 0; opacity: 0.15;'>", unsafe_allow_html=True)

    else:
      st.info("L'inventaire est actuellement vide. Scanne une carte pour commencer !")

  except Exception as e:
    st.error(f"Erreur lors du chargement du stock : {e}")
