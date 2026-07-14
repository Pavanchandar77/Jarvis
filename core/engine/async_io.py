# core/engine/async_io.py
"""Spark Asynchronous I/O Pipeline.

Implements concurrent tensor streaming and block loading. Overlaps disk I/O,
weight decompression, memory mapping, and hardware compute blocks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from .loader import TensorLoader, LoadRequest, LoadResult

logger = logging.getLogger("spark.engine.async_io")


class AsyncIOPipeline:
    """Asynchronous pipeline to overlap computation and storage reads.

    Provides a queue-based reader that continuously fetches blocks from disk
    using a worker thread while the main loop is processing the current tensor batch.
    """

    def __init__(self, loader: TensorLoader, source_path: str):
        self._loader = loader
        self._source_path = source_path
        
        # Max blocks loaded ahead in the pipeline
        self._queue: asyncio.Queue[LoadResult] = asyncio.Queue(maxsize=4)
        self._active_task: Optional[asyncio.Task] = None
        self._loading_block_ids: List[str] = []

    def start_streaming(self, execution_sequence: List[str]) -> None:
        """Start streaming blocks matching the planned execution sequence."""
        if self._active_task is None:
            self._loading_block_ids = list(execution_sequence)
            self._active_task = asyncio.create_task(self._io_worker())
            logger.info("Async I/O Pipeline started. Streaming sequence of %d blocks.", len(execution_sequence))

    async def next_block(self) -> Optional[LoadResult]:
        """Fetch the next block that has been preloaded by the background worker.

        Yields immediately if already resident, otherwise blocks until loaded.
        """
        if self._active_task is None:
            return None

        # Check if worker finished or queue is empty
        if self._queue.empty() and self._active_task.done():
            self._active_task = None
            return None

        try:
            return await self._queue.get()
        except asyncio.CancelledError:
            self.stop()
            return None

    def stop(self) -> None:
        """Stop background worker and cancel running loads."""
        if self._active_task:
            self._active_task.cancel()
            self._active_task = None
        # Drain queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.info("Async I/O Pipeline stopped.")

    # -- Worker Thread Interface --

    async def _io_worker(self) -> None:
        loop = asyncio.get_running_loop()
        
        for block_id in self._loading_block_ids:
            try:
                req = LoadRequest(
                    block_ids=[block_id],
                    source_path=self._source_path,
                    async_allowed=True,
                )

                # Run file read + decompression in thread pool to avoid blocking asyncio
                t0 = time.perf_counter()
                results = await loop.run_in_executor(
                    None, self._loader.load, req
                )
                elapsed = (time.perf_counter() - t0) * 1000

                for r in results:
                    # Push result to the queue (will block if queue is full, causing backpressure)
                    await self._queue.put(r)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Async I/O pipeline load worker: %s", e)
                # Put a failed block on the queue so the client knows
                await self._queue.put(LoadResult(
                    block_id=block_id,
                    success=False,
                    error=str(e),
                ))
