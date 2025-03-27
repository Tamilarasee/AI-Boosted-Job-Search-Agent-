from fastapi import FastAPI, HTTPException, File, UploadFile,Form
from pydantic import BaseModel
from typing import Optional, List
from utils.supabase.db import supabase
import traceback
from api.resume_extraction import extract_pdf_text
from api.search import router as search_router
from io import BytesIO


app = FastAPI()



# Pydantic models for request validation
class UserLogin(BaseModel):
    email: str 
    password: str

class JobSearch(BaseModel):
    title: str
    location: str
    description: Optional[str] = None



@app.post("/auth/login")
async def login(user: UserLogin):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })
        if response.user:
            return {"success": True, "user": response.user}
        raise HTTPException(status_code=401, detail="Login failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/register")
async def register(user: UserLogin):
    try:
        response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password
        })
        if response.user:
            return {"success": True, "user": response.user}
        raise HTTPException(status_code=400, detail="Registration failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/users/details")
async def create_user_details(
    name: str = Form(...), # required field(...),
    resumes: List[UploadFile] = File(...)
):
    try:
        # Process PDFs as before
        resume_data = []
        for resume in resumes:
            if resume.filename.endswith('.pdf'):
                content = await resume.read() # raw bytes (binary data)


    # Create a BytesIO object (in-memory file) from the content
    # This gives us a file-like object we can work with-as needed by pyPDf for processing
                pdf_file = BytesIO(content)
                text = extract_pdf_text(pdf_file)
                resume_data.append(text)

        user_data = {
            "name": name,
            "resumes": resume_data,
            "user_id": supabase.auth.get_user().user.id
        }

        response = supabase.table("users").insert(user_data).execute()

        if response.data:
            return {"success": True, "data": response.data[0]}
        raise HTTPException(status_code=400, detail="Failed to save user details")
   
    except Exception as e:
        
        error_details = traceback.format_exc()
        print(f"Error: {str(e)}\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Error processing resumes: {str(e)}")
    
# @app.post("/search/jobs")
# async def search_jobs(preferences: JobPreferences):
#     try:
#         # Just log and return for now
#         print(f"Received job preferences: {preferences}")
        
#         # We'll implement the actual search later
#         return {"status": "received", "preferences": preferences.model_dump()}
#     except Exception as e:
#         print(f"Error in job search: {str(e)}")
#         raise HTTPException(status_code=500, detail="Failed to process job search")

app.include_router(search_router, prefix="/api")
