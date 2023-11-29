import httpx
import re
import pyquery
from config import *
url = "https://{}/v1/chat/completions".format(BASE_API_URL)


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
        })
        return completion.json()['choices'][0]['message']['content']


prompt = """
你在思考、行动、暂停、观察的循环中运行。
在循环结束时输出一个答案
使用想法来描述您对所问问题的想法。
使用“操作”运行您可以执行的操作之一 - 然后返回“暂停”。
观察将是运行这些操作的结果。
请务必使用中文以及中文符号。

您可以采取的行动有：

calculate:
例如 计算：4 * 7 / 3
运行计算并返回数字 - 使用 Python，因此如有必要请务必使用浮点语法

bing_search:
例如 bing_search：Django
在 Bing 中搜索该术语。 执行 Bing 搜索后，使用 open_url 操作访问每个结果并获取页面的文本。

wikipedia:
例如 wikipedia: Django
返回搜索维基百科的摘要

simon_blog_search:
例如 simon_blog_search: Django
在 Simon 的博客中搜索该术语

open_url:
e.g. open_url: https://simonwillison.net/
使用此操作打开搜索结果中的每个 URL 并返回页面的文本。

如果有机会，请务必在bing_search上查找内容。

会话示例：

问：法国的首都是哪里？
想法：我应该在bing_search上查找法国。
行动：bing_search：法国
暂停

您将再次被呼叫并收到以下信息：

观察：法国是一个国家。 首都是巴黎。

然后你输出：

答：法国的首都是巴黎。

如果操作是 Bing 搜索：
想法：我需要分析 Bing 的搜索结果。
操作：open_url：[来自 Bing 搜索结果的 URL]
暂停

您将再次被呼叫并收到以下信息：

观察：[来自open_url的文本]

然后，您分析文本以形成您的下一个观察或答案。
""".strip()



action_re1 = re.compile('^操作[:|：](\w+)[:|：](.*)$')
action_re2 = re.compile('^行动[:|：](\w+)[:|：](.*)$')


def query(question, max_turns=10):
    i = 0
    bot = ChatBot(prompt)
    next_prompt = question
    while i < max_turns:
        i += 1
        result = bot(next_prompt)
        print(result)
        actions = [action_re1.match(a) for a in result.split('\n') if action_re1.match(a)]
        if len(actions) == 0:
            actions = [action_re2.match(a) for a in result.split('\n') if action_re2.match(a)]
        if actions:
            # There is an action to run
            action, action_input = actions[0].groups()
            if action not in known_actions:
                raise Exception("Unknown action: {}: {}".format(action, action_input))
            print(" -- running {} {}".format(action, action_input))
            observation = known_actions[action](action_input)
            print("Observation:", observation)
            next_prompt = "Observation: {}".format(observation)
        else:
            return


def wikipedia(q):
    return httpx.get("https://en.wikipedia.org/w/api.php", params={
        "action": "query",
        "list": "search",
        "srsearch": q,
        "format": "json"
    }, proxies=PROXY).json()["query"]["search"][0]["snippet"]


def simon_blog_search(q):
    results = httpx.get("https://datasette.simonwillison.net/simonwillisonblog.json", proxies=PROXY, params={
        "sql": """
        select
          blog_entry.title || ': ' || substr(html_strip_tags(blog_entry.body), 0, 1000) as text,
          blog_entry.created
        from
          blog_entry join blog_entry_fts on blog_entry.rowid = blog_entry_fts.rowid
        where
          blog_entry_fts match escape_fts(:q)
        order by
          blog_entry_fts.rank
        limit
          1""".strip(),
        "_shape": "array",
        "q": q,
    }).json()
    return results[0]["text"]


def bing_search(q):
    html = httpx.get("https://www.bing.com/search", params={"q": q}, proxies=PROXY)
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
    text = doc("body").text()
    return text


def calculate(what):
    return eval(what)


known_actions = {
    "wikipedia": wikipedia,
    "calculate": calculate,
    "simon_blog_search": simon_blog_search,
    "bing_search": bing_search,
    "open_url": open_url,
}

question = "how to create gpt agent, i want it can use bing to search?"
query(question)