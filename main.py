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
import re
import openai  # For GPT correction (requires OPENAI_API_KEY env var)
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import spacy
from dateutil import parser

# ------------------- CONFIG -------------------
RESUME_FOLDER = "resumes"
OUTPUT_JSON = "all_resumes_text.json"
OUTPUT_CSV = "resume_analysis.csv"
OUTPUT_XLSX = "resume_analysis.xlsx"

# Tesseract OCR path
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Initialize NLP models
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("⚠️ SpaCy model not found. Run: python -m spacy download en_core_web_sm")
    nlp = None

# Initialize NLTK
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

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
    return text.strip()

def gpt_correct_fields(fields, raw_text):
    """
    Use GPT to validate and correct extracted fields from resume text.
    Requires OPENAI_API_KEY to be set in environment.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    org_id = os.getenv("OPENAI_ORG_ID")
    if not api_key:
        print("⚠️ OPENAI_API_KEY not set. Skipping GPT correction.")
        return fields
    
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=api_key)
        if org_id:
            client.organization = org_id
            
        prompt = f"""
        Extract and correct the following information from this resume text. Return ONLY a JSON object with these exact fields:
        
        {{
            "Name": "Full name of the person",
            "Programme": "Academic program/course (e.g., B.Tech, M.Tech, etc.)",
            "Batch": "Year or batch (e.g., 2021-2025, 2023, etc.)",
            "Major_Specialization": "Main field of study",
            "Minor_Specialization": "Secondary field if any",
            "Professional_Summary": "Brief professional summary",
            "Education": [
                {{
                    "Level": "UG/PG/Diploma/HSC/SSC",
                    "Degree": "Degree name",
                    "Board_University": "Institution name",
                    "Specialization": "Field of study",
                    "CGPA_Percentage": "Score",
                    "Passing_Year": "Year"
                }}
            ],
            "Projects": [
                {{
                    "Title": "Project name",
                    "Organization": "If any",
                    "Period": "Duration",
                    "Description": "What the project involved"
                }}
            ],
            "Certificates": [
                {{
                    "Title": "Certificate name",
                    "Issuing_Authority": "Who issued it",
                    "Year": "When received",
                    "Remarks": "Additional info"
                }}
            ],
            "CoCurricular": "Co-curricular activities",
            "ExtraCurricular": "Extra-curricular activities",
            "Top_Core_Skills": ["skill1", "skill2", "skill3"],
            "Top_People_Skills": ["skill1", "skill2", "skill3"],
            "Top_Tech_Skills": ["skill1", "skill2", "skill3"],
            "Work_Experience": [
                {{
                    "Organization": "Company name",
                    "Role": "Job title",
                    "Duration": "Time period",
                    "Responsibilities": "What they did"
                }}
            ]
        }}
        
        Resume Text:
        {raw_text[:3000]}...
        
        Return only the JSON object, no other text.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        
        # Clean the response to extract JSON
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        corrected = json.loads(content)
        return corrected
    except Exception as e:
        print(f"GPT correction error: {e}")
        return fields

def extract_fields_from_text(text, filename):
    """
    Use advanced NLP and pattern matching to extract required fields from resume text.
    Returns a dict of all required fields.
    """
    # Initialize all fields with default structure
    fields = {
        "Name": "",
        "Programme": "",
        "Batch": "",
        "Major_Specialization": "",
        "Minor_Specialization": "",
        "Professional_Summary": "",
        "Education": [],
        "Projects": [],
        "Certificates": [],
        "CoCurricular": "",
        "ExtraCurricular": "",
        "Top_Core_Skills": [],
        "Top_People_Skills": [],
        "Top_Tech_Skills": [],
        "Work_Experience": []
    }
    
    # Clean text for processing
    text_lines = text.split('\n')
    text_lower = text.lower()
    
    # Extract Name (try multiple approaches)
    name = extract_name(text, filename)
    if name:
        fields["Name"] = name
    
    # Extract Programme/Course
    programme_patterns = [
        r'b\.?tech|bachelor of technology|bachelor.*engineering',
        r'm\.?tech|master of technology|master.*engineering',
        r'b\.?e\.?|bachelor of engineering',
        r'm\.?e\.?|master of engineering',
        r'artificial intelligence|ai|data science|computer science|electronics|mechanical|civil'
    ]
    for pattern in programme_patterns:
        match = re.search(pattern, text_lower)
        if match:
            # Extract the full programme name from the context
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end]
            fields["Programme"] = context.strip()[:100]  # Limit length
            break
    
    # Extract Batch/Year
    year_pattern = r'(20\d{2})\s*[-–—]\s*(20\d{2})|batch.*?(20\d{2})|year.*?(20\d{2})'
    year_matches = re.findall(year_pattern, text_lower)
    if year_matches:
        for match in year_matches:
            year_info = [y for y in match if y]
            if len(year_info) >= 2:
                fields["Batch"] = f"{year_info[0]}-{year_info[1]}"
                break
            elif year_info:
                fields["Batch"] = year_info[0]
    
    # Extract Specializations
    specialization_keywords = [
        'artificial intelligence', 'machine learning', 'data science', 'computer science',
        'electronics', 'mechanical', 'civil', 'aiml', 'ai&ds', 'cse', 'it', 'software'
    ]
    for keyword in specialization_keywords:
        if keyword in text_lower:
            if not fields["Major_Specialization"]:
                fields["Major_Specialization"] = keyword.title()
            elif keyword != fields["Major_Specialization"].lower():
                fields["Minor_Specialization"] = keyword.title()
                break
    
    # Extract Education with better parsing
    education_entries = extract_education(text)
    fields["Education"] = education_entries
    
    # Extract Projects
    projects = extract_projects(text)
    fields["Projects"] = projects
    
    # Extract Certificates
    certificates = extract_certificates(text)
    fields["Certificates"] = certificates
    
    # Extract Skills
    core_skills, people_skills, tech_skills = extract_skills(text)
    fields["Top_Core_Skills"] = core_skills
    fields["Top_People_Skills"] = people_skills
    fields["Top_Tech_Skills"] = tech_skills
    
    # Extract Work Experience
    work_exp = extract_work_experience(text)
    fields["Work_Experience"] = work_exp
    
    # Extract Activities
    co_curr, extra_curr = extract_activities(text)
    fields["CoCurricular"] = co_curr
    fields["ExtraCurricular"] = extra_curr
    
    # Extract Professional Summary
    summary = extract_professional_summary(text)
    fields["Professional_Summary"] = summary
    
    return fields

def extract_name(text, filename):
    """Extract name from text or filename"""
    # Try to extract from filename first
    if filename:
        # Remove common suffixes and clean filename
        name_from_file = filename.replace('.pdf', '').replace('.docx', '')
        name_from_file = re.sub(r'[_-].*', '', name_from_file)  # Remove everything after _ or -
        name_from_file = re.sub(r'[^a-zA-Z\s]', ' ', name_from_file)  # Remove non-letters
        name_from_file = ' '.join(name_from_file.split())  # Clean whitespace
        if len(name_from_file.split()) >= 2:
            return name_from_file.title()
    
    # Try to extract from text
    lines = text.split('\n')[:10]  # Check first 10 lines
    for line in lines:
        line = line.strip()
        # Look for name patterns
        if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', line) and len(line.split()) <= 4:
            return line
    
    return ""

def extract_education(text):
    """Extract education information"""
    education = []
    
    # Common education levels and patterns
    education_patterns = [
        (r'ssc|10th|tenth|secondary', 'SSC'),
        (r'hsc|12th|twelfth|higher secondary|\+2', 'HSC'),
        (r'diploma', 'Diploma'),
        (r'b\.?tech|bachelor|graduation|undergraduate|ug', 'UG'),
        (r'm\.?tech|master|postgraduate|pg', 'PG')
    ]
    
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for pattern, level in education_patterns:
            if re.search(pattern, line_lower):
                # Extract education details from this line and nearby lines
                context_lines = lines[max(0, i-2):min(len(lines), i+3)]
                context = ' '.join(context_lines)
                
                # Extract CGPA/Percentage
                cgpa_match = re.search(r'(\d+\.?\d*)\s*%|(\d+\.?\d*)\s*(cgpa|gpa)', context.lower())
                cgpa = ""
                if cgpa_match:
                    cgpa = cgpa_match.group(1) or cgpa_match.group(2)
                
                # Extract year
                year_match = re.search(r'20\d{2}', context)
                year = year_match.group(0) if year_match else ""
                
                # Extract institution
                institution = ""
                for ctx_line in context_lines:
                    if any(word in ctx_line.lower() for word in ['university', 'college', 'school', 'institute']):
                        institution = ctx_line.strip()[:100]
                        break
                
                education.append({
                    "Level": level,
                    "Degree": line.strip()[:100],
                    "Board_University": institution,
                    "Specialization": "",
                    "CGPA_Percentage": cgpa,
                    "Passing_Year": year
                })
                break
    
    return education

def extract_projects(text):
    """Extract project information"""
    projects = []
    
    # Look for project sections
    project_keywords = ['project', 'capstone', 'thesis', 'dissertation']
    lines = text.split('\n')
    
    in_project_section = False
    current_project = {
        "Title": "",
        "Organization": "",
        "Period": "",
        "Description": ""
    }
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # Check if we're entering a project section
        if any(keyword in line_lower for keyword in project_keywords) and ':' in line:
            in_project_section = True
            if current_project["Title"]:  # Save previous project
                projects.append(current_project.copy())
            current_project = {
                "Title": line_stripped,
                "Organization": "",
                "Period": "",
                "Description": ""
            }
            continue
        
        # If we're in a project section, collect information
        if in_project_section and line_stripped:
            if 'organization' in line_lower or 'company' in line_lower:
                current_project["Organization"] = line_stripped
            elif re.search(r'20\d{2}', line):
                current_project["Period"] = line_stripped
            else:
                current_project["Description"] += " " + line_stripped
        
        # Check if section ended
        if in_project_section and (line_stripped == "" or any(section in line_lower for section in ['education', 'experience', 'skills', 'certificate'])):
            if current_project["Title"]:
                projects.append(current_project.copy())
                current_project = {
                    "Title": "",
                    "Organization": "",
                    "Period": "",
                    "Description": ""
                }
            in_project_section = False
    
    # Add last project if exists
    if current_project["Title"]:
        projects.append(current_project)
    
    return projects[:5]  # Limit to 5 projects

def extract_certificates(text):
    """Extract certification information"""
    certificates = []
    
    cert_keywords = ['certificate', 'certification', 'certified', 'course completed']
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in cert_keywords):
            # Extract certificate details
            context_lines = lines[max(0, i-1):min(len(lines), i+3)]
            context = ' '.join(context_lines)
            
            # Extract year
            year_match = re.search(r'20\d{2}', context)
            year = year_match.group(0) if year_match else ""
            
            # Extract issuing authority
            authority = ""
            for auth in ['google', 'microsoft', 'ibm', 'aws', 'coursera', 'udemy', 'linkedin']:
                if auth in line_lower:
                    authority = auth.title()
                    break
            
            certificates.append({
                "Title": line.strip()[:150],
                "Issuing_Authority": authority,
                "Year": year,
                "Remarks": ""
            })
    
    return certificates[:10]  # Limit to 10 certificates

def extract_skills(text):
    """Extract and categorize skills"""
    # Define skill categories
    tech_skills_keywords = [
        'python', 'java', 'javascript', 'html', 'css', 'react', 'node.js', 'sql',
        'tensorflow', 'pytorch', 'opencv', 'pandas', 'numpy', 'scikit-learn',
        'aws', 'azure', 'docker', 'kubernetes', 'git', 'github', 'linux'
    ]
    
    core_skills_keywords = [
        'machine learning', 'data analysis', 'artificial intelligence', 'deep learning',
        'data science', 'computer vision', 'nlp', 'algorithm', 'database design',
        'software development', 'web development', 'mobile development'
    ]
    
    people_skills_keywords = [
        'leadership', 'teamwork', 'communication', 'problem solving', 'analytical',
        'creative', 'time management', 'project management', 'presentation',
        'collaboration', 'adaptability', 'critical thinking'
    ]
    
    text_lower = text.lower()
    
    # Extract skills from each category
    tech_skills = [skill for skill in tech_skills_keywords if skill in text_lower]
    core_skills = [skill for skill in core_skills_keywords if skill in text_lower]
    people_skills = [skill for skill in people_skills_keywords if skill in text_lower]
    
    return core_skills[:5], people_skills[:5], tech_skills[:8]

def extract_work_experience(text):
    """Extract work experience"""
    work_exp = []
    
    # Look for experience section
    exp_keywords = ['experience', 'internship', 'job', 'work', 'employment']
    lines = text.split('\n')
    
    in_exp_section = False
    current_exp = {
        "Organization": "",
        "Role": "",
        "Duration": "",
        "Responsibilities": ""
    }
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # Check if we're entering experience section
        if any(keyword in line_lower for keyword in exp_keywords) and (':' in line or line_stripped.isupper()):
            in_exp_section = True
            continue
        
        # If we're in experience section
        if in_exp_section and line_stripped:
            # Look for company patterns
            if any(word in line_lower for word in ['company', 'organization', 'corp', 'ltd', 'inc']):
                if current_exp["Organization"]:  # Save previous experience
                    work_exp.append(current_exp.copy())
                current_exp = {
                    "Organization": line_stripped,
                    "Role": "",
                    "Duration": "",
                    "Responsibilities": ""
                }
            elif re.search(r'20\d{2}', line):
                current_exp["Duration"] = line_stripped
            elif any(role in line_lower for role in ['intern', 'developer', 'analyst', 'engineer', 'manager']):
                current_exp["Role"] = line_stripped
            else:
                current_exp["Responsibilities"] += " " + line_stripped
        
        # Check if section ended
        if in_exp_section and any(section in line_lower for section in ['education', 'project', 'skills', 'certificate']):
            if current_exp["Organization"]:
                work_exp.append(current_exp.copy())
                current_exp = {
                    "Organization": "",
                    "Role": "",
                    "Duration": "",
                    "Responsibilities": ""
                }
            in_exp_section = False
    
    # Add last experience if exists
    if current_exp["Organization"]:
        work_exp.append(current_exp)
    
    return work_exp[:5]  # Limit to 5 experiences

def extract_activities(text):
    """Extract co-curricular and extra-curricular activities"""
    co_curricular = ""
    extra_curricular = ""
    
    lines = text.split('\n')
    activity_keywords = ['co-curricular', 'extra-curricular', 'activities', 'achievements', 'volunteer']
    
    in_activity_section = False
    current_activities = []
    
    for line in lines:
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in activity_keywords):
            in_activity_section = True
            continue
        
        if in_activity_section and line.strip():
            current_activities.append(line.strip())
        elif in_activity_section and not line.strip():
            break
    
    activities_text = ' '.join(current_activities)
    
    # Split into co-curricular and extra-curricular based on keywords
    if 'co-curricular' in activities_text.lower():
        co_curricular = activities_text
    else:
        extra_curricular = activities_text
    
    return co_curricular[:500], extra_curricular[:500]

def extract_professional_summary(text):
    """Extract professional summary or objective"""
    summary_keywords = ['summary', 'objective', 'profile', 'about']
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in summary_keywords) and len(line.strip()) < 50:
            # Get next few lines as summary
            summary_lines = []
            for j in range(i+1, min(len(lines), i+5)):
                if lines[j].strip() and not any(section in lines[j].lower() for section in ['education', 'experience', 'skills']):
                    summary_lines.append(lines[j].strip())
                else:
                    break
            return ' '.join(summary_lines)[:500]
    
    return ""


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

    print(f"📁 Found {len(resume_files)} resume files to process\n")

    # Extract text and fields
    for i, file_path in enumerate(resume_files, 1):
        filename = os.path.basename(file_path)
        print(f"📄 Processing ({i}/{len(resume_files)}): {filename}")
        
        text = extract_text_from_resume(file_path)
        print(f"   📝 Extracted {len(text)} characters")
        
        if text:
            all_text[filename] = text
            
            # NLP/regex extraction
            fields = extract_fields_from_text(text, filename)
            print(f"   🔍 Extracted basic fields")
            
            # GPT correction if available
            fields = gpt_correct_fields(fields, text)
            
            # Flatten for CSV with proper structure
            flat = {
                "Candidate": filename,
                "Name": fields.get("Name", ""),
                "Programme": fields.get("Programme", ""),
                "Batch": fields.get("Batch", ""),
                "Major_Specialization": fields.get("Major_Specialization", ""),
                "Minor_Specialization": fields.get("Minor_Specialization", ""),
                "Professional_Summary": fields.get("Professional_Summary", "")[:300],  # Limit length
                "CoCurricular": fields.get("CoCurricular", "")[:200],
                "ExtraCurricular": fields.get("ExtraCurricular", "")[:200],
                "Top_Core_Skills": ", ".join(fields.get("Top_Core_Skills", [])),
                "Top_People_Skills": ", ".join(fields.get("Top_People_Skills", [])),
                "Top_Tech_Skills": ", ".join(fields.get("Top_Tech_Skills", [])),
            }
            
            # Education - create readable format
            education_str = ""
            for edu in fields.get("Education", []):
                edu_line = f"{edu.get('Level', '')} - {edu.get('Degree', '')} from {edu.get('Board_University', '')} ({edu.get('CGPA_Percentage', '')} - {edu.get('Passing_Year', '')})"
                education_str += edu_line + "; "
            flat["Education"] = education_str.strip("; ")
            
            # Projects - create readable format
            projects_str = ""
            for proj in fields.get("Projects", []):
                proj_line = f"{proj.get('Title', '')} ({proj.get('Period', '')}) - {proj.get('Description', '')[:100]}"
                projects_str += proj_line + "; "
            flat["Projects"] = projects_str.strip("; ")
            
            # Certificates - create readable format
            certs_str = ""
            for cert in fields.get("Certificates", []):
                cert_line = f"{cert.get('Title', '')} by {cert.get('Issuing_Authority', '')} ({cert.get('Year', '')})"
                certs_str += cert_line + "; "
            flat["Certificates"] = certs_str.strip("; ")
            
            # Work Experience - create readable format
            work_str = ""
            for work in fields.get("Work_Experience", []):
                work_line = f"{work.get('Role', '')} at {work.get('Organization', '')} ({work.get('Duration', '')}) - {work.get('Responsibilities', '')[:100]}"
                work_str += work_line + "; "
            flat["Work_Experience"] = work_str.strip("; ")
            
            results.append(flat)
            print(f"   ✅ Processed successfully\n")
        else:
            print(f"   ❌ No text extracted\n")

    print(f"💾 Saving results...")

    # Save raw text
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_text, f, indent=4, ensure_ascii=False)
    print(f"✅ Raw text saved to {OUTPUT_JSON}")

    # Save structured analysis
    if results:
        df = pd.DataFrame(results)
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
        df.to_excel(OUTPUT_XLSX, index=False, engine='openpyxl')
        print(f"✅ Analysis saved to {OUTPUT_CSV} & {OUTPUT_XLSX}")
        print(f"📊 Processed {len(results)} resumes successfully")
    else:
        print("❌ No results to save")

if __name__ == "__main__":
    main()
