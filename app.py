from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

def get_nvidia_completion(prompt_text):
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY")
    )

    completion = client.chat.completions.create(
        model="meta/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt_text}],
        temperature=0.5,
        top_p=1,
        max_tokens=1024,
        stream=False
    )

    response_text = ""
    for chunk in completion:
        if chunk.choices[0].delta.content is not None:
            response_text += chunk.choices[0].delta.content

    return response_text

if __name__ == "__main__":
    prompt_text = "Provide me an article on Machine Learning"
    response = get_nvidia_completion(prompt_text)
    print(response)
    
