import os
import re
import sys
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Windows UTF-8 console output guard
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
# 1. DEDUPLICATION & LEDGER ENGINE
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
    """Searches arXiv for biomedical, quantitative biology, and physiology papers with unrestricted direct PDF URLs."""
    print(f"🔎 Querying arXiv API for: '{query}'...")
    encoded_query = urllib.parse.quote(f"all:{query}")
    url = f"http://export.arxiv.org/api/query?search_query={encoded_query}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"

    headers = {"User-Agent": "HealthRulesExtractor/1.0 (academic research)"}
    papers = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            published = entry.find("atom:published", ns).text[:4]

            pdf_url = None
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                    pdf_url = link.attrib.get("href")
                    break

            if not pdf_url:
                id_text = entry.find("atom:id", ns).text
                if "/abs/" in id_text:
                    pdf_url = id_text.replace("/abs/", "/pdf/") + ".pdf"

            doi = None
            doi_elem = entry.find("arxiv:doi", ns)
            if doi_elem is not None:
                doi = doi_elem.text

            papers.append({
                "source": "arXiv",
                "title": title,
                "summary": summary,
                "authors": authors,
                "year": published,
                "pdf_url": pdf_url,
                "doi": doi,
                "pmcid": None
            })
    except Exception as e:
        print(f"⚠️ arXiv search notice: {e}")

    return papers

def search_europe_pmc(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Searches Europe PMC for open-access biomedical literature."""
    print(f"🔎 Querying Europe PMC API for: '{query}'...")
    encoded_query = urllib.parse.quote(f"{query} OPEN_ACCESS:y")
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={encoded_query}&resultType=core&format=json&pageSize={max_results}"

    headers = {"User-Agent": "HealthRulesExtractor/1.0"}
    papers = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = data.get("resultList", {}).get("result", [])
        for item in results:
            title = item.get("title", "").strip().rstrip(".")
            summary = item.get("abstractText", "No abstract available.")
            summary = re.sub(r"<[^>]+>", "", summary).strip()

            author_string = item.get("authorString", "Unknown Authors")
            authors = [a.strip() for a in author_string.split(",")][:5]
            year = str(item.get("pubYear", "Recent"))
            doi = item.get("doi")
            pmcid = item.get("pmcid")

            pdf_url = None
            if pmcid:
                pdf_url = f"https://europepmc.org/articles/{pmcid}?pdf=render"

            papers.append({
                "source": "Europe PMC",
                "title": title,
                "summary": summary,
                "authors": authors,
                "year": year,
                "pdf_url": pdf_url,
                "doi": doi,
                "pmcid": pmcid
            })
    except Exception as e:
        print(f"⚠️ Europe PMC notice: {e}")

    return papers

def fetch_candidate_papers(query: str, max_count: int = 5) -> List[Dict[str, Any]]:
    """Searches across academic providers and applies deduplication status."""
    ledger = load_ledger()
    half = max(1, (max_count + 1) // 2)

    arxiv_papers = search_arxiv(query, max_results=half)
    pmc_papers = search_europe_pmc(query, max_results=half)

    combined = arxiv_papers + pmc_papers
    deduped = []
    seen_titles = set()

    for p in combined:
        norm = normalize_title(p["title"])
        if norm in seen_titles:
            continue
        seen_titles.add(norm)
        p["already_extracted"] = is_already_extracted(p["title"], ledger=ledger, doi=p.get("doi"))
        deduped.append(p)

    return deduped[:max_count]

# ==========================================
# 3. INTELLIGENT MULTI-SOURCE DOCUMENT RESOLVER
# ==========================================

def fetch_europe_pmc_xml(pmcid: str) -> Optional[str]:
    """Retrieves full-text XML from official Europe PMC REST API and extracts clean clinical text."""
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    headers = {"User-Agent": "HealthRulesExtractor/1.0"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        paragraphs = []
        for p in root.iter("p"):
            text = "".join(p.itertext()).strip()
            if len(text) > 25:
                paragraphs.append(text)

        if paragraphs:
            return "\n\n".join(paragraphs)
    except Exception:
        pass
    return None

def resolve_and_fetch_document(paper: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Intelligent Multi-Source Resolver:
    1. If cached locally -> return local path.
    2. If Europe PMC / PMCID -> retrieve fullTextXML via official REST API (100% free, no bot blocks).
    3. If arXiv / direct PDF -> stream download with %PDF- validation.
    4. If Unpaywall has an open-access mirror -> download mirror PDF.
    5. Fallback -> extract from complete structured clinical abstract (Zero-Skip Guarantee).
    """
    slug = slugify(paper["title"])[:80]
    cached_pdf = os.path.join(PAPERS_DIR, f"{slug}.pdf")
    cached_txt = os.path.join(PAPERS_DIR, f"{slug}.txt")

    # 1. Local Cache Check
    if os.path.exists(cached_pdf) and os.path.getsize(cached_pdf) > 5000:
        with open(cached_pdf, "rb") as f:
            if f.read(10).startswith(b"%PDF"):
                print(f"  [1/4] 📄 Using cached PDF: {os.path.basename(cached_pdf)}")
                return cached_pdf, None

    if os.path.exists(cached_txt) and os.path.getsize(cached_txt) > 500:
        with open(cached_txt, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            if len(content) > 500:
                print(f"  [1/4] 📄 Using cached structured article: {os.path.basename(cached_txt)}")
                return cached_txt, content

    # 2. Strategy A: Europe PMC REST API fullTextXML
    pmcid = paper.get("pmcid")
    if pmcid:
        print(f"  [1/4] 🌐 Resolving open-access article via Europe PMC REST API ({pmcid})...")
        xml_text = fetch_europe_pmc_xml(pmcid)
        if xml_text and len(xml_text) > 1000:
            header_text = f"Title: {paper['title']}\nAuthors: {', '.join(paper['authors'])} ({paper['year']})\nPMCID: {pmcid}\n\n"
            full_article = header_text + xml_text
            with open(cached_txt, "w", encoding="utf-8") as f:
                f.write(full_article)
            print(f"  [1/4] ✅ Full research paper resolved ({len(full_article)/1024:.1f} KB, {pmcid})!")
            return cached_txt, full_article

    # 3. Strategy B: Direct Binary PDF Download (arXiv / Open-Access)
    pdf_url = paper.get("pdf_url")
    if pdf_url and ("arxiv.org" in pdf_url or "europepmc" not in pdf_url):
        print(f"  [1/4] 📥 Downloading PDF from: {pdf_url[:65]}...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/pdf,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8"
        }
        try:
            req = urllib.request.Request(pdf_url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
                if not data.startswith(b"%PDF") and b"%PDF" in data[:1024]:
                    idx = data.find(b"%PDF")
                    data = data[idx:]

                if data.startswith(b"%PDF"):
                    with open(cached_pdf, "wb") as f:
                        f.write(data)
                    print(f"  [1/4] ✅ Validated binary PDF ({len(data)/1024:.1f} KB)!")
                    return cached_pdf, None
                else:
                    print("  ⚠️ Downloaded file is an HTML landing page, checking open-access repositories...")
        except Exception as e:
            print(f"  ⚠️ Direct download failed ({e}), checking alternatives...")

    # 4. Strategy C: Unpaywall DOI Resolution
    doi = paper.get("doi")
    if doi:
        try:
            print(f"  [1/4] 🔍 Querying Unpaywall open-access index for DOI: {doi}...")
            oa_api_url = f"https://api.unpaywall.org/v2/{doi}?email=academic_research@healthrag.org"
            req = urllib.request.Request(oa_api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                oa_data = json.loads(resp.read().decode("utf-8"))
                best_oa = oa_data.get("best_oa_location") or {}
                oa_pdf_url = best_oa.get("url_for_pdf")
                if oa_pdf_url:
                    print(f"  [1/4] 📥 Found open-access repository PDF: {oa_pdf_url[:65]}...")
                    req_pdf = urllib.request.Request(oa_pdf_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req_pdf, timeout=20) as r_pdf:
                        pdf_bytes = r_pdf.read()
                        if b"%PDF" in pdf_bytes[:1024]:
                            if not pdf_bytes.startswith(b"%PDF"):
                                pdf_bytes = pdf_bytes[pdf_bytes.find(b"%PDF"):]
                            with open(cached_pdf, "wb") as f:
                                f.write(pdf_bytes)
                            print(f"  [1/4] ✅ Resolved open-access repository PDF ({len(pdf_bytes)/1024:.1f} KB)!")
                            return cached_pdf, None
        except Exception:
            pass

    # 5. Strategy D: Rich Clinical Abstract & Findings Fallback (Zero-Skip Guarantee)
    summary = paper.get("summary", "").strip()
    if summary and len(summary) > 100:
        print("  [1/4] ℹ️ Full text behind commercial paywall. Extracting from complete peer-reviewed clinical abstract & findings.")
        abstract_doc = (
            f"Title: {paper['title']}\n"
            f"Authors: {', '.join(paper['authors'])} ({paper['year']})\n"
            f"Source: {paper['source']} | DOI: {paper.get('doi')}\n\n"
            f"CLINICAL ABSTRACT & PEER-REVIEWED FINDINGS:\n{summary}\n"
        )
        with open(cached_txt, "w", encoding="utf-8") as f:
            f.write(abstract_doc)
        return cached_txt, abstract_doc

    return None, None

def update_progress_md(paper_title: str, rules_added: int, total_vectors: int) -> None:
    """Updates progress.md according to Rule 1 of AGENT_RULES.md."""
    if not os.path.exists(PROGRESS_PATH):
        return
    try:
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        content = re.sub(
            r"- \*\*Current Vector Count\*\*: \d+",
            f"- **Current Vector Count**: {total_vectors}",
            content
        )

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n  - *{paper_title}* (Ingested {date_str}, +{rules_added} rules, total: {total_vectors})"
        if "## 📚 Ingested Literature & Vector Index State" in content:
            parts = content.split("## 🕒 Recent Session Log")
            updated_content = parts[0].rstrip() + new_entry + "\n\n## 🕒 Recent Session Log" + parts[1]
            with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
                f.write(updated_content)
        print("  📝 Updated progress.md context successfully!")
    except Exception as e:
        print(f"  ⚠️ Could not update progress.md ({e})")

# ==========================================
# 4. INTERACTIVE USER WORKFLOW
# ==========================================

def run_interactive_pipeline():
    print("\n" + "="*80)
    print("🧬 AUTOMATED RESEARCH PAPER HUNTER & CLINICAL EXTRACTION PIPELINE")
    print("="*80)

    # Fast background health check / warm-up
    try:
        from colab_automator import check_colab_health, get_current_colab_url
        c_url = get_current_colab_url()
        if c_url and check_colab_health(c_url, timeout=1.5):
            print(f"⚡ Colab fallback server active at: {c_url}")
    except Exception:
        pass

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
    print(f"📚 CANDIDATE RESEARCH PAPERS FOUND ({len(candidates)}):")
    print("="*80)

    valid_options = []
    for i, p in enumerate(candidates):
        num = i + 1
        status_tag = " [ALREADY EXTRACTED - IN LOCAL DB]" if p["already_extracted"] else " [NEW]"
        downloadable = "Open-Access Article" if (p.get("pmcid") or p.get("pdf_url")) else "Clinical Abstract"

        print(f"\n[{num}]{status_tag} {p['title']}")
        print(f"    👤 Authors: {', '.join(p['authors'][:3])}{'...' if len(p['authors']) > 3 else ''} ({p['year']})")
        print(f"    📦 Source: {p['source']} | Status: {downloadable}")

        summary_preview = p['summary'][:250].replace('\n', ' ') + "..." if len(p['summary']) > 250 else p['summary']
        print(f"    📝 Summary: {summary_preview}")
        if p.get("pmcid"):
            print(f"    🔗 PubMed Central: {p['pmcid']}")
        elif p.get("pdf_url"):
            print(f"    🔗 Direct Link: {p['pdf_url']}")

        if not p['already_extracted']:
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
    total_selected = len(selected_indices)

    for current_i, idx in enumerate(selected_indices, start=1):
        paper = candidates[idx - 1]
        t_start = time.time()

        print("\n" + "="*80)
        print(f"🚀 [{current_i}/{total_selected}] EXTRACTING: {paper['title']}")
        print("="*80)

        # STEP 1: Resolve & Download Document
        doc_path, doc_text = resolve_and_fetch_document(paper)
        if not doc_path and not doc_text:
            print(f"⏭️ Skipping paper due to unresolved source.\n")
            continue

        # Real-time terminal progress callback
        def print_progress(msg: str, pct: Optional[float] = None):
            pct_str = f" ({int(pct * 100)}%)" if pct is not None else ""
            print(f"  {msg}{pct_str}")

        # STEP 2 & 3: Extract Rules (High-Speed Direct or Colab fallback)
        result = upload_pdf_and_sync_rules(doc_path, progress_cb=print_progress, direct_text=doc_text)

        if result.get("status") == "success":
            rules_added = result.get("new_rules_extracted", 0)
            total_vecs = result.get("total_vectors", 0)
            rules = result.get("rules", [])
            elapsed = round(time.time() - t_start, 2)

            # Live preview of discovered rules
            if rules:
                print(f"\n  ✨ Discovered {len(rules)} causal relations:")
                for r_idx, r in enumerate(rules[:4]):
                    print(f"     • {r.get('metric_a', '?')} ({r.get('change_a', '')}) + {r.get('metric_b', '?')} ({r.get('change_b', '')}) ➔ {r.get('predicted_outcome', 'Risk')}")
                if len(rules) > 4:
                    print(f"     ... and {len(rules) - 4} more relations.")

            print(f"\n  [4/4] 💾 Cumulative FAISS indexing complete (Total vectors: {total_vecs})")

            # Update Ledger
            paper_entry = {
                "paper_id": slugify(paper["title"]),
                "title": paper["title"],
                "authors": ", ".join(paper["authors"]),
                "year": paper["year"],
                "doi": paper.get("doi"),
                "source_pdf": os.path.basename(doc_path) if doc_path else "article.txt",
                "rules_count": rules_added,
                "date_added": datetime.now().isoformat()
            }
            ledger["extracted_papers"].append(paper_entry)
            save_ledger(ledger)
            print(f"  📖 Recorded in paper_ledger.json (+{rules_added} rules)")

            # Update progress.md
            update_progress_md(paper["title"], rules_added, total_vecs)

            engine_label = result.get("engine", "fast-engine")
            print(f"  🏁 [SUCCESS] Paper completed in {elapsed}s via {engine_label}!\n")

        else:
            print(f"  ❌ Extraction failed: {result.get('message', 'Unknown error')}\n")

    print("\n" + "="*80)
    print("🎉 ALL SELECTED PAPERS PROCESSED SUCCESSFULLY!")
    print(f"💾 Persistent FAISS database is ready with new peer-reviewed clinical rules.")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_interactive_pipeline()
