# pip install python-dotenv requests python-jose langchain-openai

import os
import time
import requests
import jwt
from datetime import datetime
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

# === Configuration (from .env) ===
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")
APPLE_ISSUER_ID = os.getenv("APPLE_ISSUER_ID")
APPLE_PRIVATE_KEY = os.getenv("APPLE_PRIVATE_KEY")  # multiline string SEND-----
APP_ID = os.getenv("APP_ID")  # numeric App Store Connect app ID
#OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  
DRY_RUN = True  # SET TO False to post real responses

# === LLM Setup ===
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def generate_jwt():
    payload = {
        "iss": APPLE_ISSUER_ID,
        "iat": int(time.time()),
        "exp": int(time.time()) + 1200,  # 20 minutes
        "aud": "appstoreconnect-v1"
    }
    headers = {"alg": "ES256", "kid": APPLE_KEY_ID, "typ": "JWT"}
    return jwt.encode(payload, APPLE_PRIVATE_KEY, algorithm="ES256", headers=headers)

def fetch_low_rated_reviews():
    token = generate_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    
    url = f"https://api.appstoreconnect.apple.com/v1/apps/{APP_ID}/customerReviews"
    params = {
        "limit": 200,
        "filter[rating]": "1,2,3,4",  # only 1–4 stars
        "include": "response"
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error fetching reviews: {response.status_code} {response.text}")
        return []
    
    data = response.json()["data"]
    included = response.json().get("included", [])
    response_map = {item["id"] for item in included if item["type"] == "customerReviewResponses"}
    
    reviews = []
    for item in data:
        attrs = item["attributes"]
        review_id = item["id"]
        
        # Skip if we already responded
        if review_id in response_map:
            continue
            
        reviews.append({
            "id": review_id,
            "rating": attrs["rating"],
            "title": attrs.get("reviewTitle", ""),
            "body": attrs.get("reviewBody", ""),
            "territory": attrs["territory"],
            "created_date": attrs["createdDate"]
        })
    
    return reviews

def generate_response(review):
    prompt = [
        SystemMessage(content="You are a friendly, empathetic customer support representative for SightTune, a piano learning app. "
                              "Respond politely, acknowledge the issue, apologize if appropriate, offer help, "
                              "and keep the response short (2–4 sentences). Do not promise specific fixes unless obvious."),
        HumanMessage(content=f"Rating: {review['rating']}/5\n"
                             f"Title: {review['title']}\n"
                             f"Body: {review['body']}")
    ]
    return llm.invoke(prompt).content.strip()

def post_response(review_id, response_text):
    token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    url = f"https://api.appstoreconnect.apple.com/v1/customerReviews/{review_id}/response"
    payload = {
        "data": {
            "type": "customerReviewResponses",
            "attributes": {"responseBody": response_text}
        }
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        print(f"Successfully posted response to review {review_id}")
        return True
    else:
        print(f"Failed to post response to {review_id}: {resp.status_code} {resp.text}")
        return False

def main():
    print(f"Starting App Store review bot — {datetime.now()}")
    
    reviews = fetch_low_rated_reviews()
    
    if not reviews:
        print("No new low-rated reviews to respond to. All done!")
        return
    
    print(f"Found {len(reviews)} unreplied low-rated review(s)")
    
    for review in reviews:
        print(f"\n--- Review {review['id']} ---")
        print(f"Rating: {review['rating']} | Territory: {review['territory']} | Date: {review['created_date']}")
        print(f"Title: {review['title']}")
        print(f"Body: {review['body']}")
        
        generated = generate_response(review)
        print(f"\nGenerated response:\n{generated}")
        
        if DRY_RUN:
            print("DRY RUN: Not posting (set DRY_RUN = False to post live)")
        else:
            if input("Post this response? (y/N): ").strip().lower() == 'y':
                post_response(review['id'], generated)
            else:
                print("Skipped.")
    
    print("\nBot run complete.")

if __name__ == "__main__":
    main()