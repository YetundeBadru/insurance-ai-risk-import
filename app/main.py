from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import audit
from .agent import handle_message
from .extract import extract_claim
from .llm import get_llm
from .metrics import metrics
from .risk_import import import_risks

app = FastAPI(title="Claims Intake & Status Agent (starter)")
llm = get_llm()


class ExtractIn(BaseModel):
    tenant_id: str
    text: str


class ChatIn(BaseModel):
    tenant_id: str
    message: str


@app.post("/extract")
def extract(body: ExtractIn):
    return extract_claim(body.text, llm)


@app.post("/chat")
def chat(body: ChatIn):
    return handle_message(body.tenant_id, body.message)


@app.get("/metrics")
def get_metrics():
    return metrics.summary()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/risk-import")
async def risk_import(tenant_id: str = Form(...), dry_run: bool = Form(False), file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, "file too large (max 5 MB)")
    return import_risks(tenant_id, file.filename or "", raw, llm, dry_run=dry_run)


@app.get("/audit")
def get_audit(tenant_id: str):
    return audit.entries(tenant_id)
