import pandas as pd
import io
import uuid
from fastapi import FastAPI, File, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from typing import Annotated, Optional
from pydantic import BaseModel

from core.supervisor_agent import supervisor_agent
from utils.utility_functions import upload_file_to_supabase
from db.database import db, engine

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:8001", "http://localhost:8002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatResponse(BaseModel):
    session_id: str
    response: str  # or dict, depending on your response format
    is_new_session: bool
    message: Optional[str] = None


@app.post("/Chat", response_model=ChatResponse)
async def chat(
        query: Annotated[str, "Enter your query:"],
        file: Optional[UploadFile] = File(None),
        session_id: Annotated[Optional[str], Header()] = None
):
    """
    Chat endpoint with session management.

    Session Management:
    - If session_id is None: Create new session
    - If session_id is provided: Use existing session for context
    """

    is_new_session = False

    try:
        if not session_id or session_id.strip() == "":
            session_id = str(uuid.uuid4())
            is_new_session = True
            print(f"NEW SESSION CREATED: {session_id}")
        else:
            is_new_session = False
            print(f"CONTINUING SESSION: {session_id}")

        file_url = None

        try:
            if file is not None:
                file_url = upload_file_to_supabase(file, order_id=session_id)
        except Exception as e:
            return ChatResponse(
                session_id=session_id,
                response="",
                is_new_session=is_new_session,
                message=f"File upload failed: {str(e)}"
            )

        supervisor_input = f"Session ID: {session_id} | User Query: {query}"

        if file_url:
            supervisor_input += f" | FileURL: {file_url}"

        try:
            result = supervisor_agent.invoke(
                {"messages": [{"role": "user", "content": supervisor_input}]},
                {"configurable": {"thread_id": session_id}},
            )
        except Exception as e:
            return ChatResponse(
                session_id=session_id,
                response="",
                is_new_session=is_new_session,
                message=f"LLM service error: {str(e)}"
            )

        response_content = result["messages"][-1].content if hasattr(result["messages"][-1], 'content') else str(
            result["messages"][-1])

        if is_new_session:
            message = f"New session started! Response generated for: {query}"
        else:
            message = f"Response generated for: {query}"

        return ChatResponse(
            session_id=session_id,
            response=response_content,
            is_new_session=is_new_session,
            message=message
        )

    except Exception as e:
        return ChatResponse(
            session_id=session_id if session_id else str(uuid.uuid4()),
            response="",
            is_new_session=is_new_session,
            message=f"Unexpected error: {str(e)}"
        )



@app.post("/uploadfile/")
async def create_upload_file(file: Annotated[UploadFile, File(description="Upload a csv or excel file")],table_name: Annotated[str, "Enter your table name:"] = "Ecommerce_Data"):
    try:
        file_type = file.filename
        file_type = file_type.split('.')[-1]

        if file_type == 'csv':
            contents = await file.read()
            df = pd.read_csv(io.BytesIO(contents))
        elif file_type in ['xlsx', 'xls']:
            contents = await file.read()
            df = pd.read_excel(io.BytesIO(contents))
        else:
            return {"message": "Please upload a csv or excel file"}

        df.to_sql(table_name, con=engine, if_exists="replace", index=False)

        return {"message": "Your file is uploaded successfully"}

    except Exception as e:
        return f"Got an error:{e}"


@app.get("/check")
async def check():
    return {"Tables": db.get_usable_table_names()}

@app.get("/ViewData")
async def view_data(db_name: Annotated[str, "Enter your database name:"] = "Ecommerce_Data"):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {db_name} LIMIT 5"))
            rows = result.fetchall()
            columns = result.keys()

        data = [dict(zip(columns, row)) for row in rows]

        return {"data": data}

    except Exception as e:
        return f"Got an error:{e}"

@app.post("/ClearData")
async def clear_data(table_name: Annotated[str, "Enter your table name:"]):
    try:
        with engine.connect() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table_name}"))
            conn.commit()

        return {"message": f"Table {table_name} data has been cleared successfully."}

    except Exception as e:
        return f"Got an error:{e}"

@app.post("/Orders")
def orders(user_id: Annotated[str, "Enter your user id:"]):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT order_id,product_name FROM orders where user_id = {user_id}"))
            rows = result.fetchall()
            columns = result.keys()

        data = [dict(zip(columns, row)) for row in rows]

        if not data:
            return "I could not found any orders wrt this user id, please enter a valid user id"

        return {"data": data}

    except Exception as e:
        return f"Got an error:{e}"

@app.post("/check_complaints")
def check_complaints(order_id: Annotated[str, "Enter your order_id:"]):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT order_id,product_name,complaint_text,complaint_file_url FROM orders where order_id = '{order_id}' AND is_complaint = 1"))
            rows = result.fetchall()
            columns = result.keys()

        data = [dict(zip(columns, row)) for row in rows]

        return {"data": data}

    except Exception as e:
        return f"Got an error:{e}"