#!/usr/bin/env python3
"""
Categorize all subreddits into the 30 seed topics.

Strategy:
  1. Seed assignments — the explicit example lists from the plan, applied verbatim.
  2. Heuristic keyword/regex matching for the long tail (lowercase substring or
     anchored patterns). First matching rule wins.
  3. Anything still uncategorized → Miscellaneous.

This script is dry-run by default; pass --apply to POST /api/assign_topic.
"""
import argparse, json, re, sys, urllib.request

BASE = "http://localhost:1401"

# ---------- 1. SEED ASSIGNMENTS (verbatim from the plan tables) ----------
SEED = {
    "Jokes & Humor": [
        "r/Jokes", "r/dadjokes", "r/3amjokes", "r/cleanjokes", "r/cleandadjokes",
        "r/TwoSentenceComedy", "r/oneliners", "r/SipsTea", "r/HumorNama",
        "r/ScenesFromAHat", "r/Cleverpuns", "r/funny",
    ],
    "Reddit Stories & Best-Of": [
        "r/BestofRedditorUpdates", "r/BORUpdates", "r/TrueOffMyChest",
        "r/bestof", "r/redditonwiki", "r/stories", "r/tifu", "r/AskReddit",
        "r/bestofpositiveupdates", "r/OhNoConsequences", "r/confessions",
    ],
    "AITA & Judgement": [
        "r/AITAH", "r/AmIOverreacting", "r/amiwrong", "r/AITA_Relationships",
        "r/AITA_WIBTA_PUBLIC", "r/WhatShouldIDo", "r/TwoHotTakes",
    ],
    "Marriage & Divorce": [
        "r/Marriage", "r/Divorce", "r/Separation", "r/Christianmarriage",
        "r/datingoverforty", "r/Fencesitter",
    ],
    "Infidelity": [
        "r/survivinginfidelity", "r/cheating_stories", "r/Infidelity",
        "r/AsOneAfterInfidelity", "r/Cakeeater", "r/openmarriageregret",
        "r/SupportforBetrayed", "r/SupportforWaywards",
    ],
    "Relationship Advice": [
        "r/relationship_advice", "r/relationships", "r/Advice", "r/AskMenAdvice",
    ],
    "Sex & Intimacy": [
        "r/sex", "r/sexover30", "r/DeadBedrooms", "r/psychologyofsex",
        "r/TwoXSex", "r/HLCommunity", "r/HL_Women_Only", "r/IndiaTalksSex",
    ],
    "Non-monogamy": [
        "r/nonmonogamy", "r/polyamory", "r/EthicalNonMonogamy", "r/Threesome",
        "r/Swingers",
    ],
    "Erotica & NSFW": [
        "r/literotica", "r/sexstories", "r/gonewildstories", "r/CartoonPorn",
        "r/sex_comics", "r/interracialwild", "r/pornID", "r/tipofmypenis",
    ],
    "Books & Reading": [
        "r/whatsthatbook", "r/suggestmeabook", "r/books", "r/audible",
        "r/TrueLit", "r/booksuggestions", "r/Calibre",
    ],
    "Sci-Fi & Fantasy Books": [
        "r/printSF", "r/Fantasy", "r/ProgressionFantasy", "r/litrpg",
        "r/scifi", "r/haremfantasynovels", "r/sciencefiction",
    ],
    "Long-form Reading & Articles": [
        "r/Longreads", "r/longform",
    ],
    "Medicine & Healthcare": [
        "r/medicine", "r/Residency", "r/hospitalist", "r/nursing",
        "r/anesthesiology", "r/emergencymedicine", "r/FamilyMedicine",
        "r/whitecoatinvestor", "r/Cardiology", "r/CriticalCare",
    ],
    "Finance & Investing": [
        "r/Fire", "r/Bogleheads", "r/HENRYfinance", "r/financialindependence",
        "r/coastFIRE", "r/ChubbyFIRE", "r/Economics",
    ],
    "Real Estate & Housing": [
        "r/RealEstate", "r/realtors", "r/REBubble", "r/homeowners",
    ],
    "Tech & Self-hosting": [
        "r/selfhosted", "r/homelab", "r/Proxmox", "r/DataHoarder",
        "r/synology", "r/eGPU",
    ],
    "AI & LLMs": [
        "r/LocalLLaMA", "r/LocalLLM", "r/ClaudeAI",
    ],
    "Video Games (console/PC)": [
        "r/gaming", "r/Steam", "r/Nioh", "r/GodofWar", "r/JRPG",
        "r/patientgamers", "r/Persona5", "r/computerwargames",
        "r/gamingsuggestions", "r/BloodbornePC", "r/tearsofthekingdom",
        "r/MetaphorReFantazio", "r/ElevenTableTennis",
    ],
    "Handheld & Portable Gaming": [
        "r/SteamDeck", "r/OdinHandheld", "r/ROGAlly", "r/SBCGaming",
        "r/OculusQuest",
    ],
    "Gaming Deals & Bundles": [
        "r/GreatXboxDeals", "r/humblebundles", "r/ebookdeals",
        "r/Borderlandsshiftcodes",
    ],
    "Demographics Q&A": [
        "r/AskWomen", "r/AskMen", "r/AskWomenOver40", "r/AskMenOver30",
        "r/AskOldPeople", "r/AskOldPeopleAdvice", "r/blackmen", "r/blackladies",
        "r/blackgirls", "r/AskIndia", "r/thepassportbros", "r/TwoXChromosomes",
        "r/WomenDatingOverForty",
    ],
    "Generic Q&A": [
        "r/NoStupidQuestions", "r/TooAfraidToAsk", "r/ask", "r/askanything",
        "r/AMA", "r/AskHistorians", "r/AskRedditAfterDark",
    ],
    "Politics & Society": [
        "r/AskConservatives", "r/AskALiberal", "r/Conservative", "r/TrueReddit",
        "r/changemyview", "r/LeopardsAteMyFace", "r/Natalism",
    ],
    "News, Data & Tech Culture": [
        "r/dataisbeautiful", "r/technology", "r/energy",
    ],
    "Religion": [
        "r/TrueChristian", "r/Christianity",
    ],
    "TV, Movies & Sitcoms": [
        "r/vudu", "r/americandad", "r/Frasier", "r/sitcoms", "r/moviecritic",
        "r/movies", "r/ExplainAFilmPlotBadly",
    ],
    "Memes & Random Visuals": [
        "r/HolUp", "r/interestingasfuck", "r/maybemaybemaybe", "r/coolguides",
    ],
    "Writing & Creating": [
        "r/gamedev", "r/selfpublish", "r/graphicnovels",
    ],
    "Body, Fitness & Appearance": [
        "r/PetiteFitness", "r/femalefittofat", "r/progresspics", "r/FaceRatings",
        "r/PlasticSurgery", "r/OUTFITS", "r/BigBudgetBrides", "r/Faces",
        "r/drawme",
    ],
}

# ---------- 2. HEURISTIC RULES (first match wins) ----------
# Each rule: (compiled regex applied to lowercase sub name without "r/" prefix, topic)
RULES_RAW = [
    # AI / LLM specific (high priority before tech)
    (r"(localllm|ollama|openai|anthropic|gpt|claude|llama|huggingface|stable.?diffusion|midjourney|character.?ai|copilot|cursor|llm|aieth|machinelearning|singularity|chatgpt)", "AI & LLMs"),

    # Medicine
    (r"(medicine|medical|hospitalist|residency|nursing|anesthesi|cardiolog|emergencymedic|familymed|psychiatry|surgeon|surgery|oncolog|paediatric|pediatric|dermatolog|dentistry|hematolog|physician|nephrolog|rheumatolog|pharmacy|pulmonolog|premed|noctor|whitecoat|criticalcare)", "Medicine & Healthcare"),

    # Finance / investing
    (r"(invest|bogle|wallstreet|stock|crypto|bitcoin|ethereum|defi|finance|financial|bogleheads|fire|economy|economics|tax(?!a)|fund|portfolio|fatfire|leanfire|henryfinance|fidelity|vanguard|brokerage|dividend|chubbyfire|coastfire|saveandinvest|frugal|personalfinance|trader)", "Finance & Investing"),

    # Real estate
    (r"(realestate|realtor|rebubble|homeown|firsttimehomebuyer|landlord|tenant|mortgage|housing|rental|airbnb|condo|townhom|landord)", "Real Estate & Housing"),

    # Self-hosting / tech infra
    (r"(selfhost|homelab|homeserver|proxmox|datahoarder|synology|truenas|unraid|kubernetes|docker|raspberry|networking|sysadmin|linux|nas$|nvidia|amd|intel|pcmasterrace|buildapc|nvme|threadripper|epyc|cyberdeck|egpu|opnsense|pfsense|hardware|router|firewall)", "Tech & Self-hosting"),

    # News / data / tech culture (mostly tech news rather than self-hosting)
    (r"(dataisbeautiful|^technology$|energy|world.?news|news|currentevents|publichealth|climate|geopolitics|environment)", "News, Data & Tech Culture"),

    # Handheld gaming
    (r"(steamdeck|odinhandheld|rogally|sbcgaming|oculus|valveindex|emulation|retroid|miyoo|anbernic)", "Handheld & Portable Gaming"),

    # Gaming deals
    (r"(deal|bundle|freebies|epicgamesfree|shiftcode|humble|gog|greatxbox)", "Gaming Deals & Bundles"),

    # Video games (broad — catches franchise + generic gaming)
    (r"(gaming|^games?$|xbox|playstation|^ps[1-5]$|nintendo|switch|metroid|zelda|godofwar|nioh|persona|finalfantasy|skyrim|fallout|residentevil|monsterhunter|baldursgate|bloodborne|darksoul|tearsofthekingdom|tarkov|valorant|csgo|cs2|overwatch|hearthstone|magic.?tcg|tcg|elderscroll|witcher|cyberpunk|jrpg|crpg|mmo$|mmorpg|grandstrategy|paradoxplaza|civ|stellaris|hoi4|eu4|crusaderkings|warhammer|computerwargame|metaphorrefantazio|elden|bg3|rdr2|gta|battlefield|warzone|leagueoflegends|dota|d4|diablo|gungeon|deeprock|factorio|dwarffortress|terraria|minecraft|hollowknight|hades|stardew|valheim|noita|sekiro)", "Video Games (console/PC)"),

    # Writing / creating
    (r"(selfpublish|publishing|writing$|fiction|writers|gamedev|webdev|graphicnovel|illustration|drawing|animation|filmmaker|comic.?creator|songwriter|screenwriter|composer|musicproduction|edm.?producer)", "Writing & Creating"),

    # Books — sci-fi/fantasy specific
    (r"(scifi|sciencefiction|fantasy|litrpg|progressionfantasy|haremfantasy|printsf|cosmer|brandonsander|wheeloftime|stormlight|malazan|asoiaf|sandersonbooks|robinhobb)", "Sci-Fi & Fantasy Books"),

    # Long-form articles
    (r"(longread|longform|essays|aldaily)", "Long-form Reading & Articles"),

    # Books / general
    (r"(books?$|audible|reading|literature|whatsthatbook|truelit|calibre|kindle|kobo|libraries|bookclub|romancebooks|fanfiction|booksuggestion|suggestmeabook)", "Books & Reading"),

    # Erotica / NSFW (kept distinct from Sex & Intimacy)
    (r"(literotica|sexstories|gonewildstories|cartoonporn|sex.?comic|interracialwild|pornid|tipofmypenis|nsfw|hentai|rule34|gonewild|onlyfans|gw_)", "Erotica & NSFW"),

    # Non-monogamy
    (r"(polyamor|nonmonogamy|ethicalnonmonogamy|swinger|threesome|openmarriage|cuckold|hotwife)", "Non-monogamy"),

    # Infidelity
    (r"(infidelity|cheating|wayward|betrayed|cakeeater|adultery|affair)", "Infidelity"),

    # Marriage / divorce
    (r"(marriage|wedding|engaged|divorce|separation|fencesitter|datingoverforty|christianmarriage)", "Marriage & Divorce"),

    # Sex / intimacy
    (r"(^sex$|sexover|deadbedroom|psychologyofsex|hlcommunity|hl_women|twoxsex|indiatalkssex|tantra|kink)", "Sex & Intimacy"),

    # Relationship advice
    (r"(relationship.?advice|^relationships$|^advice$|askmenadvice|datingadvice|breakups|exno)", "Relationship Advice"),

    # AITA / moral judgement
    (r"(aita|amiwrong|amioverreact|whatshouldido|twohottakes|amitheasshole)", "AITA & Judgement"),

    # Reddit stories / best-of (besides AITA)
    (r"(bestof|borupdates|bestofredditor|trueoffmychest|stories$|tifu$|redditonwiki|ohnoconsequence|publicfreakout|justnomil|justno|raisedbynarcissists|prorevenge|maliciouscompliance|nuclearrevenge|amitheangel|familyproblems|relationshipsover|insaneparents|entitledparents|entitledpeople|choosingbeggar|niceguys|nicegirls|trashy|trashtaste|lethalcompany|toxic|prematuredeath|familydrama|drama|relationships|narcissism|familyabuse|adult.?children|brokenparents|narcabuse)", "Reddit Stories & Best-Of"),

    # Demographics Q&A
    (r"(^askwomen|^askmen|askmenover|askwomenover|askold|black(men|girls|ladies)|^askindia|passportbros|twoxchromosomes|women(dating|over)|asianamerican|biwomen)", "Demographics Q&A"),

    # Generic Q&A
    (r"(nostupid|tooafraidtoask|^ask$|^askanything$|^ama$|^askhistorians$|askscience|outoftheloop|askphilosophy|askhistorians|tellmeafact|whatisthisthing)", "Generic Q&A"),

    # Politics / society
    (r"(askconservative|askaliberal|^conservative$|truereddit|changemyview|leopardsatemyface|natalism|politics|democrat|republican|libertarian|socialism|communism|anarchism|socialjustice|feminism|menswritings|maga|libsoftiktok|jordanpeterson|antiwork|latestagecapitalism|socialdemocracy|policydecisions|prochoice|prolife)", "Politics & Society"),

    # Religion
    (r"(christian|catholic|orthodox|muslim|islam|judaism|jewish|hindu|buddhism|atheis|exmuslim|exchristian|exmormon|mormon|religioustrauma|theology|biblestudy|bible)", "Religion"),

    # TV / movies / sitcoms
    (r"(vudu|americandad|frasier|sitcom|moviecritic|^movies?$|explainafilmplot|tvshows?|televisionsuggestions|netflix|hbo|primevideo|disneyplus|peacock|hulu|appletv|streaming|trailers|tv$|breakingbad|betterCallSaul|bettercallsaul|sopranos|succession|gameofthrones|thelastofus|severance|whatwemovies|whatwomendoinmovies|criterion)", "TV, Movies & Sitcoms"),

    # Memes / random visuals
    (r"(holup|interestingasfuck|maybemaybemaybe|coolguides|nextfuckinglevel|wellthat|todayilearned|peoplefuckingdying|wholesomememes|memes$|dankmemes|technicallythetruth|mademesmile|aww|^funny$)", "Memes & Random Visuals"),

    # Body / fitness / appearance
    (r"(fitness|petitefitness|femalefittofat|progresspics|faceratings|plasticsurgery|outfits|bigbudgetbrides|faces|drawme|weight.?loss|gym|bodybuilding|crossfit|yoga|pilates|running|lifting|skincare|makeup|hair|nails|gainit|loseit|c25k|nutrition|caloriecounting)", "Body, Fitness & Appearance"),

    # Jokes / humor (lower priority than memes since some humor subs overlap)
    (r"(joke|comedy|pun|riddle|funny$|cleverpun)", "Jokes & Humor"),
]
RULES = [(re.compile(p, re.I), t) for p, t in RULES_RAW]


def classify(sub_name, seed_map):
    """Return the target topic for a given sub name."""
    if sub_name in seed_map:
        return seed_map[sub_name]
    name_no_prefix = sub_name.removeprefix("r/").lower()
    for rx, topic in RULES:
        if rx.search(name_no_prefix):
            return topic
    return "Miscellaneous"


def get_json(path):
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.loads(r.read())


def post_json(path, body):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually POST assignments")
    ap.add_argument("--show-misc", action="store_true",
                    help="list every sub that ends up in Miscellaneous")
    args = ap.parse_args()

    seed_map = {sub: topic for topic, subs in SEED.items() for sub in subs}

    subs = get_json("/api/all_subs?topic=__none__")["subs"]
    print(f"{len(subs)} subreddits to categorize")

    by_topic = {}
    for s in subs:
        t = classify(s["sub"], seed_map)
        by_topic.setdefault(t, []).append(s)

    # Sort topics by total items for the report.
    rows = sorted(
        ((t, len(lst), sum(s["item_count"] for s in lst)) for t, lst in by_topic.items()),
        key=lambda r: -r[2],
    )
    print()
    print(f"{'topic':<32} {'subs':>5} {'items':>9}")
    print("-" * 50)
    for topic, n_subs, n_items in rows:
        print(f"{topic:<32} {n_subs:>5} {n_items:>9}")

    if args.show_misc:
        misc = by_topic.get("Miscellaneous", [])
        print(f"\nMisc subs ({len(misc)}):")
        for s in sorted(misc, key=lambda s: -s["item_count"]):
            print(f"  {s['item_count']:>5}  {s['sub']}")

    if not args.apply:
        print("\n(dry run — pass --apply to POST assignments)")
        return

    print("\napplying assignments...")
    total = 0
    for topic, lst in by_topic.items():
        sub_names = [s["sub"] for s in lst]
        # Batch in chunks of 500 to keep request bodies small.
        for i in range(0, len(sub_names), 500):
            chunk = sub_names[i:i + 500]
            r = post_json("/api/assign_topic", {"subs": chunk, "topic": topic})
            total += r["assigned_count"]
        print(f"  {topic:<32} {len(sub_names):>5} subs assigned")
    print(f"\ntotal assignments: {total}")


if __name__ == "__main__":
    main()
