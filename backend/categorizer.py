"""
categorizer.py - Intelligent Multi-Category Store Classifier & Nuanced 18+ Detector.
Zero heavy dependencies, blazing fast (<1ms per store), rule-based NLP.
"""

import re
import html
from typing import Dict, List, Tuple, Any

# ==============================================================================
# CATEGORY VOCABULARY & WEIGHTS
# ==============================================================================

CATEGORY_RULES = {
    "Beauty & Skincare": {
        "strong": [
            "skincare", "serum", "acne", "anti-aging", "wrinkle", "moisturizer", 
            "cleanser", "toner", "face mask", "sunscreen", "cosmetics", "makeup", 
            "lipstick", "foundation", "eyelash", "botox", "dermatology", "retinol", 
            "hyaluronic", "collagen cream", "glow skin", "blemish"
        ],
        "medium": [
            "beauty", "lotion", "balm", "facial", "pores", "skin", "complexion", 
            "pigmentation", "scrub", "eyeshadow", "perfume", "fragrance"
        ]
    },
    "Health & Supplements": {
        "strong": [
            "supplement", "supplements", "vitamin", "vitamins", "dietary supplement", 
            "protein powder", "creatine", "collagen peptide", "gummies", "multivitamin", 
            "nattokinase", "nootropic", "cbd", "magnesium", "probiotic", "omega 3", 
            "herbal extract", "gut health", "immunity boost", "weight loss pill"
        ],
        "medium": [
            "nutrition", "wellness", "health", "healthy", "detox", "herbs", 
            "capsules", "powders", "superfood", "organic nutrition", "energy boost"
        ]
    },
    "Sexual Wellness & Care": {
        "strong": [
            "condom", "condoms", "lubricant", "lube", "intimate wash", "intimate care", 
            "kegel", "pelvic floor", "fertility", "ovulation", "reproductive health", 
            "libido booster", "menstrual cup", "tampons", "period care", "sexual wellness"
        ],
        "medium": [
            "intimate", "sensual oil", "pleasure gel", "sensual massage", "vaginal health"
        ]
    },
    "Adult 18+ (Hardcore)": {
        "strong": [
            "sex doll", "sexdoll", "sex dolls", "dildo", "dildos", "vibrator", "vibrators", 
            "sex toy", "sextoy", "sex toys", "sextoys", "bdsm", "bondage", "fetish", 
            "hentai", "xxx", "porn", "clit suction", "pocket pussy", "masturbator", 
            "anal plug", "erotic lingerie", "adult toy", "adult shop"
        ],
        "medium": [
            "erotic", "nude", "kinky", "adult entertainment", "bedroom pleasures"
        ]
    },
    "Fashion & Apparel": {
        "strong": [
            "clothing", "apparel", "dress", "dresses", "t-shirt", "hoodie", "jeans", 
            "pants", "swimwear", "bikini", "lingerie", "activewear", "footwear", 
            "sneakers", "boots", "jacket", "outerwear", "streetwear"
        ],
        "medium": [
            "fashion", "style", "wear", "outfit", "boutique", "shoes", "socks", 
            "scarf", "hat", "cap"
        ]
    },
    "Jewelry & Luxury": {
        "strong": [
            "jewelry", "jewellery", "necklace", "ring", "rings", "earrings", 
            "bracelet", "bracelets", "diamond", "diamonds", "sterling silver", 
            "14k gold", "18k gold", "gemstone", "moissanite", "watches", "luxury watch"
        ],
        "medium": [
            "gold", "silver", "pendant", "charm", "bangle", "brooch", "timepiece"
        ]
    },
    "Fitness & Sports": {
        "strong": [
            "gym equipment", "workout gear", "yoga mat", "dumbbells", "resistance bands", 
            "activewear", "fitness tracker", "running shoes", "pilates", "crossfit", 
            "bodybuilding", "exercise bike"
        ],
        "medium": [
            "fitness", "workout", "athletic", "exercise", "training", "sports", 
            "cycling", "running"
        ]
    },
    "Pet Supplies": {
        "strong": [
            "dog food", "cat food", "pet supplies", "dog collar", "dog harness", 
            "pet bed", "dog toys", "cat tree", "puppy", "kitten", "veterinary", 
            "pet grooming", "flea tick"
        ],
        "medium": [
            "dog", "cat", "pet", "pets", "canine", "feline", "aquarium"
        ]
    },
    "Home & Kitchen": {
        "strong": [
            "cookware", "kitchenware", "furniture", "bedding", "mattress", 
            "home decor", "candle", "lighting", "coffee maker", "sofa", "blender"
        ],
        "medium": [
            "kitchen", "home", "dining", "bedroom", "bathroom", "decor", 
            "interior", "living room", "patio", "garden"
        ]
    },
    "Tech & Gadgets": {
        "strong": [
            "smartphone", "charger", "wireless earbuds", "headphones", "smart watch", 
            "drone", "gaming setup", "pc accessories", "dash cam", "power bank", 
            "bluetooth speaker"
        ],
        "medium": [
            "electronics", "tech", "gadget", "gadgets", "cables", "usb", 
            "audio", "digital"
        ]
    },
    "Food & Beverage": {
        "strong": [
            "coffee beans", "espresso", "matcha", "loose leaf tea", "gourmet snacks", 
            "organic honey", "hot sauce", "artisan chocolate", "spices"
        ],
        "medium": [
            "coffee", "tea", "food", "snacks", "drinks", "beverage", "sweets"
        ]
    },
    "Education & Digital": {
        "strong": [
            "online course", "masterclass", "ebook", "digital download", "templates", 
            "coaching program", "academy", "training course"
        ],
        "medium": [
            "course", "learn", "skills", "tutoring", "education", "software"
        ]
    }
}


def extract_meta_tags(html_text: str) -> Tuple[str, str, str]:
    """Extract title, meta description, and meta keywords from HTML."""
    if not html_text:
        return "", "", ""

    # Unescape HTML entities
    raw = html.unescape(html_text)

    # 1. Title
    title = ""
    title_m = re.search(r'<title[^>]*>(.*?)</title>', raw, re.IGNORECASE | re.DOTALL)
    if title_m:
        title = re.sub(r'\s+', ' ', title_m.group(1)).strip()

    # 2. Meta description (try name="description" and property="og:description")
    desc = ""
    desc_m = re.search(
        r'<meta[^>]+(?:name=[\"\']description[\"\']|property=[\"\']og:description[\"\'])[^>]+content=[\"\']([^\"\']+)[\"\']', 
        raw, 
        re.IGNORECASE
    )
    if not desc_m:
        desc_m = re.search(
            r'<meta[^>]+content=[\"\']([^\"\']+)[\"\'][^>]+(?:name=[\"\']description[\"\']|property=[\"\']og:description[\"\'])', 
            raw, 
            re.IGNORECASE
        )
    if desc_m:
        desc = re.sub(r'\s+', ' ', desc_m.group(1)).strip()

    # 3. Meta keywords
    keywords = ""
    kw_m = re.search(r'<meta[^>]+name=[\"\']keywords[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', raw, re.IGNORECASE)
    if kw_m:
        keywords = re.sub(r'\s+', ' ', kw_m.group(1)).strip()

    return title, desc, keywords


def classify_store(
    title: str = "", 
    description: str = "", 
    keywords: str = "", 
    name: str = "", 
    url: str = ""
) -> Dict[str, Any]:
    """
    Intelligently classifies an e-commerce store into single or multi-category tags.
    Handles hybrid stores (e.g. Acne Serum + Supplements -> Beauty & Skincare + Health & Supplements).
    Carefully distinguishes Sexual Wellness from Hardcore Adult 18+.
    """
    text_title = (title or "").lower()
    text_desc = (description or "").lower()
    text_kw = (keywords or "").lower()
    text_name = (name or "").lower()
    text_url = (url or "").lower()

    # Scores per category
    scores: Dict[str, int] = {cat: 0 for cat in CATEGORY_RULES}

    for cat, rule in CATEGORY_RULES.items():
        # Strong keywords
        for word in rule["strong"]:
            pattern = r'\b' + re.escape(word) + r'\b'
            # Title has highest weight (30 pts per match)
            if re.search(pattern, text_title):
                scores[cat] += 30
            # Name has high weight (25 pts)
            if re.search(pattern, text_name) or re.search(pattern, text_url):
                scores[cat] += 25
            # Description has medium weight (20 pts)
            if re.search(pattern, text_desc):
                scores[cat] += 20
            # Keywords have weight (15 pts)
            if re.search(pattern, text_kw):
                scores[cat] += 15

        # Medium keywords
        for word in rule["medium"]:
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, text_title):
                scores[cat] += 12
            if re.search(pattern, text_name):
                scores[cat] += 10
            if re.search(pattern, text_desc):
                scores[cat] += 8
            if re.search(pattern, text_kw):
                scores[cat] += 5

    # Determine 18+ status
    is_adult = 0
    if scores["Adult 18+ (Hardcore)"] >= 25:
        # Check if it's purely adult
        is_adult = 1

    # Filter categories with significant score (threshold >= 25)
    matched_cats = [cat for cat, score in scores.items() if score >= 25]

    # Sort matched categories by score descending
    matched_cats.sort(key=lambda c: scores[c], reverse=True)

    # Edge case: Sexual Wellness should NOT be labeled as Adult 18+
    # unless hardcore keywords are dominating
    if "Sexual Wellness & Care" in matched_cats and scores["Sexual Wellness & Care"] >= scores["Adult 18+ (Hardcore)"]:
        is_adult = 0
        if "Adult 18+ (Hardcore)" in matched_cats:
            matched_cats.remove("Adult 18+ (Hardcore)")

    # Special Multi-Niche Synthesis:
    # E.g. Beauty & Skincare + Health & Supplements
    has_beauty = "Beauty & Skincare" in matched_cats
    has_supplements = "Health & Supplements" in matched_cats
    has_sexual_wellness = "Sexual Wellness & Care" in matched_cats
    has_adult = "Adult 18+ (Hardcore)" in matched_cats

    if is_adult == 1:
        primary_category = "Adult 18+"
        categories = ["Adult 18+"]
    elif has_beauty and has_supplements:
        # User's exact scenario: Serum mụn + TPCN
        primary_category = "Beauty & Health"
        categories = ["Beauty & Skincare", "Health & Supplements"]
    elif has_sexual_wellness:
        primary_category = "Health & Personal Care"
        categories = ["Sexual Wellness & Care", "Health & Supplements"] if has_supplements else ["Sexual Wellness & Care"]
    elif len(matched_cats) > 0:
        primary_category = matched_cats[0]
        # Keep top 2-3 tags
        categories = matched_cats[:3]
    else:
        primary_category = "General"
        categories = ["General"]

    # Clean site description
    clean_desc = (description or "").strip()
    if not clean_desc and title:
        clean_desc = title.strip()

    return {
        "primary_category": primary_category,
        "categories": categories,
        "is_adult": is_adult,
        "site_title": (title or "").strip(),
        "site_description": clean_desc,
        "scores": {k: v for k, v in scores.items() if v > 0}
    }
