"""Fill missing embeddings with the configured model (after `alembic upgrade head` or a model change).

    python scripts/reembed.py            # rows with embedding IS NULL
    python scripts/reembed.py --all      # every row (e.g. same dimension, different model)
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from src.config import settings  # noqa: E402
from src.database import AsyncSessionLocal, init_db  # noqa: E402
from src.mapping import embedder  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)

_TABLES = {
    "regulatory_changes": "coalesce(new_text, summary, '')",
    "contract_clauses": "text",
}
_BATCH = 32
_MAX_CHARS = 2000  # same cap as ingestion (nlp_service, contracts router)


async def main(all_rows: bool) -> int:
    await init_db()
    if not embedder.available():
        logger.error("No embedding backend (%s / %s) — is Ollama running and the model pulled?",
                     settings.embedding_provider, settings.embedding_model)
        return 1
    async with AsyncSessionLocal() as db:
        for table, expr in _TABLES.items():
            where = "" if all_rows else "WHERE embedding IS NULL"
            rows = (await db.execute(text(f"SELECT id, {expr} AS body FROM {table} {where}"))).fetchall()
            for i in range(0, len(rows), _BATCH):
                batch = rows[i:i + _BATCH]
                vectors = await asyncio.to_thread(embedder.embed_batch, [(r.body or " ")[:_MAX_CHARS] for r in batch])
                for r, v in zip(batch, vectors):
                    await db.execute(text(f"UPDATE {table} SET embedding = CAST(:v AS vector) WHERE id = :id"),
                                     {"v": embedder.vector_literal(v), "id": r.id})
            await db.commit()
            logger.info("%s: %d rows embedded with %s", table, len(rows), settings.embedding_model)
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--all", action="store_true", help="re-embed every row, not only missing ones")
    sys.exit(asyncio.run(main(p.parse_args().all)))
