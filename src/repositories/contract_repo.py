import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.contract import Contract, ContractClause

logger = logging.getLogger(__name__)


async def create(
    db: AsyncSession,
    name: str,
    contract_type: str,
    area: str | None = None,
    raw_text: str | None = None,
    file_path: str | None = None,
) -> Contract:
    """Create and persist a new Contract record."""
    contract = Contract(
        name=name,
        contract_type=contract_type,
        area=area,
        raw_text=raw_text,
        file_path=file_path,
    )
    db.add(contract)
    await db.flush()
    logger.info("Created contract: %s (%s)", name, contract_type)
    return contract


async def get_by_id(db: AsyncSession, contract_id: uuid.UUID) -> Contract | None:
    """Fetch a Contract by primary key, eager-loading its clauses."""
    result = await db.execute(
        select(Contract)
        .where(Contract.id == contract_id)
        .options(selectinload(Contract.clauses))
    )
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession, limit: int = 100) -> list[Contract]:
    """Return all contracts ordered by name."""
    result = await db.execute(select(Contract).order_by(Contract.name).limit(limit))
    return list(result.scalars().all())


async def get_by_type(db: AsyncSession, contract_type: str) -> list[Contract]:
    """Return contracts whose contract_type matches exactly."""
    result = await db.execute(
        select(Contract)
        .where(Contract.contract_type == contract_type)
        .order_by(Contract.name)
    )
    return list(result.scalars().all())


async def get_by_area(db: AsyncSession, area: str) -> list[Contract]:
    """Return contracts whose area matches exactly."""
    result = await db.execute(
        select(Contract)
        .where(Contract.area == area)
        .order_by(Contract.name)
    )
    return list(result.scalars().all())


async def get_by_types_or_areas(
    db: AsyncSession,
    contract_types: set[str],
    areas: set[str],
) -> list[Contract]:
    """Return contracts whose type is in contract_types OR area is in areas."""
    from sqlalchemy import or_

    conditions = []
    if contract_types:
        conditions.append(Contract.contract_type.in_(contract_types))
    if areas:
        conditions.append(Contract.area.in_(areas))
    if not conditions:
        return []

    result = await db.execute(
        select(Contract).where(or_(*conditions)).order_by(Contract.name)
    )
    return list(result.scalars().all())


async def add_clause(
    db: AsyncSession,
    contract_id: uuid.UUID,
    clause_ref: str,
    text: str,
    embedding: list[float] | None = None,
) -> ContractClause:
    """Append a clause to an existing contract."""
    clause = ContractClause(
        contract_id=contract_id,
        clause_ref=clause_ref,
        text=text,
        embedding=embedding,
    )
    db.add(clause)
    await db.flush()
    return clause
