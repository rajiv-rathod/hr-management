# HR Management Resume Analyzer

This project is an automated resume analysis tool designed for HR teams to efficiently process, analyze, and rank candidate resumes based on relevant skills, courses, and certifications. It extracts text from various resume formats, matches them against reference data, and generates detailed reports for candidate evaluation.

## Features
- **Multi-format Resume Extraction:** Supports PDF, DOCX, and image files with OCR fallback.
- **Automated Skill & Certification Matching:** Uses customizable reference lists for courses and certifications.
- **Probability-Based Ranking:** Assigns a probability score to each resume for sorting and prioritization.
- **Detailed Output:** Generates CSV, Excel, and JSON reports for further analysis.

## How It Works
1. Place all candidate resumes in the `resumes/` folder.
2. Reference data for courses and certifications is stored in `reference_courses.json` and `reference_certifications.json`.
3. Run the main script to extract, analyze, and rank resumes.
4. Results are saved in `resume_analysis.csv`, `resume_analysis.xlsx`, and `all_resumes_text.json`.

## Setup
1. **Clone the repository:**
	```bash
	git clone <repo-url>
	cd hr-management
	```
2. **Install dependencies:**
	```bash
	pip install -r requirements.txt
	```
3. **Install Tesseract OCR:**
	```bash
	sudo apt-get update
	sudo apt-get install tesseract-ocr
	```
	Ensure the path in `main.py` matches your Tesseract installation.

## Usage
1. Add resumes to the `resumes/` folder.
2. Run the analysis:
	```bash
	python main.py
	```
3. Check the output files:
	- `resume_analysis.csv` and `resume_analysis.xlsx`: Sorted analysis of candidates.
	- `all_resumes_text.json`: Raw extracted text from each resume.

## Customization
- Update `reference_courses.json` and `reference_certifications.json` to match your organization's requirements.
- Modify the analysis logic in `main.py` for advanced matching or scoring.

## Requirements
See `requirements.txt` for all Python dependencies.

## License
This project is licensed under the MIT License.

## Contributors
Shreta Das & Rajiv Rathod