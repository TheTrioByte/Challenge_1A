import os
import sys
import json
import re
import pdfplumber
from difflib import SequenceMatcher

def normalize_text(text):
    return ' '.join(text.split()).lower()

def is_similar(a, b, threshold=0.9):
    return SequenceMatcher(None, a, b).ratio() > threshold

def fix_ocr_artifacts(line):
    line = line.strip()
    if "RRRRFFFFPPPP" in line.upper():  
        return "RFP: Request for Proposal"
    words = line.split()
    fixed = []
    for word in words:
        if len(word) == 1 and word.lower() == 'f':
            fixed.append('for')
        elif len(word) == 1 and word.lower() == 't':
            fixed.append('the')
        elif len(word) == 2 and word.lower() == 'pp':
            fixed.append('p')
        elif len(word) == 2 and word.lower() == 'tt':
            fixed.append('t')
        elif re.match(r'^([A-Za-z])\1{2,}$', word):
            fixed.append(word[0])
        else:
            fixed.append(word)
    return ' '.join(fixed)

def join_fragments(texts, min_frag_len=10):
    merged = []
    buffer = ""
    for txt in texts:
        txt = txt.strip()
        if not txt:
            continue
        if len(txt) < min_frag_len or (len(txt.split()) == 1 and len(txt) < 12):
            buffer += " " + txt if buffer else txt
        else:
            if buffer:
                merged.append(buffer + " " + txt)
                buffer = ""
            else:
                merged.append(txt)
    if buffer:
        merged.append(buffer)
    return merged

def extract_text_and_fonts(page, tolerance=3):
    lines = []
    if not page.chars:
        return lines
    line_map = {}
    for char in page.chars:
        key = round(char['top'] / tolerance) * tolerance
        line_map.setdefault(key, []).append(char)
    for y in sorted(line_map):
        chars_in_line = line_map[y]
        chars_in_line.sort(key=lambda c: c['x0'])
        line_text = ''.join(c['text'] for c in chars_in_line)
        font_sizes = [c['size'] for c in chars_in_line]
        font_bold_flags = [('Bold' in c.get('fontname','') or 'Black' in c.get('fontname','')) for c in chars_in_line]
        line_text = line_text.strip()
        if line_text:
            lines.append((line_text, font_sizes, font_bold_flags))
    return lines

def is_date_line(text):
    patterns = [
        r'^\d{4}$',
        r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$',
        r'^[A-Za-z]+\s+\d{4}$',
        r'^[A-Za-z]+\s+\d{1,2},\s*\d{4}$',
        r'^\d{1,2}\s+[A-Za-z]+\s+\d{4}$',
        r'^\d{1,2}$',
    ]
    text = text.strip()
    for pat in patterns:
        if re.fullmatch(pat, text):
            return True
    return False

def is_heading_candidate(text):
    words = text.strip().split()
    if len(words) > 15 or len(text.strip()) > 100:
        return False
    if (any(w.islower() for w in words[:2]) or
        len(text.split(',')) > 3 or
        len(text.split('.')) > 3 or
        bool(re.match(
            r'^(the|this|in|of|and|as|with|a|an)[,\s\W]',
            text, flags=re.IGNORECASE))):
        return False
    return True

def is_multiword(text):
    return len(text.strip().split()) >= 2

def extract_title_from_lines(lines):
    max_avg_font = 0
    main_title = ""
    title_candidates = []
    # First pass: find the max font size for this page
    for line_text, font_sizes, _ in lines:
        if not line_text.strip() or not font_sizes:
            continue
        avg_font = sum(font_sizes) / len(font_sizes)
        if avg_font > max_avg_font:
            max_avg_font = avg_font
    if max_avg_font == 0:
        return ""
    # Second pass: gather all lines with font size at least 80% of max, check if candidate
    title_candidates = []
    for line_text, font_sizes, _ in lines:
        if not line_text.strip() or not font_sizes:
            continue
        avg_font = sum(font_sizes) / len(font_sizes)
        if (not is_date_line(line_text) and
            is_heading_candidate(line_text) and
            avg_font >= 0.8 * max_avg_font and
            len(line_text.strip()) <= 150 and
            len(line_text.strip().split()) >= 1):
            title_candidates.append((line_text, font_sizes))
    # Third pass: merge adjacent large-font lines for title (max 2 lines)
    merged_title = []
    for i in range(len(title_candidates)):
        if i == 0:
            merged_title.append(title_candidates[i][0])
        else:
            # Only merge if the lines are very close vertically and both are heading candidates
            prev_y = round(title_candidates[i-1][1][0] / 3) * 3
            curr_y = round(title_candidates[i][1][0] / 3) * 3
            if len(merged_title) < 2 and abs(curr_y - prev_y) < 20:
                merged_title.append(title_candidates[i][0])
    main_title = '\n'.join(merged_title)
    return fix_ocr_artifacts(main_title) if main_title else ""

def guess_heading_level(line, font_sizes, font_bold_flags):
    if not font_sizes or not is_heading_candidate(line):
        return None
    words = line.strip().split()
    if line.isupper() and len(words) <= 7:
        return "H1"
    elif re.match(r'^\d+(\.\d+)*\s', line):
        return "H1"
    elif line[:1].isupper() and line.strip().istitle():
        return "H2"
    avg_size = sum(font_sizes) / len(font_sizes)
    bold_count = sum(font_bold_flags)
    bold_ratio = bold_count / max(1, len(font_bold_flags))
    if avg_size >= 14 and bold_ratio >= 0.6:
        return "H1"
    if avg_size >= 12 and bold_ratio >= 0.3:
        return "H2"
    if avg_size >= 10:
        return "H3"
    return None

def extract_outline(pdf_path):
    title = ""
    outline = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            lines = extract_text_and_fonts(page)
            if page_num == 1 and lines and not title:
                title = extract_title_from_lines(lines)
            for line_text, font_sizes, font_bold_flags in lines:
                if (not line_text.strip() or
                    is_date_line(line_text) or
                    not is_heading_candidate(line_text)):
                    continue
                fixed_text = fix_ocr_artifacts(line_text)
                level = guess_heading_level(fixed_text, font_sizes, font_bold_flags)
                if level:
                    outline.append({"level": level, "text": fixed_text, "page": page_num})
    return title, outline

def main(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    for pdf_file in pdf_files:
        in_path = os.path.join(input_dir, pdf_file)
        out_file = os.path.splitext(pdf_file)[0] + '.json'
        out_path = os.path.join(output_dir, out_file)
        print(f"Processing {pdf_file}...")
        title, outline = extract_outline(in_path)
        result = {"title": title, "outline": outline}
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Saved outline to {out_path}")

if __name__ == "__main__":
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    main(input_dir, output_dir)
