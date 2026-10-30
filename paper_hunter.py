import os
import sys
import re
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAPERS_DIR = os.path.join(BASE_DIR, "RESEARCH PAPERS")
LEDGER_PATH = os.path.join(BASE_DIR, "paper_ledger.json")
PROGRESS_PATH = os.path.join(BASE_DIR, "progress.md")

os.makedirs(PAPERS_DIR, exist_ok=True)

# Import extraction engine
from main import upload_pdf_and_sync_rules

# ==========================================
# 1. LEDGER MANAGEMENT & DEDUPLICATION
# ==========================================

def load_ledger() -> Dict[str, Any]:
    if not os.path.exists(LEDGER_PATH):
        return {"version": "1.0", "extracted_papers": []}
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Could not load ledger ({e}), initializing empty.")
        return {"version": "1.0", "extracted_papers": []}

def save_ledger(ledger: Dict[str, Any]) -> None:
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text)[:100]

def normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    return " ".join(cleaned.split())

def is_already_extracted(title: str, ledger: Optional[Dict[str, Any]] = None, doi: Optional[str] = None) -> bool:
    if ledger is None:
        ledger = load_ledger()
    norm_new = normalize_title(title)
    new_words = set(norm_new.split())
    
    slug = slugify(title)
    for p in ledger.get("extracted_papers", []):
        if p.get("paper_id") == slug:
            return True
        if doi and p.get("doi") and p.get("doi").lower() == doi.lower():
            return True
        
        # Normalized substring match
        norm_existing = normalize_title(p.get("title", ""))
        if not norm_existing:
            continue
        if norm_new in norm_existing or norm_existing in norm_new:
            return True
            
        # Jaccard / word overlap match for minor phrasing/punctuation variations
        existing_words = set(norm_existing.split())
        if new_words and existing_words:
            intersection = len(new_words.intersection(existing_words))
            union = len(new_words.union(existing_words))
            jaccard = intersection / union if union > 0 else 0
            if jaccard >= 0.75:
                return True
                
    return False

# ==========================================
# 2. ACADEMIC SEARCH ENGINES
# ==========================================

def search_arxiv(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Searches arXiv for biomedical, quantitative biology, and health AI papers."""
    print(f"🔎 Querying arXiv API for: '{query}'...")
    encoded_query = urllib.parse.quote(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results={max_results * 2}"
    req = urllib.request.Request(url, headers={"User-Agent": "HealthRAG/1.0"})

    papers = []
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            xml_data = resp.read()
            tree = ET.fromstring(xml_data)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in tree.findall("atom:entry", ns):
                title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
                published = entry.find("atom:published", ns).text[:4] if entry.find("atom:published", ns) is not None else "Unknown"
                
                authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
                
                pdf_urls = [l.attrib["href"] for l in entry.findall("atom:link", ns) if l.attrib.get("title") == "pdf"]
                pdf_url = pdf_urls[0] if pdf_urls else entry.find("atom:id", ns).text.replace("abs", "pdf")
                if not pdf_url.endswith(".pdf"):
                    pdf_url += ".pdf"
                
                papers.append({
                    "title": title,
                    "authors": authors,
                    "year": published,
                    "summary": summary,
                    "source": "arXiv",
                    "doi": None,
                    "pdf_url": pdf_url
                })
    except Exception as e:
        print(f"⚠️ arXiv search notice: {e}")

    return papers

def search_europe_pmc(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Searches Europe PMC / PubMed Central open access papers."""
    print(f"🔎 Querying Europe PMC API for: '{query}'...")
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={encoded_query}&format=json&pageSize={max_results}"
    req = urllib.request.Request(url, headers={"User-Agent": "HealthRAG/1.0"})

    papers = []
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("resultList", {}).get("result", [])
            for r in results:
                title = r.get("title", "").strip().rstrip(".")
                author_str = r.get("authorString", "Unknown")
                authors = [a.strip() for a in author_str.split(",") if a.strip()]
                year = str(r.get("pubYear", "Unknown"))
                summary = r.get("abstractText", "No abstract available.")
                doi = r.get("doi")
                pmcid = r.get("pmcid")
                
                pdf_url = None
                if pmcid:
                    pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"

                papers.append({
                    "title": title,
                    "authors": authors[:5],
                    "year": year,
                    "summary": summary,
                    "source": "Europe PMC / PubMed",
                    "doi": doi,
                    "pdf_url": pdf_url
                })
    except Exception as e:
        print(f"⚠️ Europe PMC search notice: {e}")

    return papers

def fetch_candidate_papers(idea: str, max_count: int = 5) -> List[Dict[str, Any]]:
    """Fetches and deduplicates candidate research papers from academic engines."""
    ledger = load_ledger()
    arxiv_results = search_arxiv(idea, max_results=max_count)
    pmc_results = search_europe_pmc(idea, max_results=max_count)

    combined = arxiv_results + pmc_results
    candidates = []
    seen_titles = set()

    for p in combined:
        t_key = slugify(p["title"])
        if t_key in seen_titles:
            continue
        seen_titles.add(t_key)

        is_dup = is_already_extracted(p["title"], ledger, p.get("doi"))
        p["already_extracted"] = is_dup
        candidates.append(p)

    return candidates[:max_count * 2]

# ==========================================
# 3. DOWNLOAD & PIPELINE EXECUTION
# ==========================================

def download_paper_pdf(paper: Dict[str, Any]) -> Optional[str]:
    """Downloads the selected paper PDF into RESEARCH PAPERS/."""
    url = paper.get("pdf_url")
    if not url:
        print(f"❌ No direct download URL available for: {paper['title']}")
        return None

    clean_name = slugify(paper["title"])[:80] + ".pdf"
    target_path = os.path.join(PAPERS_DIR, clean_name)

    if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
        print(f"📄 Paper already downloaded locally at: {target_path}")
        return target_path

    print(f"⬇️ Downloading PDF from {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            if not content.startswith(b"%PDF") and b"%PDF" in content[:1024]:
                idx = content.find(b"%PDF")
                content = content[idx:]
            
            with open(target_path, "wb") as f:
                f.write(content)
        
        print(f"✅ Downloaded successfully ({len(content)/1024:.1f} KB): {clean_name}")
        return target_path
    except Exception as e:
        print(f"❌ Failed to download PDF ({e}).")
        return None

def update_progress_md(paper_title: str, rules_added: int, total_vectors: int) -> None:
    """Updates progress.md according to Rule 1 of AGENT_RULES.md."""
    if not os.path.exists(PROGRESS_PATH):
        return
    try:
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        # Update Vector Count line
        content = re.sub(
            r"- \*\*Current Vector Count\*\*: \d+",
            f"- **Current Vector Count**: {total_vectors}",
            content
        )

        # Append to Ingested Literature list
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n  - *{paper_title}* (Ingested {date_str}, +{rules_added} rules, total: {total_vectors})"
        if "## 📚 Ingested Literature & Vector Index State" in content:
            parts = content.split("## 🕒 Recent Session Log")
            updated_content = parts[0].rstrip() + new_entry + "\n\n## 🕒 Recent Session Log" + parts[1]
            with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
                f.write(updated_content)
        print("📝 Updated progress.md context successfully!")
    except Exception as e:
        print(f"⚠️ Notice: could not update progress.md ({e})")

# ==========================================
# 4. INTERACTIVE USER WORKFLOW
# ==========================================

def run_interactive_pipeline():
    print("\n" + "="*80)
    print("🧬 AUTOMATED RESEARCH PAPER HUNTER & CLINICAL EXTRACTION PIPELINE")
    print("="*80)

    idea = input("\n💡 Enter your health / lifestyle research idea: ").strip()
    if not idea:
        print("⚠️ No idea provided. Exiting.")
        return

    count_str = input("📊 How many research papers to fetch? (default: 5): ").strip()
    count = int(count_str) if count_str.isdigit() and int(count_str) > 0 else 5

    print(f"\n🔍 Searching for peer-reviewed papers matching: '{idea}'...")
    candidates = fetch_candidate_papers(idea, max_count=count)

    if not candidates:
        print("❌ No matching research papers found. Try broader keywords.")
        return

    print("\n" + "="*80)
    print(f"📚 CANDIDATE RESEARCH PAPERS FOUND ({len(candidates)} papers)")
    print("="*80)

    valid_options = []
    for i, p in enumerate(candidates):
        num = i + 1
        authors_display = ", ".join(p['authors'][:3]) if p['authors'] else "Unknown"
        status_tag = "🔴 [ALREADY INGESTED]" if p['already_extracted'] else "🟢 [NEW]"
        
        print(f"\n[{num}] {p['title']}")
        print(f"    👤 Authors: {authors_display} ({p['year']}) | 🏛️ Source: {p['source']} {status_tag}")
        summary_preview = (p['summary'][:200] + "...") if len(p['summary']) > 200 else p['summary']
        print(f"    📝 Summary: {summary_preview}")
        if p.get("pdf_url"):
            print(f"    🔗 PDF Link: {p['pdf_url']}")
        
        if not p['already_extracted'] and p.get("pdf_url"):
            valid_options.append(num)

    if not valid_options:
        print("\nℹ️ All retrieved papers have already been extracted into your local vector database!")
        return

    print("\n" + "-"*80)
    print(f"Available new papers for extraction: {valid_options}")
    choice = input("👉 Enter paper number(s) to extract (e.g. '1', '1,2', or 'all' / 'q' to quit): ").strip().lower()

    if choice in ["q", "quit", "exit"]:
        print("Exiting pipeline.")
        return

    selected_indices = []
    if choice == "all":
        selected_indices = valid_options
    else:
        for item in choice.split(","):
            item = item.strip()
            if item.isdigit() and int(item) in valid_options:
                selected_indices.append(int(item))

    if not selected_indices:
        print("⚠️ No valid new papers selected. Exiting.")
        return

    ledger = load_ledger()
    for idx in selected_indices:
        paper = candidates[idx - 1]
        print("\n" + "="*80)
        print(f"🚀 PROCESSING PAPER [{idx}]: {paper['title']}")
        print("="*80)

        # 1. Download PDF
        pdf_path = download_paper_pdf(paper)
        if not pdf_path:
            continue

        # 2. Extract rules via Colab
        result = upload_pdf_and_sync_rules(pdf_path)
        if result.get("status") == "success":
            rules_added = result.get("rules_added", 0)
            total_vecs = result.get("total_vectors", 0)
            
            # 3. Update Ledger
            paper_entry = {
                "paper_id": slugify(paper["title"]),
                "title": paper["title"],
                "authors": ", ".join(paper["authors"]),
                "year": paper["year"],
                "doi": paper.get("doi"),
                "source_pdf": os.path.basename(pdf_path),
                "rules_count": rules_added,
                "date_added": datetime.now().isoformat()
            }
            ledger["extracted_papers"].append(paper_entry)
            save_ledger(ledger)
            print(f"📖 Recorded paper in paper_ledger.json (+{rules_added} rules).")

            # 4. Update progress.md
            update_progress_md(paper["title"], rules_added, total_vecs)

    print("\n🎉 All selected papers processed and indexed into your local FAISS vector database!")

if __name__ == "__main__":
    run_interactive_pipeline()
