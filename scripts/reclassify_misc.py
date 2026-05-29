#!/usr/bin/env python3
"""
Reclassify subreddits currently in Miscellaneous using known sub names +
keyword/regex rules. Output-only: dry run by default; --apply POSTs.

Two layers (first match wins):
  1. EXPLICIT_MAP — sub name (case-insensitive, "r/" prefix stripped)
     mapped directly to a topic. Used for subs I recognize specifically.
  2. RULES_RAW — regex patterns applied to the lowercase sub name. Catches
     classes of subs (e.g. anything ending in "tipofmy*" → Generic Q&A).

Anything not matched stays in Miscellaneous.
"""
import argparse, json, re, sys, urllib.request

BASE = "http://localhost:1401"

# Sub names (case-insensitive, no "r/" prefix) → topic.
# Hand-built from knowledge of what these subs are about.
EXPLICIT = {
    # ---------- Reddit Stories & Best-Of ----------
    "overheard": "Reddit Stories & Best-Of",
    "self": "Reddit Stories & Best-Of",
    "vent": "Reddit Stories & Best-Of",
    "offmychest": "Reddit Stories & Best-Of",
    "offmychestindia": "Reddit Stories & Best-Of",
    "confession": "Reddit Stories & Best-Of",
    "redditforgrownups": "Reddit Stories & Best-Of",
    "redditor_updates": "Reddit Stories & Best-Of",
    "marknarrations": "Reddit Stories & Best-Of",
    "foundandexpose": "Reddit Stories & Best-Of",
    "bizarrelife": "Reddit Stories & Best-Of",
    "rs_x": "Reddit Stories & Best-Of",
    "talesfromthefrontdesk": "Reddit Stories & Best-Of",
    "talesfromtechsupport": "Reddit Stories & Best-Of",
    "talesfromretail": "Reddit Stories & Best-Of",
    "talesfromyourserver": "Reddit Stories & Best-Of",
    "talesfromthepublic": "Reddit Stories & Best-Of",
    "dustythunder": "Reddit Stories & Best-Of",
    "deepthoughts": "Reddit Stories & Best-Of",
    "seriousconversation": "Reddit Stories & Best-Of",
    "shittyaskreddit": "Reddit Stories & Best-Of",
    "stupidquestions": "Reddit Stories & Best-Of",
    "randomquestions": "Reddit Stories & Best-Of",
    "doesanybodyelse": "Reddit Stories & Best-Of",
    "morbidquestions": "Reddit Stories & Best-Of",
    "moraldilemmas": "AITA & Judgement",
    "trueratediscussions": "AITA & Judgement",
    "whatdoido": "AITA & Judgement",

    # ---------- AITA / Judgement ----------
    "shittyadvice": "AITA & Judgement",
    "amihot": "AITA & Judgement",
    "uglyduckling": "AITA & Judgement",
    "doppelganger": "AITA & Judgement",
    "doyoulooklikeme": "AITA & Judgement",
    "amiuglybrutallyhonest": "AITA & Judgement",
    "roastme": "AITA & Judgement",
    "truerateme": "AITA & Judgement",

    # ---------- Memes & Random Visuals ----------
    "utterlyinteresting": "Memes & Random Visuals",
    "interesting": "Memes & Random Visuals",
    "interestingtoread": "Memes & Random Visuals",
    "unexpected": "Memes & Random Visuals",
    "beamazed": "Memes & Random Visuals",
    "opticalillusions": "Memes & Random Visuals",
    "agedlikemilk": "Memes & Random Visuals",
    "nottheonion": "Memes & Random Visuals",
    "therewasanattempt": "Memes & Random Visuals",
    "murderedbywords": "Memes & Random Visuals",
    "abruptchaos": "Memes & Random Visuals",
    "amazing": "Memes & Random Visuals",
    "absoluteunits": "Memes & Random Visuals",
    "blackmagicfuckery": "Memes & Random Visuals",
    "confusingperspective": "Memes & Random Visuals",
    "confusing_perspective": "Memes & Random Visuals",
    "damnthatsinteresting": "Memes & Random Visuals",
    "oddlysatisfying": "Memes & Random Visuals",
    "gifsthatendtoosoon": "Memes & Random Visuals",
    "impressively": "Memes & Random Visuals",
    "justgalsbeingchicks": "Memes & Random Visuals",
    "badassanimals": "Memes & Random Visuals",
    "animalsdoingstuff": "Memes & Random Visuals",
    "germanshepherds": "Memes & Random Visuals",
    "goldenretrievers": "Memes & Random Visuals",
    "husky": "Memes & Random Visuals",
    "snakes": "Memes & Random Visuals",
    "explainitpeter": "Memes & Random Visuals",
    "infographics": "Memes & Random Visuals",
    "pics": "Memes & Random Visuals",
    "calvinandhobbes": "Memes & Random Visuals",
    "unethicallifeprotips": "Memes & Random Visuals",
    "lifehacks": "Memes & Random Visuals",
    "yousshouldknow": "Memes & Random Visuals",
    "youshouldknow": "Memes & Random Visuals",
    "coolthings": "Memes & Random Visuals",
    "whenyouseeit": "Memes & Random Visuals",
    "tierlists": "Memes & Random Visuals",
    "weirdest": "Memes & Random Visuals",
    "rareinsults": "Memes & Random Visuals",
    "humansbeingbros": "Memes & Random Visuals",
    "mademesmile": "Memes & Random Visuals",
    "funnyandsad": "Memes & Random Visuals",
    "popculturechat": "Memes & Random Visuals",
    "shittymobilegameads": "Memes & Random Visuals",
    "rareinsults": "Memes & Random Visuals",
    "todayilearned": "Memes & Random Visuals",
    "tipofmytongue": "Memes & Random Visuals",
    "toastme": "Memes & Random Visuals",
    "funfacts": "Memes & Random Visuals",
    "watchitfortheplot": "Memes & Random Visuals",
    "wholesomepranks": "Memes & Random Visuals",
    "wellthat": "Memes & Random Visuals",
    "theyknew": "Memes & Random Visuals",
    "unbgbbiivchidctiicbg": "Memes & Random Visuals",
    "trashy": "Memes & Random Visuals",
    "rareinsults": "Memes & Random Visuals",
    "copypasta": "Memes & Random Visuals",
    "programmerhumor": "Memes & Random Visuals",
    "okbuddycinephile": "Memes & Random Visuals",
    "popheadscirclejerk": "Memes & Random Visuals",
    "sadposting": "Memes & Random Visuals",

    # ---------- Generic Q&A ----------
    "answers": "Generic Q&A",
    "explainlikeimfive": "Generic Q&A",
    "asksocialscience": "Generic Q&A",
    "askscience": "Generic Q&A",
    "askphilosophy": "Generic Q&A",
    "findareddit": "Generic Q&A",
    "whatisit": "Generic Q&A",
    "whatisthisthing": "Generic Q&A",
    "askelectricians": "Generic Q&A",
    "askcarsales": "Generic Q&A",
    "askfuneraldirectors": "Generic Q&A",
    "askpsychology": "Generic Q&A",
    "askgames": "Generic Q&A",

    # ---------- Demographics Q&A ----------
    "nigeria": "Demographics Q&A",
    "nigerianfood": "Demographics Q&A",
    "ghana": "Demographics Q&A",
    "returntoindia": "Demographics Q&A",
    "developersindia": "Demographics Q&A",
    "china": "Demographics Q&A",
    "japan": "Demographics Q&A",
    "japanlife": "Demographics Q&A",
    "korea": "Demographics Q&A",
    "shanghai": "Demographics Q&A",
    "thegirlsurvivalguide": "Demographics Q&A",
    "redditforgrownups": "Demographics Q&A",
    "agingparents": "Demographics Q&A",
    "over60": "Demographics Q&A",
    "sahm": "Demographics Q&A",
    "mommit": "Demographics Q&A",
    "breakingmom": "Demographics Q&A",
    "oneanddone": "Demographics Q&A",
    "nairobi": "Demographics Q&A",
    "homeschool": "Demographics Q&A",
    "europe": "Demographics Q&A",
    "canada": "Demographics Q&A",
    "unitedkingdom": "Demographics Q&A",
    "asknyc": "Demographics Q&A",
    "newyorkcity": "Demographics Q&A",
    "washingtondc": "Demographics Q&A",
    "maryland": "Demographics Q&A",
    "philadelphia": "Demographics Q&A",
    "florida": "Demographics Q&A",
    "vegas": "Demographics Q&A",
    "appalachia": "Demographics Q&A",
    "amerexit": "Demographics Q&A",
    "askfeminists": "Demographics Q&A",
    "samegrassbutgreener": "Demographics Q&A",
    "passportbrosfemale": "Demographics Q&A",
    "widowers": "Demographics Q&A",
    "blackrules": "Demographics Q&A",
    "askindia": "Demographics Q&A",
    "saginaw": "Demographics Q&A",  # Michigan local

    # ---------- TV, Movies & Sitcoms ----------
    "moviesuggestions": "TV, Movies & Sitcoms",
    "movierecommendations": "TV, Movies & Sitcoms",
    "underratedmovies": "TV, Movies & Sitcoms",
    "moviequestions": "TV, Movies & Sitcoms",
    "whatsthemoviecalled": "TV, Movies & Sitcoms",
    "asiancinema": "TV, Movies & Sitcoms",
    "westerns": "TV, Movies & Sitcoms",
    "classicfilms": "TV, Movies & Sitcoms",
    "80smovies": "TV, Movies & Sitcoms",
    "flicks": "TV, Movies & Sitcoms",
    "film": "TV, Movies & Sitcoms",
    "iwatchedanoldmovie": "TV, Movies & Sitcoms",
    "seinfeld": "TV, Movies & Sitcoms",
    "bobsburgers": "TV, Movies & Sitcoms",
    "office": "TV, Movies & Sitcoms",
    "poirot": "TV, Movies & Sitcoms",
    "sesamestreet": "TV, Movies & Sitcoms",
    "willferrell": "TV, Movies & Sitcoms",
    "thedavidpakmanshow": "TV, Movies & Sitcoms",
    "behindthebastards": "TV, Movies & Sitcoms",
    "television": "TV, Movies & Sitcoms",
    "animesuggest": "TV, Movies & Sitcoms",
    "doctorwho": "TV, Movies & Sitcoms",
    "succession": "TV, Movies & Sitcoms",

    # ---------- Video Games ----------
    "yuzu": "Video Games (console/PC)",
    "ryujinx": "Video Games (console/PC)",
    "borderlands": "Video Games (console/PC)",
    "retroarch": "Video Games (console/PC)",
    "roms": "Video Games (console/PC)",
    "c64": "Video Games (console/PC)",
    "n64": "Video Games (console/PC)",
    "snes": "Video Games (console/PC)",
    "psx": "Video Games (console/PC)",
    "dos": "Video Games (console/PC)",
    "deadspace": "Video Games (console/PC)",
    "soulslikes": "Video Games (console/PC)",
    "demonssouls": "Video Games (console/PC)",
    "totk": "Video Games (console/PC)",
    "botw": "Video Games (console/PC)",
    "breath_of_the_wild": "Video Games (console/PC)",
    "hyruleengineering": "Video Games (console/PC)",
    "mariokartworld": "Video Games (console/PC)",
    "oblivion": "Video Games (console/PC)",
    "towerdefense": "Video Games (console/PC)",
    "realtimestrategy": "Video Games (console/PC)",
    "drpg": "Video Games (console/PC)",
    "strategyrpg": "Video Games (console/PC)",
    "roguelites": "Video Games (console/PC)",
    "monstertrain": "Video Games (console/PC)",
    "simracing": "Video Games (console/PC)",
    "virtualpinball": "Video Games (console/PC)",
    "cemu": "Video Games (console/PC)",
    "shadps4": "Video Games (console/PC)",
    "ps4piracy": "Video Games (console/PC)",
    "ps4homebrew": "Video Games (console/PC)",
    "rpcs3": "Video Games (console/PC)",
    "remoteplay": "Video Games (console/PC)",
    "xcloud": "Video Games (console/PC)",
    "spiritisland": "Video Games (console/PC)",
    "rocksmith": "Video Games (console/PC)",
    "lego": "Video Games (console/PC)",
    "wingspan": "Video Games (console/PC)",
    "gamerecommendations": "Video Games (console/PC)",
    "askgames": "Video Games (console/PC)",
    "adventuregames": "Video Games (console/PC)",
    "rocksmith": "Video Games (console/PC)",
    "nfsu2": "Video Games (console/PC)",
    "tabletennis": "Video Games (console/PC)",
    "elevenbox": "Video Games (console/PC)",
    "tetris": "Video Games (console/PC)",

    # ---------- Handheld & Portable Gaming ----------
    "virtualreality": "Handheld & Portable Gaming",
    "cloudygamer": "Handheld & Portable Gaming",
    "ipad": "Handheld & Portable Gaming",
    "ios": "Handheld & Portable Gaming",
    "surfaceduo": "Handheld & Portable Gaming",

    # ---------- Tech & Self-hosting ----------
    "tailscale": "Tech & Self-hosting",
    "wireguard": "Tech & Self-hosting",
    "vpnrecommendations": "Tech & Self-hosting",
    "jellyfin": "Tech & Self-hosting",
    "homeassistant": "Tech & Self-hosting",
    "joplinapp": "Tech & Self-hosting",
    "redditdev": "Tech & Self-hosting",
    "comfyui": "Tech & Self-hosting",
    "minipcs": "Tech & Self-hosting",
    "thinkpad": "Tech & Self-hosting",
    "kasmweb": "Tech & Self-hosting",
    "rustdesk": "Tech & Self-hosting",
    "sonarr": "Tech & Self-hosting",
    "radarr": "Tech & Self-hosting",
    "portainer": "Tech & Self-hosting",
    "ticktick": "Tech & Self-hosting",
    "monarchmoney": "Finance & Investing",
    "wifi": "Tech & Self-hosting",
    "techsupport": "Tech & Self-hosting",
    "techforlife": "Tech & Self-hosting",
    "iptvniverse": "Tech & Self-hosting",
    "vseebox": "Tech & Self-hosting",
    "calibre-web": "Tech & Self-hosting",
    "computers": "Tech & Self-hosting",
    "software": "Tech & Self-hosting",
    "strixhalo": "Tech & Self-hosting",
    "robotics": "Tech & Self-hosting",
    "spotify": "Tech & Self-hosting",
    "verizon": "Tech & Self-hosting",
    "piracy": "Tech & Self-hosting",
    "mangapiracy": "Tech & Self-hosting",
    "dhexchange": "Tech & Self-hosting",
    "datahoarder_": "Tech & Self-hosting",
    "usenet": "Tech & Self-hosting",
    "radio": "Tech & Self-hosting",
    "pwnhub": "Tech & Self-hosting",
    "unixporn": "Tech & Self-hosting",
    "electricvehicles": "Tech & Self-hosting",
    "solar": "Tech & Self-hosting",

    # ---------- AI & LLMs ----------
    "genaiapps": "AI & LLMs",
    "aitoolsperformance": "AI & LLMs",
    "vibecoding": "AI & LLMs",
    "stablediffusion": "AI & LLMs",
    "automatic1111": "AI & LLMs",

    # ---------- Writing & Creating ----------
    "kdp": "Writing & Creating",
    "eroticauthors": "Writing & Creating",
    "selfimprovement": "Writing & Creating",
    "photoshoprequest": "Writing & Creating",
    "comics": "Writing & Creating",
    "comixology": "Writing & Creating",
    "musicians": "Writing & Creating",
    "musicbusiness": "Writing & Creating",
    "guitar": "Writing & Creating",
    "songwriters": "Writing & Creating",
    "letstalkmusic": "Writing & Creating",
    "coding": "Writing & Creating",
    "learnpython": "Writing & Creating",
    "python": "Writing & Creating",
    "cpp": "Writing & Creating",
    "dataengineering": "Writing & Creating",
    "devops": "Writing & Creating",
    "softwarearchitecture": "Writing & Creating",

    # ---------- Books & Reading ----------
    "noveltranslations": "Sci-Fi & Fantasy Books",
    "lightnovels": "Sci-Fi & Fantasy Books",
    "wuxiaworld": "Sci-Fi & Fantasy Books",
    "royalroad": "Sci-Fi & Fantasy Books",
    "manhwa": "Sci-Fi & Fantasy Books",
    "manhwarecommendations": "Sci-Fi & Fantasy Books",
    "doujinshi": "Sci-Fi & Fantasy Books",
    "kavitamanga": "Sci-Fi & Fantasy Books",
    "tachimanga": "Sci-Fi & Fantasy Books",
    "mangarockapp": "Sci-Fi & Fantasy Books",
    "iteration110cradle": "Sci-Fi & Fantasy Books",
    "motheroflearning": "Sci-Fi & Fantasy Books",
    "adriantchaikovsky": "Sci-Fi & Fantasy Books",
    "horrorlit": "Sci-Fi & Fantasy Books",
    "brontesisters": "Books & Reading",
    "tolkienfans": "Sci-Fi & Fantasy Books",
    "ireadabookandadoreedit": "Books & Reading",
    "ireadabookandadoredit": "Books & Reading",
    "terriblebookcovers": "Books & Reading",
    "music": "Reddit Stories & Best-Of",  # broad
    "hiphopheads": "Writing & Creating",
    "hiphop101": "Writing & Creating",
    "indieheads": "Writing & Creating",
    "kendricklamar": "Writing & Creating",
    "billboard": "Writing & Creating",
    "rap": "Writing & Creating",

    # ---------- Medicine & Healthcare ----------
    "radiology": "Medicine & Healthcare",
    "neurology": "Medicine & Healthcare",
    "attendings": "Medicine & Healthcare",
    "medschool": "Medicine & Healthcare",
    "crna": "Medicine & Healthcare",
    "therapists": "Medicine & Healthcare",
    "stopdrinking": "Medicine & Healthcare",
    "askpsychology": "Medicine & Healthcare",
    "premed": "Medicine & Healthcare",
    "noctor": "Medicine & Healthcare",

    # ---------- Finance & Investing ----------
    "rich": "Finance & Investing",
    "wealth": "Finance & Investing",
    "salary": "Finance & Investing",
    "money": "Finance & Investing",
    "accounting": "Finance & Investing",
    "bonds": "Finance & Investing",
    "letfs": "Finance & Investing",
    "daytrading": "Finance & Investing",
    "diyretirement": "Finance & Investing",
    "retirement401k": "Finance & Investing",
    "syndications": "Finance & Investing",
    "private_equity": "Finance & Investing",
    "velocitybanking": "Finance & Investing",
    "overemployed": "Finance & Investing",
    "consulting": "Finance & Investing",
    "lawyertalk": "Finance & Investing",
    "lawfirm": "Finance & Investing",
    "law": "Finance & Investing",
    "biglaw": "Finance & Investing",
    "legaladvice": "Finance & Investing",
    "publicdefenders": "Finance & Investing",
    "architects": "Finance & Investing",
    "sales": "Finance & Investing",
    "salesdevelopment": "Finance & Investing",
    "journalism": "Finance & Investing",
    "airlinepilots": "Finance & Investing",
    "aviation": "Finance & Investing",
    "flying": "Finance & Investing",
    "consulting": "Finance & Investing",
    "business": "Finance & Investing",
    "scotus": "Finance & Investing",
    "layoffs": "Finance & Investing",

    # ---------- Real Estate & Housing ----------
    "homeimprovement": "Real Estate & Housing",
    "homebuilding": "Real Estate & Housing",
    "construction": "Real Estate & Housing",
    "fuckhoa": "Real Estate & Housing",
    "propertymanagement": "Real Estate & Housing",
    "hvacadvice": "Real Estate & Housing",
    "plumbing": "Real Estate & Housing",
    "electricians": "Real Estate & Housing",

    # ---------- Politics & Society ----------
    "unpopularopinion": "Politics & Society",
    "trueunpopularopinion": "Politics & Society",
    "centrist": "Politics & Society",
    "skeptic": "Politics & Society",
    "qanoncasualties": "Politics & Society",
    "hermancainaward": "Politics & Society",
    "votedem": "Politics & Society",
    "whatbidenhasdone": "Politics & Society",
    "anime_titties": "Politics & Society",  # actually world politics
    "theeconomist": "Politics & Society",
    "ezraklein": "Politics & Society",
    "europe_news": "Politics & Society",
    "geography": "Politics & Society",
    "holyshithistory": "Politics & Society",
    "askhistorians_": "Politics & Society",
    "askhistorians2": "Politics & Society",
    "geopolitics": "Politics & Society",
    "yimby": "Politics & Society",
    "rant": "Politics & Society",

    # ---------- News, Data & Tech Culture ----------
    "infographics_": "News, Data & Tech Culture",
    "iphone": "News, Data & Tech Culture",
    "preppers": "News, Data & Tech Culture",

    # ---------- Erotica & NSFW ----------
    "joi": "Erotica & NSFW",
    "long_porn": "Erotica & NSFW",
    "short_porn": "Erotica & NSFW",
    "goonvids4u": "Erotica & NSFW",
    "stupidslutsclub": "Erotica & NSFW",
    "girlskissing": "Erotica & NSFW",
    "realhomeporn": "Erotica & NSFW",
    "homemadexxx": "Erotica & NSFW",
    "pornvids": "Erotica & NSFW",
    "pornstar_domain": "Erotica & NSFW",
    "adultvrgames": "Erotica & NSFW",
    "adultcaptiongod": "Erotica & NSFW",
    "clappingdemcheeks": "Erotica & NSFW",
    "illusionporn": "Erotica & NSFW",
    "chickflixxx": "Erotica & NSFW",
    "tightdresses": "Erotica & NSFW",
    "hotpast": "Erotica & NSFW",
    "passionx": "Erotica & NSFW",
    "blackrules": "Erotica & NSFW",
    "sexynormalgirl": "Erotica & NSFW",
    "sneakyporn": "Erotica & NSFW",
    "slutsofsnapchat": "Erotica & NSFW",
    "pornwha": "Erotica & NSFW",
    "doujinshi": "Erotica & NSFW",
    "titfuck": "Erotica & NSFW",
    "watchitfortheplot": "Erotica & NSFW",
    "wholesomepranks": "Erotica & NSFW",
    "stripper": "Erotica & NSFW",
    "sextoys": "Erotica & NSFW",

    # ---------- Non-monogamy ----------
    "enm": "Non-monogamy",
    "polyadvice": "Non-monogamy",
    "theotherwoman": "Non-monogamy",

    # ---------- Sex & Intimacy ----------
    "psychologyofsex": "Sex & Intimacy",

    # ---------- Body, Fitness & Appearance ----------
    "cico": "Body, Fitness & Appearance",
    "emogothstyle": "Body, Fitness & Appearance",
    "fashion": "Body, Fitness & Appearance",
    "style": "Body, Fitness & Appearance",
    "vindicta": "Body, Fitness & Appearance",
    "lookyourbest": "Body, Fitness & Appearance",

    # ---------- Gaming Deals & Bundles ----------
    "kdp": "Writing & Creating",  # duplicate but keep

    # ---------- Math / Education ----------
    "math": "Generic Q&A",
    "mathematics": "Generic Q&A",
    "college": "Generic Q&A",
    "teaching": "Generic Q&A",

    # ---------- Cooking-ish (no category, goes to Misc, but cluster) ----------
    "smoking": "Miscellaneous",
    "sousvide": "Miscellaneous",
    "steak": "Miscellaneous",
    "restaurant": "Miscellaneous",

    # ---------- Misc explicit ----------
    "maxcactus_trailguide": "Miscellaneous",  # personal sub
    "test": "Miscellaneous",
}

# Lowercase the keys for safety
EXPLICIT = {k.lower(): v for k, v in EXPLICIT.items()}

# ---------- Pattern rules (lowercased sub name, "r/" stripped) ----------
RULES_RAW = [
    # AI / LLMs
    (r"(localllm|ollama|openai|anthropic|gpt|claude|llama|huggingface|stable.?diffusion|midjourney|character.?ai|copilot|^cursor|llm|machinelearning|singularity|chatgpt|aitools|generativeai|comfyui|automatic1111|vibecoding|stablediffusion)", "AI & LLMs"),

    # Medicine
    (r"(medicine|medical|hospitalist|residency|nursing|anesthesi|cardiolog|emergencymedic|familymed|psychiatry|surgeon|surgery|oncolog|paediatric|pediatric|dermatolog|dentistry|hematolog|physician|nephrolog|rheumatolog|pharmacy|pulmonolog|premed|noctor|whitecoat|criticalcare|radiology|neurology|attending|medschool|crna|stopdrinking|therapist|psychology)", "Medicine & Healthcare"),

    # Finance / investing
    (r"(invest|bogle|wallstreet|^stock|crypto|bitcoin|ethereum|defi|finance|financial|bogleheads|fire|economy|economics|tax(?!a)|portfolio|fatfire|leanfire|henryfinance|fidelity|vanguard|brokerage|dividend|chubbyfire|coastfire|saveandinvest|frugal|personalfinance|trader|salary|wealth|^rich$|^money$|monarchmoney|accounting|bonds|letfs|daytrading|retirement|consulting|biglaw|lawfirm|lawyer|^law$|legaladvice|publicdefender|architects|^sales$|salesdevelopment|journalism|aviation|flying|airline|business|scotus|layoffs|private_equity|velocity|overemployed|career)", "Finance & Investing"),

    # Real estate / housing / construction / home
    (r"(realestate|realtor|rebubble|homeown|firsttimehomebuyer|landlord|tenant|mortgage|housing|rental|airbnb|condo|townhom|landord|homeimprovement|homebuilding|construction|fuckhoa|propertymanagement|hvac|plumbing|electrician)", "Real Estate & Housing"),

    # Self-hosting / tech infra
    (r"(selfhost|homelab|homeserver|proxmox|datahoarder|synology|truenas|unraid|kubernetes|docker|raspberry|networking|sysadmin|^linux$|nas$|nvidia|amd|intel|pcmasterrace|buildapc|nvme|threadripper|epyc|cyberdeck|egpu|opnsense|pfsense|hardware|router|firewall|tailscale|wireguard|vpn|jellyfin|homeassistant|joplin|comfyui|minipc|thinkpad|kasmweb|rustdesk|sonarr|radarr|portainer|ticktick|wifi|techsupport|iptv|vseebox|computers|software|robotics|spotify|verizon|piracy|usenet|radio|pwnhub|unixporn|techforlife|sveltejs|programming|rubyonrails|webdev|frontend|backend|fullstack|typescript|^rust$|golang|^python|kubernetes|terraform|aws$|gcp$|azure|opensource|github|gitops|cpp|dataengineering|devops|softwarearchitect|coding|learnpython|electricvehicles|solar|^cars$|chargingstations|tesla|^evs$|teslamodel)", "Tech & Self-hosting"),

    # News / data / tech culture
    (r"(dataisbeautiful|^technology$|energy|world.?news|^news$|currentevents|publichealth|climate|geopolitics|environment|infographics|preppers)", "News, Data & Tech Culture"),

    # Handheld / portable
    (r"(steamdeck|odinhandheld|rogally|sbcgaming|oculus|valveindex|emulation|retroid|miyoo|anbernic|virtualreality|cloudygamer)", "Handheld & Portable Gaming"),

    # Gaming deals
    (r"(deal|bundle|freebies|epicgamesfree|shiftcode|humble|^gog$|greatxbox)", "Gaming Deals & Bundles"),

    # Video games (broad)
    (r"(gaming|^games?$|xbox|playstation|^ps[1-5]$|nintendo|switch|metroid|zelda|godofwar|nioh|persona|finalfantasy|skyrim|fallout|residentevil|monsterhunter|baldursgate|bloodborne|darksoul|tearsofthekingdom|tarkov|valorant|csgo|cs2|overwatch|hearthstone|magic.?tcg|^tcg|elderscroll|witcher|cyberpunk|jrpg|crpg|^mmo|mmorpg|grandstrategy|paradoxplaza|^civ|stellaris|hoi4|eu4|crusaderkings|warhammer|computerwargame|metaphorrefantazio|elden|^bg3|rdr2|^gta|battlefield|warzone|leagueoflegends|dota|^d4$|diablo|gungeon|deeprock|factorio|dwarffortress|terraria|minecraft|hollowknight|hades|stardew|valheim|noita|sekiro|borderlands|^yuzu$|^ryujinx$|retroarch|^roms?$|^c64$|^n64$|^snes$|^psx$|^dos$|deadspace|souls|demonssouls|^totk$|^botw$|hyrule|^mariokart|^oblivion|towerdefense|realtimestrategy|drpg|strategyrpg|roguelite|monstertrain|simracing|virtualpinball|cemu|shadps4|ps4piracy|ps4homebrew|rpcs3|remoteplay|xcloud|spiritisland|rocksmith|lego|wingspan|^chess|adventuregames|nfsu2|tabletennis|stardewvalley|spelunky|elderring|asssassinscreed|farcry|^gta|nfsmw|simcity|theme_hospital|ratchet)", "Video Games (console/PC)"),

    # Writing / creating
    (r"(selfpublish|publishing|writing|fiction|writers|gamedev|webdev|graphicnovel|illustration|drawing|animation|filmmaker|comic.?creator|songwriter|screenwriter|composer|musicproduction|edm.?producer|musicians?$|musicbusiness|guitar|letstalkmusic|hiphop|indieheads|kendrick|^rap$|billboard|spotifyplaylists|^kdp$|eroticauthor|^comics$|comixology|photoshoprequest)", "Writing & Creating"),

    # Books — SF & Fantasy specific
    (r"(scifi|sciencefiction|fantasy|litrpg|progressionfantasy|haremfantasy|printsf|cosmer|brandonsander|wheeloftime|stormlight|malazan|asoiaf|sandersonbooks|robinhobb|tolkien|lightnovel|wuxia|wuxiaworld|royalroad|^manhwa|noveltranslation|horrorlit|motheroflearning|iteration110cradle|adriantchaikovsky)", "Sci-Fi & Fantasy Books"),

    # Long-form articles
    (r"(longread|longform|essays|aldaily|theeconomist|^theatlantic$|nytimes$|theverge)", "Long-form Reading & Articles"),

    # Books / general
    (r"(books?$|audible|reading|^literature$|whatsthatbook|truelit|calibre|kindle|kobo|libraries|bookclub|romancebooks|fanfiction|booksuggestion|suggestmeabook|terriblebookcover|brontesisters|graphicnovel|manga|manhwa|tachimanga|kavitamanga|^comics$|mangapiracy|doujinshi)", "Books & Reading"),

    # Erotica / NSFW
    (r"(literotica|sexstories|gonewildstories|cartoonporn|sex.?comic|interracialwild|pornid|tipofmypenis|nsfw|hentai|rule34|gonewild|onlyfans|gw_|^joi$|long_porn|short_porn|goonvids|stupidsluts|girlskissing|realhomeporn|homemadexxx|pornvids|pornstar|^adult|clappingdem|illusionporn|chickflixxx|tightdresses|hotpast|passionx|sexynormalgirl|sneakyporn|slutsofsnapchat|pornwha|titfuck|sextoy|stripper|porn$|porngif)", "Erotica & NSFW"),

    # Non-monogamy
    (r"(polyamor|nonmonogamy|ethicalnonmonogamy|swinger|threesome|openmarriage|cuckold|hotwife|^enm$|polyadvice|theotherwoman)", "Non-monogamy"),

    # Infidelity
    (r"(infidelity|cheating|wayward|betrayed|cakeeater|adultery|affair)", "Infidelity"),

    # Marriage / divorce
    (r"(marriage|wedding|engaged|divorce|separation|fencesitter|datingoverforty|christianmarriage)", "Marriage & Divorce"),

    # Sex / intimacy
    (r"(^sex$|sexover|deadbedroom|psychologyofsex|hlcommunity|hl_women|twoxsex|indiatalkssex|tantra|^kink$|kinkster)", "Sex & Intimacy"),

    # Relationship advice
    (r"(relationship.?advice|^relationships$|^advice$|askmenadvice|datingadvice|breakups|^exno|sexlife|datingapp)", "Relationship Advice"),

    # AITA / moral judgement
    (r"(aita|amiwrong|amioverreact|whatshouldido|twohottakes|amitheasshole|moraldilemma|moralorette|trueratediscussion|whatdoido)", "AITA & Judgement"),

    # Reddit stories / best-of
    (r"(bestof|borupdates|bestofredditor|trueoffmychest|stories$|tifu$|redditonwiki|ohnoconsequence|publicfreakout|justnomil|justno|raisedbynarcissists|prorevenge|maliciouscompliance|nuclearrevenge|amitheangel|familyproblems|relationshipsover|insaneparents|entitledparents|entitledpeople|choosingbeggar|niceguys|nicegirls|^trashy$|trashtaste|lethalcompany|toxic|prematuredeath|familydrama|^drama$|^relationships$|narcissism|familyabuse|adult.?children|brokenparents|narcabuse|^overheard$|^self$|^vent$|offmychest|^confession$|redditforgrownups|redditor_updates|marknarrations|foundandexpose|bizarrelife|talesfrom|dustythunder|deepthoughts|seriousconv|shittyaskreddit|stupidquestions|^answers$|randomquestion|doesanybodyelse|morbidquestions)", "Reddit Stories & Best-Of"),

    # Demographics Q&A
    (r"(^askwomen|^askmen|askmenover|askwomenover|askold|black(men|girls|ladies)|^askindia|passportbros|twoxchromosomes|women(dating|over)|asianamerican|biwomen|^nigeria|^ghana|^china|^japan|^korea|shanghai|nairobi|returntoindia|developersindia|thegirlsurvivalguide|agingparents|over60|^sahm$|^mommit$|breakingmom|oneanddone|^europe$|^canada$|unitedkingdom|asknyc|newyorkcity|washingtondc|^maryland$|philadelphia|^florida$|^vegas$|appalachia|amerexit|askfeminists|samegrass|widowers|homeschool|saginaw|over30|over40|justgalsbeingchicks)", "Demographics Q&A"),

    # Generic Q&A
    (r"(nostupid|tooafraidtoask|^ask$|^askanything$|^ama$|^askhistorians$|askscience|outoftheloop|askphilosophy|tellmeafact|whatisthisthing|^answers$|explainlikeimfive|asksocialscience|findareddit|whatisit|askelectricians|askcarsales|askfuneraldirectors|askpsychology|askgames|^math$|mathematics|^college$|teaching|^statistics$)", "Generic Q&A"),

    # Politics / society
    (r"(askconservative|askaliberal|^conservative$|truereddit|changemyview|leopardsatemyface|natalism|politics|democrat|republican|libertarian|socialism|communism|anarchism|socialjustice|feminism|^maga$|libsoftiktok|jordanpeterson|antiwork|latestagecapitalism|socialdemocracy|policydecisions|prochoice|prolife|unpopular|^centrist$|skeptic|qanon|hermancain|votedem|whatbidenhasdone|anime_titties|theeconomist|ezraklein|^geography$|holyshithistory|geopolitics|^yimby$|^rant$|truecrime|crimepodcast)", "Politics & Society"),

    # Religion
    (r"(christian|catholic|orthodox|muslim|islam|judaism|jewish|hindu|buddhism|atheis|exmuslim|exchristian|exmormon|mormon|religioustrauma|theology|biblestudy|bible)", "Religion"),

    # TV / movies / sitcoms
    (r"(vudu|americandad|frasier|sitcom|moviecritic|^movies?$|explainafilmplot|tvshows?|televisionsuggest|netflix|hbo|primevideo|disneyplus|peacock|hulu|appletv|streaming|trailers|^tv$|breakingbad|bettercallsaul|sopranos|succession|gameofthrones|thelastofus|severance|criterion|^moviesuggestions$|movierecommend|underrated.*movies|moviequestions|whatsthemoviecalled|asiancinema|^westerns$|classicfilm|^80smovies$|^flicks$|^film$|iwatchedanold|^seinfeld$|bobsburgers|^office$|^poirot$|sesamestreet|willferrell|thedavidpakman|behindthebastards|^television$|animesuggest|doctorwho|^anime$|animations|moviereview|cinephile)", "TV, Movies & Sitcoms"),

    # Memes / random visuals (catch many of the "look at this" subs)
    (r"(holup|interestingasfuck|maybemaybemaybe|coolguides|nextfuckinglevel|wellthat|todayilearned|peoplefuckingdying|wholesomememes|memes$|dankmemes|technicallythetruth|mademesmile|^aww$|^funny$|utterlyinteresting|^interesting$|interestingtoread|unexpected|beamazed|opticalillusions|agedlikemilk|nottheonion|therewasanattempt|murderedbywords|abruptchaos|^amazing$|absoluteunits|blackmagicfuck|confusingperspective|confusing_perspective|damnthatsinteresting|oddlysatisfying|gifsthatendtoo|impressively|justgalsbeingchicks|badassanimals|animalsdoingstuff|germanshepherd|goldenretriever|^husky$|^snakes$|^pics$|^calvinandhobbes$|unethicallifeprotips|lifehacks|youshouldknow|^infographics$|^toastme$|^funfacts$|popculturechat|todayilearned|tipofmytongue|copypasta|programmerhumor|okbuddycinephile|popheadscirclejerk|sadposting|whenyouseeit|tierlists|reidditmoment|woah|whoa|^trashy$|sci_fi|peoplebeing|notinteresting|illusion|cursedimages|abandonedporn|earthporn|cityporn|villageporn|natureporn|botanicalporn|spaceporn|architectureporn|machineporn|^satisfying$|^tools$|toolgifs|spotted)", "Memes & Random Visuals"),

    # Body / fitness / appearance
    (r"(fitness|petitefitness|femalefittofat|progresspics|faceratings|plasticsurgery|outfits|bigbudgetbrides|^faces$|drawme|weight.?loss|^gym$|bodybuilding|crossfit|^yoga$|pilates|^running$|lifting|skincare|makeup|^hair$|^nails$|gainit|loseit|c25k|nutrition|caloriecounting|^cico$|emogothstyle|^fashion$|^style$|^vindicta$|lookyourbest|aginggracefully|^ootd$|trendymakeup)", "Body, Fitness & Appearance"),

    # Jokes / humor
    (r"(^jokes?$|comedy|^pun|riddle|cleverpun|onelinersfunny)", "Jokes & Humor"),
]
RULES = [(re.compile(p, re.I), t) for p, t in RULES_RAW]


def classify(sub):
    if not sub.startswith("r/"):
        return "Miscellaneous"
    name = sub[2:].lower()
    if name in EXPLICIT:
        return EXPLICIT[name]
    for rx, topic in RULES:
        if rx.search(name):
            return topic
    return "Miscellaneous"


def get_json(path):
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.loads(r.read())


def post_json(path, body):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--source-topic", default="Miscellaneous")
    ap.add_argument("--show-misc", action="store_true")
    args = ap.parse_args()

    subs = get_json(f"/api/all_subs?topic={urllib.request.quote(args.source_topic)}")["subs"]
    print(f"{len(subs)} subs in '{args.source_topic}'")

    by_topic = {}
    for s in subs:
        t = classify(s["sub"])
        by_topic.setdefault(t, []).append(s)

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
        print(f"\nStill Misc ({len(misc)}):")
        for s in sorted(misc, key=lambda s: -s["item_count"]):
            print(f"  {s['item_count']:>4}  {s['sub']}")

    if not args.apply:
        print("\n(dry run — pass --apply to POST)")
        return

    print("\napplying...")
    total = 0
    for topic, lst in by_topic.items():
        if topic == args.source_topic:
            continue  # don't re-assign back to itself
        sub_names = [s["sub"] for s in lst]
        for i in range(0, len(sub_names), 500):
            chunk = sub_names[i:i + 500]
            r = post_json("/api/assign_topic", {"subs": chunk, "topic": topic})
            total += r["assigned_count"]
        print(f"  {topic:<32} {len(sub_names):>5} subs assigned")
    print(f"\ntotal: {total}")


if __name__ == "__main__":
    main()
