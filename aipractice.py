
import os
import requests

API_URL = "https://router.huggingface.co/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {os.environ['HF_TOKEN']}",
}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

if __name__ == "__main__":
    prompt = input("Enter prompt: ")
    print("One moment, please...")
    response = query({

        "messages": [{"role": "user",
                      "content": prompt}],

        "model": "meta-llama/Llama-3.1-8B-Instruct:novita"

    })

    print(response["choices"][0]["message"]["content"].replace("**", "").replace("*", ""))