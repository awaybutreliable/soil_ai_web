from flask import Flask, render_template_string, request, jsonify
import random
import threading
import time

app = Flask(__name__)

# -----------------------------
# Crop nutrient targets (demo)
# Values are simplified example targets (not agronomy-perfect).
# -----------------------------
CROP_REQUIREMENTS = {
    "tomato":     {"N": 120, "P": 60, "K": 80},
    "rice":       {"N": 100, "P": 50, "K": 50},
    "wheat":      {"N": 90,  "P": 40, "K": 40},
    "maize":      {"N": 110, "P": 50, "K": 60},
    "potato":     {"N": 140, "P": 70, "K": 140},
    "onion":      {"N": 80,  "P": 40, "K": 60},
    "cotton":     {"N": 120, "P": 60, "K": 60},
    "soybean":    {"N": 30,  "P": 60, "K": 40},
    "sugarcane":  {"N": 180, "P": 80, "K": 120},
    "groundnut":  {"N": 25,  "P": 50, "K": 50},
}

CROP_LABELS = {
    "tomato": "Tomato",
    "rice": "Rice",
    "wheat": "Wheat",
    "maize": "Maize (Corn)",
    "potato": "Potato",
    "onion": "Onion",
    "cotton": "Cotton",
    "soybean": "Soybean",
    "sugarcane": "Sugarcane",
    "groundnut": "Groundnut (Peanut)",
}

# -----------------------------
# Simulated live soil sensor feed
# -----------------------------
soil_data = {
    "N": 40,
    "P": 35,
    "K": 30,
    "moisture": 55,
    "ph": 6.8,
    "temp": 28
}

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def simulate_live_data():
    while True:
        soil_data["N"] = clamp(soil_data["N"] + random.randint(-2, 2), 0, 200)
        soil_data["P"] = clamp(soil_data["P"] + random.randint(-2, 2), 0, 200)
        soil_data["K"] = clamp(soil_data["K"] + random.randint(-2, 2), 0, 200)
        soil_data["moisture"] = clamp(soil_data["moisture"] + random.randint(-1, 1), 0, 100)
        soil_data["temp"] = clamp(soil_data["temp"] + random.randint(-1, 1), -10, 60)
        soil_data["ph"] = round(clamp(soil_data["ph"] + random.choice([-0.1, 0, 0.1]), 4.5, 8.5), 1)
        time.sleep(5)

threading.Thread(target=simulate_live_data, daemon=True).start()

# -----------------------------
# Fertilizer conversions (demo)
# -----------------------------
PPM_TO_KG_PER_HA = 2.0
UREA_N = 0.46
DAP_P = 0.46
MOP_K = 0.60

def calculate_deficit_ppm(crop: str):
    req = CROP_REQUIREMENTS[crop]
    return {
        "N": max(req["N"] - soil_data["N"], 0),
        "P": max(req["P"] - soil_data["P"], 0),
        "K": max(req["K"] - soil_data["K"], 0),
    }

def calculate_fertilizers_total(crop: str, hectares: float):
    deficit = calculate_deficit_ppm(crop)

    n_kg_ha = deficit["N"] * PPM_TO_KG_PER_HA
    p_kg_ha = deficit["P"] * PPM_TO_KG_PER_HA
    k_kg_ha = deficit["K"] * PPM_TO_KG_PER_HA

    urea_kg_ha = (n_kg_ha / UREA_N) if n_kg_ha > 0 else 0
    dap_kg_ha  = (p_kg_ha / DAP_P) if p_kg_ha > 0 else 0
    mop_kg_ha  = (k_kg_ha / MOP_K) if k_kg_ha > 0 else 0

    fertilizers = {
        "Urea": round(urea_kg_ha * hectares, 1),
        "DAP":  round(dap_kg_ha * hectares, 1),
        "MOP":  round(mop_kg_ha * hectares, 1),
    }
    return deficit, fertilizers

# -----------------------------
# Farmer "what to do" advice
# -----------------------------
def generate_farmer_advice(crop: str, hectares: float, fertilizers: dict, soil: dict):
    steps = []

    if fertilizers.get("Urea", 0) > 0:
        steps.append(f"Apply {fertilizers['Urea']} kg Urea")
    if fertilizers.get("DAP", 0) > 0:
        steps.append(f"Apply {fertilizers['DAP']} kg DAP")
    if fertilizers.get("MOP", 0) > 0:
        steps.append(f"Apply {fertilizers['MOP']} kg MOP")

    crop_name = CROP_LABELS.get(crop, crop).lower()

    if steps:
        fert_text = " and ".join(steps) + f" to your {hectares} ha {crop_name} field."
    else:
        fert_text = "No fertilizer needed right now. Nutrients look sufficient."

    moisture = soil.get("moisture", 50)
    if moisture < 40:
        water_text = "Irrigation: High watering required (soil is dry)."
    elif moisture < 60:
        water_text = "Irrigation: Moderate watering recommended."
    else:
        water_text = "Irrigation: Soil moisture is sufficient."

    temp = soil.get("temp", 25)
    if temp >= 35:
        climate_text = "Climate: Very hot — water early morning/evening if possible."
    elif temp <= 15:
        climate_text = "Climate: Cold — nutrient uptake may be slower."
    else:
        climate_text = "Climate: Temperature is okay."

    return fert_text, water_text, climate_text

# -----------------------------
# Languages
# -----------------------------
TRANSLATIONS = {
    "English": {
        "title": "Soil AI Live Dashboard",
        "crop": "Select Crop",
        "hectares": "Land (hectares)",
        "language": "Language",
        "analyze": "Analyze",
        "live": "Live Soil Data",
        "fert": "Fertilizer Recommendation (kg total)",
        "deficit": "Deficiency (ppm)",
        "action": "Recommended Action",
    },
    "Hindi": {
        "title": "मृदा एआई डैशबोर्ड",
        "crop": "फसल चुनें",
        "hectares": "भूमि (हेक्टेयर)",
        "language": "भाषा",
        "analyze": "विश्लेषण करें",
        "live": "लाइव मिट्टी डेटा",
        "fert": "उर्वरक सिफारिश (कुल किलो)",
        "deficit": "कमी (ppm)",
        "action": "क्या करें",
    },
    "Telugu": {
        "title": "సాయిల్ ఏఐ డాష్‌బోర్డ్",
        "crop": "పంట ఎంచుకోండి",
        "hectares": "భూమి (హెక్టార్లు)",
        "language": "భాష",
        "analyze": "విశ్లేషించండి",
        "live": "లైవ్ నేల డేటా",
        "fert": "ఎరువు సిఫారసు (మొత్తం కిలోలు)",
        "deficit": "లోపం (ppm)",
        "action": "ఏం చేయాలి",
    }
}

# Build crop <option> HTML automatically
def build_crop_options(selected_crop: str) -> str:
    options = []
    for key in CROP_REQUIREMENTS.keys():
        label = CROP_LABELS.get(key, key.title())
        selected = "selected" if key == selected_crop else ""
        options.append(f"<option value='{key}' {selected}>{label}</option>")
    return "\n".join(options)

HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>{{ t.title }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { font-family: Arial; background:#e8f5e9; text-align:center; margin:0; padding:18px; }
    h1 { color:#1b5e20; margin:10px 0 18px; }
    .box { background:white; padding:18px; margin:14px auto; width:min(92%, 700px); border-radius:12px; }
    .row { display:flex; justify-content:center; gap:16px; flex-wrap:wrap; align-items:flex-end; }
    .row > div { text-align:left; min-width:180px; }
    label { font-weight:700; }
    select, input { padding:8px; margin-top:6px; min-width:170px; }
    button { padding:10px 18px; background:#2e7d32; color:white; border:0; border-radius:8px; cursor:pointer; }
    button:hover { opacity:0.92; }
    .kv { display:grid; grid-template-columns:1fr 1fr; gap:8px 18px; margin-top:12px; text-align:left; }
    .pill { display:inline-block; background:#e0f2f1; padding:6px 10px; border-radius:999px; margin:4px; }
    @media (max-width: 600px) { .kv { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <h1>🌱 <span id="title">{{ t.title }}</span></h1>

  <div class="box">
    <form id="controls">
      <div class="row">
        <div>
          <label id="lblCrop">{{ t.crop }}</label><br>
          <select name="crop" id="crop">
            {{ crop_options|safe }}
          </select>
        </div>

        <div>
          <label id="lblHectares">{{ t.hectares }}</label><br>
          <input type="number" step="0.1" min="0.1" name="hectares" id="hectares" value="{{ hectares }}" required>
        </div>

        <div>
          <label id="lblLang">{{ t.language }}</label><br>
          <select name="language" id="language">
            <option value="English" {% if language=='English' %}selected{% endif %}>English</option>
            <option value="Hindi"   {% if language=='Hindi' %}selected{% endif %}>Hindi</option>
            <option value="Telugu"  {% if language=='Telugu' %}selected{% endif %}>Telugu</option>
          </select>
        </div>

        <div>
          <button type="submit" id="btnAnalyze">{{ t.analyze }}</button>
        </div>
      </div>
    </form>

    <p style="margin-top:14px">
      <span class="pill" id="pillCrop">Crop: {{ crop|upper }}</span>
      <span class="pill" id="pillArea">Area: {{ hectares }} ha</span>
      <span class="pill">Live: 5s</span>
    </p>
  </div>

  <div class="box">
    <h2>📡 <span id="hdrLive">{{ t.live }}</span></h2>
    <div class="kv">
      <div>Nitrogen (N)</div><div id="soilN">—</div>
      <div>Phosphorus (P)</div><div id="soilP">—</div>
      <div>Potassium (K)</div><div id="soilK">—</div>
      <div>Moisture</div><div id="soilM">—</div>
      <div>pH</div><div id="soilPH">—</div>
      <div>Temperature</div><div id="soilT">—</div>
    </div>
  </div>

  <div class="box">
    <h2>🧪 <span id="hdrFert">{{ t.fert }}</span></h2>

    <h3 style="margin-bottom:6px"><span id="hdrDef">{{ t.deficit }}</span></h3>
    <div class="kv">
      <div>N</div><div id="defN">—</div>
      <div>P</div><div id="defP">—</div>
      <div>K</div><div id="defK">—</div>
    </div>

    <h3 style="margin-top:18px;margin-bottom:6px">Fertilizers</h3>
    <div class="kv">
      <div>Urea</div><div id="fertU">—</div>
      <div>DAP</div><div id="fertD">—</div>
      <div>MOP</div><div id="fertMOP">—</div>
    </div>
  </div>

  <div class="box">
    <h2>✅ <span id="hdrAction">{{ t.action }}</span></h2>
    <div class="kv">
      <div>Fertilizer</div><div id="advFert">—</div>
      <div>Irrigation</div><div id="advWater">—</div>
      <div>Climate</div><div id="advClimate">—</div>
    </div>
  </div>

<script>
  let state = {
    crop: "{{ crop }}",
    hectares: "{{ hectares }}",
    language: "{{ language }}"
  };

  function applyText(t) {
    document.getElementById("title").textContent = t.title;
    document.getElementById("lblCrop").textContent = t.crop;
    document.getElementById("lblHectares").textContent = t.hectares;
    document.getElementById("lblLang").textContent = t.language;
    document.getElementById("btnAnalyze").textContent = t.analyze;
    document.getElementById("hdrLive").textContent = t.live;
    document.getElementById("hdrFert").textContent = t.fert;
    document.getElementById("hdrDef").textContent = t.deficit;
    document.getElementById("hdrAction").textContent = t.action;
  }

  async function refreshData() {
    const params = new URLSearchParams(state);
    const r = await fetch("/data?" + params.toString());
    const d = await r.json();

    applyText(d.text);

    document.getElementById("soilN").textContent = d.soil.N;
    document.getElementById("soilP").textContent = d.soil.P;
    document.getElementById("soilK").textContent = d.soil.K;
    document.getElementById("soilM").textContent = d.soil.moisture;
    document.getElementById("soilPH").textContent = d.soil.ph;
    document.getElementById("soilT").textContent = d.soil.temp + " °C";

    document.getElementById("defN").textContent = d.deficit.N + " ppm";
    document.getElementById("defP").textContent = d.deficit.P + " ppm";
    document.getElementById("defK").textContent = d.deficit.K + " ppm";

    document.getElementById("fertU").textContent = d.fertilizers.Urea + " kg";
    document.getElementById("fertD").textContent = d.fertilizers.DAP + " kg";
    document.getElementById("fertMOP").textContent = d.fertilizers.MOP + " kg";

    document.getElementById("advFert").textContent = d.advice.fertilizer;
    document.getElementById("advWater").textContent = d.advice.irrigation;
    document.getElementById("advClimate").textContent = d.advice.climate;

    document.getElementById("pillCrop").textContent = "Crop: " + d.crop.toUpperCase();
    document.getElementById("pillArea").textContent = "Area: " + d.hectares + " ha";
  }

  document.getElementById("controls").addEventListener("submit", (e) => {
    e.preventDefault();
    state.crop = document.getElementById("crop").value;
    state.hectares = document.getElementById("hectares").value || "1";
    state.language = document.getElementById("language").value;
    refreshData();
  });

  refreshData();
  setInterval(refreshData, 5000);
</script>
</body>
</html>
"""

def safe_float(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

@app.route("/", methods=["GET"])
def dashboard():
    crop = (request.args.get("crop", "tomato") or "tomato").lower()
    language = request.args.get("language", "English") or "English"
    hectares = safe_float(request.args.get("hectares", "1"), default=1.0)

    if crop not in CROP_REQUIREMENTS:
        crop = "tomato"
    if language not in TRANSLATIONS:
        language = "English"
    hectares = clamp(hectares, 0.1, 10_000)

    crop_options = build_crop_options(crop)

    return render_template_string(
        HTML,
        crop=crop,
        hectares=hectares,
        language=language,
        t=TRANSLATIONS[language],
        crop_options=crop_options
    )

@app.route("/data", methods=["GET"])
def data():
    crop = (request.args.get("crop", "tomato") or "tomato").lower()
    language = request.args.get("language", "English") or "English"
    hectares = safe_float(request.args.get("hectares", "1"), default=1.0)

    if crop not in CROP_REQUIREMENTS:
        crop = "tomato"
    if language not in TRANSLATIONS:
        language = "English"
    hectares = clamp(hectares, 0.1, 10_000)

    deficit, fertilizers = calculate_fertilizers_total(crop, hectares)
    fert_text, water_text, climate_text = generate_farmer_advice(crop, hectares, fertilizers, soil_data)

    return jsonify({
        "crop": crop,
        "hectares": hectares,
        "soil": soil_data,
        "deficit": deficit,
        "fertilizers": fertilizers,
        "advice": {
            "fertilizer": fert_text,
            "irrigation": water_text,
            "climate": climate_text
        },
        "text": TRANSLATIONS[language]
    })

if __name__ == "__main__":
    # host 0.0.0.0 lets other devices on Wi-Fi access it
    app.run(host="0.0.0.0", port=5000, debug=False)
