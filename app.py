from flask import Flask, render_template_string, request, jsonify, Response
import random
import threading
import time
from collections import deque
from datetime import datetime
import csv
import io

app = Flask(__name__)

# -----------------------------
# Crop nutrient targets (demo values)
# -----------------------------
CROP_REQUIREMENTS = {
    "rice":       {"N": 100, "P": 50, "K": 50},
    "wheat":      {"N": 90,  "P": 40, "K": 40},
    "maize":      {"N": 110, "P": 50, "K": 60},
    "tomato":     {"N": 120, "P": 60, "K": 80},
    "potato":     {"N": 140, "P": 70, "K": 140},
    "onion":      {"N": 80,  "P": 40, "K": 60},
    "cotton":     {"N": 120, "P": 60, "K": 60},
    "soybean":    {"N": 30,  "P": 60, "K": 40},
    "sugarcane":  {"N": 180, "P": 80, "K": 120},
    "groundnut":  {"N": 25,  "P": 50, "K": 50},
    "banana":     {"N": 150, "P": 60, "K": 200},
    "chili":      {"N": 100, "P": 50, "K": 70},
    "cabbage":    {"N": 120, "P": 60, "K": 80},
    "cauliflower":{"N": 110, "P": 55, "K": 75},
    "chickpea":   {"N": 20,  "P": 45, "K": 35},
    "lentil":     {"N": 20,  "P": 40, "K": 30},
    "sunflower":  {"N": 80,  "P": 50, "K": 60},
    "mustard":    {"N": 70,  "P": 40, "K": 40},
    "barley":     {"N": 75,  "P": 35, "K": 35},
    "sorghum":    {"N": 85,  "P": 40, "K": 45},
}

CROP_LABELS = {
    "English": {
        "rice": "Rice", "wheat": "Wheat", "maize": "Maize", "tomato": "Tomato",
        "potato": "Potato", "onion": "Onion", "cotton": "Cotton", "soybean": "Soybean",
        "sugarcane": "Sugarcane", "groundnut": "Groundnut", "banana": "Banana",
        "chili": "Chili", "cabbage": "Cabbage", "cauliflower": "Cauliflower",
        "chickpea": "Chickpea", "lentil": "Lentil", "sunflower": "Sunflower",
        "mustard": "Mustard", "barley": "Barley", "sorghum": "Sorghum",
    },
    "Hindi": {
        "rice": "चावल", "wheat": "गेहूं", "maize": "मक्का", "tomato": "टमाटर",
        "potato": "आलू", "onion": "प्याज", "cotton": "कपास", "soybean": "सोयाबीन",
        "sugarcane": "गन्ना", "groundnut": "मूंगफली", "banana": "केला",
        "chili": "मिर्च", "cabbage": "पत्ता गोभी", "cauliflower": "फूल गोभी",
        "chickpea": "चना", "lentil": "मसूर", "sunflower": "सूरजमुखी",
        "mustard": "सरसों", "barley": "जौ", "sorghum": "ज्वार",
    },
    "Telugu": {
        "rice": "వరి", "wheat": "గోధుమ", "maize": "మొక్కజొన్న", "tomato": "టమాటా",
        "potato": "బంగాళదుంప", "onion": "ఉల్లిపాయ", "cotton": "పత్తి", "soybean": "సోయాబీన్",
        "sugarcane": "చెరకు", "groundnut": "వేరుశెనగ", "banana": "అరటి",
        "chili": "మిర్చి", "cabbage": "క్యాబేజీ", "cauliflower": "కాలీఫ్లవర్",
        "chickpea": "సెనగ", "lentil": "మసూర్", "sunflower": "పొద్దుతిరుగుడు",
        "mustard": "ఆవాలు", "barley": "బార్లీ", "sorghum": "జొన్న",
    }
}

FERTILIZER_PRICES = {
    "Urea": 6,
    "DAP": 25,
    "MOP": 17,
}

STATE_OPTIONS = [
    "Andhra Pradesh", "Telangana", "Karnataka", "Tamil Nadu",
    "Maharashtra", "Punjab", "Haryana", "Uttar Pradesh"
]

DISTRICT_OPTIONS = [
    "Krishna", "Guntur", "Prakasam", "NTR", "Hyderabad",
    "Warangal", "Chennai", "Bengaluru", "Pune", "Ludhiana"
]

SOIL_TYPES = [
    "Red Soil", "Black Soil", "Alluvial Soil", "Sandy Soil", "Clay Soil", "Loamy Soil"
]

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

history = deque(maxlen=20)
analysis_logs = deque(maxlen=500)

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

        history.append({
            "N": soil_data["N"],
            "P": soil_data["P"],
            "K": soil_data["K"],
            "moisture": soil_data["moisture"],
            "temp": soil_data["temp"],
            "ph": soil_data["ph"],
        })

        time.sleep(5)

threading.Thread(target=simulate_live_data, daemon=True).start()

# -----------------------------
# Fertilizer conversion
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
        "DAP": round(dap_kg_ha * hectares, 1),
        "MOP": round(mop_kg_ha * hectares, 1),
    }
    return deficit, fertilizers

TEXT = {
    "English": {
        "title": "Soil AI Final Dashboard",
        "subtitle": "Prototype advisory tool for smart farming support.",
        "crop": "Select Crop",
        "land": "Land (hectares)",
        "language": "Language",
        "state": "State",
        "district": "District",
        "soil_type": "Soil Type",
        "analyze": "Analyze",
        "live": "Live Soil Data",
        "fert": "Fertilizer Recommendation",
        "action": "Recommended Action",
        "speak": "Speak Advice",
        "soil_score": "Soil Health Score",
        "weather": "Weather & Irrigation Hint",
        "crop_label": "Crop",
        "area_label": "Area",
        "fertilizers": "Fertilizers",
        "deficit": "Deficiency",
        "risk": "Risk Warnings",
        "yield": "Estimated Yield",
        "cost": "Estimated Fertilizer Cost",
        "water_use": "Estimated Irrigation Need",
        "schedule": "Application Schedule",
        "trend": "Trend Snapshot",
        "evidence": "Explanation Panel",
        "disclaimer_title": "Prototype Disclaimer",
        "disclaimer_text": "This tool provides advisory estimates only. Verify recommendations with local agronomy guidance before field use.",
        "download": "Download Log CSV",
        "score_good": "Good",
        "score_medium": "Moderate",
        "score_poor": "Poor",
        "no_fert": "No fertilizer needed right now. Nutrients look sufficient.",
        "apply": "Apply about {amount} kg {name}",
        "joiner": " and ",
        "field_suffix": " to your {hectares} ha {crop} field.",
        "irr_high": "Irrigation: High watering required (soil is dry).",
        "irr_mod": "Irrigation: Moderate watering recommended.",
        "irr_ok": "Irrigation: Soil moisture is sufficient.",
        "cl_hot": "Climate: Very hot — water early morning or evening if possible.",
        "cl_cold": "Climate: Cold — nutrient uptake may be slower.",
        "cl_ok": "Climate: Temperature is okay.",
        "weather_unavailable": "Weather hint unavailable. Allow location for local forecast.",
        "rain_heavy": "Rain likely soon. Reduce irrigation for now.",
        "rain_possible": "Some rain is possible. Irrigate carefully.",
        "rain_none": "Low rain chance. Continue irrigation based on soil moisture.",
        "temp_hint_hot": "Hot day expected. Avoid midday watering.",
        "temp_hint_cool": "Cool conditions expected.",
        "risk_n_low": "Nitrogen critically low.",
        "risk_ph_low": "Soil is too acidic.",
        "risk_ph_high": "Soil is too alkaline.",
        "risk_dry": "Dry soil risk.",
        "risk_heat": "Heat stress risk.",
        "risk_none": "No major risk detected.",
        "yield_unit": "tons / hectare",
        "water_unit": "liters / hectare",
        "basal": "50% basal application",
        "vegetative": "30% vegetative stage",
        "flowering": "20% flowering stage",
        "increasing": "increasing",
        "decreasing": "decreasing",
        "stable": "stable",
        "target": "Target",
        "current": "Current",
        "formula": "Formula",
        "region": "Region",
    },
    "Hindi": {
        "title": "सॉइल एआई अंतिम डैशबोर्ड",
        "subtitle": "स्मार्ट खेती सहायता के लिए प्रोटोटाइप सलाह उपकरण।",
        "crop": "फसल चुनें",
        "land": "भूमि (हेक्टेयर)",
        "language": "भाषा",
        "state": "राज्य",
        "district": "जिला",
        "soil_type": "मिट्टी का प्रकार",
        "analyze": "विश्लेषण करें",
        "live": "लाइव मिट्टी डेटा",
        "fert": "उर्वरक सिफारिश",
        "action": "क्या करें",
        "speak": "सलाह सुनें",
        "soil_score": "मिट्टी स्वास्थ्य स्कोर",
        "weather": "मौसम और सिंचाई संकेत",
        "crop_label": "फसल",
        "area_label": "क्षेत्र",
        "fertilizers": "उर्वरक",
        "deficit": "कमी",
        "risk": "जोखिम चेतावनी",
        "yield": "अनुमानित उपज",
        "cost": "अनुमानित उर्वरक लागत",
        "water_use": "अनुमानित सिंचाई आवश्यकता",
        "schedule": "प्रयोग कार्यक्रम",
        "trend": "रुझान",
        "evidence": "व्याख्या पैनल",
        "disclaimer_title": "प्रोटोटाइप चेतावनी",
        "disclaimer_text": "यह उपकरण केवल अनुमानित सलाह देता है। खेत में उपयोग से पहले स्थानीय कृषि विशेषज्ञ से पुष्टि करें।",
        "download": "लॉग CSV डाउनलोड करें",
        "score_good": "अच्छा",
        "score_medium": "मध्यम",
        "score_poor": "कमज़ोर",
        "no_fert": "अभी उर्वरक की जरूरत नहीं है। पोषक तत्व पर्याप्त हैं।",
        "apply": "लगभग {amount} किलो {name} डालें",
        "joiner": " और ",
        "field_suffix": "{hectares} हेक्टेयर {crop} खेत में।",
        "irr_high": "सिंचाई: अधिक पानी की जरूरत है (मिट्टी सूखी है)।",
        "irr_mod": "सिंचाई: मध्यम पानी देने की सलाह।",
        "irr_ok": "सिंचाई: मिट्टी में पर्याप्त नमी है।",
        "cl_hot": "मौसम: बहुत गर्म — सुबह या शाम पानी दें।",
        "cl_cold": "मौसम: ठंड — पोषक अवशोषण धीमा हो सकता है।",
        "cl_ok": "मौसम: तापमान ठीक है।",
        "weather_unavailable": "मौसम संकेत उपलब्ध नहीं। स्थानीय पूर्वानुमान के लिए लोकेशन अनुमति दें।",
        "rain_heavy": "जल्द बारिश की संभावना है। अभी सिंचाई कम करें।",
        "rain_possible": "कुछ बारिश संभव है। सावधानी से सिंचाई करें।",
        "rain_none": "बारिश की संभावना कम है। मिट्टी की नमी के अनुसार सिंचाई जारी रखें।",
        "temp_hint_hot": "गर्म दिन की संभावना है। दोपहर में पानी न दें।",
        "temp_hint_cool": "ठंडे मौसम की संभावना है।",
        "risk_n_low": "नाइट्रोजन बहुत कम है।",
        "risk_ph_low": "मिट्टी बहुत अम्लीय है।",
        "risk_ph_high": "मिट्टी बहुत क्षारीय है।",
        "risk_dry": "सूखी मिट्टी का जोखिम।",
        "risk_heat": "गर्मी तनाव का जोखिम।",
        "risk_none": "कोई बड़ा जोखिम नहीं मिला।",
        "yield_unit": "टन / हेक्टेयर",
        "water_unit": "लीटर / हेक्टेयर",
        "basal": "50% बेसल प्रयोग",
        "vegetative": "30% वृद्धि चरण",
        "flowering": "20% फूल आने का चरण",
        "increasing": "बढ़ रहा है",
        "decreasing": "घट रहा है",
        "stable": "स्थिर",
        "target": "लक्ष्य",
        "current": "वर्तमान",
        "formula": "सूत्र",
        "region": "क्षेत्र",
    },
    "Telugu": {
        "title": "సాయిల్ ఏఐ ఫైనల్ డాష్‌బోర్డ్",
        "subtitle": "స్మార్ట్ వ్యవసాయ సహాయానికి ప్రోటోటైప్ సలహా సాధనం.",
        "crop": "పంట ఎంచుకోండి",
        "land": "భూమి (హెక్టార్లు)",
        "language": "భాష",
        "state": "రాష్ట్రం",
        "district": "జిల్లా",
        "soil_type": "నేల రకం",
        "analyze": "విశ్లేషించండి",
        "live": "లైవ్ నేల డేటా",
        "fert": "ఎరువు సిఫారసు",
        "action": "ఏం చేయాలి",
        "speak": "సలహా వినండి",
        "soil_score": "నేల ఆరోగ్య స్కోర్",
        "weather": "వాతావరణం మరియు నీటి సూచన",
        "crop_label": "పంట",
        "area_label": "విస్తీర్ణం",
        "fertilizers": "ఎరువులు",
        "deficit": "లోపం",
        "risk": "ప్రమాద హెచ్చరికలు",
        "yield": "అంచనా దిగుబడి",
        "cost": "అంచనా ఎరువు ఖర్చు",
        "water_use": "అంచనా నీటి అవసరం",
        "schedule": "ఎరువు వేయు షెడ్యూల్",
        "trend": "మార్పుల దిశ",
        "evidence": "వ్యాఖ్యానం ప్యానెల్",
        "disclaimer_title": "ప్రోటోటైప్ హెచ్చరిక",
        "disclaimer_text": "ఈ సాధనం అంచనా సలహాలు మాత్రమే ఇస్తుంది. పొలంలో ఉపయోగించే ముందు స్థానిక వ్యవసాయ నిపుణులను సంప్రదించండి.",
        "download": "లాగ్ CSV డౌన్‌లోడ్",
        "score_good": "మంచిది",
        "score_medium": "మధ్యస్థం",
        "score_poor": "బలహీనంగా ఉంది",
        "no_fert": "ప్రస్తుతం ఎరువులు అవసరం లేదు. పోషకాలు సరిపోతున్నాయి.",
        "apply": "సుమారు {amount} కిలోల {name} వేయండి",
        "joiner": " మరియు ",
        "field_suffix": "{hectares} హెక్టార్ల {crop} పొలంలో.",
        "irr_high": "నీరు: ఎక్కువ నీరు అవసరం (నేల పొడిగా ఉంది).",
        "irr_mod": "నీరు: మధ్యమ స్థాయిలో నీరు ఇవ్వండి.",
        "irr_ok": "నీరు: నేల తేమ సరిపోతుంది.",
        "cl_hot": "వాతావరణం: చాలా వేడి — ఉదయం లేదా సాయంత్రం నీరు ఇవ్వండి.",
        "cl_cold": "వాతావరణం: చల్లగా ఉంది — పోషక శోషణ నెమ్మదిగా ఉండొచ్చు.",
        "cl_ok": "వాతావరణం: ఉష్ణోగ్రత బాగుంది.",
        "weather_unavailable": "వాతావరణ సూచన అందుబాటులో లేదు. స్థానిక సమాచారం కోసం లోకేషన్ అనుమతించండి.",
        "rain_heavy": "త్వరలో వర్షం వచ్చే అవకాశం ఉంది. ఇప్పటికి నీరు తగ్గించండి.",
        "rain_possible": "కొంత వర్షం వచ్చే అవకాశం ఉంది. జాగ్రత్తగా నీరు ఇవ్వండి.",
        "rain_none": "వర్షం అవకాశం తక్కువ. నేల తేమను బట్టి నీరు కొనసాగించండి.",
        "temp_hint_hot": "వేడి రోజు వచ్చే అవకాశం ఉంది. మధ్యాహ్నం నీరు ఇవ్వవద్దు.",
        "temp_hint_cool": "చల్లటి వాతావరణం ఉండొచ్చు.",
        "risk_n_low": "నైట్రోజన్ చాలా తక్కువగా ఉంది.",
        "risk_ph_low": "నేల చాలా ఆమ్లంగా ఉంది.",
        "risk_ph_high": "నేల చాలా క్షారంగా ఉంది.",
        "risk_dry": "పొడి నేల ప్రమాదం.",
        "risk_heat": "వేడిమి ఒత్తిడి ప్రమాదం.",
        "risk_none": "పెద్ద ప్రమాదం కనిపించలేదు.",
        "yield_unit": "టన్నులు / హెక్టేరు",
        "water_unit": "లీటర్లు / హెక్టేరు",
        "basal": "50% బేసల్ వేయండి",
        "vegetative": "30% ఎదుగుదల దశలో",
        "flowering": "20% పుష్పించే దశలో",
        "increasing": "పెరుగుతోంది",
        "decreasing": "తగ్గుతోంది",
        "stable": "స్థిరంగా ఉంది",
        "target": "లక్ష్యం",
        "current": "ప్రస్తుత",
        "formula": "సూత్రం",
        "region": "ప్రాంతం",
    }
}

FERT_NAMES = {
    "English": {"Urea": "Urea", "DAP": "DAP", "MOP": "MOP"},
    "Hindi": {"Urea": "यूरिया", "DAP": "डीएपी", "MOP": "एमओपी"},
    "Telugu": {"Urea": "యూరియా", "DAP": "డీఎపీ", "MOP": "ఎంఓపీ"},
}

def compute_soil_health_score(crop: str):
    deficit = calculate_deficit_ppm(crop)

    npk_penalty = (deficit["N"] + deficit["P"] + deficit["K"]) / 6.0
    moisture_penalty = abs(soil_data["moisture"] - 60) * 0.5
    ph_penalty = abs(soil_data["ph"] - 6.5) * 8
    temp_penalty = abs(soil_data["temp"] - 28) * 0.8

    score = 100 - npk_penalty - moisture_penalty - ph_penalty - temp_penalty
    return round(clamp(score, 0, 100), 1)

def score_status(score: float, lang: str):
    t = TEXT[lang]
    if score >= 75:
        return t["score_good"]
    elif score >= 50:
        return t["score_medium"]
    return t["score_poor"]

def estimate_yield(crop: str, score: float):
    base_yield = {
        "rice": 4.5, "wheat": 4.0, "maize": 5.0, "tomato": 25.0, "potato": 20.0,
        "onion": 18.0, "cotton": 2.5, "soybean": 2.8, "sugarcane": 70.0, "groundnut": 2.2,
        "banana": 35.0, "chili": 2.0, "cabbage": 22.0, "cauliflower": 20.0, "chickpea": 2.0,
        "lentil": 1.8, "sunflower": 2.2, "mustard": 1.8, "barley": 3.2, "sorghum": 3.0
    }
    base = base_yield.get(crop, 3.0)
    factor = 0.55 + (score / 100.0) * 0.65
    return round(base * factor, 2)

def estimate_water_use(soil: dict):
    moisture = soil.get("moisture", 55)
    if moisture < 35:
        liters = 7000
    elif moisture < 50:
        liters = 5200
    elif moisture < 65:
        liters = 3500
    else:
        liters = 1800
    return liters

def estimate_cost(fertilizers: dict):
    total = 0
    for name, amount in fertilizers.items():
        total += FERTILIZER_PRICES.get(name, 0) * amount
    return round(total, 1)

def generate_risks(lang: str):
    t = TEXT[lang]
    risks = []

    if soil_data["N"] < 20:
        risks.append(t["risk_n_low"])
    if soil_data["ph"] < 5.5:
        risks.append(t["risk_ph_low"])
    if soil_data["ph"] > 7.8:
        risks.append(t["risk_ph_high"])
    if soil_data["moisture"] < 35:
        risks.append(t["risk_dry"])
    if soil_data["temp"] > 38:
        risks.append(t["risk_heat"])

    if not risks:
        risks.append(t["risk_none"])
    return risks

def trend_word(delta, lang):
    t = TEXT[lang]
    if delta > 1:
        return t["increasing"]
    if delta < -1:
        return t["decreasing"]
    return t["stable"]

def generate_trend_snapshot(lang: str):
    if len(history) < 2:
        return {
            "N": TEXT[lang]["stable"],
            "P": TEXT[lang]["stable"],
            "K": TEXT[lang]["stable"],
            "moisture": TEXT[lang]["stable"],
            "temp": TEXT[lang]["stable"],
        }

    old = history[0]
    new = history[-1]
    return {
        "N": trend_word(new["N"] - old["N"], lang),
        "P": trend_word(new["P"] - old["P"], lang),
        "K": trend_word(new["K"] - old["K"], lang),
        "moisture": trend_word(new["moisture"] - old["moisture"], lang),
        "temp": trend_word(new["temp"] - old["temp"], lang),
    }

def generate_farmer_advice(crop: str, hectares: float, fertilizers: dict, soil: dict, lang: str):
    t = TEXT[lang]
    crop_name = CROP_LABELS[lang].get(crop, crop)

    steps = []
    for fert_key in ["Urea", "DAP", "MOP"]:
        amt = fertilizers.get(fert_key, 0)
        if amt > 0:
            steps.append(
                t["apply"].format(amount=amt, name=FERT_NAMES[lang][fert_key])
            )

    if steps:
        fert_text = t["joiner"].join(steps) + t["field_suffix"].format(
            hectares=hectares, crop=crop_name
        )
    else:
        fert_text = t["no_fert"]

    moisture = soil.get("moisture", 50)
    if moisture < 40:
        water_text = t["irr_high"]
    elif moisture < 60:
        water_text = t["irr_mod"]
    else:
        water_text = t["irr_ok"]

    temp = soil.get("temp", 25)
    if temp >= 35:
        climate_text = t["cl_hot"]
    elif temp <= 15:
        climate_text = t["cl_cold"]
    else:
        climate_text = t["cl_ok"]

    return fert_text, water_text, climate_text

def build_crop_options(selected_crop: str, lang: str) -> str:
    options = []
    for key in CROP_REQUIREMENTS.keys():
        label = CROP_LABELS[lang].get(key, key.title())
        selected = "selected" if key == selected_crop else ""
        options.append(f"<option value='{key}' {selected}>{label}</option>")
    return "\n".join(options)

def make_evidence(crop: str, lang: str):
    t = TEXT[lang]
    targets = CROP_REQUIREMENTS[crop]
    deficit = calculate_deficit_ppm(crop)
    return {
        "crop": CROP_LABELS[lang].get(crop, crop),
        "target_N": targets["N"],
        "target_P": targets["P"],
        "target_K": targets["K"],
        "current_N": soil_data["N"],
        "current_P": soil_data["P"],
        "current_K": soil_data["K"],
        "deficit_N": deficit["N"],
        "deficit_P": deficit["P"],
        "deficit_K": deficit["K"],
        "formula_1": f"1 ppm ≈ {PPM_TO_KG_PER_HA} kg/ha",
        "formula_2": "Urea=46% N, DAP=46% P, MOP=60% K"
    }

def log_analysis(crop, hectares, lang, state, district, soil_type, score, yield_est, cost_est):
    analysis_logs.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "crop": crop,
        "hectares": hectares,
        "language": lang,
        "state": state,
        "district": district,
        "soil_type": soil_type,
        "N": soil_data["N"],
        "P": soil_data["P"],
        "K": soil_data["K"],
        "moisture": soil_data["moisture"],
        "ph": soil_data["ph"],
        "temp": soil_data["temp"],
        "score": score,
        "yield_est": yield_est,
        "cost_est": cost_est,
    })

HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>{{ t.title }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg: #eef7ef;
      --card: #ffffff;
      --green: #1b5e20;
      --green2: #2e7d32;
      --muted: #5f6f65;
      --pill: #dff2e3;
      --shadow: 0 8px 24px rgba(0,0,0,0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 20px;
      font-family: Arial, sans-serif;
      background: linear-gradient(180deg, #f3fbf4 0%, #e9f5ea 100%);
      color: #1d2a1f;
    }
    .wrap { max-width: 1220px; margin: 0 auto; }
    .hero { text-align: center; margin-bottom: 18px; }
    .hero h1 { color: var(--green); margin: 0 0 6px; font-size: 2rem; }
    .hero p { margin: 0; color: var(--muted); }
    .card {
      background: var(--card);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 18px;
      margin: 14px 0;
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(7, minmax(130px, 1fr));
      gap: 12px;
      align-items: end;
    }
    .field { text-align: left; }
    .field label { font-weight: 700; display: block; margin-bottom: 6px; }
    select, input {
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid #cbd9ce;
      font-size: 1rem;
      background: #fbfffc;
    }
    button, .download-link {
      padding: 11px 16px;
      border: none;
      border-radius: 12px;
      background: var(--green2);
      color: white;
      font-weight: 700;
      cursor: pointer;
      width: 100%;
      text-decoration: none;
      display: inline-block;
      text-align: center;
    }
    button:hover, .download-link:hover { opacity: 0.94; }
    .speak-btn { margin-top: 10px; background: #0d6d3a; }
    .pills { margin-top: 14px; text-align: center; }
    .pill {
      display: inline-block;
      background: var(--pill);
      color: #194b22;
      padding: 8px 12px;
      border-radius: 999px;
      margin: 4px;
      font-weight: 700;
    }
    .grid2 { display: grid; grid-template-columns: 1.1fr 1fr; gap: 14px; }
    .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
    .kv {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px 18px;
      margin-top: 12px;
      text-align: left;
    }
    .kv div:nth-child(odd) { font-weight: 700; color: #2a4030; }
    .section-title { margin: 0; color: var(--green); font-size: 1.15rem; }
    .score-box {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      flex-wrap: wrap;
    }
    .score-big { font-size: 2rem; font-weight: 800; color: var(--green); }
    .status-badge {
      display: inline-block;
      padding: 8px 12px;
      border-radius: 999px;
      background: #eef8ef;
      font-weight: 700;
    }
    .advice-text { line-height: 1.6; text-align: left; }
    ul.clean { text-align: left; margin: 10px 0 0 18px; padding: 0; }
    .muted { color: var(--muted); }
    .disclaimer {
      border-left: 5px solid #d98e00;
      background: #fff7e8;
    }
    @media (max-width: 1080px) {
      .controls { grid-template-columns: repeat(3, 1fr); }
      .grid2, .grid3 { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .controls { grid-template-columns: 1fr; }
      .kv { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>🌱 <span id="title">{{ t.title }}</span></h1>
    <p id="subtitle">{{ t.subtitle }}</p>
  </div>

  <div class="card disclaimer">
    <h2 class="section-title" id="hdrDisclaimer">{{ t.disclaimer_title }}</h2>
    <p id="disclaimerText" class="advice-text">{{ t.disclaimer_text }}</p>
  </div>

  <div class="card">
    <form id="controlsForm">
      <div class="controls">
        <div class="field">
          <label id="lblCrop">{{ t.crop }}</label>
          <select id="crop">{{ crop_options|safe }}</select>
        </div>

        <div class="field">
          <label id="lblLand">{{ t.land }}</label>
          <input id="land" type="number" min="0.1" step="0.1" value="{{ hectares }}">
        </div>

        <div class="field">
          <label id="lblLang">{{ t.language }}</label>
          <select id="lang">
            <option value="English" {% if language=='English' %}selected{% endif %}>English</option>
            <option value="Hindi" {% if language=='Hindi' %}selected{% endif %}>Hindi</option>
            <option value="Telugu" {% if language=='Telugu' %}selected{% endif %}>Telugu</option>
          </select>
        </div>

        <div class="field">
          <label id="lblState">{{ t.state }}</label>
          <select id="state">
            {% for s in states %}
            <option value="{{ s }}">{{ s }}</option>
            {% endfor %}
          </select>
        </div>

        <div class="field">
          <label id="lblDistrict">{{ t.district }}</label>
          <select id="district">
            {% for d in districts %}
            <option value="{{ d }}">{{ d }}</option>
            {% endfor %}
          </select>
        </div>

        <div class="field">
          <label id="lblSoilType">{{ t.soil_type }}</label>
          <select id="soilType">
            {% for s in soil_types %}
            <option value="{{ s }}">{{ s }}</option>
            {% endfor %}
          </select>
        </div>

        <div class="field">
          <button type="submit" id="btnAnalyze">{{ t.analyze }}</button>
        </div>
      </div>
    </form>

    <div class="pills">
      <span class="pill" id="pillCrop">{{ t.crop_label }}: {{ crop }}</span>
      <span class="pill" id="pillArea">{{ t.area_label }}: {{ hectares }} ha</span>
      <span class="pill" id="pillRegion">{{ t.region }}: —</span>
      <span class="pill">Live: 5s</span>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2 class="section-title" id="hdrLive">{{ t.live }}</h2>
      <div class="kv">
        <div>Nitrogen (N)</div><div id="soilN">—</div>
        <div>Phosphorus (P)</div><div id="soilP">—</div>
        <div>Potassium (K)</div><div id="soilK">—</div>
        <div>Moisture</div><div id="soilM">—</div>
        <div>pH</div><div id="soilPH">—</div>
        <div>Temperature</div><div id="soilT">—</div>
      </div>
    </div>

    <div class="card">
      <h2 class="section-title" id="hdrScore">{{ t.soil_score }}</h2>
      <div class="score-box">
        <div class="score-big" id="scoreValue">—</div>
        <div class="status-badge" id="scoreStatus">—</div>
      </div>
      <div style="margin-top:14px">
        <h3 class="section-title" id="hdrWeather">{{ t.weather }}</h3>
        <div class="advice-text" id="weatherHint" style="margin-top:10px">—</div>
      </div>
    </div>
  </div>

  <div class="grid3">
    <div class="card">
      <h2 class="section-title" id="hdrFert">{{ t.fert }}</h2>
      <h3 class="section-title" style="font-size:1rem;margin-top:14px" id="hdrDef">{{ t.deficit }}</h3>
      <div class="kv">
        <div>N</div><div id="defN">—</div>
        <div>P</div><div id="defP">—</div>
        <div>K</div><div id="defK">—</div>
      </div>

      <h3 class="section-title" style="font-size:1rem;margin-top:16px" id="hdrFertilizers">{{ t.fertilizers }}</h3>
      <div class="kv">
        <div>Urea</div><div id="fertU">—</div>
        <div>DAP</div><div id="fertD">—</div>
        <div>MOP</div><div id="fertMOP">—</div>
      </div>
    </div>

    <div class="card">
      <h2 class="section-title" id="hdrYield">{{ t.yield }}</h2>
      <div class="score-big" id="yieldValue">—</div>
      <div class="muted" id="yieldUnit">{{ t.yield_unit }}</div>

      <h3 class="section-title" style="font-size:1rem;margin-top:16px" id="hdrCost">{{ t.cost }}</h3>
      <div class="score-big" style="font-size:1.3rem" id="costValue">—</div>

      <h3 class="section-title" style="font-size:1rem;margin-top:16px" id="hdrWaterUse">{{ t.water_use }}</h3>
      <div class="score-big" style="font-size:1.3rem" id="waterValue">—</div>
      <div class="muted" id="waterUnit">{{ t.water_unit }}</div>
    </div>

    <div class="card">
      <h2 class="section-title" id="hdrRisk">{{ t.risk }}</h2>
      <ul class="clean" id="riskList">
        <li>—</li>
      </ul>

      <h3 class="section-title" style="font-size:1rem;margin-top:16px" id="hdrTrend">{{ t.trend }}</h3>
      <div class="kv">
        <div>N</div><div id="trendN">—</div>
        <div>P</div><div id="trendP">—</div>
        <div>K</div><div id="trendK">—</div>
        <div>Moisture</div><div id="trendM">—</div>
        <div>Temp</div><div id="trendT">—</div>
      </div>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2 class="section-title" id="hdrAction">{{ t.action }}</h2>
      <div class="advice-text">
        <p id="advFert">—</p>
        <p id="advWater">—</p>
        <p id="advClimate">—</p>
      </div>
      <button class="speak-btn" onclick="speakAdvice()" id="btnSpeak">{{ t.speak }}</button>
    </div>

    <div class="card">
      <h2 class="section-title" id="hdrSchedule">{{ t.schedule }}</h2>
      <ul class="clean">
        <li id="sched1">{{ t.basal }}</li>
        <li id="sched2">{{ t.vegetative }}</li>
        <li id="sched3">{{ t.flowering }}</li>
      </ul>
      <div style="margin-top:14px">
        <a class="download-link" href="/download_logs" id="btnDownload">{{ t.download }}</a>
      </div>
    </div>
  </div>

  <div class="card">
    <h2 class="section-title" id="hdrEvidence">{{ t.evidence }}</h2>
    <div class="kv">
      <div>{{ t.crop }}</div><div id="evCrop">—</div>
      <div>{{ t.target }} N</div><div id="evTargetN">—</div>
      <div>{{ t.current }} N</div><div id="evCurrentN">—</div>
      <div>{{ t.target }} P</div><div id="evTargetP">—</div>
      <div>{{ t.current }} P</div><div id="evCurrentP">—</div>
      <div>{{ t.target }} K</div><div id="evTargetK">—</div>
      <div>{{ t.current }} K</div><div id="evCurrentK">—</div>
      <div>Deficit N</div><div id="evDefN">—</div>
      <div>Deficit P</div><div id="evDefP">—</div>
      <div>Deficit K</div><div id="evDefK">—</div>
      <div>{{ t.formula }} 1</div><div id="evFormula1">—</div>
      <div>{{ t.formula }} 2</div><div id="evFormula2">—</div>
    </div>
  </div>
</div>

<script>
  let state = {
    crop: "{{ crop }}",
    hectares: "{{ hectares }}",
    language: "{{ language }}",
    stateName: "{{ states[0] }}",
    district: "{{ districts[0] }}",
    soilType: "{{ soil_types[0] }}"
  };

  let lastSpeechText = "";

  const voiceLangMap = {
    "English": ["en-IN", "en-US", "en-GB", "en"],
    "Hindi": ["hi-IN", "hi"],
    "Telugu": ["te-IN", "te"]
  };

  function pickVoice(language) {
    const voices = window.speechSynthesis.getVoices();
    const preferred = voiceLangMap[language] || ["en"];
    for (const code of preferred) {
      const found = voices.find(v => (v.lang || "").toLowerCase().startsWith(code.toLowerCase()));
      if (found) return found;
    }
    return voices[0] || null;
  }

  function speakAdvice() {
    if (!lastSpeechText) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(lastSpeechText);
    const voice = pickVoice(state.language);
    if (voice) {
      utter.voice = voice;
      utter.lang = voice.lang;
    } else {
      utter.lang = voiceLangMap[state.language]?.[0] || "en-US";
    }
    utter.rate = 0.95;
    utter.pitch = 1.0;
    window.speechSynthesis.speak(utter);
  }

  function applyText(t) {
    document.getElementById("title").textContent = t.title;
    document.getElementById("subtitle").textContent = t.subtitle;
    document.getElementById("lblCrop").textContent = t.crop;
    document.getElementById("lblLand").textContent = t.land;
    document.getElementById("lblLang").textContent = t.language;
    document.getElementById("lblState").textContent = t.state;
    document.getElementById("lblDistrict").textContent = t.district;
    document.getElementById("lblSoilType").textContent = t.soil_type;
    document.getElementById("btnAnalyze").textContent = t.analyze;
    document.getElementById("hdrLive").textContent = t.live;
    document.getElementById("hdrScore").textContent = t.soil_score;
    document.getElementById("hdrWeather").textContent = t.weather;
    document.getElementById("hdrFert").textContent = t.fert;
    document.getElementById("hdrDef").textContent = t.deficit;
    document.getElementById("hdrFertilizers").textContent = t.fertilizers;
    document.getElementById("hdrAction").textContent = t.action;
    document.getElementById("btnSpeak").textContent = t.speak;
    document.getElementById("hdrYield").textContent = t.yield;
    document.getElementById("hdrCost").textContent = t.cost;
    document.getElementById("hdrWaterUse").textContent = t.water_use;
    document.getElementById("hdrRisk").textContent = t.risk;
    document.getElementById("hdrTrend").textContent = t.trend;
    document.getElementById("hdrSchedule").textContent = t.schedule;
    document.getElementById("hdrEvidence").textContent = t.evidence;
    document.getElementById("hdrDisclaimer").textContent = t.disclaimer_title;
    document.getElementById("disclaimerText").textContent = t.disclaimer_text;
    document.getElementById("btnDownload").textContent = t.download;
    document.getElementById("yieldUnit").textContent = t.yield_unit;
    document.getElementById("waterUnit").textContent = t.water_unit;
    document.getElementById("sched1").textContent = t.basal;
    document.getElementById("sched2").textContent = t.vegetative;
    document.getElementById("sched3").textContent = t.flowering;
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

    document.getElementById("pillCrop").textContent = d.text.crop_label + ": " + d.crop_label;
    document.getElementById("pillArea").textContent = d.text.area_label + ": " + d.hectares + " ha";
    document.getElementById("pillRegion").textContent = d.text.region + ": " + d.region;

    document.getElementById("scoreValue").textContent = d.score.value + " / 100";
    document.getElementById("scoreStatus").textContent = d.score.status;

    document.getElementById("yieldValue").textContent = d.yield.value;
    document.getElementById("costValue").textContent = "₹ " + d.cost.value;
    document.getElementById("waterValue").textContent = d.water.value;

    const riskList = document.getElementById("riskList");
    riskList.innerHTML = "";
    d.risks.forEach(item => {
      const li = document.createElement("li");
      li.textContent = item;
      riskList.appendChild(li);
    });

    document.getElementById("trendN").textContent = d.trend.N;
    document.getElementById("trendP").textContent = d.trend.P;
    document.getElementById("trendK").textContent = d.trend.K;
    document.getElementById("trendM").textContent = d.trend.moisture;
    document.getElementById("trendT").textContent = d.trend.temp;

    document.getElementById("evCrop").textContent = d.evidence.crop;
    document.getElementById("evTargetN").textContent = d.evidence.target_N;
    document.getElementById("evCurrentN").textContent = d.evidence.current_N;
    document.getElementById("evTargetP").textContent = d.evidence.target_P;
    document.getElementById("evCurrentP").textContent = d.evidence.current_P;
    document.getElementById("evTargetK").textContent = d.evidence.target_K;
    document.getElementById("evCurrentK").textContent = d.evidence.current_K;
    document.getElementById("evDefN").textContent = d.evidence.deficit_N;
    document.getElementById("evDefP").textContent = d.evidence.deficit_P;
    document.getElementById("evDefK").textContent = d.evidence.deficit_K;
    document.getElementById("evFormula1").textContent = d.evidence.formula_1;
    document.getElementById("evFormula2").textContent = d.evidence.formula_2;

    lastSpeechText = [
      d.advice.fertilizer,
      d.advice.irrigation,
      d.advice.climate,
      d.weather_hint
    ].filter(Boolean).join(" ");
  }

  async function updateWeatherHintTexts() {
    const r = await fetch("/weather_text?lang=" + encodeURIComponent(state.language));
    return await r.json();
  }

  async function loadWeatherHint() {
    const baseTexts = await updateWeatherHintTexts();

    if (!navigator.geolocation) {
      document.getElementById("weatherHint").textContent = baseTexts.weather_unavailable;
      return;
    }

    navigator.geolocation.getCurrentPosition(async (pos) => {
      try {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        const url =
          `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
          `&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum` +
          `&timezone=auto&forecast_days=1`;

        const res = await fetch(url);
        const data = await res.json();

        const rainProb = data?.daily?.precipitation_probability_max?.[0] ?? null;
        const rainSum = data?.daily?.precipitation_sum?.[0] ?? null;
        const tmax = data?.daily?.temperature_2m_max?.[0] ?? null;

        let parts = [];

        if (rainProb !== null) {
          if (rainProb >= 70 || (rainSum !== null && rainSum >= 8)) {
            parts.push(baseTexts.rain_heavy);
          } else if (rainProb >= 30 || (rainSum !== null && rainSum >= 2)) {
            parts.push(baseTexts.rain_possible);
          } else {
            parts.push(baseTexts.rain_none);
          }
        } else {
          parts.push(baseTexts.weather_unavailable);
        }

        if (tmax !== null) {
          if (tmax >= 34) {
            parts.push(baseTexts.temp_hint_hot);
          } else if (tmax <= 20) {
            parts.push(baseTexts.temp_hint_cool);
          }
        }

        const finalText = parts.join(" ");
        document.getElementById("weatherHint").textContent = finalText;
        lastSpeechText = [lastSpeechText, finalText].filter(Boolean).join(" ");
      } catch (e) {
        document.getElementById("weatherHint").textContent = baseTexts.weather_unavailable;
      }
    }, () => {
      document.getElementById("weatherHint").textContent = baseTexts.weather_unavailable;
    });
  }

  document.getElementById("controlsForm").addEventListener("submit", (e) => {
    e.preventDefault();
    state.crop = document.getElementById("crop").value;
    state.hectares = document.getElementById("land").value || "1";
    state.language = document.getElementById("lang").value;
    state.stateName = document.getElementById("state").value;
    state.district = document.getElementById("district").value;
    state.soilType = document.getElementById("soilType").value;
    refreshData();
    loadWeatherHint();
  });

  if (speechSynthesis.onvoiceschanged !== undefined) {
    speechSynthesis.onvoiceschanged = () => {};
  }

  refreshData();
  loadWeatherHint();
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
    if language not in TEXT:
        language = "English"
    hectares = clamp(hectares, 0.1, 10000)

    crop_options = build_crop_options(crop, language)

    return render_template_string(
        HTML,
        crop=crop,
        hectares=hectares,
        language=language,
        t=TEXT[language],
        crop_options=crop_options,
        states=STATE_OPTIONS,
        districts=DISTRICT_OPTIONS,
        soil_types=SOIL_TYPES
    )

@app.route("/data", methods=["GET"])
def data():
    crop = (request.args.get("crop", "tomato") or "tomato").lower()
    language = request.args.get("language", "English") or "English"
    hectares = safe_float(request.args.get("hectares", "1"), default=1.0)
    state_name = request.args.get("stateName", STATE_OPTIONS[0])
    district = request.args.get("district", DISTRICT_OPTIONS[0])
    soil_type = request.args.get("soilType", SOIL_TYPES[0])

    if crop not in CROP_REQUIREMENTS:
        crop = "tomato"
    if language not in TEXT:
        language = "English"
    hectares = clamp(hectares, 0.1, 10000)

    deficit, ferts = calculate_fertilizers_total(crop, hectares)
    fert_text, water_text, climate_text = generate_farmer_advice(crop, hectares, ferts, soil_data, language)
    score = compute_soil_health_score(crop)
    yield_est = estimate_yield(crop, score)
    water_need = estimate_water_use(soil_data)
    cost_est = estimate_cost(ferts)
    risks = generate_risks(language)
    trend = generate_trend_snapshot(language)
    evidence = make_evidence(crop, language)

    log_analysis(crop, hectares, language, state_name, district, soil_type, score, yield_est, cost_est)

    return jsonify({
        "crop": crop,
        "crop_label": CROP_LABELS[language].get(crop, crop),
        "region": f"{state_name}, {district}, {soil_type}",
        "hectares": hectares,
        "soil": soil_data,
        "deficit": deficit,
        "fertilizers": ferts,
        "advice": {
            "fertilizer": fert_text,
            "irrigation": water_text,
            "climate": climate_text
        },
        "score": {
            "value": score,
            "status": score_status(score, language)
        },
        "yield": {
            "value": yield_est
        },
        "water": {
            "value": water_need
        },
        "cost": {
            "value": cost_est
        },
        "risks": risks,
        "trend": trend,
        "evidence": evidence,
        "text": TEXT[language]
    })

@app.route("/weather_text", methods=["GET"])
def weather_text():
    language = request.args.get("lang", "English") or "English"
    if language not in TEXT:
        language = "English"
    t = TEXT[language]
    return jsonify({
        "weather_unavailable": t["weather_unavailable"],
        "rain_heavy": t["rain_heavy"],
        "rain_possible": t["rain_possible"],
        "rain_none": t["rain_none"],
        "temp_hint_hot": t["temp_hint_hot"],
        "temp_hint_cool": t["temp_hint_cool"],
    })

@app.route("/download_logs", methods=["GET"])
def download_logs():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "timestamp", "crop", "hectares", "language", "state", "district", "soil_type",
        "N", "P", "K", "moisture", "ph", "temp", "score", "yield_est", "cost_est"
    ])

    for row in analysis_logs:
        writer.writerow([
            row["timestamp"], row["crop"], row["hectares"], row["language"],
            row["state"], row["district"], row["soil_type"],
            row["N"], row["P"], row["K"], row["moisture"], row["ph"], row["temp"],
            row["score"], row["yield_est"], row["cost_est"]
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=soil_ai_logs.csv"}
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
