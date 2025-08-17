# main.py
import os
import json
import glob
from docx import Document
import fitz  # PyMuPDF
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import pandas as pd
import numpy as np

# ------------------- CONFIG -------------------
RESUME_FOLDER = "resumes"
OUTPUT_JSON = "all_resumes_text.json"
OUTPUT_CSV = "resume_analysis.csv"
OUTPUT_XLSX = "resume_analysis.xlsx"

# Tesseract OCR path
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# ------------------- REFERENCE DATA -------------------
# Example courses JSON
reference_courses = {
    "Python": ["python", "data analysis", "pandas", "numpy"],
    "Machine Learning": ["machine learning", "tensorflow", "keras", "scikit-learn"],
    "Digital Marketing": ["digital marketing", "seo", "google analytics"],
    "Web Development": ["html", "css", "javascript", "react", "node"],
    "Cloud Computing": ["aws", "azure", "gcp", "cloud"]
}

# Example certifications JSON
reference_certifications = {
    "AWS Certified Solutions Architect": ["aws certified solutions architect", "aws certification"],
    "Google Data Analytics": ["google data analytics", "data analytics certificate"]
}

# ------------------- FUNCTIONS -------------------
def extract_text_from_resume(filepath):
    """Extract text from PDF, DOCX, or image resumes with OCR fallback."""
    text = ""
    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext == ".pdf":
            pdf_doc = fitz.open(filepath)
            for page in pdf_doc:
                page_text = page.get_text()
                if page_text.strip():
                    text += page_text + "\n"
                else:
                    # OCR fallback
                    images = convert_from_path(filepath)
                    for img in images:
                        text += pytesseract.image_to_string(img) + "\n"
            pdf_doc.close()

        elif ext == ".docx":
            doc = Document(filepath)
            for para in doc.paragraphs:
                text += para.text + "\n"

        elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            img = Image.open(filepath)
            text += pytesseract.image_to_string(img) + "\n"

        else:
            print(f"⚠️ Skipping unsupported file: {filepath}")

    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")

    return text.strip().lower()


def analyze_resume(text):
    """Match courses and certifications, assign skill levels and probability score."""
    matched_courses = []
    course_levels = {}
    matched_certs = []

    # Courses
    total_keywords = sum(len(keywords) for keywords in reference_courses.values())
    matched_keywords = 0

    for course, keywords in reference_courses.items():
        count = sum(text.count(k.lower()) for k in keywords)
        matched_keywords += count
        if count > 0:
            matched_courses.append(course)
            if count > 3:
                course_levels[course] = "Advanced"
            elif count == 2:
                course_levels[course] = "Intermediate"
            else:
                course_levels[course] = "Beginner"

    # Certifications
    for cert, keywords in reference_certifications.items():
        if any(k.lower() in text for k in keywords):
            matched_certs.append(cert)

    # Probability calculation (simple ratio of matched keywords to total)
    probability = round(matched_keywords / total_keywords, 2) if total_keywords > 0 else 0.0

    return matched_courses, course_levels, matched_certs, probability

# ------------------- MAIN -------------------
def main():
    all_text = {}
    results = []

    resume_files = glob.glob(os.path.join(RESUME_FOLDER, "*"))
    if not resume_files:
        print(f"❌ No resumes found in {RESUME_FOLDER}")
        return

    # Extract text
    for file_path in resume_files:
        text = extract_text_from_resume(file_path)
        print(f"📄 {os.path.basename(file_path)} extracted: {len(text)} chars")  # DEBUG
        if text:
            all_text[os.path.basename(file_path)] = text

            # Analyze
            courses, levels, certs, probability = analyze_resume(text)
            results.append({
                "Candidate": os.path.basename(file_path),
                "Courses": courses,
                "Course Levels": levels,
                "Certifications": certs,
                "Probability": probability
            })

    # Sort results by probability (descending)
    results = sorted(results, key=lambda x: x["Probability"], reverse=True)

    # Save raw text
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_text, f, indent=4)
    print(f"✅ All resumes text saved to {OUTPUT_JSON}")

    # Save analysis
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_CSV, index=False)
    df.to_excel(OUTPUT_XLSX, index=False)
    print(f"✅ Analysis saved to {OUTPUT_CSV} & {OUTPUT_XLSX}")

if __name__ == "__main__":
    main()
