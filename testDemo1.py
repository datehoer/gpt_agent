import httpx
import re
import pyquery
from config import *
url = "https://{}/v1/chat/completions".format(BASE_API_URL)
headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",
    "sec-ch-ua-arch": "\"x86\"",
    "sec-ch-ua-bitness": "\"64\"",
    "sec-ch-ua-full-version": "\"116.0.5845.187\"",
    "sec-ch-ua-full-version-list": "\"Chromium\";v=\"116.0.5845.187\", \"Not)A;Brand\";v=\"24.0.0.0\", \"Google Chrome\";v=\"116.0.5845.187\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": "\"\"",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-ch-ua-platform-version": "\"10.13.6\"",
    "sec-ch-ua-wow64": "?0",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Referrer-Policy": "origin"
}


class ChatBot:
    def __init__(self, system=""):
        self.system = system
        self.messages = []
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + BASE_API_KEY
        }
        if self.system:
            self.messages.append({"role": "system", "content": system})

    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "system", "content": result})
        return result

    def execute(self):
        completion = httpx.post(url, headers=self.headers, json={
            "model": "gpt-3.5-turbo-1106",
            "messages": self.messages,
        }, timeout=120, proxies=PROXY)
        return completion.json()['choices'][0]['message']['content']


prompt = """
You run in a loop of Thought, Action, PAUSE, Observation.
At the end of the loop you output an Answer.
Use Thought to describe your thoughts about the question you have been asked.
Use Action to run one of the actions available to you - then return PAUSE.
Observation will be the result of running those actions.

Your available actions are:

calculate:
e.g. calculate: 4 * 7 / 3
Runs a calculation and returns the number - uses Python so be sure to use floating point syntax if necessary.

bing_search:
e.g. bing_search: Django
Search Bing for that term.

open_url:
e.g. open_url: https://simonwillison.net/
Returns the text of the page at that URL. This action should only be used after a bing_search action.

wikipedia:
e.g. wikipedia: Django
Returns a summary from searching Wikipedia.

Always look things up on bing_search if you have the opportunity to do so.

Example session:

Question: What is the capital of France?
Thought: I should first search Bing for information about France.
Action: bing_search: France
PAUSE

You will be called again with this:

Observation: Bing search results for France are available.
Thought: I should find the one I think is most relevant from the search results and open its URL to find more detailed information.
Action: open_url: [selected link from the search results]
PAUSE

You will be called again with this:

Observation: The selected page mentions that France is a country and its capital is Paris.

You then output:

Answer: The capital of France is Paris.
""".strip()


action_re = re.compile('^Action[:|：] (\w+)[:|：] (.*)$')


def query(question, max_turns=10):
    i = 0
    bot = ChatBot(prompt)
    next_prompt = question
    while i < max_turns:
        i += 1
        result = bot(next_prompt)
        print(result)
        actions = [action_re.match(a) for a in result.split('\n') if action_re.match(a)]
        if actions:
            # There is an action to run
            action, action_input = actions[0].groups()
            if action not in known_actions:
                raise Exception("Unknown action: {}: {}".format(action, action_input))
            print(" -- running {} {}".format(action, action_input))
            observation = known_actions[action](action_input)
            # print("Observation:", observation)
            next_prompt = "Observation: {}".format(observation)
        else:
            return


def wikipedia(question):
    return httpx.get("https://en.wikipedia.org/w/api.php", params={
        "action": "query",
        "list": "search",
        "srsearch": question,
        "format": "json"
    }, proxies=PROXY).json()["query"]["search"][0]["snippet"]


def bing_search(question):
    html = httpx.get("https://www.bing.com/search", params={"q": question}, proxies=PROXY, headers=headers, verify=False)
    doc = pyquery.PyQuery(html.content)
    items = doc("#b_results .b_algo").items()
    data = []
    for item in items:
        title = item("h2 a").text()
        link = item("h2 a").attr("href")
        slug = item(".b_algoSlug").text()
        data.append({
            "title": title,
            "link": link,
            "slug": slug,
        })
    return data


def open_url(link):
    html = httpx.get(link, proxies=PROXY)
    doc = pyquery.PyQuery(html.content)
    doc('script').remove()
    doc('style').remove()
    text = doc("body").text()
    return text


def calculate(what):
    return eval(what)


known_actions = {
    "wikipedia": wikipedia,
    "calculate": calculate,
    "bing_search": bing_search,
    "open_url": open_url,
}

q = "how to create vue page?"
query(q)
