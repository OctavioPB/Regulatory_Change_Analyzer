import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import ContractIn, ContractOut
from src.config import settings
from src.database import get_db
from src.mapping.embedder import embed_batch
from src.models.contract import Contract, ContractClause
from src.parsing.docx_parser import extract_text_from_docx
from src.parsing.pdf_parser import extract_text_from_pdf_bytes

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/", response_model=list[ContractOut])
async def list_contracts(db: AsyncSession = Depends(get_db)) -> list[Contract]:
    result = await db.execute(select(Contract).order_by(Contract.name))
    return list(result.scalars().all())


@router.post("/upload", response_model=ContractOut, status_code=201)
async def upload_contract(
    file: UploadFile,
    name: str,
    contract_type: str,
    area: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Contract:
    """Upload a contract PDF or DOCX, extract text, split into clauses, and embed."""
    content = await file.read()
    filename = file.filename or ""

    if filename.lower().endswith(".pdf"):
        raw_text = extract_text_from_pdf_bytes(content)
    elif filename.lower().endswith(".docx"):
        tmp_path = settings.contracts_dir / filename
        tmp_path.write_bytes(content)
        raw_text = extract_text_from_docx(tmp_path)
    else:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    contract = Contract(name=name, contract_type=contract_type, area=area, raw_text=raw_text)
    db.add(contract)
    await db.flush()

    clause_texts = _split_into_clauses(raw_text)
    if clause_texts:
        embeddings = embed_batch(clause_texts)
        for i, (clause_text, embedding) in enumerate(zip(clause_texts, embeddings)):
            clause = ContractClause(
                contract_id=contract.id,
                clause_ref=f"Clause {i + 1}",
                text=clause_text,
                embedding=embedding,
            )
            db.add(clause)

    return contract


def _split_into_clauses(text: str) -> list[str]:
    """Naive clause splitter: break on double newlines, keep chunks ≥ 50 chars."""
    chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) >= 50]
    return chunks[:200]  # cap at 200 clauses per contract
