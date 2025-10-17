import os
import io
import json
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from PIL import Image
from google import genai
from google.genai import types




app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())
USERS_FILE = 'users.json'




def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Warning: users.json is empty or corrupted. Starting with no users.")
            return {}
    else:
        return {}




def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)




users = load_users()




GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "your api key")
try:
    client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
    if client:
        print("Gemini Client initialized successfully.")
    else:
        print("Gemini Client not initialized: GEMINI_API_KEY missing.")
except Exception as e:
    print(f"ERROR: Could not initialize Gemini Client. Error: {e}")
    client = None




DIAGNOSIS_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "disease": types.Schema(type=types.Type.STRING, description="The most probable dermatological condition. If unclear, use 'Unknown Dermatosis (Consult a specialist)'"),
        "causes": types.Schema(type=types.Type.STRING, description="A brief summary of the primary causes."),
        "precautions": types.Schema(type=types.Type.STRING, description="Key protective and preventative measures."),
        "tablets": types.Schema(type=types.Type.STRING, description="Examples of prescription or oral treatments (for triage awareness)."),
        "creams": types.Schema(type=types.Type.STRING, description="Examples of topical treatments/creams (for triage awareness)."),
    },
    required=["disease", "causes", "precautions", "tablets", "creams"]
)




def predict_disease_gemini(image):
    if client is None:
        return {"error": "Analysis Error: Gemini Client not initialized (API Key missing)."}
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    prompt = (
        "You are an expert dermatological triage assistant. Analyze the visible skin condition in the provided image. "
        "Based on the image, identify the most probable condition and provide concise, accurate information for the "
        "causes, precautions, and recommended treatments (tablets/creams). "
        "Ensure your output strictly adheres to the required JSON schema. "
        "If the image is not a skin condition, is not clearly visible, or is non-diagnostic, set the 'disease' field to "
        "'Unknown Dermatosis (Consult a specialist)' and fill other fields with 'Not determinable from image.'"
    )
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, types.Part.from_bytes(data=img_bytes, mime_type='image/png')],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DIAGNOSIS_SCHEMA,
                temperature=0.0
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini API call failed: {e}")
        return {"error": f"Analysis Error: API call failed or returned invalid data. Details: {e}"}
      @app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('home'))
        return render_template_string(login_html, error="Invalid credentials")
    return render_template_string(login_html)




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users:
            return render_template_string(register_html, message="Username already exists. Please choose a different one.", error="Username already exists.")
        users[username] = password
        save_users(users)
        return render_template_string(register_html, message="Account created! You can now login.")
    return render_template_string(register_html)




@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))




@app.route('/')
def home():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template_string(main_app_html)




@app.route('/analyze', methods=['POST'])
def analyze():
    if 'logged_in' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if 'image' not in request.files:
        return jsonify({"error": "No image file found"}), 400
    file = request.files['image']
    try:
        file_data = file.read()
        img = Image.open(io.BytesIO(file_data))
    except Exception:
        return jsonify({"error": "Invalid image file"}), 400
    diagnosis_data = predict_disease_gemini(img)
    if "error" in diagnosis_data:
        return jsonify(diagnosis_data), 500
    return jsonify({
        "disease": diagnosis_data.get("disease", "Unknown"),
        "causes": diagnosis_data.get("causes", "AI analysis unavailable."),
        "precautions": diagnosis_data.get("precautions", "AI analysis unavailable."),
        "tablets": diagnosis_data.get("tablets", "AI analysis unavailable."),
        "creams": diagnosis_data.get("creams", "AI analysis unavailable."),
    })




if __name__ == '__main__':
    app.run(debug=True)
