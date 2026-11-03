"""Source registry for harvest job B (modern everyday how-to pages). Each source: sitemaps or crawl seeds, URL filter, cap,
default domain, platform. Hosts deliberately NOT used (and why) are listed in SKIPPED."""
import re
D_TECH, D_AI, D_SOC, D_RENT, D_MKT, D_SHOP, D_DIG = ("howto.tech_phone", "howto.ai_tools", "howto.social_creator",
    "howto.rental", "howto.marketplace", "howto.shopping_returns", "howto.digital_life")
DOMAINS = [D_TECH, D_AI, D_SOC, D_RENT, D_MKT, D_SHOP, D_DIG]
SOURCES = [
 # name, host, sitemaps, crawl seeds, include regex, cap, default domain, platform
 dict(name="learnfree", classify=True, sitemaps=["https://edu.gcfglobal.org/sitemap.xml"], crawl=r"https://learnfree\.org/series/[a-z0-9-]+/[a-z0-9-]+$",
      include=r"learnfree\.org/series/(?!.*(algebra|fraction|decimal|percent|grammar|addition|multiplication|statistics|interview|resume|cover-letter|career|job|workplace|writing|communication|excel|word|powerpoint|access|teams|outlook|prezi|photoshop|graphic|html|css|math))", cap=900, domain=D_TECH, platform="web"),
 dict(name="ftc", classify=True, sitemaps=["https://consumer.ftc.gov/sitemap.xml"], include=r"consumer\.ftc\.gov/(consumer-alerts/20(2[3-6])|articles/)", cap=700, domain=D_SHOP, platform="web"),
 dict(name="cfpb", classify=True, sitemaps=["https://www.consumerfinance.gov/sitemap.xml"], include=r"consumerfinance\.gov/(ask-cfpb/[^/]+-en-\d+|consumer-tools/[a-z-]+/(answers/)?[a-z-]+/?$|about-us/blog/[a-z0-9-]+/?$)", cap=700, domain=D_DIG, platform="web"),
 dict(name="usagov", classify=True, sitemaps=["https://www.usa.gov/sitemap.xml"], include=r"usa\.gov/(?!es/)[a-z0-9-]+$", cap=250, domain=D_DIG, platform="web"),
 dict(name="cisa", classify=True, sitemaps=["https://www.cisa.gov/sitemap.xml"], include=r"cisa\.gov/(secure-our-world|resources-tools/resources/[a-z0-9-]*(secure|password|phish|mfa|multifactor|update|scam|online|tips)[a-z0-9-]*|news-events/news/[a-z0-9-]*(tips|secure|password|phish|mfa|scam)[a-z0-9-]*)", cap=200, domain=D_DIG, platform="web"),
 dict(name="offerup", sitemaps=["https://help.offerup.com/hc/sitemap.xml"], include=r"/hc/en-us/articles/", cap=200, domain=D_MKT, platform="offerup"),
 dict(name="mercari", sitemaps=[], seeds=["https://www.mercari.com/us/help_center/"], crawl=r"https://www\.mercari\.com/us/help_center/(article/\d+|topics/[a-z0-9/-]+)$", include=r"mercari\.com/us/help_center/", cap=250, domain=D_MKT, platform="mercari"),
 dict(name="discord", sitemaps=["https://support.discord.com/hc/sitemap.xml"], include=r"/hc/en-us/articles/", cap=400, domain=D_SOC, platform="discord"),
 dict(name="snapchat", sitemaps=["https://help.snapchat.com/hc/sitemap.xml"], include=r"/hc/en-us/articles/", cap=300, domain=D_SOC, platform="snapchat"),
 dict(name="reddit", sitemaps=["https://www.reddithelp.com/hc/sitemap.xml"], include=r"/hc/en-us/articles/", cap=300, domain=D_SOC, platform="reddit"),
 dict(name="signal", sitemaps=["https://support.signal.org/hc/sitemap.xml"], include=r"/hc/en-us/articles/", cap=250, domain=D_TECH, platform="signal"),
 dict(name="cashapp", sitemaps=["https://cash.app/help-sitemap.xml"], include=r"cash\.app/help/(us/en-us/)?\d+", cap=350, domain=D_DIG, platform="cash_app"),
 dict(name="zelle", sitemaps=["https://www.zellepay.com/sitemap.xml"], include=r"zelle(pay)?\.com/(faq|get-started|safety|how-it-works|pay-it-safe|[a-z-]*(scam|safe|send|request|enroll)[a-z-]*)", cap=80, domain=D_DIG, platform="zelle"),
 dict(name="bitwarden", sitemaps=["https://bitwarden.com/sitemap.xml"], include=r"bitwarden\.com/help/[a-z0-9-]+/?$", cap=350, domain=D_DIG, platform="bitwarden"),
 dict(name="onepassword", sitemaps=["https://support.1password.com/sitemap.xml"], include=r"support\.1password\.com/(?!(de|es|fr|it|ja|ko|nl|pt-br|ru|zh-cn|zh-tw)/)[a-z0-9-]+/?$", cap=300, domain=D_DIG, platform="1password"),
 dict(name="dropbox", sitemaps=["https://help.dropbox.com/sitemap.xml"], include=r"help\.dropbox\.com/(?!(de-de|es-es|es-la|fr-fr|it-it|ja-jp|ko-kr|pt-br|ru-ru|zh-cn|zh-tw|id-id|ms-my|pl-pl|sv-se|th-th|uk-ua|nb-no|da-dk|nl-nl)/)[a-z-]+/[a-z0-9-]+$", cap=350, domain=D_TECH, platform="dropbox"),
 dict(name="apartmentlist", sitemaps=["https://www.apartmentlist.com/sitemap.xml"], include=r"apartmentlist\.com/renter-life/[a-z0-9-]+$", cap=350, domain=D_RENT, platform="web"),
 dict(name="rentcafe", sitemaps=["https://www.rentcafe.com/sitemap/sitemap.xml"], include=r"rentcafe\.com/blog/(apartment-search|renting|apartment-living|moving)[a-z0-9/-]*", cap=250, domain=D_RENT, platform="web"),
 dict(name="hud", sitemaps=[], seeds=["https://www.hud.gov/topics/rental_assistance", "https://www.hud.gov/topics/rental_assistance/tenantrights", "https://www.hud.gov/states/shared/working/r10/tenantrights"], crawl=r"https://www\.hud\.gov/(topics|helping-americans)/[a-z_/-]*(rent|tenant|lease|housing)[a-z_/-]*$", include=r"hud\.gov/", cap=60, domain=D_RENT, platform="web"),
 # --- added after first pass (more AI-tool / creator / security / shopping guide coverage) ---
 dict(name="zapier", sitemaps=["https://zapier.com/blog/sitemap.xml"], include=r"zapier\.com/blog/[a-z0-9-]*(chatgpt|ai-|-ai|claude|gemini|copilot|perplexity|midjourney|prompt|notebooklm|llm|gpt)[a-z0-9-]*/?$", cap=300, domain=D_AI, platform="web"),
 dict(name="grammarly", sitemaps=["https://www.grammarly.com/blog/sitemap_index.xml"], include=r"grammarly\.com/blog/(ai|[a-z0-9-]*(chatgpt|ai-|prompt|gemini|claude|copilot))[a-z0-9/-]*$", cap=150, domain=D_AI, platform="web"),
 dict(name="buffer", sitemaps=["https://buffer.com/sitemap.xml"], include=r"buffer\.com/resources/[a-z0-9-]*(how|guide|tips|instagram|tiktok|youtube|reels|shorts|creator|monetiz|grow|post|schedule|threads|linkedin|pinterest)[a-z0-9-]*/?$", cap=300, domain=D_SOC, platform="web"),
 dict(name="later", sitemaps=["https://later.com/sitemap.xml"], include=r"later\.com/blog/[a-z0-9-]*(how|guide|tips|instagram|tiktok|youtube|reels|creator|monetiz|grow|post|schedule|brand-deal|link-in-bio)[a-z0-9-]*/?$", cap=250, domain=D_SOC, platform="web"),
 dict(name="hootsuite", sitemaps=["https://blog.hootsuite.com/sitemap_index.xml"], include=r"blog\.hootsuite\.com/[a-z0-9-]*(how-to|guide|tips|instagram|tiktok|youtube|reels|creator|monetiz|grow)[a-z0-9-]*/?$", cap=250, domain=D_SOC, platform="web"),
 dict(name="staysafeonline", sitemaps=["https://www.staysafeonline.org/sitemap.xml"], include=r"staysafeonline\.org/(articles|resources)/[a-z0-9-]+/?$", cap=200, domain=D_DIG, platform="web"),
 dict(name="nerdwallet", classify=True, sitemaps=["https://www.nerdwallet.com/sitemaps/us/wp-sitemap.xml"], include=r"nerdwallet\.com/article/(banking|finance|shopping)/[a-z0-9-]*(how|app|zelle|venmo|paypal|cash-app|return|refund|scam|fraud|deposit|rent|online|transfer|pay)[a-z0-9-]*/?$", cap=250, domain=D_DIG, platform="web"),
 dict(name="aarp", classify=True, sitemaps=["https://www.aarp.org/sitemap.xml"], include=r"aarp\.org/(personal-technology|home-family/personal-technology|money/scams-fraud)/[a-z0-9/-]*(how|tips|set|use|protect|secure|phone|password|app|ai|chatgpt)[a-z0-9/-]*", cap=250, domain=D_TECH, platform="web"),
 dict(name="bbb", classify=True, sitemaps=["https://www.bbb.org/sitemap-articles-index.xml"], include=r"bbb\.org/(us/)?article/(news-releases|scams|tips|consumer|investigations)[a-z0-9/-]*(tip|how|scam|shop|online|rent|marketplace|return|refund|buy|sell|gift|delivery|package|payment|account)[a-z0-9/-]*", cap=300, domain=D_SHOP, platform="web"),
 dict(name="apartmenttherapy", sitemaps=["https://www.apartmenttherapy.com/sitemap.xml"], include=r"apartmenttherapy\.com/[a-z0-9-]*(renter|renting|apartment-hunt|apartment-search|lease|landlord|security-deposit|rental-application|tour|viewing)[a-z0-9-]*-\d+$", cap=150, domain=D_RENT, platform="web"),
]
SKIPPED = {
 "www.wikihow.com": "robots.txt NOTICE prohibits use 'for training or retrieval for AI models or similar machine learning systems' without a licence; NYCH abstraction for a KG is close enough that we did not crawl",
 "help.chime.com": "Content-signal ai-train=no; skipped conservatively",
 "www.techboomers.com": "Cloudflare content-signal block in robots.txt; skipped conservatively",
 "www.rentcafe.com": "sitemap returned HTTP 403 to our UA; not crawled",
 "learnfree.org (GCFGlobal)": "fetched 60 series pages, but lesson text is client-side rendered (no steps in HTML; old edu.gcfglobal.org lesson URLs 404); 0 actions",
 "www.digitallearn.org": "courses are video-based; not crawled",
 "www.vinted.com": "Content-Signal ai-train=no; skipped",
 "help.offerup.com": "Zendesk articles returned HTTP 403 to our UA (bot block) after 4 pages; stopped",
 "buffer.com": "sitemap lists no individual resources posts (JS-paginated index); 1 page only",
 "www.apartments.com": "robots.txt 403 (bot block)",
 "help.depop.com": "robots.txt 403 (bot block)",
 "www.apartmentguide.com": "robots.txt 429",
 "www.howtogeek.com/www.lifewire.com": "commercial publishers whose robots.txt block AI crawlers; not used",
 "facebook/craigslist/ebay": "forbidden by brief (listings) and robots",
 "job A hosts": "Apple, Google/Android/YouTube help, Meta help, AI-tool help docs, creator-platform help centres: not used (job A)",
}
KW = [  # (domain, regex on url+title) first match wins
 (D_AI, r"\b(ai|chatgpt|copilot|gemini|claude|prompt|generative|chatbot|artificial intelligence)\b|-ai-|/ai-"),
 (D_RENT, r"\b(rent|renter|renting|rental|tenant|lease|landlord|apartment|security deposit|eviction|roommate|moving)\b"),
 (D_MKT, r"\b(marketplace|offerup|mercari|poshmark|sell(ing)? (online|used)|buyer|seller|listing|meetup|resell|secondhand)\b"),
 (D_SOC, r"\b(social media|youtube|tiktok|instagram|facebook|snapchat|discord|reddit|creator|influencer|followers|livestream|podcast|subreddit|server)\b"),
 (D_SHOP, r"\b(shop(ping)?|return(s|ing)?|refund|purchase|order|delivery|package|warrant(y|ies)|chargeback|gift card|subscription|cancel)\b"),
 (D_DIG, r"\b(bank(ing)?|payment|pay|money|password|2fa|two-factor|multi-?factor|mfa|passkey|scam|fraud|identity|phishing|security|credit|debit|account|zelle|cash app|venmo|paypal|privacy|hack)"),
 (D_TECH, r"\b(phone|smartphone|android|iphone|ipad|tablet|app|computer|laptop|wi-?fi|bluetooth|browser|email|file|cloud|update|settings|chromebook|windows|mac)\b"),
]
def classify(url, title, default):
    s = (url.replace("-", " ").replace("_", " ") + " " + (title or "")).lower()
    for d, rx in KW:
        if re.search(rx, s): return d
    return default
