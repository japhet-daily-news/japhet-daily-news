from flask import Flask, request, render_template_string, jsonify
import feedparser
import re
import html
from datetime import datetime

app = Flask(__name__)

# Some news servers reject requests that do not look like a normal browser.
# Use a simple User-Agent for RSS requests.
import urllib.request
from urllib.parse import quote_plus

class NewsRequestHandler(urllib.request.HTTPRedirectHandler):
    pass

def fetch_feed(url):
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            data = response.read()
        return feedparser.parse(data)
    except Exception as error:
        print("Could not fetch feed:", url, "|", error)
        return feedparser.FeedParserDict(entries=[])


# ============================================================
# JAPHET DAILY NEWS
# AUTOMATIC FRESH NEWS + BETTER SEARCH + VIDEOS
# ============================================================

FEEDS = {
    # Google News RSS search feeds are used here because they are
    # designed for current search results and do not require an API key.
    "Nigeria": [
        "https://news.google.com/rss/search?q=Nigeria&hl=en-NG&gl=NG&ceid=NG:en",
        "https://news.google.com/rss/search?q=Nigeria+news&hl=en-NG&gl=NG&ceid=NG:en",
    ],
    "World": [
        "https://news.google.com/rss/search?q=world+news&hl=en-US&gl=US&ceid=US:en",
    ],
    "Football": [
        "https://news.google.com/rss/search?q=football+news&hl=en-GB&gl=GB&ceid=GB:en",
    ],
    "Technology": [
        "https://news.google.com/rss/search?q=technology+news&hl=en-US&gl=US&ceid=US:en",
    ],
    "AI": [
        "https://news.google.com/rss/search?q=artificial+intelligence+AI+news&hl=en-US&gl=US&ceid=US:en",
        "https://openai.com/news/rss.xml",
    ],
    "WWE": [
        "https://news.google.com/rss/search?q=WWE+news&hl=en-US&gl=US&ceid=US:en",
    ],
    "Business": [
        "https://news.google.com/rss/search?q=business+news&hl=en-US&gl=US&ceid=US:en",
    ],
}

SOURCES = {
    "Nigeria": "BBC News / Premium Times",
    "World": "BBC News",
    "Football": "BBC Sport",
    "Technology": "BBC News",
    "AI": "OpenAI News",
    "WWE": "POST Wrestling",
    "Business": "BBC News",
}

ICONS = {
    "Nigeria": "🇳🇬",
    "World": "🌍",
    "Football": "⚽",
    "Technology": "💻",
    "AI": "🤖",
    "WWE": "🤼",
    "Business": "💼",
}


def clean_text(text):
    if not text:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_timestamp(item):
    try:
        if getattr(item, "published_parsed", None):
            return datetime(*item.published_parsed[:6]).timestamp()
        if getattr(item, "updated_parsed", None):
            return datetime(*item.updated_parsed[:6]).timestamp()
    except Exception:
        pass
    return 0


def get_image(item):
    try:
        for image in item.get("media_content", []):
            if image.get("url"):
                return image["url"]
    except Exception:
        pass

    try:
        for image in item.get("media_thumbnail", []):
            if image.get("url"):
                return image["url"]
    except Exception:
        pass

    try:
        for enclosure in item.get("enclosures", []):
            url = enclosure.get("href", "")
            mime = enclosure.get("type", "")
            if url and ("image" in mime or not mime):
                return url
    except Exception:
        pass

    try:
        description = item.get("summary", "")
        match = re.search(r'<img[^>]+src=["\']([^"\']+)', description, re.I)
        if match:
            return match.group(1)
    except Exception:
        pass

    return ""


def detect_video(item):
    title = clean_text(item.get("title", "")).lower()
    description = clean_text(
        item.get("summary", item.get("description", ""))
    ).lower()
    link = item.get("link", "").lower()

    combined = title + " " + description

    video_words = [
        "video",
        "watch",
        "highlights",
        "footage",
        "clip",
        "live",
        "watch live",
    ]

    if any(word in combined for word in video_words):
        return True

    return any(
        site in link
        for site in ["youtube.com", "youtu.be", "vimeo.com"]
    )


def search_news(query, limit=30):
    """Search Google News RSS live across all JAPHET DAILY NEWS categories."""
    query = clean_text(query).strip()
    if not query:
        return []

    results = []
    seen = set()

    for category in FEEDS:
        search_url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(query + " " + category)
            + "&hl=en-NG&gl=NG&ceid=NG:en"
        )

        try:
            print("Searching:", search_url)
            feed = fetch_feed(search_url)

            for item in feed.entries:
                title = clean_text(item.get("title", ""))
                if not title:
                    continue

                key = title.lower()
                if key in seen:
                    continue
                seen.add(key)

                description = clean_text(
                    item.get(
                        "summary",
                        item.get(
                            "description",
                            item.get("title", "")
                        )
                    )
                )

                results.append({
                    "title": title,
                    "description": description,
                    "link": item.get("link", "#"),
                    "published": item.get(
                        "published",
                        item.get("updated", "")
                    ),
                    "timestamp": get_timestamp(item),
                    "category": category,
                    "source": SOURCES.get(category, ""),
                    "image": get_image(item),
                    "video": detect_video(item),
                })

        except Exception as error:
            print("Search error:", error)

    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results[:limit]


def get_stories(category, limit=20, start=0):
    stories = []
    all_entries = []

    for feed_url in FEEDS.get(category, []):
        try:
            print("Loading:", feed_url)
            feed = fetch_feed(feed_url)
            if feed.entries:
                all_entries.extend(feed.entries)
        except Exception as error:
            print("Feed error:", error)

    unique_entries = {}

    for item in all_entries:
        title = clean_text(item.get("title", "No title"))
        if not title:
            continue

        key = title.lower()
        if key not in unique_entries:
            unique_entries[key] = item

    all_entries = list(unique_entries.values())
    all_entries.sort(key=get_timestamp, reverse=True)

    for item in all_entries[start:start + limit]:
        title = clean_text(item.get("title", "No title"))
        description = clean_text(
            item.get(
                "summary",
                item.get(
                    "description",
                    item.get("title", "")
                )
            )
        )
        link = item.get("link", "#")
        published = item.get(
            "published",
            item.get("updated", "")
        )

        stories.append({
            "title": title,
            "description": description,
            "link": link,
            "published": published,
            "timestamp": get_timestamp(item),
            "category": category,
            "source": SOURCES.get(category, ""),
            "image": get_image(item),
            "video": detect_video(item),
        })

    return stories


def get_all_news(limit=20):
    all_stories = []
    category_stories = {}

    for category in FEEDS:
        stories = get_stories(category, limit, 0)
        category_stories[category] = stories
        all_stories.extend(stories)

    all_stories.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return all_stories, category_stories


@app.route("/")
def home():
    search = request.args.get("search", "").strip()
    selected_category = request.args.get("category", "").strip()

    all_stories, category_stories = get_all_news(20)

    if search:
        # Perform a fresh live search instead of searching only
        # the stories already loaded on the homepage.
        all_stories = search_news(search, 30)

        category_stories = {
            category: []
            for category in FEEDS
        }

    if selected_category in FEEDS:
        all_stories = [
            story for story in all_stories
            if story["category"] == selected_category
        ]

    breaking = all_stories[0] if all_stories else None
    videos = [story for story in all_stories if story["video"]]

    return render_template_string(
        HTML,
        categories=FEEDS.keys(),
        icons=ICONS,
        category_stories=category_stories,
        all_stories=all_stories,
        breaking=breaking,
        videos=videos,
        search=search,
        selected_category=selected_category,
    )


@app.route("/load_more")
def load_more():
    try:
        offset = int(request.args.get("offset", 20))
    except ValueError:
        offset = 20

    stories = []

    for category in FEEDS:
        stories.extend(get_stories(category, 10, offset))

    stories.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return jsonify({
        "stories": stories,
        "has_more": len(stories) > 0,
    })


@app.route("/refresh")
def refresh():
    try:
        stories, _ = get_all_news(20)

        return jsonify({
            "success": True,
            "count": len(stories),
            "message": "Fresh news loaded.",
            "stories": stories[:30],
        })

    except Exception as error:
        print("Refresh error:", error)

        return jsonify({
            "success": False,
            "message": "Unable to refresh news.",
        }), 500


@app.route("/story")
def story():
    return render_template_string(
        STORY_HTML,
        title=request.args.get("title", ""),
        description=request.args.get("description", ""),
        link=request.args.get("link", "#"),
        category=request.args.get("category", ""),
        source=request.args.get("source", ""),
        image=request.args.get("image", ""),
        icon=ICONS.get(
            request.args.get("category", ""),
            "📰"
        ),
    )


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>JAPHET DAILY NEWS</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    background:
        linear-gradient(
            rgba(0,0,0,0.78),
            rgba(0,0,0,0.78)
        ),
        url("/static/images/background.jpg");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    color: #222;
}

.header {
    background: rgba(0,0,0,0.94);
    color: white;
    padding: 25px 15px;
    text-align: center;
}

.logo {
    font-size: 38px;
    font-weight: bold;
    letter-spacing: 2px;
}

.tagline {
    margin-top: 7px;
    color: #ccc;
    font-size: 14px;
}

.live-status {
    margin-top: 12px;
    font-size: 13px;
}

.live-dot {
    display: inline-block;
    width: 9px;
    height: 9px;
    background: red;
    border-radius: 50%;
    margin-right: 5px;
}

.search-area {
    background: white;
    padding: 20px;
    text-align: center;
}

.search-box {
    max-width: 850px;
    margin: auto;
    display: flex;
}

.search-box input {
    flex: 1;
    padding: 15px;
    border: 1px solid #ddd;
    border-radius: 8px 0 0 8px;
    font-size: 16px;
    outline: none;
}

.search-box button {
    padding: 15px 25px;
    border: none;
    background: #111;
    color: white;
    border-radius: 0 8px 8px 0;
    cursor: pointer;
    font-weight: bold;
}

.nav {
    background: white;
    padding: 10px;
    display: flex;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
    border-bottom: 1px solid #ddd;
}

.nav a {
    text-decoration: none;
    color: #222;
    background: #f1f1f1;
    padding: 9px 15px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: bold;
}

.nav a:hover {
    background: #111;
    color: white;
}

.refresh-bar {
    background: white;
    text-align: center;
    padding: 12px;
    border-bottom: 1px solid #ddd;
}

.refresh-btn {
    background: #111;
    color: white;
    border: none;
    padding: 10px 18px;
    border-radius: 7px;
    cursor: pointer;
    font-weight: bold;
}

.refresh-btn:disabled {
    opacity: 0.6;
}

#refreshMessage {
    margin-left: 10px;
    color: #555;
    font-size: 13px;
}

.breaking {
    background: #b00000;
    color: white;
    padding: 13px 20px;
    font-weight: bold;
}

.breaking span {
    margin-right: 10px;
}

.container {
    max-width: 1250px;
    margin: auto;
    padding: 25px 15px;
}

.featured {
    background: white;
    padding: 25px;
    border-radius: 12px;
    margin-bottom: 30px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.18);
}

.featured-label {
    color: #b00000;
    font-weight: bold;
    margin-bottom: 10px;
}

.featured h1 {
    font-size: 30px;
    margin: 10px 0;
}

.featured p {
    color: #555;
    line-height: 1.6;
}

.section-title {
    color: white;
    font-size: 25px;
    margin: 30px 0 15px;
    border-left: 5px solid white;
    padding-left: 10px;
}

.news-grid {
    display: grid;
    grid-template-columns: repeat(
        auto-fit,
        minmax(280px, 1fr)
    );
    gap: 18px;
}

.card {
    background: white;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 15px rgba(0,0,0,0.15);
    transition: transform 0.2s;
}

.card:hover {
    transform: translateY(-4px);
}

.card-image {
    width: 100%;
    height: 190px;
    object-fit: cover;
    background: #ddd;
}

.card-top {
    padding: 18px;
}

.category {
    font-size: 13px;
    font-weight: bold;
    color: #b00000;
    margin-bottom: 8px;
}

.card h3 {
    margin: 5px 0 10px;
    font-size: 19px;
    line-height: 1.35;
}

.card p {
    color: #555;
    font-size: 14px;
    line-height: 1.5;
}

.card-footer {
    padding: 12px 18px;
    background: #f5f5f5;
    font-size: 12px;
    color: #777;
}

.read-btn {
    display: inline-block;
    margin-top: 10px;
    padding: 10px 14px;
    background: #111;
    color: white;
    text-decoration: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: bold;
}

.video-card {
    position: relative;
}

.video-badge {
    display: inline-block;
    background: #b00000;
    color: white;
    padding: 5px 9px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: bold;
    margin-bottom: 8px;
}

.play-button {
    position: absolute;
    top: 65px;
    left: 50%;
    transform: translateX(-50%);
    width: 58px;
    height: 58px;
    border-radius: 50%;
    background: rgba(0,0,0,0.75);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
}

.load-more-container {
    text-align: center;
    margin: 35px 0 45px;
}

.load-more-btn {
    background: white;
    color: #111;
    border: none;
    padding: 14px 30px;
    border-radius: 8px;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
}

.load-more-btn:disabled {
    opacity: 0.6;
}

.search-info {
    background: white;
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 18px;
    color: #555;
    font-size: 14px;
    text-align: center;
}

.no-results {
    background: white;
    padding: 30px;
    border-radius: 10px;
    text-align: center;
}

.footer {
    background: rgba(0,0,0,0.94);
    color: white;
    text-align: center;
    padding: 25px;
    margin-top: 40px;
}


.video-search {
    max-width: 850px;
    margin: 0 auto 20px;
    display: flex;
    gap: 8px;
}

.video-search input {
    flex: 1;
    padding: 14px;
    border: none;
    border-radius: 8px;
    font-size: 15px;
}

.video-search button {
    padding: 14px 18px;
    border: none;
    border-radius: 8px;
    background: white;
    color: #111;
    font-weight: bold;
    cursor: pointer;
}

@media(max-width:600px) {

    .logo {
        font-size: 27px;
    }

    .search-box input {
        width: 70%;
    }

    .search-box button {
        width: 30%;
        padding: 12px 5px;
    }

    .featured h1 {
        font-size: 23px;
    }

    .container {
        padding: 18px 10px;
    }

    .card-image {
        height: 170px;
    }
}
</style>
</head>

<body>

<header class="header">
    <div class="logo">JAPHET DAILY NEWS</div>
    <div class="tagline">
        Stay informed. Stay connected.
    </div>
    <div class="live-status">
        <span class="live-dot"></span>
        LIVE NEWS UPDATES
    </div>
</header>

<div class="search-area">
<form method="GET" action="/">
    <div class="search-box">
        <input
            type="text"
            name="search"
            value="{{ search }}"
            placeholder="Search any news topic..."
        >
        <button type="submit">🔎 SEARCH</button>
    </div>
</form>
</div>

<nav class="nav">
    <a href="/">🏠 Home</a>

    {% for category in categories %}
    <a href="/?category={{ category|urlencode }}">
        {{ icons[category] }} {{ category }}
    </a>
    {% endfor %}

    <a href="#videos">🎥 Videos</a>
</nav>

<div class="refresh-bar">
    <button
        class="refresh-btn"
        id="refreshButton"
        onclick="refreshNews()"
    >
        🔄 Refresh News
    </button>

    <span id="refreshMessage">
        Fresh news updates automatically.
    </span>
</div>

{% if breaking %}
<div class="breaking">
    <span>🔴 BREAKING NEWS</span>
    {{ breaking.title }}
</div>
{% endif %}

<main class="container">

{% if search %}

<h2 class="section-title">
    🔎 Search Results: "{{ search }}"
</h2>

<div class="search-info">
    Live search across Nigeria, World, Football, Technology, AI, WWE and Business.
</div>
</h2>

{% if all_stories %}

<div class="news-grid">

{% for story in all_stories %}

<article class="card">

{% if story.image %}
<img
    class="card-image"
    src="{{ story.image }}"
    alt="News image"
    loading="lazy"
>
{% endif %}

<div class="card-top">

<div class="category">
    {{ icons[story.category] }}
    {{ story.category }}
</div>

<h3>{{ story.title }}</h3>

{% if story.description %}
<p>
    {{ story.description[:250] }}
    {% if story.description|length > 250 %}...{% endif %}
</p>
{% endif %}

<a
class="read-btn"
href="/story?title={{ story.title|urlencode }}&description={{ story.description|urlencode }}&link={{ story.link|urlencode }}&category={{ story.category|urlencode }}&source={{ story.source|urlencode }}&image={{ story.image|urlencode }}"
>
    Read Story →
</a>

</div>

<div class="card-footer">
    {{ story.source }}
</div>

</article>

{% endfor %}

</div>

{% else %}

<div class="no-results">
    <h2>No stories found</h2>
    <p>Try another search term.</p>
</div>

{% endif %}

{% else %}

{% if breaking %}

<section class="featured">

<div class="featured-label">
    🔥 LATEST STORY
</div>

<h1>{{ breaking.title }}</h1>

<p>
    {{ breaking.description[:400] }}
    {% if breaking.description|length > 400 %}...{% endif %}
</p>

<a
class="read-btn"
href="/story?title={{ breaking.title|urlencode }}&description={{ breaking.description|urlencode }}&link={{ breaking.link|urlencode }}&category={{ breaking.category|urlencode }}&source={{ breaking.source|urlencode }}&image={{ breaking.image|urlencode }}"
>
    Read Full Story →
</a>

</section>

{% endif %}

<section id="videos">

<h2 class="section-title">
    🎥 Latest Videos
</h2>

<div class="news-grid">

{% for story in videos[:10] %}

<article class="card video-card">

{% if story.image %}
<img
    class="card-image"
    src="{{ story.image }}"
    alt="Video thumbnail"
    loading="lazy"
>
{% endif %}

<div class="play-button">▶</div>

<div class="card-top">

<div class="video-badge">
    🎥 VIDEO
</div>

<div class="category">
    {{ icons[story.category] }}
    {{ story.category }}
</div>

<h3>{{ story.title }}</h3>

<p>
    {{ story.description[:180] }}
    {% if story.description|length > 180 %}...{% endif %}
</p>

<a
class="read-btn"
href="{{ story.link }}"
target="_blank"
rel="noopener noreferrer"
>
    ▶ Watch Video
</a>

</div>

<div class="card-footer">
    {{ story.source }}
</div>

</article>

{% else %}

<div class="no-results">
    <h3>🎥 No videos available yet</h3>
    <p>
        Video stories will appear here when our news feeds provide them.
    </p>
</div>

{% endfor %}

</div>
</section>

{% for category in categories %}

<section id="{{ category|replace(' ', '-') }}">

<h2 class="section-title">
    {{ icons[category] }} {{ category }} News
</h2>

<div class="news-grid">

{% for story in category_stories[category] %}

<article class="card">

{% if story.image %}
<img
    class="card-image"
    src="{{ story.image }}"
    alt="News image"
    loading="lazy"
>
{% endif %}

<div class="card-top">

<div class="category">
    {{ icons[story.category] }}
    {{ story.category }}
</div>

<h3>{{ story.title }}</h3>

{% if story.description %}
<p>
    {{ story.description[:180] }}
    {% if story.description|length > 180 %}...{% endif %}
</p>
{% endif %}

<a
class="read-btn"
href="/story?title={{ story.title|urlencode }}&description={{ story.description|urlencode }}&link={{ story.link|urlencode }}&category={{ story.category|urlencode }}&source={{ story.source|urlencode }}&image={{ story.image|urlencode }}"
>
    Read Story →
</a>

</div>

<div class="card-footer">
    {{ story.source }}
</div>

</article>

{% endfor %}

</div>
</section>

{% endfor %}

<div class="load-more-container">

<button
id="loadMoreButton"
class="load-more-btn"
onclick="loadMoreNews()"
>
    ➕ Load More News
</button>

</div>

{% endif %}

</main>

<footer class="footer">

<strong>JAPHET DAILY NEWS</strong>

<br><br>

Bringing you the latest news from Nigeria and around the world.

<br><br>

🔄 Automatic fresh news enabled

<br><br>

© 2026 Japhet Daily News

</footer>

<script>

let newsOffset = 20;
let loading = false;

async function loadMoreNews() {

    if (loading) return;

    loading = true;

    const button =
        document.getElementById("loadMoreButton");

    button.innerText = "⏳ Loading...";
    button.disabled = true;

    try {

        const response = await fetch(
            "/load_more?offset=" + newsOffset
        );

        if (!response.ok) {
            throw new Error("Could not load news");
        }

        const data = await response.json();
        const stories = data.stories || [];

        if (stories.length === 0) {

            button.innerText =
                "No More News Available";

            return;
        }

        const grid =
            document.querySelector(".news-grid");

        if (!grid) {
            throw new Error("News grid not found");
        }

        stories.forEach(function(story) {

            const card =
                document.createElement("article");

            card.className = "card";

            let description =
                story.description || "";

            description =
                description.substring(0, 180);

            if (
                story.description &&
                story.description.length > 180
            ) {
                description += "...";
            }

            let imageHTML = "";

            if (story.image) {

                imageHTML = `
                    <img
                        class="card-image"
                        src="${escapeHtml(story.image)}"
                        alt="News image"
                        loading="lazy"
                    >
                `;
            }

            card.innerHTML = `

                ${imageHTML}

                <div class="card-top">

                    <div class="category">

                        ${getIcon(story.category)}

                        ${escapeHtml(
                            story.category
                        )}

                    </div>

                    <h3>
                        ${escapeHtml(
                            story.title
                        )}
                    </h3>

                    <p>
                        ${escapeHtml(
                            description
                        )}
                    </p>

                    <a
                        class="read-btn"
                        href="/story?title=${
                            encodeURIComponent(
                                story.title || ""
                            )
                        }&description=${
                            encodeURIComponent(
                                story.description || ""
                            )
                        }&link=${
                            encodeURIComponent(
                                story.link || ""
                            )
                        }&category=${
                            encodeURIComponent(
                                story.category || ""
                            )
                        }&source=${
                            encodeURIComponent(
                                story.source || ""
                            )
                        }&image=${
                            encodeURIComponent(
                                story.image || ""
                            )
                        }"
                    >
                        Read Story →
                    </a>

                </div>

                <div class="card-footer">

                    ${escapeHtml(
                        story.source || ""
                    )}

                </div>
            `;

            grid.appendChild(card);
        });

        newsOffset += 10;

        button.innerText =
            "➕ Load More News";

        button.disabled = false;

    } catch (error) {

        console.error(error);

        button.innerText =
            "❌ Try Again";

        button.disabled = false;

    }

    loading = false;
}


async function refreshNews() {

    const button =
        document.getElementById("refreshButton");

    const message =
        document.getElementById("refreshMessage");

    button.disabled = true;
    button.innerText = "⏳ Updating...";

    message.innerText =
        "Fetching fresh news...";

    try {

        const response =
            await fetch("/refresh");

        if (!response.ok) {
            throw new Error("Refresh failed");
        }

        const data =
            await response.json();

        if (!data.success) {
            throw new Error(
                "News update failed"
            );
        }

        message.innerText =
            "✅ Fresh news found: "
            + data.count;

        setTimeout(function() {

            location.reload();

        }, 700);

    } catch (error) {

        console.error(error);

        message.innerText =
            "❌ Update failed. Try again.";

        button.disabled = false;
        button.innerText =
            "🔄 Refresh News";
    }
}


/*
    AUTOMATIC REFRESH
    Checks for fresh news every 5 minutes.
*/

setInterval(function() {

    refreshNews();

}, 5 * 60 * 1000);



function searchVideos() {

    const input =
        document.getElementById("videoSearch");

    const query =
        input.value.trim();

    if (!query) {
        alert("Type something to search for videos.");
        return;
    }

    const url =
        "https://www.youtube.com/results?search_query="
        + encodeURIComponent(
            query + " news"
        );

    window.open(
        url,
        "_blank",
        "noopener,noreferrer"
    );
}


function getIcon(category) {

    const icons = {

        "Nigeria": "🇳🇬",
        "World": "🌍",
        "Football": "⚽",
        "Technology": "💻",
        "AI": "🤖",
        "WWE": "🤼",
        "Business": "💼"

    };

    return icons[category] || "📰";
}


function escapeHtml(text) {

    const div =
        document.createElement("div");

    div.textContent = text || "";

    return div.innerHTML;
}

</script>

</body>
</html>
"""


STORY_HTML = r"""
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

<title>
{{ title }} - JAPHET DAILY NEWS
</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    font-family:
        Arial,
        Helvetica,
        sans-serif;

    background:
        linear-gradient(
            rgba(0,0,0,0.75),
            rgba(0,0,0,0.75)
        ),
        url(
            "/static/images/background.jpg"
        );

    background-size: cover;
    background-position: center;
    background-attachment: fixed;

    color: #222;
}

.header {

    background:
        rgba(0,0,0,0.94);

    color: white;

    text-align: center;

    padding: 25px;

}

.logo {

    font-size: 30px;

    font-weight: bold;

}

.article {

    max-width: 850px;

    margin: 40px auto;

    background: white;

    padding: 30px;

    border-radius: 12px;

    box-shadow:
        0 4px 20px
        rgba(0,0,0,0.2);

}

.article-image {

    width: 100%;

    max-height: 450px;

    object-fit: cover;

    border-radius: 10px;

    margin:
        15px 0 25px;

}

.category {

    color: #b00000;

    font-weight: bold;

}

h1 {

    font-size: 34px;

    line-height: 1.3;

}

.description {

    font-size: 17px;

    line-height: 1.8;

    color: #444;

}

.source {

    margin-top: 20px;

    color: #777;

}

.original {

    display: inline-block;

    margin-top: 25px;

    padding: 14px 20px;

    background: #111;

    color: white;

    text-decoration: none;

    border-radius: 7px;

    font-weight: bold;

}

.back {

    display: inline-block;

    margin-bottom: 20px;

    text-decoration: none;

    color: #111;

    font-weight: bold;

}

@media(max-width:600px) {

    .article {

        margin: 20px 10px;

        padding: 20px;

    }

    h1 {

        font-size: 25px;

    }

    .description {

        font-size: 16px;

    }

}

</style>

</head>

<body>

<header class="header">

    <div class="logo">
        JAPHET DAILY NEWS
    </div>

</header>

<article class="article">

<a class="back" href="/">
    ← Back to News
</a>

<div class="category">

    {{ icon }} {{ category }}

</div>

<h1>

    {{ title }}

</h1>

{% if image %}

<img
    class="article-image"
    src="{{ image }}"
    alt="News image"
>

{% endif %}

<div class="description">

    {{ description }}

</div>

<div class="source">

    Source: {{ source }}

</div>

<a
    class="original"
    href="{{ link }}"
    target="_blank"
    rel="noopener noreferrer"
>

    Read Full Article at Original Source →

</a>

</article>

</body>

</html>
"""


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
