"""
api/assess.py — Risk assessment endpoint.

Streams Server-Sent Events as the pipeline progresses:
  started          -> assessment has begun
  collector_update -> a data source started / finished / errored
  profile_ready    -> final structured risk profile
  error            -> something went wrong (stream still closes cleanly)
  done             -> stream complete

Timeout hierarchy (all configurable via config.py / .env):
  ASSESSMENT_TIMEOUT_SECS  overall hard ceiling
    COLLECTOR_TIMEOUT_SECS   per data source
    LLM_TIMEOUT_SECS         Claude structuring step
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from collectors import get_collectors_for_jurisdiction
from config import ASSESSMENT_TIMEOUT_SECS, COLLECTOR_TIMEOUT_SECS, LLM_TIMEOUT_SECS
from llm import structure_with_llm
from types_ import CollectorStatus, CollectorUpdate, CompanyQuery, RawCollectorData

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/assess")
async def assess_company(query: CompanyQuery) -> StreamingResponse:
    return StreamingResponse(
        _assessment_stream(query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Stream orchestrator ────────────────────────────────────────────────────────

async def _assessment_stream(query: CompanyQuery) -> AsyncGenerator[str, None]:
    """
    Top-level SSE generator.

    Wraps the entire pipeline in asyncio.wait_for() for a hard timeout.
    Uses a shared queue so events still stream progressively to the browser
    rather than buffering until the pipeline completes.

    Always emits 'done' — even on timeout or error — so the browser
    knows the stream has closed.
    """
    def sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    # Shared queue between the pipeline producer and this consumer.
    # None is used as a sentinel to signal the producer is finished.
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def producer() -> None:
        """Runs the pipeline and feeds every SSE chunk into the queue."""
        try:
            async for chunk in _run_pipeline(query, sse):
                await queue.put(chunk)
        except Exception as e:
            logger.error("[assess] pipeline error: %s", e)
            await queue.put(sse({"type": "error", "payload": {"message": "An unexpected error occurred."}}))
        finally:
            await queue.put(None)  # sentinel — consumer will stop here

    async def consumer() -> AsyncGenerator[str, None]:
        """Drains the queue and yields each chunk."""
        while True:
            item = await queue.get()
            if item is None:
                return
            yield item

    yield sse({"type": "started"})

    task = asyncio.create_task(producer())

    try:
        # apply the hard ceiling to the consumer — when it times out,
        # the producer task is cancelled and we emit the timeout error
        async for chunk in asyncio.timeout_at(
            asyncio.get_event_loop().time() + ASSESSMENT_TIMEOUT_SECS,
            consumer().__aiter__()
        ) if False else _consume_with_timeout(consumer(), ASSESSMENT_TIMEOUT_SECS):
            yield chunk

    except asyncio.TimeoutError:
        task.cancel()
        logger.warning("[assess] timed out after %ss — %s", ASSESSMENT_TIMEOUT_SECS, query.model_dump())
        yield sse({
            "type": "error",
            "payload": {
                "message": (
                    f"Assessment timed out after {int(ASSESSMENT_TIMEOUT_SECS)} seconds. "
                    "Some data sources may be slow — please try again."
                )
            },
        })
    except Exception as e:
        task.cancel()
        logger.error("[assess] stream error: %s", e)
        yield sse({"type": "error", "payload": {"message": "An unexpected error occurred."}})
    finally:
        yield sse({"type": "done"})


async def _consume_with_timeout(
    gen: AsyncGenerator[str, None],
    timeout_secs: float,
) -> AsyncGenerator[str, None]:
    """
    Wraps an async generator with a per-item deadline using asyncio.wait_for.
    Raises asyncio.TimeoutError if any item takes longer than timeout_secs total.

    This is the reliable cross-version approach (Python 3.9+) vs asyncio.timeout()
    which requires 3.11+.
    """
    start = asyncio.get_event_loop().time()

    async def _next(gen):
        return await gen.__anext__()

    while True:
        elapsed = asyncio.get_event_loop().time() - start
        remaining = timeout_secs - elapsed
        if remaining <= 0:
            raise asyncio.TimeoutError()
        try:
            item = await asyncio.wait_for(_next(gen), timeout=remaining)
            yield item
        except StopAsyncIteration:
            return


# ── Pipeline ───────────────────────────────────────────────────────────────────

async def _run_pipeline(
    query: CompanyQuery,
    sse,
) -> AsyncGenerator[str, None]:
    """
    Core pipeline — separated from all timeout and error handling.

    1. Fan out all relevant collectors concurrently
    2. Yield a collector_update event as each one completes
    3. Send collected data to Claude for structuring
    4. Yield the final risk profile
    """
    collected: list[RawCollectorData] = []
    collectors = get_collectors_for_jurisdiction(query.jurisdiction)

    if not collectors:
        yield sse({
            "type": "error",
            "payload": {"message": f"No data collectors available for jurisdiction: {query.jurisdiction}"},
        })
        return

    # ── Fan out collectors ─────────────────────────────────────────────────────
    event_queue: asyncio.Queue[CollectorUpdate | None] = asyncio.Queue()

    async def run_one(collector) -> None:
        await event_queue.put(
            CollectorUpdate(collector=collector.name, status=CollectorStatus.RUNNING)
        )
        try:
            data = await asyncio.wait_for(
                collector.collect(query),
                timeout=COLLECTOR_TIMEOUT_SECS,
            )
            collected.append(data)
            await event_queue.put(
                CollectorUpdate(collector=collector.name, status=CollectorStatus.DONE, data=data)
            )
        except asyncio.TimeoutError:
            logger.warning("[%s] timed out after %ss", collector.name, COLLECTOR_TIMEOUT_SECS)
            await event_queue.put(CollectorUpdate(
                collector=collector.name,
                status=CollectorStatus.ERROR,
                error=f"Timed out after {int(COLLECTOR_TIMEOUT_SECS)}s",
            ))
        except Exception as e:
            logger.error("[%s] error: %s", collector.name, e)
            await event_queue.put(CollectorUpdate(
                collector=collector.name,
                status=CollectorStatus.ERROR,
                error=str(e),
            ))

    async def run_all() -> None:
        await asyncio.gather(*[run_one(c) for c in collectors])
        await event_queue.put(None)  # sentinel

    asyncio.create_task(run_all())

    while True:
        update = await event_queue.get()
        if update is None:
            break
        yield sse({"type": "collector_update", "payload": update.model_dump()})

    # ── LLM structuring ────────────────────────────────────────────────────────
    if not collected:
        yield sse({
            "type": "error",
            "payload": {"message": "All data collectors failed — cannot produce a risk profile."},
        })
        return

    try:
        profile = await asyncio.wait_for(
            structure_with_llm(query, collected),
            timeout=LLM_TIMEOUT_SECS,
        )
        yield sse({"type": "profile_ready", "payload": profile.model_dump()})

    except asyncio.TimeoutError:
        logger.warning("[assess] LLM timed out after %ss", LLM_TIMEOUT_SECS)
        yield sse({"type": "error", "payload": {"message": "AI structuring timed out — please try again."}})
    except Exception as e:
        logger.error("[assess] LLM error: %s", e)
        yield sse({"type": "error", "payload": {"message": "AI structuring failed — please try again."}})