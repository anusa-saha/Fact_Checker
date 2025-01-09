
from flask import Flask, request, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract

app = Flask(__name__)

# Your Google Fact Check Explorer API Key
API_KEY = "AIzaSyB6whZ5EVEVhC4f_ldjySiuH3_X1WCBH7k"
FACT_CHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

# Function to extract text from uploaded images
def extract_text_from_image(image):
    try:
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        return str(e)

# Function to verify claims using Google Fact Check API
def verify_claim_with_api(claim):
    try:
        response = requests.get(
            FACT_CHECK_URL,
            params={"query": claim, "key": API_KEY}
        )
        data = response.json()
        if "claims" not in data:
            return {"verified": False, "evidence": [], "context": "No fact checks found."}

        claims = data["claims"]
        evidence = []
        for claim_item in claims:
            evidence.append({
                "text": claim_item["text"],
                "reviewer": claim_item.get("claimReview", [{}])[0].get("publisher", {}).get("name", "Unknown"),
                "review_url": claim_item.get("claimReview", [{}])[0].get("url", ""),
                "review_rating": claim_item.get("claimReview", [{}])[0].get("textualRating", "Unknown")
            })

        return {"verified": True, "evidence": evidence}
    except Exception as e:
        return {"verified": False, "evidence": [], "context": str(e)}

# Function to scrape Google for additional evidence
def scrape_google(claim):
    query = "+".join(claim.split())
    search_url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        links = [
            link.get("href").split("url?q=")[1].split("&")[0]
            for link in soup.select("a") if "url?q=" in link.get("href", "")
        ]
        return links[:5]  # Return top 5 links
    except Exception as e:
        return []

# Function to calculate a misinformation score
def calculate_score(api_evidence, scraped_links):
    verified_count = len(api_evidence)
    scraped_count = len(scraped_links)

    if verified_count == 0 and scraped_count == 0:
        return 100  # Fully misinformation if no evidence found

    return max(0, 100 - (verified_count * 20))  # Example formula

# API Endpoint to analyze claims
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    claim = data.get("claim")
    if not claim:
        return jsonify({"error": "No claim provided"}), 400

    api_result = verify_claim_with_api(claim)
    scraped_links = scrape_google(claim)
    score = calculate_score(api_result["evidence"], scraped_links)

    return jsonify({
        "claim": claim,
        "misinformation_score": score,
        "google_fact_check": api_result,
        "additional_evidence_links": scraped_links
    })

# API Endpoint to process images
@app.route('/ocr', methods=['POST'])
def ocr():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    try:
        image = Image.open(file)
        extracted_text = extract_text_from_image(image)
        return jsonify({"extracted_text": extracted_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True)
