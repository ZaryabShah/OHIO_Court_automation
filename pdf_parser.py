
#!/usr/bin/env python3
"""
foreclosure_pdf_parser.py — v2.1

Improvements:
- Case number from footers and guards against capturing "JUDGE" placeholder.
- Court/County detection for "IN THE COURT OF COMMON PLEAS\nSUMMIT COUNTY, OHIO".
- Plaintiff extraction robust to multi-line captions.
- Defendant name filter that ignores address lines.
- Address parsing supports "PROPERTY ADDRESS:" and OH/Ohio with line wraps.
- Certificate number supports multiple label variants.
- Interest rate accepts numeric and spelled-out forms.
- Statutes capture bare 5721.xx / 323.xx sections.
- Prosecutor/attorney block handles newline between name and title.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# ---------------- Text Extraction ----------------

def extract_text_pdfminer(path: str) -> str:
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        return ""
    try:
        return extract_text(path) or ""
    except Exception:
        return ""

def extract_text_pypdf2(path: str) -> str:
    try:
        import PyPDF2
    except Exception:
        return ""
    try:
        text_parts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                text_parts.append(t)
        return "\n".join(text_parts)
    except Exception:
        return ""

def extract_text_ocr(path: str, dpi: int = 300, lang: str = "eng") -> str:
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception:
        return ""
    try:
        images = convert_from_path(path, dpi=dpi)
        texts = []
        for img in images:
            txt = pytesseract.image_to_string(img, lang=lang)
            texts.append(txt or "")
        return "\n".join(texts)
    except Exception:
        return ""

def normalize_text(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"[’‘]", "'", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def extract_text_any(path: str, use_ocr: bool = False) -> str:
    text = extract_text_pdfminer(path)
    if len(text.strip()) < 200:
        alt = extract_text_pypdf2(path)
        if len(alt.strip()) > len(text.strip()):
            text = alt
    if use_ocr and len(text.strip()) < 200:
        ocr = extract_text_ocr(path)
        if len(ocr.strip()) > len(text.strip()):
            text = ocr
    return normalize_text(text)

# ---------------- Helpers ----------------

def to_float_currency(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    s = s.strip().replace(",", "").replace("$", "")
    try:
        return float(s)
    except Exception:
        return None

def parse_date_any(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    try:
        from dateutil import parser as dparser
        dt = dparser.parse(s, fuzzy=True, default=datetime(1900,1,1))
        if re.fullmatch(r"[A-Za-z]+\s+\d{4}", s):
            return dt.strftime("%Y-%m")
        return dt.isoformat()
    except Exception:
        for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).isoformat()
            except Exception:
                continue
    return None

def find_first(patterns: List[re.Pattern], text: str, group: int = 1) -> Optional[str]:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(group).strip()
    return None

# ---------------- Data Models ----------------

@dataclass
class AttorneyBlock:
    prosecutor_name: Optional[str] = None
    office: Optional[str] = None
    assistant_name: Optional[str] = None
    bar_number: Optional[str] = None
    title: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

@dataclass
class ParsedComplaint:
    file: str
    case_number: Optional[str] = None
    court: Optional[str] = None
    county: Optional[str] = None
    filing_datetime: Optional[str] = None
    plaintiff: Optional[str] = None
    defendants: List[str] = dataclasses.field(default_factory=list)
    property_address: Optional[str] = None
    parcel_number: Optional[str] = None
    lien_holder: Optional[str] = None
    tax_certificate_number: Optional[str] = None
    tax_certificate_sale_date: Optional[str] = None
    redemption_price: Optional[float] = None
    redemption_good_through: Optional[str] = None
    interest_rate_percent: Optional[float] = None
    statutes: List[str] = dataclasses.field(default_factory=list)
    relief_requested: List[str] = dataclasses.field(default_factory=list)
    exhibits: List[str] = dataclasses.field(default_factory=list)
    attorney: AttorneyBlock = dataclasses.field(default_factory=AttorneyBlock)
    raw_excerpt: Optional[str] = None

# ---------------- Parser ----------------

class ForeclosureComplaintParser:
    def __init__(self, text: str):
        self.text = text
        self.lower = text.lower()

    def parse_case_number(self) -> Optional[str]:
        pats = [
            re.compile(r"Case\s+No\.?\s*[:#]?\s*([A-Za-z0-9\-]+)", re.I),
            re.compile(r"Case\s*#\s*([A-Za-z0-9\-]+)", re.I),
            re.compile(r"CASE\s+NUMBER\s*:\s*(?!JUDGE\b)([A-Za-z0-9\-]+)", re.I),
        ]
        num = find_first(pats, self.text)
        if num and num.upper() != "JUDGE":
            return num
        # Footer / anywhere pattern: CV-YYYY-MM-####
        m = re.search(r"\b([A-Z]{1,3}-\d{4}-\d{2}-\d{3,8})\b", self.text)
        if m:
            return m.group(1)
        return None

    def parse_court_and_county(self) -> (Optional[str], Optional[str]):
        court = county = None
        # "COURT OF COMMON PLEAS, SUMMIT COUNTY"
        m = re.search(r"(COURT OF [A-Z \t]+?),\s*([A-Z][A-Z]+)\s+COUNTY", self.text, re.I)
        if m:
            court = m.group(1).title().replace("Of", "of")
            county = m.group(2).title()
        else:
            # "IN THE COURT OF COMMON PLEAS\nSUMMIT COUNTY, OHIO"
            m2 = re.search(r"IN THE\s+COURT OF\s+([A-Z ]+)\s*\n\s*([A-Z][A-Z]+)\s+COUNTY,\s*OHIO", self.text, re.I)
            if m2:
                court = f"Court of {m2.group(1).title().strip()}"
                county = m2.group(2).title().strip()
            else:
                # Fallback: just the county
                m3 = re.search(r"\b([A-Z][A-Z]+)\s+COUNTY,\s*OHIO\b", self.text, re.I)
                if m3:
                    county = m3.group(1).title().strip()
                    # If "COURT OF COMMON PLEAS" appears anywhere, set that as court
                    if re.search(r"COURT OF COMMON PLEAS", self.text, re.I):
                        court = "Court of Common Pleas"
        return court, county

    def parse_filing_datetime(self) -> Optional[str]:
        pats = [
            re.compile(r"Filed\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})(?:\s+at\s+([0-9:]+\s*(?:AM|PM)))?", re.I),
            re.compile(r"FILED\s+(\w+\s+\d{1,2},\s*\d{4})\s+(\d{1,2}:\d{2}:\d{2}\s*(?:AM|PM)?)", re.I),
        ]
        for pat in pats:
            m = pat.search(self.text)
            if m:
                date = m.group(1)
                time = m.group(2) if m.lastindex and m.lastindex >= 2 else None
                return parse_date_any(f"{date} {time}" if time else date)
        m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2}\s*(?:AM|PM))\b", self.text)
        if m:
            return parse_date_any(f"{m.group(1)} {m.group(2)}")
        return None

    def parse_parties(self) -> (Optional[str], List[str]):
        lines = [ln.strip() for ln in self.text.splitlines()]
        plaintiff = None
        defendants: List[str] = []

        # Try line-based capture around "Plaintiff"
        for i, ln in enumerate(lines):
            if re.fullmatch(r"Plaintiff\b", ln, re.I):
                block = []
                j = i - 1
                while j >= 0 and len(block) < 4 and lines[j].strip():
                    block.append(lines[j].strip(", "))
                    j -= 1
                block = list(reversed(block))
                if block:
                    # Keep first line as the party name
                    plaintiff = block[0]
                break

        # Fallback: look at up to 4 lines before the "Plaintiff" label and pick the first non-empty line
        if not plaintiff:
            m = re.search(r"((?:[^\n]*\n){1,4})\s*Plaintiff\b", self.text, re.I)
            if m:
                lines_block = [ln.strip(" ,") for ln in m.group(1).splitlines() if ln.strip()]
                if lines_block:
                    plaintiff = lines_block[0]

        # Defendants between "vs." and "Defendant(s)"
        m2 = re.search(r"\bvs\.\s*(.+?)\bDefendant\(s\)", self.text, re.I | re.S)
        if m2:
            chunk = m2.group(1)
            for raw in chunk.splitlines():
                raw = raw.strip(" ,;-")
                if not raw or re.search(r"\d", raw):
                    continue
                tokens = raw.split()
                if 2 <= len(tokens) <= 6:
                    letters = re.sub(r"[^A-Za-z]", "", raw)
                    if letters and sum(1 for c in letters if c.isupper()) / max(1, len(letters)) > 0.6:
                        if raw.upper() != "ET AL.":
                            defendants.append(raw)

        return plaintiff, defendants

    def parse_property(self) -> (Optional[str], Optional[str]):
        address = None
        m = re.search(r"PROPERTY\s+ADDRESS\s*:\s*([^\n]+)(?:\n([^\n]+))?", self.text, re.I)
        if m:
            a = m.group(1).strip()
            b = (m.group(2) or "").strip()
            address = re.sub(r"\s{2,}", " ", (" ".join([a, b])).strip())
        if not address:
            m2 = re.search(r"(\d{1,6}\s+[A-Za-z0-9 .'-]+(?:\n|\s)+[A-Za-z .'-]+,\s*O(?:H|h)(?:io)?\s*\d{5})", self.text)
            if m2:
                address = re.sub(r"\s*\n\s*", " ", m2.group(1)).strip()
        m3 = re.search(r"(?:Permanent\s+Parcel\s+(?:No\.|Number)|Parcel(?:\s+Number)?)\s*[:#]?\s*([A-Za-z0-9\-]+)", self.text, re.I)
        parcel = m3.group(1).strip() if m3 else None
        return address, parcel

    def parse_tax_certificate(self) -> (Optional[str], Optional[str], Optional[str]):
        lien_holder = None
        m = re.search(r"lien\s+(?:vested\s+in|held\s+by)\s+([A-Z0-9 .,&\-]+?)(?:,|\.)", self.text, re.I)
        if m:
            lien_holder = m.group(1).strip()
        cert_pats = [
            re.compile(r"Tax\s+Certificate(?:\s*(?:No\.|Number|#))?\s*[:#]?\s*([A-Za-z0-9\-]+)", re.I),
            re.compile(r"Certificate\s+Number(?:\(s\))?\s*:\s*([A-Za-z0-9\-]+)", re.I),
            re.compile(r"tax\s+certificate\s+number\s*([A-Za-z0-9\-]+)", re.I),
        ]
        cert_no = find_first(cert_pats, self.text)
        sale_pats = [
            re.compile(r"sold\s+on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})", re.I),
            re.compile(r"certificate\s+sale\s+date\s*[:#]?\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})", re.I),
        ]
        sale_date_raw = find_first(sale_pats, self.text)
        if not sale_date_raw:
            m_fallback = re.search(r"on\s+or\s+about\s+([A-Za-z]+\s+\d{1,2},\s*\d{4}).{0,120}?\bwas\s+sold\b", self.text, re.I|re.S)
            if m_fallback:
                sale_date_raw = m_fallback.group(1)
        sale_date = parse_date_any(sale_date_raw) if sale_date_raw else None
        return lien_holder, cert_no, sale_date

    def parse_redemption_and_interest(self) -> (Optional[float], Optional[str], Optional[float]):
        red_price = None
        good_through = None
        interest = None

        m = re.search(r"redemption\s+price[^$\n]*\$\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)", self.text, re.I)
        if m:
            red_price = to_float_currency(m.group(1))

        m2 = re.search(r"(?:good|valid)\s+through\s+([A-Za-z]+\s+\d{4})", self.text, re.I)
        if m2:
            good_through = parse_date_any(m2.group(1))

        m3 = re.search(r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:per\s+year|per\s+annum|annual\s+interest)", self.text, re.I)
        if m3:
            try:
                interest = float(m3.group(1))
            except Exception:
                interest = None
        if interest is None:
            words_to_num = {
                "one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
                "eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,
                "eighteen":18,"nineteen":19,"twenty":20,"twenty-one":21,"twenty two":22,"twenty-three":23,
                "twenty four":24,"twenty-five":25,"twenty six":26,"twenty-seven":27,"twenty eight":28,
                "twenty-nine":29,"thirty":30
            }
            m4 = re.search(r"\b([A-Za-z\- ]+?)\s+percent\s+(?:per\s+year|per\s+annum)?", self.text, re.I)
            if m4:
                key = re.sub(r"\s+", " ", m4.group(1).strip().lower())
                if key in words_to_num:
                    interest = float(words_to_num[key])

        return red_price, good_through, interest

    def parse_statutes(self) -> List[str]:
        out = set()
        for s in re.findall(r"R\.C\.\s*(\d{3,4}\.\d+)", self.text, re.I):
            out.add(f"R.C.{s}")
        for s in re.findall(r"\b(5721\.\d+|323\.\d+)\b", self.text):
            out.add(f"R.C.{s}")
        return sorted(out)

    def parse_relief(self) -> List[str]:
        out = []
        if re.search(r"\bforeclos(e|ure)\b", self.text, re.I):
            out.append("Foreclosure of liens")
        if re.search(r"sheriff[’']?s\s+sale|order\s+the\s+sale|order\s+of\s+sale", self.text, re.I):
            out.append("Order sheriff's sale")
        if re.search(r"\bbar(?:ring)?\s+.*claims", self.text, re.I):
            out.append("Bar other claims unless asserted")
        return sorted(set(out))

    def parse_exhibits(self) -> List[str]:
        labs = re.findall(r"\bExhibit\s+([A-Z])\b", self.text, re.I)
        return sorted(set([l.upper() for l in labs]))

    def parse_attorney_block(self) -> AttorneyBlock:
        block = ""
        m = re.search(r"Respectfully\s+submitted[^\n]*\n(.{0,1400})", self.text, re.I | re.S)
        if m:
            block = m.group(1)
        else:
            m2 = re.search(r"([A-Z][A-Z ]+Prosecutor[^\n]*\n(?:.*\n){1,10})", self.text, re.I)
            if m2:
                block = m2.group(1)

        ab = AttorneyBlock()

        m = re.search(r"\b([A-Z][A-Za-z.\- ]+)[,\n ]+\s*([A-Z][A-Za-z ]*Prosecutor)\b", block, re.I)
        if m:
            ab.prosecutor_name = m.group(1).strip()
            ab.office = m.group(2).strip().title()

        m = re.search(r"/s/\s*([A-Z][A-Z .'-]+).*?#\s*(\d{6,7})", block, re.I)
        if not m:
            m = re.search(r"([A-Z][A-Z .'-]+)\s*,?\s*#\s*(\d{6,7})", block, re.I)
        if m:
            ab.assistant_name = m.group(1).strip().title()
            ab.bar_number = m.group(2).strip()

        if re.search(r"\bAssistant\s+Prosecuting\s+Attorney\b", block, re.I):
            ab.title = "Assistant Prosecuting Attorney"

        m = re.search(r"(\d{2,5}\s+[A-Za-z0-9 .'-]+?\n[^\n]*O[hH](?:io)?\s+\d{5})", block, re.I)
        if m:
            ab.address = re.sub(r"\s*\n\s*", ", ", m.group(1).strip())
        if not ab.address:
            m = re.search(r"Assistant\s+Prosecuting\s+Attorney\s*\n\s*([^\n]+)\n\s*([^\n]*O[hH](?:io)?\s+\d{5})", block, re.I)
            if m:
                ab.address = (m.group(1).strip() + ", " + m.group(2).strip())

        m = re.search(r"(\(\d{3}\)\s*\d{3}\-\d{4})", block)
        if m:
            ab.phone = m.group(1)

        m = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", block)
        if m:
            ab.email = m.group(1)

        return ab

    def parse_all(self) -> ParsedComplaint:
        court, county = self.parse_court_and_county()
        plaintiff, defendants = self.parse_parties()
        address, parcel = self.parse_property()
        lien_holder, cert_no, sale_date = self.parse_tax_certificate()
        red_price, good_through, interest = self.parse_redemption_and_interest()
        statutes = self.parse_statutes()
        relief = self.parse_relief()
        exhibits = self.parse_exhibits()
        atty = self.parse_attorney_block()
        data = ParsedComplaint(
            file="",
            case_number=self.parse_case_number(),
            court=court,
            county=county,
            filing_datetime=self.parse_filing_datetime(),
            plaintiff=plaintiff,
            defendants=defendants,
            property_address=address,
            parcel_number=parcel,
            lien_holder=lien_holder,
            tax_certificate_number=cert_no,
            tax_certificate_sale_date=sale_date,
            redemption_price=red_price,
            redemption_good_through=good_through,
            interest_rate_percent=interest,
            statutes=statutes,
            relief_requested=relief,
            exhibits=exhibits,
            attorney=atty,
            raw_excerpt=self.text[:600].strip() if self.text else None,
        )
        return data

# --------------- CLI ---------------

def as_csv_rows(items: List[ParsedComplaint]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for it in items:
        d = asdict(it)
        atty = d.pop("attorney", {}) or {}
        for k, v in atty.items():
            d[f"attorney_{k}"] = v
        for list_key in ("defendants", "statutes", "relief_requested", "exhibits"):
            v = d.get(list_key)
            if isinstance(v, list):
                d[list_key] = "; ".join(v)
        rows.append(d)
    return rows

def main():
    import glob
    ap = argparse.ArgumentParser(description="Parse foreclosure complaint PDFs into structured data (v2.1).")
    ap.add_argument("inputs", nargs="+", help="PDF file(s) or glob pattern(s)")
    ap.add_argument("--ocr", action="store_true", help="Enable OCR fallback (requires pytesseract & pdf2image)")
    ap.add_argument("--csv", type=str, help="Write CSV to this path")
    ap.add_argument("--json", type=str, help="Write JSON to this path")
    args = ap.parse_args()

    files: List[Path] = []
    for inp in args.inputs:
        matches = glob.glob(inp)
        if matches:
            files.extend([Path(m) for m in matches])
        else:
            p = Path(inp)
            if p.is_dir():
                files.extend([f for f in sorted(p.glob("**/*.pdf"))])
            else:
                files.append(p)
    files = [f for f in files if f.exists()]

    results: List[ParsedComplaint] = []
    for f in files:
        txt = extract_text_any(str(f), use_ocr=args.ocr)
        parser = ForeclosureComplaintParser(txt)
        out = parser.parse_all()
        out.file = str(f)
        results.append(out)

    if args.csv:
        rows = as_csv_rows(results)
        fieldnames = sorted({k for row in rows for k in row.keys()})
        with open(args.csv, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=fieldnames)
            w.writeheader()
            for row in rows:
                w.writerow(row)
        print(f"Wrote CSV: {args.csv}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fp:
            json.dump([asdict(r) for r in results], fp, ensure_ascii=False, indent=2)
        print(f"Wrote JSON: {args.json}")

    if not args.csv and not args.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
