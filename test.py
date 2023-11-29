import httpx
from config import *
url = "https://{}/v1/chat/completions".format(BASE_API_URL)


headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + BASE_API_KEY
}
completion = httpx.post(url, headers=headers, json={
    "model": "gpt-4",
    "messages": [{'role': "user", "content": "hello"}],
}, proxies=PROXY)
print(completion.json()['choices'][0]['message']['content'])


