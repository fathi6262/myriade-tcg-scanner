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
# 1. CONFIGURATION DE LA PAGE & STYLES CSS (DA MYRIADE GAMES)
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
# 2. CONFIGURATION DES API (GROQ + GOOGLE SHEETS)
# ---------------------------------------------------------
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())

SPREADSHEET_ID = "1rd14kfknX9z1P-72V_G2ITVBv2K1aMnLy5H_qt8c6eo"

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scopes
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1


# ---------------------------------------------------------
# 3. FONCTIONS UTILITAIRES
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
  clean_slug = slug.strip().split("/")[0]
  clean_term = re.sub(r"[\-\/,\.:#]", " ", search_term)
  clean_term = " ".join(clean_term.split())
  search_query = urllib.parse.quote(clean_term)
  return f"https://www.cardmarket.com/fr/{clean_slug}/Products/Search?searchString={search_query}"


def analyze_card_image_groq(image_bytes):
  base64_image = base64.b64encode(image_bytes).decode("utf-8")

  prompt = """
    Identifie cette carte TCG et réponds EXCLUSIVEMENT au format JSON strict respectant cette structure exacte :
    {
      "game_name": "Nom du jeu (ex: Pokemon, Magic, Lorcana, Yu-Gi-Oh!)",
      "card_name": "Nom exact de la carte",
      "set_name": "Nom de l'extension",
      "card_number": "Numéro de la carte (ex: 199/165)",
      "cardmarket_slug": "Catégorie principale Cardmarket en un seul mot (ex: Pokemon, Magic, YuGiOh, Lorcana)",
      "cardmarket_search_term": "Nom de la carte et extension combinés sans slashes ni tirets",
      "language": "Code langue (FR, EN, JP, DE)",
      "is_foil": "Holo/Foil, Reverse ou Normal",
      "estimated_price_eur": 2.50
    }
    """

  chat_completion = groq_client.chat.completions.create(
      messages=[{
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
      }],
      model="llama-3.2-11b-vision-preview",
      response_format={"type": "json_object"},
  )

  return json.loads(chat_completion.choices[0].message.content)


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
      with st.spinner("Analyse visuelle en cours par Groq (Llama Vision)..."):
        pil_image = Image.open(image_input).convert("RGB")
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format="JPEG")

        try:
          card = analyze_card_image_groq(img_byte_arr.getvalue())

          st.markdown("---")
          st.subheader(f"🔮 {card.get('card_name', 'Carte inconnue')}")

          col1, col2, col3 = st.columns(3)
          with col1:
            st.markdown(f"**Jeu :** `{card.get('game_name', 'N/A')}`")
            st.markdown(f"**Extension :** {card.get('set_name', 'N/A')}")
          with col2:
            st.markdown(f"**Numéro :** {card.get('card_number', 'N/A')}")
            st.markdown(f"**Langue :** {card.get('language', 'FR')}")
          with col3:
            st.markdown(f"**Finition :** {card.get('is_foil', 'Normal')}")
            price = float(card.get("estimated_price_eur", 0.0))
            st.markdown(f"**Cote est. :** ~{price:.2f} €")

          cardmarket_url = build_cardmarket_url(
              card.get("cardmarket_slug", "Pokemon"),
              card.get("cardmarket_search_term", card.get("card_name", "")),
          )
          st.markdown(
              f'<p style="margin-top: 5px;"><a href="{cardmarket_url}"'
              ' target="_blank">↗ Voir la cote Cardmarket</a></p>',
              unsafe_allow_html=True,
          )

          with st.form("single_add_form"):
            c_qty, c_cond, c_loc = st.columns(3)
            with c_qty:
              quantite = st.number_input(
                  "Quantité", min_value=1, value=1, step=1
              )
            with c_cond:
              condition = st.selectbox(
                  "État",
                  [
                      "Near Mint (NM)",
                      "Excellent (EX)",
                      "Good (GD)",
                      "Light Played (LP)",
                      "Played (PL)",
                  ],
              )
            with c_loc:
              emplacement = st.text_input(
                  "Emplacement physique", value="Classeur 1"
              )

            if st.form_submit_button("⚡ Ajouter au stock"):
              date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
              sheet.append_row([
                  date_str,
                  card.get("game_name", ""),
                  card.get("card_name", ""),
                  card.get("set_name", ""),
                  card.get("card_number", ""),
                  card.get("is_foil", "Normal"),
                  card.get("language", "FR"),
                  condition,
                  emplacement,
                  quantite,
                  price,
                  cardmarket_url,
              ])
              st.success(
                  f"✅ {card.get('card_name')} enregistré avec succès !"
              )

        except Exception as e:
          st.error(f"⚠️ Erreur d'analyse : {e}")

  else:
    uploaded_files = st.file_uploader(
        "Importe plusieurs images de cartes simultanément",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

    if uploaded_files:
      c_batch_loc, c_batch_cond = st.columns(2)
      with c_batch_loc:
        batch_loc = st.text_input(
            "Emplacement commun pour ce lot :", value="Boîte Arrivage"
        )
      with c_batch_cond:
        batch_cond = st.selectbox(
            "État commun :",
            [
                "Near Mint (NM)",
                "Excellent (EX)",
                "Good (GD)",
                "Light Played (LP)",
            ],
        )

      if st.button(f"⚡ Analyser le lot ({len(uploaded_files)} images)"):
        progress_bar = st.progress(0)
        analyzed_cards = []

        for idx, file in enumerate(uploaded_files):
          pil_img = Image.open(file).convert("RGB")
          img_byte_arr = io.BytesIO()
          pil_img.save(img_byte_arr, format="JPEG")

          try:
            parsed_card = analyze_card_image_groq(img_byte_arr.getvalue())
            analyzed_cards.append(parsed_card)
          except Exception as e:
            st.warning(f"Impossible d'analyser l'image {file.name}: {e}")

          progress_bar.progress((idx + 1) / len(uploaded_files))

        st.session_state["batch_results"] = analyzed_cards
        st.success("Analyse du lot terminée !")

    if "batch_results" in st.session_state and st.session_state["batch_results"]:
      st.markdown("### 📋 Récapitulatif du lot")

      batch_data = []
      for c in st.session_state["batch_results"]:
        url = build_cardmarket_url(
            c.get("cardmarket_slug", "Pokemon"),
            c.get("cardmarket_search_term", c.get("card_name", "")),
        )
        batch_data.append({
            "Jeu": c.get("game_name", ""),
            "Nom": c.get("card_name", ""),
            "Extension": c.get("set_name", ""),
            "Numéro": c.get("card_number", ""),
            "Finition": c.get("is_foil", "Normal"),
            "Langue": c.get("language", "FR"),
            "Prix Est. (€)": c.get("estimated_price_eur", 0.0),
            "URL": url,
        })

      batch_df = pd.DataFrame(batch_data)
      st.dataframe(batch_df, use_container_width=True)

      if st.button("💾 Tout valider dans Google Sheets"):
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        for item in batch_data:
          sheet.append_row([
              date_str,
              item["Jeu"],
              item["Nom"],
              item["Extension"],
              item["Numéro"],
              item["Finition"],
              item["Langue"],
              batch_cond,
              batch_loc,
              1,
              item["Prix Est. (€)"],
              item["URL"],
          ])
        st.success("✅ Lot ajouté au stock !")
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
      df["Prix Est. (€)"] = pd.to_numeric(
          df.get("Prix Est. (€)", 0), errors="coerce"
      ).fillna(0.0)
      df["Valeur Totale (€)"] = df["Quantité"] * df["Prix Est. (€)"]

      col_m1, col_m2, col_m3, col_m4 = st.columns(4)
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
                "Valeur Estimée", f"{df['Valeur Totale (€)'].sum():.2f} €", "💎"
            ),
            unsafe_allow_html=True,
        )
      with col_m4:
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
                f"📍 `{row.get('Emplacement', 'N/A')}` |"
                f" `{row.get('État', 'NM')}`"
            )
            st.caption(
                f"{row.get('Finition', 'Normal')} • {row.get('Langue', 'FR')} •"
                f" ~{row.get('Prix Est. (€)', 0):.2f} €"
            )

          with c_qty:
            st.markdown(f"### {row['Quantité']} ex.")

          with c_actions:
            b1, b2, b3 = st.columns(3)
            if b1.button("➕", key=f"add_{idx}"):
              df.loc[idx, "Quantité"] += 1
              update_sheet_data(df.drop(columns=["Valeur Totale (€)"]))
              st.rerun()

            if b2.button("➖", key=f"sub_{idx}"):
              if df.loc[idx, "Quantité"] > 1:
                df.loc[idx, "Quantité"] -= 1
              else:
                df = df.drop(idx)
              update_sheet_data(df.drop(columns=["Valeur Totale (€)"]))
              st.rerun()

            if b3.button("🗑️", key=f"del_{idx}"):
              df = df.drop(idx)
              update_sheet_data(df.drop(columns=["Valeur Totale (€)"]))
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
