from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase import acreate_client, AsyncClient
from typing import Optional, List
import os
from dotenv import load_dotenv

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase environment variables not set.")

# ----------------------------
# App & Security
# ----------------------------
app = FastAPI(title="Todo App API")
security = HTTPBearer()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ----------------------------
# Pydantic Models
# ----------------------------
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


# ----------------------------
# Auth Dependency
# ----------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Returns:
        user -> Supabase user
        client -> Supabase client scoped to this JWT
    """
    try:
        token = credentials.credentials

        user_client: AsyncClient = await acreate_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

        user_client.postgrest.auth(token)

        user_resp = await user_client.auth.get_user(token)

        if not user_resp.user:
            raise Exception("Invalid user")

        return {"user": user_resp.user, "client": user_client}

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth failed: {str(e)}")


# ----------------------------
# Health Check Endpoint
# ----------------------------
@app.get("/health")
async def health_check():
    try:
        global_client: AsyncClient = await acreate_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

        await (
            global_client
            .table("todos")
            .select("id")
            .limit(1)
            .execute()
        )

        return {"status": "healthy", "database": "connected"}

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )


# ----------------------------
# CRUD Endpoints
# ----------------------------

@app.get("/")
async def root():
    return {"message": "Todo API Running"}


# Create Todo
@app.post("/todos", response_model=TodoResponse)
async def create_todo(todo: TodoCreate, context=Depends(get_current_user)):
    user = context["user"]
    client: AsyncClient = context["client"]

    data = {
        "user_id": user.id,
        "title": todo.title,
        "description": todo.description
    }

    resp = await client.table("todos").insert(data).execute()

    if not resp.data:
        raise HTTPException(status_code=400, detail="Failed to create todo")

    return resp.data[0]


# Get All Todos
@app.get("/todos", response_model=List[TodoResponse])
async def get_todos(context=Depends(get_current_user)):
    user = context["user"]
    client: AsyncClient = context["client"]

    resp = await (
        client
        .table("todos")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )

    return resp.data


# Get Single Todo
@app.get("/todos/{todo_id}", response_model=TodoResponse)
async def get_todo(todo_id: str, context=Depends(get_current_user)):
    user = context["user"]
    client: AsyncClient = context["client"]

    resp = await (
        client
        .table("todos")
        .select("*")
        .eq("id", todo_id)
        .eq("user_id", user.id)
        .single()
        .execute()
    )

    if not resp.data:
        raise HTTPException(status_code=404, detail="Todo not found")

    return resp.data


# Update Todo
@app.put("/todos/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: str, updates: TodoUpdate, context=Depends(get_current_user)):
    user = context["user"]
    client: AsyncClient = context["client"]

    update_data = updates.dict(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    resp = await (
        client
        .table("todos")
        .update(update_data)
        .eq("id", todo_id)
        .eq("user_id", user.id)
        .execute()
    )

    if not resp.data:
        raise HTTPException(status_code=404, detail="Todo not found")

    return resp.data[0]


# Delete Todo
@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: str, context=Depends(get_current_user)):
    user = context["user"]
    client: AsyncClient = context["client"]

    resp = await (
        client
        .table("todos")
        .delete()
        .eq("id", todo_id)
        .eq("user_id", user.id)
        .execute()
    )

    if not resp.data:
        raise HTTPException(status_code=404, detail="Todo not found")

    return {"message": "Todo deleted successfully"}
