from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------
# Config
# --------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase environment variables not set.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Todo App API")
security = HTTPBearer()

# --------------------------------------------------
# Health Check Endpoint
# --------------------------------------------------

@app.get("/health")
def health_check():
    """
    Checks:
    - Backend is running
    - Supabase client is initialized
    - Database connection works
    """

    try:
        # Lightweight query to test DB connectivity
        response = supabase.table("todos").select("id").limit(1).execute()

        return {
            "status": "healthy",
            "database": "connected",
            "supabase_url": SUPABASE_URL
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )

# --------------------------------------------------
# Models
# --------------------------------------------------

class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None

class TodoUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    completed: Optional[bool]

class TodoResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    completed: bool
    created_at: str

# --------------------------------------------------
# Auth Dependency
# --------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        token = credentials.credentials

        # Create a user-scoped Supabase client
        user_supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        user_supabase.postgrest.auth(token)

        user = user_supabase.auth.get_user(token)

        return {
            "user": user.user,
            "client": user_supabase
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# --------------------------------------------------
# Routes
# --------------------------------------------------

@app.get("/")
def root():
    return {"message": "API Running"}

@app.post("/todos", response_model=TodoResponse)
def create_todo(todo: TodoCreate, context=Depends(get_current_user)):

    user = context["user"]
    client = context["client"]

    data = {
        "user_id": user.id,
        "title": todo.title,
        "description": todo.description
    }

    response = client.table("todos").insert(data).execute()

    return response.data[0]

@app.get("/todos", response_model=List[TodoResponse])
def get_todos(context=Depends(get_current_user)):
    user = context["user"]
    client = context["client"]

    response = (
        client
        .table("todos")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )

    return response.data
