from flask import Flask, request, render_template_string, jsonify
import feedparser
import re
import html
from datetime import datetime
from urllib.parse import quote_plus

app = Flask(__name__)

# ============================================================
# JAPHET DAILY NEWS - UPGRADED VERSION
# Features:
# 1. Automatic fresh news
# 2. Better search
# 3. Videos section
# ============================================================

# =========================
# NEWS FEEDS
# =========================

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

# Video feeds. These are kept separate from normal news feeds.
VIDEO_FEEDS = {
    "BBC News": "https://feeds.bbci.co.uk/news/video_and_audio/rss.xml",
    "BBC Sport": "https://feeds.bbci.co.uk/sport/rss.xml"
}


# =========================
# CLEAN TEXT
# =========================

def clean_text(text):
    if not text:
        return ""

    text = html.unescape(str(text))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================
# TIME HELPERS
# =========================

def get_timestamp(item):
    try:
        if getattr(item, "published_parsed", None):
            return datetime(*item.published_parsed[:6]).timestamp()

        if getattr(item, "updated_parsed", None):
            return datetime(*item.updated_parsed[:6]).timestamp()
    except Exception:
        pass

    return 0


def get_published_text(item):
    return item.get(
        "published",
        item.get("updated", "")
    )


# =========================
# GET NEWS
# =========================

def get_stories(category, limit=20, start=0):
    stories = []

    try:
        feed = feedparser.parse(FEEDS[category])
        entries = feed.entries[start:start + limit]

        for item in entries:
            title = clean_text(item.get("title", "No title"))
            description = clean_text(
                item.get("summary", item.get("description", ""))
            )
            link = item.get("link", "#")
            published = get_published_text(item)

            stories.append({
                "title": title,
                "description": description,
                "link": link,
                "published": published,
                "timestamp": get_timestamp(item),
                "category": category,
                "source": SOURCES.get(category, ""),
                "image": get_image(item)
            })

    except Exception as e:
        print(f"Error loading {category}: {e}")

    return stories


# =========================
# IMAGE EXTRACTION
# =========================

def get_image(item):
    try:
        media_content = item.get("media_content", [])
        if media_content:
            for media in media_content:
                if media.get("url"):
                    return media["url"]

        media_thumbnail = item.get("media_thumbnail", [])
        if media_thumbnail:
            for media in media_thumbnail:
                if media.get("url"):
                    return media["url"]

        enclosures = item.get("enclosures", [])
        for enclosure in enclosures:
            url = enclosure.get("href") or enclosure.get("url")
            mime = enclosure.get("type", "")
            if url and ("image" in mime or not mime):
                return url

    except Exception:
        pass

    return ""


# =========================
# GET VIDEOS
# =========================

def get_videos(limit=20):
    videos = []

    for source_name, feed_url in VIDEO_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)

            for item in feed.entries[:limit]:
                title = clean_text(item.get("title", "Video"))
                description = clean_text(
                    item.get("summary", item.get("description", ""))
                )
                link = item.get("link", "#")

                videos.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "published": get_published_text(item),
                    "timestamp": get_timestamp(item),
                    "source": source_name,
                    "image": get_image(item)
                })

        except Exception as e:
            print(f"Error loading videos from {source_name}: {e}")

    videos.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return videos[:limit]


# =========================
# HOME PAGE
# =========================

@app.route("/")
def home():

    search = request.args.get("search", "").strip()
    category_filter = request.args.get("category", "").strip()

    category_stories = {}
    all_stories = []

    # Fresh RSS data is fetched on each page request.
    for category in FEEDS:
        stories = get_stories(category, 20, 0)
        category_stories[category] = stories
        all_stories.extend(stories)

    # Sort newest first
    all_stories.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    # Better search
    if search:
        search_lower = search.lower()
        words = [
            word for word in re.findall(r"\w+", search_lower)
            if len(word) > 1
        ]

        def matches(story):
            searchable = " ".join([
                story.get("title", ""),
                story.get("description", ""),
                story.get("category", ""),
                story.get("source", "")
            ]).lower()

            # Exact phrase match
            if search_lower in searchable:
                return True

            # Match all search words
            return bool(words) and all(word in searchable for word in words)

        all_stories = [
            story for story in all_stories
            if matches(story)
        ]

    if category_filter and category_filter in FEEDS:
        all_stories = [
            story for story in all_stories
            if story["category"] == category_filter
        ]

    breaking = all_stories[0] if all_stories else None
    videos = get_videos(12)

    return render_template_string(
        HTML,
        categories=FEEDS.keys(),
        icons=ICONS,
        category_stories=category_stories,
        all_stories=all_stories,
        breaking=breaking,
        search=search,
        category_filter=category_filter,
        videos=videos
    )


# =========================
# LOAD MORE NEWS
# =========================

@app.route("/load_more")
def load_more():

    try:
        offset = int(request.args.get("offset", 20))
    except ValueError:
        offset = 20

    stories = []

    for category in FEEDS:
        new_stories = get_stories(category, 10, offset)
        stories.extend(new_stories)

    stories.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return jsonify({
        "stories": stories,
        "has_more": len(stories) > 0
    })


# =========================
# REFRESH NEWS API
# =========================

@app.route("/api/refresh")
def refresh_news():
    stories = []

    for category in FEEDS:
        stories.extend(get_stories(category, 10, 0))

    stories.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return jsonify({
        "updated": True,
        "count": len(stories),
        "stories": stories[:30]
    })


# =========================
# VIDEOS API
# =========================

@app.route("/videos")
def videos_page():
    videos = get_videos(30)

    return render_template_string(
        VIDEO_HTML,
        videos=videos
    )


@app.route("/api/videos")
def videos_api():
    videos = get_videos(20)

    return jsonify({
        "videos": videos
    })


# =========================
# STORY PAGE
# =========================

@app.route("/story")
def story():

    title = request.args.get("title", "")
    description = request.args.get("description", "")
    link = request.args.get("link", "#")
    category = request.args.get("category", "")
    source = request.args.get("source", "")

    return render_template_string(
        STORY_HTML,
        title=title,
        description=description,
        link=link,
        category=category,
        source=source,
        icon=ICONS.get(category, "📰")
    )


# ============================================================
# HOME HTML
# ============================================================

HTML = """
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
            rgba(0,0,0,0.70),
            rgba(0,0,0,0.70)
        ),
        url("/static/images/background.jpg");

    background-size: cover;
    background-position: center;
    background-attachment: fixed;

    color: #222;
}

/* HEADER */

.header {
    background: rgba(0,0,0,0.92);
    color: white;
    padding: 22px 15px;
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

/* LIVE UPDATE */

.live-bar {
    background: #111;
    color: white;
    text-align: center;
    padding: 9px;
    font-size: 13px;
}

.live-dot {
    display: inline-block;
    width: 9px;
    height: 9px;
    background: #00c853;
    border-radius: 50%;
    margin-right: 6px;
}

/* SEARCH */

.search-area {
    background: white;
    padding: 20px;
    text-align: center;
}

.search-box {
    max-width: 800px;
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

/* NAV */

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

/* BREAKING */

.breaking {
    background: #b00000;
    color: white;
    padding: 13px 20px;
    font-weight: bold;
}

.breaking span {
    margin-right: 10px;
}

/* MAIN */

.container {
    max-width: 1250px;
    margin: auto;
    padding: 25px 15px;
}

/* FEATURED */

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

/* SECTION */

.section-title {
    color: white;
    font-size: 25px;
    margin: 30px 0 15px;
    border-left: 5px solid white;
    padding-left: 10px;
}

/* GRID */

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

/* BUTTON */

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

/* VIDEO */

.video-section {
    margin-top: 45px;
}

.video-card {
    position: relative;
}

.video-card .play {
    position: absolute;
    left: 50%;
    top: 95px;
    transform: translate(-50%, -50%);
    background: rgba(0,0,0,0.8);
    color: white;
    width: 55px;
    height: 55px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
}

.video-btn {
    background: #b00000;
}

.view-videos {
    text-align: center;
    margin: 25px 0;
}

.view-videos a {
    display: inline-block;
    background: white;
    color: #111;
    text-decoration: none;
    padding: 13px 25px;
    border-radius: 8px;
    font-weight: bold;
}

/* LOAD MORE */

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
    box-shadow: 0 3px 10px rgba(0,0,0,0.2);
}

.load-more-btn:hover {
    background: #111;
    color: white;
}

.load-more-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

/* NO RESULTS */

.no-results {
    background: white;
    padding: 30px;
    border-radius: 10px;
    text-align: center;
}

/* FOOTER */

.footer {
    background: rgba(0,0,0,0.92);
    color: white;
    text-align: center;
    padding: 25px;
    margin-top: 40px;
}

/* MOBILE */

@media(max-width: 600px) {

    .logo {
        font-size: 27px;
    }

    .search-box {
        width: 100%;
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
        height: 180px;
    }
}

</style>
</head>


<body>

<!-- HEADER -->

<header class="header">

    <div class="logo">
        JAPHET DAILY NEWS
    </div>

    <div class="tagline">
        Stay informed. Stay connected.
    </div>

</header>


<!-- AUTOMATIC UPDATE STATUS -->

<div class="live-bar">
    <span class="live-dot"></span>
    LIVE NEWS • Automatically refreshed
    <span id="lastUpdated"></span>
</div>


<!-- SEARCH -->

<div class="search-area">

<form method="GET" action="/">

    <div class="search-box">

        <input
            type="text"
            name="search"
            value="{{ search }}"
            placeholder="Search news, topics, football, AI, Nigeria..."
        >

        <button type="submit">
            🔎 SEARCH
        </button>

    </div>

</form>

</div>


<!-- NAV -->

<nav class="nav">

    <a href="/">
        🏠 Home
    </a>

    {% for category in categories %}

        <a href="#{{ category|replace(' ', '-') }}">
            {{ icons[category] }}
            {{ category }}
        </a>

    {% endfor %}

    <a href="/videos">
        🎥 Videos
    </a>

</nav>


<!-- BREAKING -->

{% if breaking %}

<div class="breaking">

    <span>
        🔴 BREAKING NEWS
    </span>

    {{ breaking.title }}

</div>

{% endif %}


<!-- MAIN -->

<main class="container">


{% if search %}

<h2 class="section-title">
    🔎 Search results for "{{ search }}"
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
        onerror="this.style.display='none'"
    >
    {% endif %}

    <div class="card-top">

        <div class="category">
            {{ icons[story.category] }}
            {{ story.category }}
        </div>

        <h3>
            {{ story.title }}
        </h3>

        {% if story.description %}

        <p>
            {{ story.description[:250] }}
            {% if story.description|length > 250 %}
                ...
            {% endif %}
        </p>

        {% endif %}

        <a
            class="read-btn"
            href="/story?title={{ story.title|urlencode }}&description={{ story.description|urlencode }}&link={{ story.link|urlencode }}&category={{ story.category|urlencode }}&source={{ story.source|urlencode }}"
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

    <h2>
        No stories found
    </h2>

    <p>
        Try another search word or phrase.
    </p>

</div>

{% endif %}


{% else %}


<!-- FEATURED -->

{% if breaking %}

<section class="featured">

    <div class="featured-label">
        🔥 LATEST STORY
    </div>

    <h1>
        {{ breaking.title }}
    </h1>

    <p>
        {{ breaking.description[:400] }}

        {% if breaking.description|length > 400 %}
            ...
        {% endif %}
    </p>

    <a
        class="read-btn"
        href="/story?title={{ breaking.title|urlencode }}&description={{ breaking.description|urlencode }}&link={{ breaking.link|urlencode }}&category={{ breaking.category|urlencode }}&source={{ breaking.source|urlencode }}"
    >
        Read Full Story →
    </a>

</section>

{% endif %}


<!-- VIDEO SECTION -->

<section class="video-section">

    <h2 class="section-title">
        🎥 Latest Videos
    </h2>

    <div class="news-grid">

    {% for video in videos[:6] %}

    <article class="card video-card">

        {% if video.image %}

        <img
            class="card-image"
            src="{{ video.image }}"
            alt="Video thumbnail"
            loading="lazy"
            onerror="this.style.display='none'"
        >

        {% endif %}

        <div class="play">
            ▶
        </div>

        <div class="card-top">

            <div class="category">
                🎥 VIDEO
            </div>

            <h3>
                {{ video.title }}
            </h3>

            {% if video.description %}

            <p>
                {{ video.description[:150] }}

                {% if video.description|length > 150 %}
                    ...
                {% endif %}
            </p>

            {% endif %}

            <a
                class="read-btn video-btn"
                href="{{ video.link }}"
                target="_blank"
                rel="noopener noreferrer"
            >
                ▶ Watch Video
            </a>

        </div>

        <div class="card-footer">
            {{ video.source }}
        </div>

    </article>

    {% endfor %}

    </div>

    <div class="view-videos">
        <a href="/videos">
            🎥 View All Videos →
        </a>
    </div>

</section>


<!-- CATEGORIES -->

{% for category in categories %}

<section id="{{ category|replace(' ', '-') }}">

    <h2 class="section-title">

        {{ icons[category] }}

        {{ category }} News

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
            onerror="this.style.display='none'"
        >

        {% endif %}

        <div class="card-top">

            <div class="category">

                {{ icons[story.category] }}

                {{ story.category }}

            </div>


            <h3>

                {{ story.title }}

            </h3>


            {% if story.description %}

            <p>

                {{ story.description[:180] }}

                {% if story.description|length > 180 %}
                    ...
                {% endif %}

            </p>

            {% endif %}


            <a
                class="read-btn"
                href="/story?title={{ story.title|urlencode }}&description={{ story.description|urlencode }}&link={{ story.link|urlencode }}&category={{ story.category|urlencode }}&source={{ story.source|urlencode }}"
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


<!-- LOAD MORE -->

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


<!-- FOOTER -->

<footer class="footer">

    <strong>
        JAPHET DAILY NEWS
    </strong>

    <br><br>

    Bringing you fresh news
    from Nigeria and around the world.

    <br><br>

    © 2026 Japhet Daily News

</footer>


<script>

let newsOffset = 20;
let loading = false;


/* =========================
   LAST UPDATED
========================= */

function updateTime() {

    const now = new Date();

    document.getElementById("lastUpdated").innerText =
        " • Updated " + now.toLocaleTimeString();

}

updateTime();


/* =========================
   AUTOMATIC FRESH NEWS
========================= */

/*
   Refresh the page every 5 minutes.
   This means the browser asks Flask for
   fresh RSS data automatically.
*/

setInterval(function() {

    if (!document.hidden && !document.querySelector('input:focus')) {
        window.location.reload();
    }

}, 5 * 60 * 1000);


/* =========================
   LOAD MORE
========================= */

async function loadMoreNews() {

    if (loading) {
        return;
    }

    loading = true;

    const button =
        document.getElementById("loadMoreButton");

    button.innerText =
        "⏳ Loading more news...";

    button.disabled = true;


    try {

        const response =
            await fetch(
                "/load_more?offset=" + newsOffset
            );


        if (!response.ok) {

            throw new Error(
                "Could not load news"
            );

        }


        const data =
            await response.json();


        const stories =
            data.stories;


        if (!stories || stories.length === 0) {

            button.innerText =
                "No More News Available";

            button.disabled = true;

            loading = false;

            return;

        }


        let grid =
            document.querySelector(".news-grid");


        if (!grid) {

            throw new Error(
                "News grid not found"
            );

        }


        stories.forEach(function(story) {

            const card =
                document.createElement("article");

            card.className =
                "card";


            const description =
                story.description
                ? story.description.substring(
                    0,
                    180
                ) + (
                    story.description.length > 180
                    ? "..."
                    : ""
                )
                : "";


            const image =
                story.image
                ? `
                    <img
                        class="card-image"
                        src="${escapeHtml(story.image)}"
                        alt="News image"
                        loading="lazy"
                    >
                  `
                : "";


            card.innerHTML = `

                ${image}

                <div class="card-top">

                    <div class="category">

                        ${getIcon(story.category)}

                        ${escapeHtml(story.category)}

                    </div>


                    <h3>

                        ${escapeHtml(story.title)}

                    </h3>


                    ${
                        description
                        ? `
                        <p>
                            ${escapeHtml(description)}
                        </p>
                        `
                        : ""
                    }


                    <a
                        class="read-btn"
                        href="/story?title=${encodeURIComponent(story.title)}&description=${encodeURIComponent(story.description || "")}&link=${encodeURIComponent(story.link)}&category=${encodeURIComponent(story.category)}&source=${encodeURIComponent(story.source)}"
                    >

                        Read Story →

                    </a>

                </div>


                <div class="card-footer">

                    ${escapeHtml(story.source)}

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


/* =========================
   ICONS
========================= */

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


/* =========================
   SECURITY
========================= */

function escapeHtml(text) {

    const div =
        document.createElement("div");

    div.textContent =
        text || "";

    return div.innerHTML;

}

</script>


</body>
</html>
"""


# ============================================================
# VIDEO PAGE HTML
# ============================================================

VIDEO_HTML = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Videos - JAPHET DAILY NEWS</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    font-family: Arial, Helvetica, sans-serif;

    background:
        linear-gradient(
            rgba(0,0,0,0.72),
            rgba(0,0,0,0.72)
        ),
        url("/static/images/background.jpg");

    background-size: cover;
    background-position: center;
    background-attachment: fixed;

}

.header {

    background: rgba(0,0,0,0.92);

    color: white;

    text-align: center;

    padding: 25px;

}

.logo {

    font-size: 30px;

    font-weight: bold;

}

.container {

    max-width: 1200px;

    margin: auto;

    padding: 25px 15px;

}

.title {

    color: white;

    border-left: 5px solid white;

    padding-left: 12px;

    margin-bottom: 25px;

}

.grid {

    display: grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(280px, 1fr)
        );

    gap: 20px;

}

.card {

    background: white;

    border-radius: 12px;

    overflow: hidden;

    box-shadow:
        0 4px 15px
        rgba(0,0,0,0.2);

}

.thumbnail {

    width: 100%;

    height: 210px;

    object-fit: cover;

    background: #ddd;

}

.card-body {

    padding: 18px;

}

.card h2 {

    font-size: 19px;

    line-height: 1.4;

}

.card p {

    color: #555;

    line-height: 1.5;

}

.watch {

    display: inline-block;

    margin-top: 10px;

    padding: 11px 16px;

    background: #111;

    color: white;

    text-decoration: none;

    border-radius: 7px;

    font-weight: bold;

}

.back {

    display: inline-block;

    margin-bottom: 20px;

    color: white;

    text-decoration: none;

    font-weight: bold;

}

</style>

</head>


<body>


<header class="header">

    <div class="logo">
        JAPHET DAILY NEWS
    </div>

</header>


<main class="container">

    <a class="back" href="/">
        ← Back to News
    </a>

    <h1 class="title">
        🎥 Latest News Videos
    </h1>


    <div class="grid">

    {% for video in videos %}

    <article class="card">

        {% if video.image %}

        <img
            class="thumbnail"
            src="{{ video.image }}"
            alt="Video thumbnail"
            loading="lazy"
        >

        {% endif %}


        <div class="card-body">

            <h2>
                🎥 {{ video.title }}
            </h2>

            {% if video.description %}

            <p>
                {{ video.description[:250] }}

                {% if video.description|length > 250 %}
                    ...
                {% endif %}
            </p>

            {% endif %}

            <a
                class="watch"
                href="{{ video.link }}"
                target="_blank"
                rel="noopener noreferrer"
            >
                ▶ Watch Video
            </a>

        </div>

    </article>

    {% endfor %}

    </div>

</main>


</body>

</html>
"""


# ============================================================
# STORY HTML
# ============================================================

STORY_HTML = """

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>
{{ title }} - JAPHET DAILY NEWS
</title>


<style>

body {

    margin: 0;

    font-family:
        Arial,
        sans-serif;

    background:
        linear-gradient(
            rgba(0,0,0,0.72),
            rgba(0,0,0,0.72)
        ),
        url("/static/images/background.jpg");

    background-size: cover;

    background-position: center;

    color: #222;

}


.header {

    background:
        rgba(0,0,0,0.92);

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

    padding:
        14px 20px;

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

</style>

</head>


<body>


<header class="header">

    <div class="logo">

        JAPHET DAILY NEWS

    </div>

</header>


<article class="article">


<a
    class="back"
    href="/"
>

    ← Back to News

</a>


<div class="category">

    {{ icon }}

    {{ category }}

</div>


<h1>

    {{ title }}

</h1>


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


# =========================
# START SERVER
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
a
