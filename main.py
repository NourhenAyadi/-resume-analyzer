import os
import tempfile
import json
import fitz  # PyMuPDF
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import groq

# Load environment variables
load_dotenv(dotenv_path="../.env") # Access the chatbot_moliere .env if reasonable
# Fallback if no .env is found or key is missing.
api_key = os.getenv("GROQ_API_KEY")

# Initialize FastAPI app
app = FastAPI(title="Resume Analyzer AI")

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Initialize Groq client
if api_key:
    client = groq.Groq(api_key=api_key)
else:
    client = None

def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def analyze_resume_with_ai(resume_text: str):
    if not client:
        return {
            "Skills": ["N/A"],
            "Strengths": ["N/A"],
            "Weaknesses": ["API Key not found"],
            "Score": 0
        }
    
    prompt = f"""
    Analyze the following resume text and provide the candidate's core skills, strengths, weaknesses, and a score out of 100 based on the quality and completeness of the resume. 
    You MUST return the output ONLY as a valid JSON object with EXACTLY these keys: "Skills" (list of strings), "Strengths" (list of strings), "Weaknesses" (list of strings), "Score" (integer).
    
    Resume Text:
    {resume_text[:4000]}  # limit text to avoid token limits just in case
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama3-8b-8192", 
            response_format={"type": "json_object"},
        )
        content = chat_completion.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error during AI analysis: {e}")
        return {
            "Skills": [],
            "Strengths": [],
            "Weaknesses": [f"Error during analysis: {str(e)}"],
            "Score": 0
        }

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze")
async def analyze_resume(file: UploadFile = File(...)):
    # Save file temporarily
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as f:
        f.write(await file.read())
    
    # Extract text from the saved PDF
    resume_text = extract_text_from_pdf(file_location)
    
    if not resume_text.strip():
         return {"error": "Could not extract text from the provided PDF."}
         
    # Analyze the extracted text using Groq LLM
    analysis_result = analyze_resume_with_ai(resume_text)
    
    # Return the clean structured data
    return analysis_result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
