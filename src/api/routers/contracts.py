import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import ContractOut
from src.auth.dependencies import RequireAnalyst, RequireViewer
from src.config import settings
from src.database import get_db
from src.models.contract import Contract, ContractClause
from src.parsing.docx_parser import extract_text_from_docx_bytes
from src.parsing.pdf_parser import extract_text_from_pdf_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/", response_model=list[ContractOut], dependencies=[RequireViewer])
async def list_contracts(db: AsyncSession = Depends(get_db)) -> list[Contract]:
    result = await db.execute(select(Contract).order_by(Contract.name))
    return list(result.scalars().all())


@router.post("/upload", response_model=ContractOut, status_code=201, dependencies=[RequireAnalyst])
async def upload_contract(
    file: UploadFile,
    name: str,
    contract_type: str,
    area: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Contract:
    """Upload a contract PDF or DOCX, extract text, split into clauses, and embed."""
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    filename = (file.filename or "").lower()
    try:
        # Parsing is CPU-bound — keep it off the event loop. Never write the
        # client-supplied filename to disk (path traversal).
        if filename.endswith(".pdf"):
            raw_text = await asyncio.to_thread(extract_text_from_pdf_bytes, content)
        elif filename.endswith(".docx"):
            raw_text = await asyncio.to_thread(extract_text_from_docx_bytes, content)
        else:
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {exc}") from exc

    contract = Contract(name=name, contract_type=contract_type, area=area, raw_text=raw_text)
    db.add(contract)
    await db.flush()

    clause_texts = _split_into_clauses(raw_text)
    embeddings = await _embed_or_none(clause_texts)
    for i, clause_text in enumerate(clause_texts):
        db.add(ContractClause(
            contract_id=contract.id,
            clause_ref=f"Clause {i + 1}",
            text=clause_text,
            embedding=embeddings[i] if embeddings else None,
        ))

    return contract


@router.post("/seed", status_code=201, dependencies=[RequireAnalyst])
async def seed_demo_contracts(db: AsyncSession = Depends(get_db)) -> dict:
    """Seed the database with representative sample contracts for demo purposes.

    Idempotent — skips contracts that already exist by name.
    """
    _DEMO = [
        {
            "name": "Master Investment Agreement — Fintech ABC",
            "contract_type": "investment",
            "area": "Legal",
            "clauses": [
                ("Clause 4.2", "The counterparty exposure limit shall not exceed 20% of the total portfolio value. Any modification to applicable leverage limits imposed by regulatory authorities shall trigger an automatic review of this clause."),
                ("Clause 7.1", "Investment fund allocations must comply with the limits established by the applicable regulatory authority for mutual funds and investment vehicles, including any fintech-specific restrictions."),
            ],
        },
        {
            "name": "SOFOM XYZ Loan Portfolio Agreement",
            "contract_type": "loan",
            "area": "Risk",
            "clauses": [
                ("Clause 3.1", "Credit exposure and leverage ratios shall comply with the capital adequacy requirements set forth by the CNBV and Basel III standards. The maximum leverage ratio is established at the regulatory threshold in force at the time of each calculation."),
                ("Clause 5.4", "Capital requirements for the loan portfolio shall be maintained in accordance with Basel/Basilea III guidelines, including minimum common equity tier 1 capital ratios as mandated by the applicable regulatory authority."),
            ],
        },
        {
            "name": "Client Onboarding and AML Policy",
            "contract_type": "onboarding",
            "area": "AML",
            "clauses": [
                ("Section 2.1", "Customer due diligence (CDD) and enhanced due diligence (EDD) procedures must comply with anti-money laundering (AML) and PLD regulations, including FATF/GAFI recommendations and applicable national legislation."),
                ("Section 4.3", "Suspicious activity reports (SAR) and regulatory disclosure obligations must be submitted within the timeframes established by the applicable AML/PLD regulatory framework. All reporting thresholds shall be updated upon regulatory amendment."),
            ],
        },
        {
            "name": "ISDA Derivative Trading Master Agreement",
            "contract_type": "derivative",
            "area": "Treasury",
            "clauses": [
                ("Clause 6.1", "Swap, forward, and option transaction limits shall comply with the derivative exposure rules established by the applicable regulatory authority. Capital requirements for derivative positions follow Basel III standards."),
                ("Clause 8.2", "Leverage and capital adequacy requirements for derivative instruments shall be recalculated upon any regulatory amendment affecting counterparty credit risk, including changes mandated by Basel/Basilea framework updates."),
            ],
        },
        {
            "name": "Data Processing and Privacy Agreement",
            "contract_type": "data_processing",
            "area": "IT",
            "clauses": [
                ("Clause 3.1", "All personal data processing activities must comply with applicable data protection and privacy regulations, including GDPR, LFPDP, and any sector-specific rules governing the handling of personal data in financial services."),
                ("Clause 5.2", "Data subjects' rights and the obligations of the data controller shall be updated upon amendment of the applicable privacy regulatory framework. The data processor shall notify the controller of any regulatory change within 5 business days."),
            ],
        },
        {
            "name": "Fintech Electronic Payment Service Agreement",
            "contract_type": "service",
            "area": "Compliance",
            "clauses": [
                ("Clause 2.3", "Electronic payment processing and crowdfunding activities must comply with the Fintech/ITF Law and any regulations issued by the CNBV or Banxico governing electronic payment institutions and financial technology companies."),
                ("Clause 6.1", "Regulatory reporting, disclosure obligations, and SAR filings shall be performed in accordance with the compliance framework established by the applicable fintech regulatory authority. Reporting thresholds are subject to amendment."),
            ],
        },
    ]

    existing_names = set((await db.execute(select(Contract.name))).scalars().all())
    pending = [spec for spec in _DEMO if spec["name"] not in existing_names]

    # Embed every new clause in one batch so semantic mapping and RAG work on seeds
    all_texts = [text for spec in pending for _, text in spec["clauses"]]
    embeddings = await _embed_or_none(all_texts)
    emb_iter = iter(embeddings) if embeddings else None

    for spec in pending:
        contract = Contract(
            name=spec["name"],
            contract_type=spec["contract_type"],
            area=spec["area"],
            raw_text=" ".join(text for _, text in spec["clauses"]),
        )
        db.add(contract)
        await db.flush()
        for clause_ref, text in spec["clauses"]:
            db.add(ContractClause(
                contract_id=contract.id,
                clause_ref=clause_ref,
                text=text,
                embedding=next(emb_iter) if emb_iter else None,
            ))

    return {"detail": f"{len(pending)} contract(s) seeded", "skipped": len(_DEMO) - len(pending)}


async def _embed_or_none(texts: list[str]) -> list[list[float]] | None:
    """Batch-embed texts in a worker thread; None if the embedder is unavailable."""
    if not texts:
        return None
    try:
        from src.mapping.embedder import embed_batch

        return await asyncio.to_thread(embed_batch, texts)
    except Exception as exc:
        logger.warning("Embedding unavailable — clauses stored without vectors: %s", exc)
        return None


def _split_into_clauses(text: str) -> list[str]:
    """Naive clause splitter: break on double newlines, keep chunks ≥ 50 chars."""
    chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) >= 50]
    return chunks[:200]  # cap at 200 clauses per contract
