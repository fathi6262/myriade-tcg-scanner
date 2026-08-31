import io
import json
import re
import urllib.parse
from datetime import datetime

from google.oauth2.service_account import Credentials
import google.generativeai as genai
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
st.markdown('<div class="brand-title">✨ Myriade Games</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="brand-subtitle">Une multitude d\'univers, une seule communauté</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 2. CONFIGURATION ET CACHE DES API
# ---------------------------------------------------------
SPREADSHEET_ID = "1rd14kfknX9z1P-72V_G2ITVBv2K1aMnLy5H_qt8c6eo"
QTY_COL_LETTER = "J"


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
# 3. FONCTIONS UTILITAIRES ET ACCÈS DONNÉES
# ---------------------------------------------------------
@st.cache_data(ttl=15, show_spinner=False)
def load_stock_records():
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
  return pandas_idx + 2


def update_qty_cell(pandas_idx: int, new_qty: int):
  row = sheet_row_index(pandas_idx)
  sheet.update_acell(f"{QTY_COL_LETTER}{row}", new_qty)
  load_stock_records.clear()


def delete_sheet_row(pandas_idx: int):
  row = sheet_row_index(pandas_idx)
  sheet.delete_rows(row)
  load_stock_records.clear()


# ================== API TIERCES ==================

def _normalize_card_text(text: str) -> str:
  text = text.strip().lower()
  text = re.sub(r"[,\-–—'’\.]", " ", text)
  text = re.sub(r"\s+", " ", text)
  return text.strip()


def _extract_collector_number(number: str):
  match = re.search(r"\d+", number or "")
  return int(match.group(0)) if match else None


def _champion_name_only(card_name: str) -> str:
  parts = re.split(r"\s*[,:\-–—]\s*", card_name.strip(), maxsplit=1)
  return parts[0].strip() if parts else card_name.strip()


@st.cache_data(show_spinner=False)
def _query_riftcodex_by_name(name: str):
  if not name:
    return []
  try:
    response = requests.get(
        "https://api.riftcodex.com/cards/name",
        params={"fuzzy": name, "size": 20},
        timeout=8,
    )
    response.raise_for_status()
    return response.json().get("items", [])
  except Exception:
    return []


def search_riftcodex_raw(card_name: str):
  if not card_name:
    return []
  results = _query_riftcodex_by_name(card_name.strip())
  if results:
    return results
  champion_only = _champion_name_only(card_name)
  if champion_only and champion_only.lower() != card_name.strip().lower():
    results = _query_riftcodex_by_name(champion_only)
  return results


def fetch_riftbound_card_from_riftcodex(card_name: str, card_number: str = ""):
  results = search_riftcodex_raw(card_name)
  if not results:
    return {}

  best_match = None
  target_number = _extract_collector_number(card_number)

  if target_number is not None:
    number_matches = [c for c in results if c.get("collector_number") == target_number]
    if len(number_matches) == 1:
      best_match = number_matches[0]
    elif len(number_matches) > 1:
      target_name = _normalize_card_text(card_name)
      best_match = next(
          (c for c in number_matches if _normalize_card_text(c.get("name", "")) == target_name),
          None,
      )

  if best_match is None:
    target_name = _normalize_card_text(card_name)
    exact_matches = [c for c in results if _normalize_card_text(c.get("name", "")) == target_name]
    if len(exact_matches) == 1:
      best_match = exact_matches[0]

  if best_match is None:
    target_name = _normalize_card_text(card_name)
    prefix_matches = [
        c for c in results
        if _normalize_card_text(c.get("name", ""))
        and target_name.startswith(_normalize_card_text(c.get("name", "")))
    ]
    if len(prefix_matches) == 1:
      best_match = prefix_matches[0]

  if best_match is None:
    return {}

  classification = best_match.get("classification", {}) or {}
  attributes = best_match.get("attributes", {}) or {}
  set_info = best_match.get("set", {}) or {}

  details = {}
  if best_match.get("name"): details["card_name"] = str(best_match["name"])
  if set_info.get("label"): details["set_name"] = str(set_info["label"])
  if classification.get("rarity"): details["rarity"] = str(classification["rarity"]).capitalize()
  if attributes.get("energy") is not None: details["play_cost"] = str(attributes["energy"])
  if best_match.get("collector_number") is not None: details["card_number"] = str(best_match["collector_number"])
  return details


@st.cache_data(show_spinner=False)
def fetch_onepiece_card_from_optcgapi(card_id: str):
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
    best_match = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
    if not best_match:
      return {}

    details = {}
    if "name" in best_match: details["card_name"] = str(best_match["name"])
    if "set_name" in best_match: details["set_name"] = str(best_match["set_name"])
    if "rarity" in best_match: details["rarity"] = str(best_match["rarity"])
    if "cost" in best_match: details["play_cost"] = str(best_match["cost"])
    if "color" in best_match: details["color"] = str(best_match["color"]) # Récupération de la couleur officielle
    return details
  except Exception:
    return {}


@st.cache_data(show_spinner=False)
def fetch_pokemon_card_from_pokemontcgio(card_name: str, card_number: str):
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
    if "name" in best_match: details["card_name"] = str(best_match["name"])
    if "set" in best_match and "name" in best_match["set"]: details["set_name"] = str(best_match["set"]["name"])
    if "rarity" in best_match: details["rarity"] = str(best_match["rarity"])
    if "types" in best_match: details["color"] = " / ".join(best_match["types"]) # Types Pokémon
    return details
  except Exception:
    return {}


@st.cache_data(show_spinner=False)
def fetch_lorcana_card_from_api(card_name: str):
  if not card_name:
    return {}
  try:
    clean_name = card_name.split("-")[0].strip()
    response = requests.get(f"https://api.lorcana-api.com/cards/fetch?search=name~{clean_name}", timeout=8)
    response.raise_for_status()
    results = response.json()
    if not results or not isinstance(results, list):
      return {}

    best_match = results[0]
    details = {}
    full_name = str(best_match.get("Name", ""))
    if best_match.get("Subtitle"):
      full_name += f" - {best_match['Subtitle']}"
    if full_name: details["card_name"] = full_name

    if best_match.get("Set_Name"): details["set_name"] = str(best_match["Set_Name"])
    if best_match.get("Rarity"): details["rarity"] = str(best_match["Rarity"])
    if best_match.get("Cost"): details["play_cost"] = str(best_match["Cost"])
    if best_match.get("Card_Num"): details["card_number"] = str(best_match["Card_Num"])
    if best_match.get("Color"): details["color"] = str(best_match["Color"]) # Couleur (Encre)
    return details
  except Exception:
    return {}


def enrich_card_data(card: dict) -> dict:
  game_lower = card.get("game_name", "").lower()

  if "riftbound" in game_lower:
    riftcodex_data = fetch_riftbound_card_from_riftcodex(
        card.get("card_name", ""), card.get("card_number", "")
    )
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
    7. "color": La couleur ou le type dominant de la carte (ex: "Rouge", "Bleu", "Violet", "Améthyste", "Feu", "Ténèbres"). Si carte multicolore, sépare par un slash (ex: "Rouge/Vert").
    8. "language" : Code langue du texte de la carte ("JP", "EN", "FR", "DE").
    9. "cardmarket_slug" : Nom de la catégorie sur Cardmarket en 1 mot (ex: "OnePiece", "Riftbound", "Pokemon", "Magic", "Lorcana", "Palworld").
    10. "cardmarket_search_term" : Termes exacts pour chercher la carte sur Cardmarket (Nom anglais + Référence).

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
      index=0,
  )

  if source_type == "💻 PC":
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
      with st.spinner("Analyse visuelle par Gemini..."):
        card = analyze_card_gemini_cached(image_bytes)

      with st.spinner("Enrichissement des métadonnées officielles..."):
        card = enrich_card_data(card)

      st.markdown("---")
      st.subheader("✏️ Vérifier et valider les informations")

      with st.form("single_add_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
          edit_game_name = st.text_input("Jeu", value=card.get("game_name", ""))
          edit_card_name = st.text_input("Nom de la carte", value=card.get("card_name", ""))
          edit_set_name = st.text_input("Extension", value=card.get("set_name", ""))
          edit_card_number = st.text_input("Numéro de carte", value=card.get("card_number", ""))

        with col2:
          edit_rarity = st.text_input("Rareté", value=card.get("rarity", ""))
          edit_couleur = st.text_input("Couleur / Type", value=card.get("color", ""))
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

          # ÉCRITURE STRICTE DANS L'ORDRE DES 12 COLONNES DU GSHEET
          sheet.append_row([
              date_str,          # Col A: Date
              edit_game_name,    # Col B: Jeu
              edit_card_name,    # Col C: Nom
              edit_set_name,     # Col D: Extension
              edit_card_number,  # Col E: Numéro
              edit_rarity,       # Col F: Rareté
              edit_play_cost,    # Col G: Coût
              edit_language,     # Col H: Langue
              edit_emplacement,  # Col I: Emplacement
              edit_quantite,     # Col J: Quantité
              edit_couleur,      # Col K: Couleur
              cardmarket_url,    # Col L: Lien Cardmarket
          ])
          load_stock_records.clear()
          st.success(f"✅ {edit_card_name} enregistré dans le stock !")

    except Exception as e:
      st.error(f"⚠️ Erreur d'analyse : {e}")

# --- ONGLET 2 : INVENTAIRE ET GESTION DU STOCK ---
with tab2:
  try:
    records = load_stock_records()

    if records:
      df = pd.DataFrame(records)
      df["Quantité"] = pd.to_numeric(df.get("Quantité", 1), errors="coerce").fillna(1).astype(int)

      col_m1, col_m2, col_m3 = st.columns(3)
      with col_m1:
        st.markdown(render_kpi("Références uniques", str(len(df)), "🎴"), unsafe_allow_html=True)
      with col_m2:
        st.markdown(
            render_kpi("Total Exemplaires", str(int(df["Quantité"].sum())), "📦"),
            unsafe_allow_html=True,
        )
      with col_m3:
        st.markdown(
            render_kpi("Jeux représentés", str(df["Jeu"].nunique() if "Jeu" in df else 0), "🎮"),
            unsafe_allow_html=True,
        )

      st.markdown("<br>", unsafe_allow_html=True)

      st.subheader("🔍 Filtrer et gérer le stock")
      f1, f2, f3, f4, f5 = st.columns([1.5, 1.2, 1.2, 1.2, 1.2])

      with f1:
        search_term = st.text_input("Recherche", placeholder="Nom, Couleur, Numéro...")

      with f2:
        list_jeux = ["Tous les jeux"] + sorted([str(j) for j in df["Jeu"].unique() if j])
        selected_game = st.selectbox("Jeu", list_jeux)

      temp_df = df if selected_game == "Tous les jeux" else df[df["Jeu"] == selected_game]

      with f3:
        list_sets = ["Toutes les extensions"] + sorted([str(s) for s in temp_df.get("Extension", pd.Series()).unique() if s])
        selected_set = st.selectbox("Extension", list_sets)

      with f4:
        # Filtre sur la Rareté
        list_rarities = ["Toutes les raretés"] + sorted([str(r) for r in temp_df.get("Rareté", pd.Series()).unique() if r and str(r) != "nan"])
        selected_rarity = st.selectbox("Rareté", list_rarities)

      with f5:
        list_locs = ["Tous les emplacements"] + sorted([str(l) for l in temp_df.get("Emplacement", pd.Series()).unique() if l])
        selected_loc = st.selectbox("Emplacement", list_locs)

      filtered_df = df.copy()

      if selected_game != "Tous les jeux":
        filtered_df = filtered_df[filtered_df["Jeu"] == selected_game]

      if selected_set != "Toutes les extensions":
        filtered_df = filtered_df[filtered_df["Extension"] == selected_set]

      if selected_rarity != "Toutes les raretés":
        filtered_df = filtered_df[filtered_df["Rareté"] == selected_rarity]

      if selected_loc != "Tous les emplacements":
        filtered_df = filtered_df[filtered_df["Emplacement"] == selected_loc]

      if search_term:
        filtered_df = filtered_df[
            filtered_df["Nom"].astype(str).str.contains(search_term, case=False, na=False)
            | filtered_df["Numéro"].astype(str).str.contains(search_term, case=False, na=False)
            | filtered_df.get("Couleur", pd.Series(dtype=str)).astype(str).str.contains(search_term, case=False, na=False)
        ]

      st.markdown(f"**Cartes trouvées : {len(filtered_df)}**")

      for idx, row in filtered_df.iterrows():
        with st.container():
          c_info, c_details, c_qty, c_actions, c_link = st.columns([3.5, 2.5, 1.2, 2, 1])

          # Correction de l'ancien décalage si nécessaire
          raw_cost = row.get("Coût")
          raw_lang = row.get("Langue")
          raw_etat = row.get("État")
          raw_rarity = row.get("Rareté") or row.get("Finition") or "N/A"
          raw_color = row.get("Couleur") or "N/A"

          if (raw_cost is None or pd.isna(raw_cost) or str(raw_cost).strip() in ["", "N/A"]) and str(raw_lang).isdigit():
            cost_val = str(raw_lang)
            lang_val = str(raw_etat) if raw_etat and not pd.isna(raw_etat) else "JP"
          else:
            cost_val = str(raw_cost) if pd.notna(raw_cost) and str(raw_cost) != "" else "N/A"
            lang_val = str(raw_lang) if pd.notna(raw_lang) and str(raw_lang) != "" else "FR"

          with c_info:
            st.markdown(f"**{row.get('Nom', '')}** `{row.get('Numéro', '')}`")
            st.caption(f"{row.get('Jeu', '')} • {row.get('Extension', '')}")

          with c_details:
            st.markdown(f"📍 `{row.get('Emplacement', 'N/A')}` | Coût : `{cost_val}`")
            color_text = f" • Couleur : {raw_color}" if raw_color != "N/A" else ""
            st.caption(f"Rareté : {raw_rarity}{color_text} • Langue : {lang_val}")

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
            link_url = row.get("Lien Cardmarket") or row.get("Prix Est. (€)") or "#"
            st.markdown(
                f"<br><a href='{link_url}' target='_blank'>↗ Voir</a>",
                unsafe_allow_html=True,
            )

          st.markdown("<hr style='margin: 8px 0; opacity: 0.15;'>", unsafe_allow_html=True)

    else:
      st.info("L'inventaire est actuellement vide.")

  except Exception as e:
    st.error(f"Erreur lors du chargement du stock : {e}")
