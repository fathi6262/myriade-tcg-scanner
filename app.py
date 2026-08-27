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
# 3. FONCTIONS UTILITAIRES & CACHE IA
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


def resize_image_for_api(pil_image: Image.Image, max_dimension: int = 1280) -> Image.Image:
  """Redimensionne l'image pour limiter le coût en tokens côté API (le nombre
  de tokens d'une image dépend de sa résolution)."""
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


@st.cache_data(show_spinner=False)
def analyze_card_image_groq_cached(image_bytes):
  base64_image = base64.b64encode(image_bytes).decode("utf-8")

  prompt = """
    Identifie cette carte TCG et génère un objet JSON structuré avec ces clés exactes :
    {
      "printed_code_line": "Le petit code imprimé sur la carte, transcrit tel quel",
      "game_name": "Nom du jeu",
      "card_name": "Nom de la carte",
      "set_name": "Code d'extension (best-effort, vérifié ensuite via le web)",
      "card_number": "Numéro tel qu'imprimé (best-effort, vérifié ensuite via le web)",
      "rarity": "Rareté (best-effort, vérifiée ensuite via le web)",
      "play_cost": "Coût de la carte",
      "cardmarket_slug": "Nom du jeu en un mot",
      "cardmarket_search_term": "Nom carte et extension",
      "language": "FR"
    }

    MÉTHODE OBLIGATOIRE : la plupart des TCG impriment un petit code compact
    dans un coin de la carte (souvent en bas), qui regroupe ensemble le code
    d'extension, le numéro de carte et l'abréviation de rareté (par exemple :
    "OP01-120 SEC" pour One Piece Card Game, ou "SWSH045" pour Pokémon, ou
    "227/221 R" pour d'autres jeux). Repère cette ligne en premier, transcris-
    la EXACTEMENT dans "printed_code_line", puis déduis les champs suivants
    à partir de cette transcription plutôt que de les inventer séparément :

    - "set_name" : le CODE d'extension tel qu'imprimé (ex: "OP01", "ST01",
      "SWSH045"). N'invente JAMAIS un nom thématique ou narratif (ex: "The
      Four Emperors", "Romance Dawn") si ce n'est pas littéralement le texte
      imprimé sur la carte — utilise uniquement le code visible.
    - "card_number" : recopie le numéro EXACTEMENT tel qu'il est imprimé.
      Tous les jeux n'utilisent PAS un format "X/Y" : certains n'impriment
      qu'un seul nombre (ex: One Piece Card Game). Si un seul nombre est
      imprimé, ne le duplique pas et n'invente pas de second nombre après
      un "/" — laisse le champ tel quel (ex: "120", pas "120/120").
    - "rarity" : de nombreux jeux impriment une abréviation de rareté à côté
      du numéro (ex pour One Piece Card Game : L=Leader, C=Commune,
      UC=Peu Commune, R=Rare, SR=Super Rare, SEC=Secrète, P=Promo). Si tu
      repères cette abréviation, développe-la en toutes lettres. Ne
      remplace jamais une abréviation clairement visible par une estimation
      basée sur la couleur d'un symbole.

    Si aucun code compact n'est visible ou lisible, laisse
    "printed_code_line" vide et fais de ton mieux pour chaque champ
    individuellement, en restant fidèle à ce qui est réellement imprimé
    plutôt qu'à ce qui te semblerait plausible.
    """

  chat_completion = groq_client.chat.completions.create(
      messages=[
          {
              "role": "system",
              "content": (
                  "Tu es un processeur d'images TCG. Génère directement le JSON"
                  " en fin de réponse."
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
      max_tokens=1024,  # suffisant pour un JSON court, raisonnement désactivé
      temperature=0.0,
      reasoning_format="hidden",  # ne renvoie que la réponse finale, pas le <think>
      reasoning_effort="none",    # désactive le raisonnement, inutile pour cette tâche d'extraction
  )

  raw_text = chat_completion.choices[0].message.content

  # Nettoyage de la réponse (gardé en filet de sécurité)
  clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
  clean_text = re.sub(r"```json\s*", "", clean_text)
  clean_text = re.sub(r"```\s*", "", clean_text).strip()

  # Extraction de l'objet JSON
  json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
  if json_match:
    try:
      return json.loads(json_match.group())
    except json.JSONDecodeError:
      pass

  json_match_raw = re.search(r"\{.*\}", raw_text, re.DOTALL)
  if json_match_raw:
    try:
      return json.loads(json_match_raw.group())
    except json.JSONDecodeError:
      pass

  raise ValueError(f"Format JSON invalide reçu : {raw_text[:200]}")


@st.cache_data(show_spinner=False)
def fetch_precise_card_details_from_web(
    game_name: str,
    card_name: str,
    rough_set_hint: str = "",
    rough_number_hint: str = "",
    printed_code_line: str = "",
):
  """Utilise Groq Compound (recherche web intégrée, propulsée par Tavily)
  pour retrouver l'extension, le numéro et la rareté officiels d'une carte,
  en appliquant les conventions propres au jeu identifié plutôt que des
  règles codées en dur pour chaque TCG. Les valeurs issues du scan visuel
  ne sont transmises que comme indices à vérifier, pas comme vérités.
  Retourne un dict partiel (clés absentes si non trouvées avec confiance) ;
  ne lève jamais d'exception — un échec renvoie {} et l'appelant garde les
  valeurs du scan visuel."""
  hints = []
  if rough_set_hint:
    hints.append(f"extension possible d'après le scan : « {rough_set_hint} »")
  if rough_number_hint:
    hints.append(f"numéro possible d'après le scan : « {rough_number_hint} »")
  if printed_code_line:
    hints.append(f"code compact repéré sur la carte : « {printed_code_line} »")
  hints_text = (
      " Indices du scan visuel, à vérifier et corriger si besoin (ils"
      f" peuvent être faux) : {' ; '.join(hints)}."
      if hints
      else ""
  )

  query = (
      "Recherche sur le web les informations officielles précises de cette"
      f" carte à jouer : jeu « {game_name} », carte « {card_name} »."
      f"{hints_text} Chaque TCG a ses propres conventions pour le format du"
      " numéro de carte et pour le système de rareté (les libellés, les"
      " abréviations, la présence ou non d'un total après un « / ») : ne"
      " suppose rien, applique les conventions réelles du jeu identifié"
      " ci-dessus telles que tu les trouves sur le web.\n\n"
      "Réponds UNIQUEMENT avec un objet JSON strict, sans aucun texte"
      " avant ou après, au format exact :\n"
      '{"set_name": "code ou nom d\'extension officiel",'
      ' "card_number": "numéro exact, écrit selon la convention du jeu",'
      ' "rarity": "nom complet de la rareté, en français"}\n\n'
      "Si une information reste introuvable malgré la recherche, mets une"
      ' chaîne vide "" pour ce champ plutôt que de deviner.'
  )

  try:
    completion = groq_client.chat.completions.create(
        model="groq/compound",
        messages=[{"role": "user", "content": query}],
        temperature=0.0,
        max_tokens=300,
    )
    raw_text = completion.choices[0].message.content.strip()
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not json_match:
      return {}
    result = json.loads(json_match.group())
    # On ne garde que les champs non vides renvoyés par la recherche
    return {k: v for k, v in result.items() if isinstance(v, str) and v.strip()}
  except Exception:
    # Recherche web best-effort : en cas d'échec on garde les valeurs du scan visuel
    return {}


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
        with st.spinner("Analyse visuelle par Groq..."):
          card = analyze_card_image_groq_cached(image_bytes)

        with st.spinner("Vérification de l'extension, du numéro et de la rareté sur le web..."):
          verified_fields = fetch_precise_card_details_from_web(
              card.get("game_name", ""),
              card.get("card_name", ""),
              card.get("set_name", ""),
              card.get("card_number", ""),
              card.get("printed_code_line", ""),
          )
          card.update(verified_fields)

        st.markdown("---")
        st.subheader("✏️ Vérifier et corriger les informations scannées")

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
                "Numéro de carte (ex: 227/227)",
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
                "Langue", value=card.get("language", "FR")
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
                f"{edit_card_name} {edit_set_name}",
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
            parsed_card = analyze_card_image_groq_cached(
                img_byte_arr.getvalue()
            )
            verified_fields = fetch_precise_card_details_from_web(
                parsed_card.get("game_name", ""),
                parsed_card.get("card_name", ""),
                parsed_card.get("set_name", ""),
                parsed_card.get("card_number", ""),
                parsed_card.get("printed_code_line", ""),
            )
            parsed_card.update(verified_fields)
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
            "Langue": c.get("language", "FR"),
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
                f" {row.get('Langue', 'FR')}"
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
