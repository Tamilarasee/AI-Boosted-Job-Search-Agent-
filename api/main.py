from fastapi import FastAPI, HTTPException, File, UploadFile,Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from utils.supabase.db import supabase
import requests
from api.resume_extraction import extract_pdf_text
from api.search_jobs import router as search_router
from io import BytesIO


app = FastAPI()



# Pydantic models for request validation
class UserLogin(BaseModel):
    email: str 
    password: str

class UserDetails(BaseModel):
    name: str = Form(...)
    resume_files: List[UploadFile] = File(...)

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
    name: str = Form(...),
    resumes: List[UploadFile] = File(...),
    token: str = Form(None)  # Optional auth token
):
    try:
        # Process PDFs as before
        resume_data = []
        for resume in resumes:
            await resume.seek(0)
            content = await resume.read()
            pdf_file = BytesIO(content)
            text = extract_pdf_text(pdf_file)
            resume_data.append(text)

        user_data = {
            "name": name,
            "resumes": resume_data
        }

        # Use authenticated client if token is provided
        if token:
            # Create a new Supabase client with the user's token
            from utils.supabase.db import create_client, url
            auth_client = create_client(url, token)
            response = auth_client.table("users").insert(user_data).execute()
        else:
            # For development/testing, you could disable RLS in Supabase
            response = supabase.table("users").insert(user_data).execute()

        if response.data:
            return {"success": True, "data": response.data[0]}
        raise HTTPException(status_code=400, detail="Failed to save user details")
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error: {str(e)}\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Error processing resumes: {str(e)}")
    

app.include_router(search_router, prefix="/api/search", tags=["search"])
