from flask import Flask, request, render_template_string
from urllib.parse import quote_plus
from email.utils import parsedate_to_datetime
import feedparser
import html
import re
import time

app = Flask(__name__)

FEEDS = {
    "Nigeria": "https://feeds.bbci.co.uk/news/topics/c50znx8v132t/rss.xml",
    "World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Football": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "Technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "AI": "https://openai.com/news/rss.xml",
    "WWE": "https://www.postwrestling.com/feed/",
    "Business": "https://feeds.bbci.co.uk/news/business/rss.xml"
}

SOURCES = {
    "Nigeria": "BBC News",
    "World": "BBC News",
    "Football": "BBC Sport",
    "Technology": "BBC News",
    "AI": "OpenAI News",
    "WWE": "POST Wrestling",
    "Business": "BBC News"
}

ICONS = {
    "Nigeria": "🇳🇬",
    "World": "🌍",
    "Football": "⚽",
    "Technology": "💻",
    "AI": "🤖",
    "WWE": "🤼",
    "Business": "💼"
}

CATEGORIES = list(FEEDS.keys())


def clean_text(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_date(item):
    value = item.get("published", "") or item.get("updated", "")

    try:
        return parsedate_to_datetime(value).timestamp()
    except Exception:
        return 0


def get_stories(category, limit=20):
    feed_url = FEEDS.get(category)

    if not feed_url:
        return []

    try:
        feed = feedparser.parse(feed_url)

        if not feed.entries:
            print(f"No stories available for {category}")
            return []

        stories = []

        for item in feed.entries[:limit]:
            title = clean_text(item.get("title", "Untitled"))
            link = item.get("link", "#")
            description = clean_text(
                item.get("summary", "")
                or item.get("description", "")
            )

            if len(description) > 280:
                description = description[:280].rsplit(" ", 1)[0] + "..."

            date_text = (
                item.get("published", "")
                or item.get("updated", "")
                or "Latest"
            )

            stories.append({
                "title": title,
                "link": link,
                "description": description,
                "date": date_text,
                "timestamp": get_date(item),
                "category": category,
                "source": SOURCES.get(category, "News Source")
            })

        stories.sort(key=lambda x: x["timestamp"], reverse=True)

        print(f"{category}: {len(stories)} stories")
        return stories

    except Exception as error:
        print(f"{category} feed failed: {error}")
        return []


def story_link(story):
    return (
        "/story?"
        f"title={quote_plus(story['title'])}"
        f"&link={quote_plus(story['link'])}"
        f"&category={quote_plus(story['category'])}"
        f"&source={quote_plus(story['source'])}"
        f"&date={quote_plus(story['date'])}"
        f"&description={quote_plus(story['description'])}"
    )


BASE_CSS = """
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    background-color: #eef2f6;
    background-image:
        linear-gradient(rgba(238,242,246,0.90), rgba(238,242,246,0.90)),
        url("/static/images/background.jpg");
    background-size: cover;
    background-attachment: fixed;
    color: #172033;
}

a {
    text-decoration: none;
}

.container {
    width: 94%;
    max-width: 1200px;
    margin: auto;
}

header {
    background: #071a3d;
    padding: 15px 0;
    box-shadow: 0 3px 12px rgba(0,0,0,0.2);
}

.logo {
    width: 100%;
    max-height: 190px;
    object-fit: cover;
    border-radius: 10px;
    display: block;
}

nav {
    background: #0b2a5b;
    margin-top: 10px;
    border-radius: 8px;
    padding: 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

nav a {
    color: white;
    padding: 9px 13px;
    border-radius: 6px;
    font-weight: bold;
    font-size: 14px;
}

nav a:hover {
    background: #17457f;
}

.search-box {
    background: white;
    padding: 18px;
    margin: 18px 0;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
}

.search-box form {
    display: flex;
    gap: 8px;
}

.search-box input {
    flex: 1;
    padding: 13px;
    border: 1px solid #ccd3dd;
    border-radius: 7px;
    font-size: 16px;
}

.search-box button {
    padding: 13px 20px;
    background: #0b2a5b;
    color: white;
    border: none;
    border-radius: 7px;
    font-weight: bold;
    cursor: pointer;
}

.breaking {
    background: #b40000;
    color: white;
    padding: 14px 16px;
    border-radius: 8px;
    margin: 18px 0;
}

.breaking strong {
    margin-right: 10px;
}

.breaking a {
    color: white;
    font-weight: bold;
}

.section-title {
    background: #071a3d;
    color: white;
    padding: 12px 15px;
    border-radius: 8px;
    margin-top: 25px;
}

.cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 15px;
    margin-top: 15px;
}

.card {
    background: white;
    border-radius: 10px;
    padding: 17px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    border: 1px solid #e0e5eb;
}

.card h3 {
    margin-top: 0;
    font-size: 19px;
    line-height: 1.35;
}

.meta {
    color: #687386;
    font-size: 13px;
    margin-bottom: 10px;
}

.card p {
    color: #4b5565;
    line-height: 1.5;
}

.read {
    display: inline-block;
    margin-top: 8px;
    color: #0b4ea2;
    font-weight: bold;
}

.page {
    background: white;
    margin: 20px 0;
    padding: 25px;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
}

.page h1 {
    line-height: 1.3;
}

.back {
    display: inline-block;
    margin-top: 15px;
    background: #071a3d;
    color: white;
    padding: 10px 15px;
    border-radius: 7px;
}

footer {
    margin-top: 35px;
    background: #071a3d;
    color: white;
    text-align: center;
    padding: 25px;
}

.empty {
    background: white;
    padding: 20px;
    border-radius: 8px;
}

@media (max-width: 800px) {
    .cards {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 550px) {
    .cards {
        grid-template-columns: 1fr;
    }

    .search-box form {
        flex-direction: column;
    }

    .logo {
        max-height: 130px;
    }

    nav a {
        font-size: 12px;
        padding: 8px 9px;
    }
}
"""


HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>JAPHET DAILY NEWS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>{{ css }}</style>
</head>

<body>

<header>
    <div class="container">
        <img class="logo"
             src="{{ url_for('static', filename='images/banner.png') }}"
             alt="JAPHET DAILY NEWS">
    </div>
</header>

<div class="container">

<nav>
    <a href="/">🏠 Home</a>
    {% for category in categories %}
        <a href="/?category={{ category|urlencode }}">
            {{ icons[category] }} {{ category }}
        </a>
    {% endfor %}
</nav>

<div class="search-box">
    <form method="get" action="/">
        <input
            type="text"
            name="search"
            value="{{ search }}"
            placeholder="Search breaking news, Nigeria, football, technology..."
        >
        <button type="submit">🔎 Search</button>
    </form>
</div>

{% if breaking %}
<div class="breaking">
    <strong>🚨 BREAKING / LATEST</strong>
    <a href="{{ story_link(breaking) }}">{{ breaking.title }}</a>
</div>
{% endif %}

{% if search %}
<h2 class="section-title">
    Search results for: "{{ search }}"
</h2>

<div class="cards">
    {% for story in search_results %}
    <div class="card">
        <div class="meta">
            {{ icons[story.category] }} {{ story.category }}
            • {{ story.source }}
        </div>

        <h3>{{ story.title }}</h3>

        <div class="meta">{{ story.date }}</div>

        <p>{{ story.description }}</p>

        <a class="read" href="{{ story_link(story) }}">
            Read Full Story →
        </a>
    </div>
    {% endfor %}
</div>

{% if not search_results %}
<div class="empty">
    No matching stories were found. Try another search.
</div>
{% endif %}

{% else %}

{% for category in categories %}

{% if category_stories[category] %}
<h2 class="section-title">
    {{ icons[category] }} {{ category }} News
</h2>

<div class="cards">

    {% for story in category_stories[category][:6] %}

    <div class="card">

        <div class="meta">
            {{ story.source }} • {{ story.date }}
        </div>

        <h3>{{ story.title }}</h3>

        <p>{{ story.description }}</p>

        <a class="read" href="{{ story_link(story) }}">
            Read Full Story →
        </a>

    </div>

    {% endfor %}

</div>
{% endif %}

{% endfor %}

{% endif %}

</div>

<footer>
    <strong>JAPHET DAILY NEWS</strong>
    <br>
    Real News • Real People • A Better Informed You
</footer>

</body>
</html>
"""


STORY_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ story.title }} - JAPHET DAILY NEWS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>{{ css }}</style>
</head>

<body>

<header>
    <div class="container">
        <img class="logo"
             src="{{ url_for('static', filename='images/banner.png') }}"
             alt="JAPHET DAILY NEWS">
    </div>
</header>

<div class="container">

<nav>
    <a href="/">🏠 Home</a>
    {% for category in categories %}
        <a href="/?category={{ category|urlencode }}">
            {{ icons[category] }} {{ category }}
        </a>
    {% endfor %}
</nav>

<div class="page">

    <div class="meta">
        {{ icons[story.category] }}
        {{ story.category }}
        • {{ story.source }}
        • {{ story.date }}
    </div>

    <h1>{{ story.title }}</h1>

    <p>{{ story.description }}</p>

    <p>
        This page provides a short summary from the news feed.
        For the complete article, visit the original publisher.
    </p>

    <a class="read"
       href="{{ story.link }}"
       target="_blank"
       rel="noopener noreferrer">
        Read Full Article at Original Source →
    </a>

    <br>

    <a class="back" href="/">
        ← Back to JAPHET DAILY NEWS
    </a>

</div>

</div>

<footer>
    <strong>JAPHET DAILY NEWS</strong>
    <br>
    Real News • Real People • A Better Informed You
</footer>

</body>
</html>
"""


@app.route("/")
def home():
    search = request.args.get("search", "").strip()
    selected_category = request.args.get("category", "").strip()

    category_stories = {}
    all_stories = []

    categories_to_load = (
        [selected_category]
        if selected_category in CATEGORIES
        else CATEGORIES
    )

    for category in categories_to_load:
        stories = get_stories(category, 20)
        category_stories[category] = stories
        all_stories.extend(stories)

    all_stories.sort(
        key=lambda story: story["timestamp"],
        reverse=True
    )

    breaking = all_stories[0] if all_stories else None

    if search:
        search_lower = search.lower()

        search_results = [
            story for story in all_stories
            if search_lower in story["title"].lower()
            or search_lower in story["description"].lower()
            or search_lower in story["category"].lower()
        ]
    else:
        search_results = []

    return render_template_string(
        HOME_TEMPLATE,
        css=BASE_CSS,
        categories=CATEGORIES,
        icons=ICONS,
        category_stories=category_stories,
        search=search,
        search_results=search_results,
        breaking=breaking,
        story_link=story_link
    )


@app.route("/story")
def story():
    story_data = {
        "title": request.args.get("title", "News Story"),
        "link": request.args.get("link", "#"),
        "category": request.args.get("category", "News"),
        "source": request.args.get("source", "News Source"),
        "date": request.args.get("date", "Latest"),
        "description": request.args.get("description", "")
    }

    return render_template_string(
        STORY_TEMPLATE,
        css=BASE_CSS,
        categories=CATEGORIES,
        icons=ICONS,
        story=story_data
    )


@app.errorhandler(500)
def server_error(error):
    return """
    <h1>JAPHET DAILY NEWS</h1>
    <h2>Something went wrong temporarily.</h2>
    <p>Please refresh the page or try another news category.</p>
    <a href="/">← Back to News</a>
    """, 500


if __name__ == "__main__":
    app.run(debug=True)