from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
from travel_scraper import TravelDataScraper
from xhtml2pdf import pisa
import io
import os
import requests
from langchain.llms import HuggingFaceHub
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL")
app = Flask(__name__)
scraper = TravelDataScraper()

# Initialize LangChain LLM with Hugging Face Hub (Mistral-7B-Instruct)
hf_api_key = "Add the key"
llm = HuggingFaceHub(
    repo_id="mistralai/Mistral-7B-Instruct-v0.2",
    huggingfacehub_api_token=hf_api_key
)

  # Corrected endpoint  # Example endpoint

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json['message']
    itinerary = request.json.get('itinerary')
    if itinerary:
        itinerary_summary = f"Here is the user's itinerary: {itinerary}. "
    else:
        itinerary_summary = ""
    prompt = f"You are a helpful travel assistant. {itinerary_summary}User question: {user_message}"

    # Groq API payload
    payload = {
        "model": "llama3-8b-8192",  # Replace with your Groq model name
        "messages": [
            {"role": "system", "content": "You are a helpful travel assistant."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 512,
        "temperature": 0.7
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(GROQ_API_URL, json=payload, headers=headers)
    print("Status code:", response.status_code)
    print("Response text:", response.text)
    if response.status_code == 200:
        data = response.json()
        reply = data['choices'][0]['message']['content']
    else:
        reply = "Sorry, I couldn't process your request at the moment."
    return jsonify({'response': reply})

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        starting_city = request.form['starting_city']
        destination = request.form['destination']
        days = int(request.form['days'])
        budget = int(request.form['budget'])
        data = scraper.scrape_all_data(starting_city, destination, days, budget)
        itinerary = data['itinerary']
        travel_info = data['travel_info']
        return render_template('index.html', itinerary=itinerary, travel_info=travel_info, starting_city=starting_city, destination=destination, days=days, budget=budget)
    return render_template('index.html', itinerary=None)

def generate_itinerary(starting_city, destination, days):
    data = scraper.scrape_all_data(starting_city, destination, days)
    return data['itinerary']

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    starting_city = request.form['starting_city']
    destination = request.form['destination']
    days = int(request.form['days'])
    data = scraper.scrape_all_data(starting_city, destination, days)
    itinerary = data['itinerary']
    travel_info = data['travel_info']
    html = render_template('itinerary.html', itinerary=itinerary, travel_info=travel_info, starting_city=starting_city, destination=destination, days=days)
    pdf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=pdf)
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name=f"itinerary_{destination}.pdf", mimetype='application/pdf')

@app.route('/map')
def map_view():
    destination = request.args.get('destination')
    days = int(request.args.get('days', 1))
    itinerary = generate_itinerary(destination, 0, days)
    # Collect all places for all days
    places = []
    for day in itinerary:
        for attr in day['attractions']:
            places.append(attr)
    return render_template('map.html', destination=destination, places=places)

if __name__ == '__main__':

    app.run(debug=True)
