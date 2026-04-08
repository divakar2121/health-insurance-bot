#!/usr/bin/env python
"""Test OpenRouter API key"""

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
URL = "https://openrouter.ai/api/v1/chat/completions"

print(f"API Key loaded: {bool(API_KEY)}")
print(f"Key length: {len(API_KEY)}")
print(f"Key starts with: {API_KEY[:20]}...")

if not API_KEY:
    print("ERROR: No API key found!")
    exit(1)

import requests

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:5000",
    "X-Title": "Test"
}

payload = {
    "model": "meta-llama/llama-3.1-8b-instruct",
    "messages": [{"role": "user", "content": "Say 'Hello' if you can hear me"}],
    "max_tokens": 50
}

print("\nTesting API...")
try:
    resp = requests.post(URL, json=payload, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"\n✓ SUCCESS! Response: {data['choices'][0]['message']['content']}")
    else:
        print(f"\n✗ FAILED: {resp.status_code}")
except Exception as e:
    print(f"ERROR: {e}")