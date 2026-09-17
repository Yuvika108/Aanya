"""
Comprehensive Automated Test Suite for Aanya Assistant Intent Recognition,
Music Playback, Dynamic Temporal Grounding, and Passive Learning.
"""

import os
import shutil
import pytest
from server.engine import AanyaEngine, _match_site_intent, _match_close_tab_intent, DEFAULT_MEMORY
from main import AanyaEngine as MainEngine, _match_site_intent as main_match_site_intent, _match_close_tab_intent as main_match_close_tab_intent

TEST_SESSION = "test_assistant_eval"


@pytest.fixture(autouse=True)
def clean_test_session():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")
    engine.forget("all")
    yield
    engine.forget("all")


def test_date_and_time_intent():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")

    # Strict time questions should trigger instant responses
    for q in ["what is the time", "what's the time", "what time is it", "current time", "tell me the time"]:
        res = engine._handle_instant_command(q)
        assert res is not None, f"Expected instant command for: {q}"
        assert ":" in res["reply"]
        assert ("AM" in res["reply"] or "PM" in res["reply"])

    # Strict date questions should trigger instant responses
    for q in ["what is today's date", "what's the date", "what date is it today", "today's date", "what is the date"]:
        res = engine._handle_instant_command(q)
        assert res is not None, f"Expected instant command for: {q}"
        assert "Today is" in res["reply"]

    # Conversational or historical queries containing 'today' or 'time' MUST NOT be intercepted
    conversational_queries = [
        "How are you today?",
        "What should I wear today?",
        "Help me plan my workday today.",
        "What time did Apollo 11 land on the moon?",
        "How many times should I water my snake plant per week?",
        "Every time I run this script it throws an error",
        "It is time to learn a new language",
    ]
    for q in conversational_queries:
        res = engine._handle_instant_command(q)
        assert res is None, f"Query '{q}' should NOT be intercepted by instant command!"


def test_site_and_search_intent():
    # Direct site openings
    yt = _match_site_intent("open youtube")
    assert yt is not None
    assert "youtube.com" in yt["url"]

    # GitHub variations
    for q in ["open github", "open my github", "github", "git hub", "can you open github", "please open github"]:
        gh = _match_site_intent(q)
        assert gh is not None, f"Expected match for: {q}"
        assert gh["name"] == "GitHub"
        assert "github.com" in gh["url"]

    # Email variations
    email_queries = [
        "open email", "open emails", "open my email", "open my emails",
        "check email", "check my email", "check emails", "check my emails",
        "email", "emails", "mail", "gmail", "open gmail", "show my email", "read my emails"
    ]
    for q in email_queries:
        m = _match_site_intent(q)
        assert m is not None, f"Expected match for email query: {q}"
        assert m["name"] == "Gmail"
        assert "mail.google.com" in m["url"]

    # Codolio variations
    for q in ["open codolio", "open my codolio", "codolio", "can you open codolio", "please open codolio"]:
        c = _match_site_intent(q)
        assert c is not None, f"Expected match for: {q}"
        assert c["name"] == "Codolio"
        assert "codolio.com" in c["url"]

    # LinkedIn variations
    for q in ["open linkedin", "open my linkedin", "linkedin", "can you open linkedin", "please open linkedin"]:
        li = _match_site_intent(q)
        assert li is not None, f"Expected match for: {q}"
        assert li["name"] == "LinkedIn"
        assert "linkedin.com" in li["url"]

    # Spotify site opening
    for q in ["open spotify", "spotify", "open my spotify"]:
        sp = _match_site_intent(q)
        assert sp is not None, f"Expected match for: {q}"
        assert sp["name"] == "Spotify"
        assert "spotify.com" in sp["url"]

    # Search intents
    g_search = _match_site_intent("search google for quantum computing")
    assert g_search is not None
    assert "google.com/search?q=" in g_search["url"]
    assert "quantum%20computing" in g_search["url"]

    yt_search = _match_site_intent("search youtube for lo-fi beats")
    assert yt_search is not None
    assert "youtube.com/results?search_query=" in yt_search["url"]

    wiki_search = _match_site_intent("search wikipedia for Marie Curie")
    assert wiki_search is not None
    assert "wikipedia.org/w/index.php?search=" in wiki_search["url"]

    # Drafting, informational questions must NOT open sites
    assert _match_site_intent("draft an email to my professor") is None
    assert _match_site_intent("write an email asking for leave") is None
    assert _match_site_intent("How does Google search indexing work?") is None
    assert _match_site_intent("Tell me about Wikipedia articles") is None
    assert _match_site_intent("What is a mail transfer agent?") is None


def test_music_intent():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")

    # Natural & generic music requests must all trigger music playback
    generic_music_queries = [
        "play songs",
        "play a song",
        "play song",
        "play music",
        "play some music",
        "play some songs",
        "can you play a song",
        "could you play some music",
        "play me a song",
        "i want to listen to music",
        "put on some songs",
        "sing a song",
    ]
    for q in generic_music_queries:
        res = engine._parse_song_intent(q)
        assert res is not None, f"Expected music intent for query: {q}"
        assert "url" in res and "video_id" in res
        # User constraint: ALWAYS play songs from YouTube
        assert "youtube.com" in res["url"]

    # Specific song requests
    specific_queries = [
        ("play espresso", "eVli-tstM5E"),
        ("can you please play espresso", "eVli-tstM5E"),
        ("i want to listen to espresso", "eVli-tstM5E"),
        ("play flowers", "G7KNmW9a75Y"),
        ("play bohemian rhapsody", "fJ9rUzIMcZQ"),
    ]
    for q, vid in specific_queries:
        res = engine._parse_song_intent(q)
        assert res is not None, f"Expected match for: {q}"
        assert res["video_id"] == vid
        assert "autoplay=1" in res["url"]
        assert "youtube.com" in res["url"]

    # Song suggestions
    suggest = engine._parse_song_intent("suggest a song")
    assert suggest is not None
    assert suggest["video_id"] is not None
    assert "youtube.com" in suggest["url"]

    # Spotify song request — User constraint: ALWAYS play songs from YouTube
    spotify_song = engine._parse_song_intent("play bohemian rhapsody on spotify")
    assert spotify_song is not None
    assert "youtube.com" in spotify_song["url"]
    assert spotify_song["video_id"] == "fJ9rUzIMcZQ"

    # Controls
    stop_res = engine._handle_instant_command("pause music")
    assert stop_res is not None
    assert stop_res["action"] == "pause-music"

    resume_res = engine._handle_instant_command("resume music")
    assert resume_res is not None
    assert resume_res["action"] == "resume-music"

    # Exclusions: non-music 'play' queries must NOT trigger music playback
    non_music_queries = [
        "how to play guitar",
        "how do i play chess",
        "can you teach me how to play poker",
        "let's play twenty questions",
        "can you play the devil's advocate for this argument?",
        "play a role in our interview practice",
        "play along with me",
        "play with different ideas",
    ]
    for q in non_music_queries:
        assert engine._parse_song_intent(q) is None, f"Query '{q}' should NOT trigger music intent!"


def test_tasks_and_reminders():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")

    # Add task
    add_res = engine._handle_instant_command("remember to buy groceries")
    assert add_res is not None
    assert add_res["action"] == "task-added"
    assert "buy groceries" in add_res["reply"]

    # Show tasks
    show_res = engine._handle_instant_command("show my tasks")
    assert show_res is not None
    assert show_res["action"] == "show-tasks"
    assert "buy groceries" in show_res["action_data"]

    # Conversational 'remember' that are NOT tasks should NOT be added as tasks
    assert engine._handle_instant_command("do you remember my name?") is None
    assert engine._handle_instant_command("remember when we talked about AI?") is None


def test_passive_learning_and_stopword_sanity():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")

    # Common phrases with "I am" / "I'm" must NOT change user name to adjectives
    adjectives_to_test = ["ready", "tired", "back", "here", "hungry", "learning", "confused", "sorry", "sure", "happy"]
    for adj in adjectives_to_test:
        engine._learn_from_message(f"I am {adj}")
        engine._learn_from_message(f"I'm {adj}")
        assert engine.memory["user_profile"].get("name") != adj.capitalize(), f"Name should NOT be {adj.capitalize()}"

    # Explicit name introduction MUST work
    engine._learn_from_message("My name is Yuvi")
    assert engine.memory["user_profile"].get("name") == "Yuvi"

    # 'Actually' compliments should NOT increment negative feedback
    initial_thumbs_down = engine.memory["feedback"].get("thumbs_down", 0)
    engine._learn_from_message("Actually, that sounds great!")
    engine._learn_from_message("Actually, I completely agree.")
    assert engine.memory["feedback"].get("thumbs_down", 0) == initial_thumbs_down

    # Everyday sentences with 'always' or 'never' should NOT pollute rules/aversions
    engine._learn_from_message("The sun always sets in the west")
    assert "sets in the west" not in engine.memory["behavior_rules"]

    engine._learn_from_message("I don't know the answer to this question")
    assert "know the answer to this question" not in engine.memory["aversions"]


def test_farewell_intent():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")

    # True farewells
    for q in ["goodbye", "bye", "bye bye", "see you later", "aanya quit"]:
        res = engine._handle_instant_command(q)
        assert res is not None
        assert res["action"] == "quit"

    # Sentences containing 'sleep' or 'exit' must NOT quit
    for q in [
        "How many hours of sleep do adults need?",
        "I need good sleep tonight",
        "Why does python exit with code 1?",
        "What is an emergency exit?",
    ]:
        res = engine._handle_instant_command(q)
        assert res is None, f"Query '{q}' should NOT be treated as a farewell!"


def test_custom_links():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")

    # Initially empty or clean
    links = engine.get_links()
    initial_count = len(links)

    # 1. Add link programmatically
    new_link = engine.add_link("portfolio", "https://yuvika.dev")
    assert new_link["name"] == "portfolio"
    assert new_link["url"] == "https://yuvika.dev"
    assert len(engine.get_links()) == initial_count + 1

    # 2. Match site intent with custom links
    match = _match_site_intent("open portfolio", custom_links=engine.get_links())
    assert match is not None
    assert match["url"] == "https://yuvika.dev"
    assert match["name"] == "portfolio"

    # 3. Voice instant command: open custom link
    open_res = engine._handle_instant_command("open portfolio")
    assert open_res is not None
    assert open_res["action"] == "open-url"
    assert open_res["action_data"] == "https://yuvika.dev"

    # 4. Voice instant command: add link
    add_voice = engine._handle_instant_command("add link docs https://docs.python.org")
    assert add_voice is not None
    assert add_voice["action"] == "link-added"
    assert "docs" in add_voice["reply"]

    # 5. Voice instant command: show links
    show_links = engine._handle_instant_command("show links")
    assert show_links is not None
    assert show_links["action"] == "show-links"
    assert len(show_links["action_data"]) >= 2

    # 6. Delete link
    deleted = engine.delete_link(new_link["id"])
    assert deleted is True
    assert not any(l["id"] == new_link["id"] for l in engine.get_links())


def test_main_py_engine_consistency():
    main_eng = MainEngine()

    # Song intent — ALWAYS YouTube
    res = main_eng._parse_song_intent("play espresso")
    assert res is not None
    assert res["video_id"] == "eVli-tstM5E"
    assert "youtube.com" in res["url"]

    # Spotify song request routes to YouTube
    spot_res = main_eng._parse_song_intent("play flowers on spotify")
    assert spot_res is not None
    assert spot_res["video_id"] == "G7KNmW9a75Y"
    assert "youtube.com" in spot_res["url"]

    # Non-music intent exclusion
    assert main_eng._parse_song_intent("how to play piano") is None
    assert main_eng._parse_song_intent("play chess") is None

    # Search & site matching
    site = main_match_site_intent("search google for python")
    assert site is not None
    assert "google.com/search?q=" in site["url"]

    # LinkedIn search in main.py
    li_site = main_match_site_intent("Search LinkedIn for AI/ML internships")
    assert li_site is not None
    assert li_site["name"] == "LinkedIn"
    assert "linkedin.com/search/results/all/?keywords=" in li_site["url"]

    # Close tab intent in main.py
    c_tab = main_match_close_tab_intent("Close Github")
    assert c_tab is not None
    assert c_tab["name"] == "GitHub"


    # Platforms in main.py
    for q, domain in [
        ("open codolio", "codolio.com"),
        ("open linkedin", "linkedin.com"),
        ("open spotify", "spotify.com"),
        ("open gmail", "mail.google.com"),
        ("open github", "github.com"),
    ]:
        m = main_match_site_intent(q)
        assert m is not None, f"Expected main.py match for: {q}"
        assert domain in m["url"]


def test_linkedin_search_intent():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")

    # 1. Direct query requested by user: "Search LinkedIn for AI/ML internships"
    res = engine._handle_instant_command("Search LinkedIn for AI/ML internships")
    assert res is not None
    assert res["action"] == "open-url"
    assert "linkedin.com/search/results/all/?keywords=" in res["action_data"]
    assert "ai/ml" in res["action_data"].lower()
    assert "ai/ml internships" in res["reply"].lower()

    # 2. Variants of LinkedIn search
    queries = [
        ("search on linkedin for python developer", "python%20developer"),
        ("search linkedin for data science", "data%20science"),
        ("linkedin search for software engineer", "software%20engineer"),
        ("linkedin search deep learning", "deep%20learning"),
    ]
    for q, encoded in queries:
        m = _match_site_intent(q)
        assert m is not None, f"Expected match for: {q}"
        assert m["name"] == "LinkedIn"
        assert "linkedin.com/search/results/all/?keywords=" in m["url"]
        assert encoded in m["url"].lower()

    # Exclusions: standard open linkedin should open home, not search
    open_li = _match_site_intent("open linkedin")
    assert open_li is not None
    assert open_li["url"] == "https://www.linkedin.com"
    assert "search" not in open_li["url"]


def test_close_browser_tab_intent():
    engine = AanyaEngine(session_id=TEST_SESSION, api_key="fake-key-for-unit-test")

    # 1. Close specific tabs (e.g. "Close Github")
    res = engine._handle_instant_command("Close Github")
    assert res is not None
    assert res["action"] == "close-tab"
    assert res["action_data"]["site"] == "GitHub"
    assert "Closing GitHub tab." in res["reply"]

    # 2. Case and polite variants
    for q in [
        "close github",
        "close the github tab",
        "can you please close github?",
        "close the tab for github",
    ]:
        c = engine._handle_instant_command(q)
        assert c is not None, f"Expected close tab match for: {q}"
        assert c["action"] == "close-tab"
        assert c["action_data"]["site"] == "GitHub"

    # 3. Other known sites
    for site, name in [("linkedin", "LinkedIn"), ("youtube", "YouTube"), ("spotify", "Spotify")]:
        c = engine._handle_instant_command(f"close {site}")
        assert c is not None, f"Expected close tab match for: close {site}"
        assert c["action"] == "close-tab"
        assert c["action_data"]["site"] == name

    # 4. Generic active tab
    for q in ["close tab", "close browser tab", "close active tab", "close this tab"]:
        c = engine._handle_instant_command(q)
        assert c is not None, f"Expected active tab match for: {q}"
        assert c["action"] == "close-tab"
        assert c["action_data"]["target"] == "active"

    # 5. Exclusions
    for q in [
        "how to close a deal",
        "what is github",
        "pause music",
    ]:
        m = _match_close_tab_intent(q)
        assert m is None, f"Query '{q}' should NOT match close tab intent!"
