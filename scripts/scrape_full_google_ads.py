import asyncio
import json
import sys
from playwright.async_api import async_playwright

async def main():
    target_domain = sys.argv[1] if len(sys.argv) > 1 else "binize.com"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"Loading Google Ads Transparency for {target_domain}...")
        await page.goto(f"https://adstransparency.google.com/?region=anywhere&domain={target_domain}", wait_until="networkidle", timeout=30000)
        
        btn = page.get_by_text("See all ads")
        if await btn.count() > 0:
            print("Clicking 'See all ads'...")
            await btn.first.click()
            await page.wait_for_timeout(4000)
            
            # Scroll down to load all items
            for _ in range(6):
                await page.mouse.wheel(0, 5000)
                await page.wait_for_timeout(1500)
            
            cards_data = await page.evaluate('''() => {
                const list = [];
                const cards = document.querySelectorAll("creative-preview");
                cards.forEach(card => {
                    const text = card.innerText || "";
                    const lines = text.split("\\n").map(l => l.trim()).filter(Boolean);
                    const a = card.closest("a") || card.querySelector("a");
                    const link = a ? a.href : "";
                    const img = card.querySelector("img") ? card.querySelector("img").src : null;
                    list.push({ lines, link, img });
                });
                return list;
            }''')
            
            print(f"Captured {len(cards_data)} total cards!")
            
            advs = {}
            for c in cards_data:
                name = c["lines"][0] if c["lines"] else "Unknown"
                if name.lower() == "videocam":
                    name = "TKTX"
                if name not in advs:
                    advs[name] = {
                        "name": name,
                        "ad_count": 0,
                        "link": c["link"],
                        "has_img": bool(c["img"]),
                        "img_url": c["img"]
                    }
                advs[name]["ad_count"] += 1
                if not advs[name]["link"] and c["link"]:
                    advs[name]["link"] = c["link"]
            
            results = list(advs.values())
            print(f"Discovered {len(results)} distinct advertisers:")
            for idx, r in enumerate(results, 1):
                print(f"{idx}. {r['name']} - {r['ad_count']} ads | {r['link']}")
                
            fname = f"data/scraped_advertisers_{target_domain.replace('.', '_')}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"Saved results to {fname}!")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
