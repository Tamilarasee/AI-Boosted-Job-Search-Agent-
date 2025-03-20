from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from utils.supabase.db import supabase
import requests


app = FastAPI()

# Pydantic models for request validation
class UserLogin(BaseModel):
    email: str
    password: str

class UserDetails(BaseModel):
    name: str
    resumes: str
    preferences: Optional[str] = None
    target_roles: Optional[str] = None

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
async def create_user_details(details: UserDetails):
    try:
        response = supabase.table("users").insert(details.model_dump()).execute()
        if response.data:
            return {"success": True, "data": response.data[0]}
        raise HTTPException(status_code=400, detail="Failed to save user details")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@app.post("/jobs/search")
async def search_jobs(search: JobSearch):
    try:
        url = "https://linkedin-jobs-api2.p.rapidapi.com/active-jb-24h"
        
        querystring = {
            "title_filter": search.title,
            "location_filter": search.location,
            "description_filter": search.description if search.description else search.title,
            "description_type": "text"
        }
        
        headers = {
            "x-rapidapi-key": "cded3f121emsh2724131035ba867p1f62c6jsn16c0d2cc37f6",
            "x-rapidapi-host": "linkedin-jobs-api2.p.rapidapi.com"
        }
        
        response = requests.get(url, headers=headers, params=querystring)
        
        # Check if the request was successful
        if response.status_code == 200:
            return {"success": True, "jobs": response.json()}
        else:
            raise HTTPException(status_code=response.status_code, 
                               detail=f"API request failed: {response.text}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jobs: {str(e)}")
