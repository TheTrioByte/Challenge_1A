# PDF Outline Extractor ![docker]

Extract **title** and **heading hierarchy** (H1, H2, H3) from batches of PDFs, with **automatic OCR artifact cleanup** and **headings ranking** by style.  
Works fully offline in Docker—outputs one JSON per PDF.

---

## Features ✨

- **Batch processing** of all PDFs in a directory
- **Robust heading detection** using font size, boldness, and layout
- **OCR artifact cleaning** (e.g., fixes repeated letters: “RRRRFFFFPPPP” → “RFP: Request for Proposal”)
- **Line merging** for fragmented text and **duplicate removal**
- **Dockerized** for portability and reproducibility on AMD64 (x86_64) hosts
- **Lightweight dependencies** (only `pdfplumber` needed)

---

## Get Started 🚀

### 1. Prepare your input

Put all your PDFs in an `input/` directory at your project root.

### 2. Build the Docker image

docker build --platform linux/amd64 -t outline-extractor:latest .

### 3. Create the output directory

mkdir -p output

### 4. Run the extractor

docker run --rm -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" --network none outline-extractor:latest

**Output:**  
For each PDF (e.g., `report.pdf`), you’ll find a matching `report.json` in the `output/` directory, containing the extracted title and outline.

---

## Output Format 📜

{
"title": "Document Title",
"outline": [
{"level": "H1", "text": "INTRODUCTION", "page": 1},
{"level": "H2", "text": "Background", "page": 2},
{"level": "H3", "text": "Related Work", "page": 3}
// ...and so on
]
}

pip install -r requirements.txt
python extract_outline.py input output
