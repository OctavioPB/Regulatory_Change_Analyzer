"""Seed synthetic CNBV documents for development when dof.gob.mx is unreachable.

Usage:
    python scripts/seed_cnbv.py
"""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import AsyncSessionLocal, init_db
from src.ingestion.base import RawDocument
from src.repositories import audit_repo, document_repo
from src.storage.local_storage import save_processed_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)

_CNBV_SAMPLES = [
    RawDocument(
        external_id="CNBV-seed-001",
        source="CNBV",
        title="Circular 12/2025 — Modificación límites de apalancamiento SOFOM",
        url="https://www.dof.gob.mx/nota_detalle.php?codigo=seed001",
        publication_date=datetime(2025, 3, 20, tzinfo=timezone.utc),
        raw_text=(
            "COMISIÓN NACIONAL BANCARIA Y DE VALORES\n"
            "Circular 12/2025 — Modificaciones a las Disposiciones de Carácter General\n\n"
            "ARTÍCULO 5. El límite de contraparte para operaciones de Sociedades Financieras "
            "de Objeto Múltiple (SOFOM) se reduce del veinte por ciento (20%) al quince por "
            "ciento (15%) del capital neto de la institución.\n\n"
            "ARTÍCULO 6. Las instituciones de crédito deberán ajustar sus sistemas de "
            "administración de riesgos para reflejar el nuevo límite dentro de los noventa "
            "días naturales siguientes a la entrada en vigor de la presente Circular.\n\n"
            "ARTÍCULO 7. Los contratos maestros de operaciones derivadas celebrados con "
            "SOFOMs deberán incluir una cláusula de adaptación automática cuando el "
            "porcentaje de exposición supere el límite establecido en el artículo 5.\n\n"
            "TRANSITORIO ÚNICO. La presente Circular entrará en vigor al día siguiente de "
            "su publicación en el Diario Oficial de la Federación."
        ),
    ),
    RawDocument(
        external_id="CNBV-seed-002",
        source="CNBV",
        title="Circular 15/2025 — Requisitos de reporte PLD/AML para instituciones fintech",
        url="https://www.dof.gob.mx/nota_detalle.php?codigo=seed002",
        publication_date=datetime(2025, 4, 5, tzinfo=timezone.utc),
        raw_text=(
            "COMISIÓN NACIONAL BANCARIA Y DE VALORES\n"
            "Circular 15/2025 — Prevención de Lavado de Dinero (PLD) para Entidades Fintech\n\n"
            "ARTÍCULO 1. Las Instituciones de Tecnología Financiera (ITF) sujetas a la Ley "
            "Fintech deberán implementar controles de antilavado de dinero (AML) equivalentes "
            "a los exigidos a la banca múltiple.\n\n"
            "ARTÍCULO 2. El umbral de reporte de operaciones inusuales se establece en "
            "MXN 50,000 (cincuenta mil pesos) para operaciones en efectivo y MXN 100,000 "
            "(cien mil pesos) para operaciones electrónicas.\n\n"
            "ARTÍCULO 3. Las ITF deberán designar un oficial de cumplimiento certificado "
            "en materia de PLD dentro de los ciento ochenta días naturales siguientes a la "
            "entrada en vigor de esta Circular.\n\n"
            "ARTÍCULO 4. Los contratos de servicio con clientes personas morales deberán "
            "incluir cláusulas de debida diligencia reforzada (DDR) cuando el riesgo "
            "asignado al cliente sea alto conforme a la metodología interna de la institución."
        ),
    ),
    RawDocument(
        external_id="CNBV-seed-003",
        source="CNBV",
        title="Circular 18/2025 — Coeficiente de capital neto Basilea III para banca múltiple",
        url="https://www.dof.gob.mx/nota_detalle.php?codigo=seed003",
        publication_date=datetime(2025, 4, 15, tzinfo=timezone.utc),
        raw_text=(
            "COMISIÓN NACIONAL BANCARIA Y DE VALORES\n"
            "Circular 18/2025 — Requerimientos de Capital Basilea III\n\n"
            "ARTÍCULO 1. El coeficiente de capital neto (CCN) mínimo requerido para "
            "instituciones de banca múltiple se incrementa del diez punto cinco por ciento "
            "(10.5%) al doce por ciento (12%) del total de activos ponderados por riesgo.\n\n"
            "ARTÍCULO 2. El coeficiente de apalancamiento mínimo, conforme a los estándares "
            "del Comité de Supervisión Bancaria de Basilea (BCBS), se establece en el cuatro "
            "por ciento (4%) del capital Tier 1 sobre exposición total.\n\n"
            "ARTÍCULO 3. Las instituciones con déficit de capital deberán presentar un plan "
            "de capitalización ante la CNBV dentro de los treinta días naturales siguientes "
            "a la notificación del incumplimiento.\n\n"
            "ARTÍCULO 4. Los contratos de deuda subordinada computable como capital "
            "complementario deberán ajustarse a los criterios de elegibilidad establecidos "
            "en el Anexo 1-R de las presentes disposiciones."
        ),
    ),
]


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as db:
        seeded = 0
        for raw_doc in _CNBV_SAMPLES:
            existing = await document_repo.get_by_external_id(db, raw_doc.external_id)
            if existing is not None:
                logger.info("Already exists: %s — skipped", raw_doc.external_id)
                continue

            doc = await document_repo.create_from_raw(
                db, raw_doc, raw_text=raw_doc.raw_text or "", file_path=None
            )
            save_processed_text(raw_doc.source, raw_doc.external_id, raw_doc.raw_text or "")
            await audit_repo.log(
                db,
                action="document_seeded",
                entity_type="RegulatoryDocument",
                entity_id=str(doc.id),
                detail=f"synthetic CNBV seed — {raw_doc.external_id}",
            )
            seeded += 1
            logger.info("Seeded: %s", raw_doc.title)

        await db.commit()

    logger.info("Done — %d CNBV documents seeded", seeded)


if __name__ == "__main__":
    asyncio.run(main())
