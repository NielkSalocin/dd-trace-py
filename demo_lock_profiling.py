#!/usr/bin/env python
"""
Demo script for lock profiling with various primitives.

Usage:
  ddtrace-run python demo_lock_profiling.py [PRIMITIVE]

Primitives:
  threading-semaphore       threading.Semaphore (default)
  threading-bounded         threading.BoundedSemaphore
  asyncio-semaphore         asyncio.Semaphore
  asyncio-bounded           asyncio.BoundedSemaphore
  all                       All primitives

Environment:
  DD_SERVICE=lock-demo DD_ENV=dev DD_PROFILING_ENABLED=true ddtrace-run python demo_lock_profiling.py

Examples:
  ddtrace-run python demo_lock_profiling.py threading-semaphore
  ddtrace-run python demo_lock_profiling.py asyncio-bounded
  ddtrace-run python demo_lock_profiling.py all
"""

import argparse
import asyncio
import random
import threading
import time
from typing import Callable
from typing import List


# =============================================================================
# PRIMITIVES - Define lock objects at module level for clear naming in UI
# =============================================================================

# Threading primitives
connection_pool = threading.Semaphore(3)
rate_limiter = threading.BoundedSemaphore(5)

# Asyncio primitives (created lazily in async context)
async_connection_pool: asyncio.Semaphore = None  # type: ignore
async_rate_limiter: asyncio.BoundedSemaphore = None  # type: ignore


def init_asyncio_primitives() -> None:
    """Initialize asyncio primitives (must be called within event loop)."""
    global async_connection_pool, async_rate_limiter
    async_connection_pool = asyncio.Semaphore(3)
    async_rate_limiter = asyncio.BoundedSemaphore(5)


# =============================================================================
# THREADING DEMOS
# =============================================================================


def demo_threading_semaphore() -> None:
    """Demo threading.Semaphore with contention."""
    print("\n[threading.Semaphore] Starting demo...")

    def worker(worker_id: int) -> None:
        for i in range(30):
            with connection_pool:
                time.sleep(random.uniform(0.02, 0.08))
            if i % 10 == 0:
                print(f"  Semaphore worker-{worker_id}: iteration {i}")

    _run_threaded_workers(worker, num_workers=8, prefix="Semaphore")


def demo_threading_bounded_semaphore() -> None:
    """Demo threading.BoundedSemaphore with contention."""
    print("\n[threading.BoundedSemaphore] Starting demo...")

    def worker(worker_id: int) -> None:
        for i in range(30):
            with rate_limiter:
                time.sleep(random.uniform(0.02, 0.08))
            if i % 10 == 0:
                print(f"  BoundedSemaphore worker-{worker_id}: iteration {i}")

    _run_threaded_workers(worker, num_workers=10, prefix="BoundedSem")


def _run_threaded_workers(target: Callable[[int], None], num_workers: int, prefix: str) -> None:
    """Helper to run threaded workers."""
    threads: List[threading.Thread] = []
    for i in range(num_workers):
        t = threading.Thread(target=target, args=(i,), name=f"{prefix}-{i}")
        threads.append(t)
        t.start()
    for t in threads:
        t.join()


# =============================================================================
# ASYNCIO DEMOS
# =============================================================================


def demo_asyncio_semaphore() -> None:
    """Demo asyncio.Semaphore with contention."""
    print("\n[asyncio.Semaphore] Starting demo...")
    asyncio.run(_asyncio_semaphore_workload())


async def _asyncio_semaphore_workload() -> None:
    """Async workload for Semaphore demo."""
    init_asyncio_primitives()

    async def worker(worker_id: int) -> None:
        for i in range(30):
            async with async_connection_pool:
                await asyncio.sleep(random.uniform(0.02, 0.08))
            if i % 10 == 0:
                print(f"  Async Semaphore worker-{worker_id}: iteration {i}")

    await asyncio.gather(*[worker(i) for i in range(8)])


def demo_asyncio_bounded_semaphore() -> None:
    """Demo asyncio.BoundedSemaphore with contention."""
    print("\n[asyncio.BoundedSemaphore] Starting demo...")
    asyncio.run(_asyncio_bounded_workload())


async def _asyncio_bounded_workload() -> None:
    """Async workload for BoundedSemaphore demo."""
    init_asyncio_primitives()

    async def worker(worker_id: int) -> None:
        for i in range(30):
            async with async_rate_limiter:
                await asyncio.sleep(random.uniform(0.02, 0.08))
            if i % 10 == 0:
                print(f"  Async BoundedSem worker-{worker_id}: iteration {i}")

    await asyncio.gather(*[worker(i) for i in range(10)])


# =============================================================================
# MAIN
# =============================================================================

PRIMITIVES = {
    "threading-semaphore": ("threading.Semaphore", demo_threading_semaphore),
    "threading-bounded": ("threading.BoundedSemaphore", demo_threading_bounded_semaphore),
    "asyncio-semaphore": ("asyncio.Semaphore", demo_asyncio_semaphore),
    "asyncio-bounded": ("asyncio.BoundedSemaphore", demo_asyncio_bounded_semaphore),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo lock profiling with various primitives.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ddtrace-run python demo_lock_profiling.py threading-semaphore
  ddtrace-run python demo_lock_profiling.py asyncio-bounded
  ddtrace-run python demo_lock_profiling.py all
        """,
    )
    parser.add_argument(
        "primitive",
        nargs="?",
        default="threading-semaphore",
        choices=list(PRIMITIVES.keys()) + ["all"],
        help="Lock primitive to demo (default: threading-semaphore)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("LOCK PROFILING DEMO")
    print("=" * 70)

    if args.primitive == "all":
        demos = list(PRIMITIVES.values())
    else:
        demos = [PRIMITIVES[args.primitive]]

    print(f"\nPrimitives: {', '.join(name for name, _ in demos)}")
    print("\nExpected in Datadog UI (APM -> Profiler -> Lock Wait/Hold Time):")
    print("  - Lock names: connection_pool, rate_limiter, async_*")
    print("  - Stack traces pointing to worker functions in this file")
    print()

    start = time.time()
    for name, demo_fn in demos:
        demo_fn()
        print(f"  ✓ {name} done")

    print(f"\nCompleted in {time.time() - start:.2f}s")
    print("Waiting 5s for profiler to flush...")
    time.sleep(5)
    print("Done!")


if __name__ == "__main__":
    main()
