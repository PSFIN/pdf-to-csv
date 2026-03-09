import asyncio
import gc
import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from pdf_processor import (
    calculate_summary,
    extract_page_transactions,
    validate_balances,
    write_csv,
)

app = FastAPI(title="PDF to CSV Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@dataclass
class Job:
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    pdf_path: Path | None = None
    csv_path: Path | None = None


jobs: dict[str, Job] = {}


def step_event(message: str) -> dict:
    return {"type": "step", "data": {"message": message}}


def progress_event(message: str, page: int, total_pages: int) -> dict:
    return {"type": "progress", "data": {"message": message, "page": page, "total_pages": total_pages}}


async def process_pdf_job(job_id: str):
    job = jobs[job_id]
    q = job.queue

    try:
        await q.put(step_event("Opening PDF file..."))
        await asyncio.sleep(0)

        pdf = pdfplumber.open(str(job.pdf_path))
        total_pages = len(pdf.pages)
        await q.put(step_event(f"Found {total_pages} pages in the PDF"))
        await asyncio.sleep(0)

        await q.put(step_event("Beginning table extraction from each page..."))
        await asyncio.sleep(0)

        all_transactions = []
        pages_with_data = 0

        for i in range(total_pages):
            # Open and process one page at a time to minimize memory
            page = pdf.pages[i]
            txns = extract_page_transactions(page)

            if txns:
                pages_with_data += 1
                all_transactions.extend(txns)

            # Flush page from cache to free memory
            page.flush_cache()

            # Force garbage collection every 50 pages
            if (i + 1) % 50 == 0:
                gc.collect()

            # Send progress every 10 pages or on first/last page
            if i == 0 or i == total_pages - 1 or (i + 1) % 10 == 0:
                await q.put(progress_event(
                    f"Processing page {i + 1}/{total_pages} — {len(all_transactions)} transactions found so far",
                    i + 1,
                    total_pages,
                ))
                await asyncio.sleep(0)

        pdf.close()
        gc.collect()

        await q.put(step_event(f"Table extraction complete. Scanned {total_pages} pages."))
        await asyncio.sleep(0)

        await q.put(step_event(f"Total transactions extracted: {len(all_transactions)}"))
        await asyncio.sleep(0)

        # Validate balances
        await q.put(step_event("Validating running balance continuity..."))
        await asyncio.sleep(0)

        errors = validate_balances(all_transactions)
        if errors:
            await q.put(step_event(f"⚠ {len(errors)} balance discrepancies detected"))
        else:
            await q.put(step_event("All balances validated — 0 errors found"))
        await asyncio.sleep(0)

        # Calculate summary
        await q.put(step_event("Calculating summary statistics..."))
        await asyncio.sleep(0)

        summary = calculate_summary(all_transactions)

        await q.put(step_event(
            f"Credits: ${float(summary['total_credits']):,.2f} | "
            f"Debits: ${float(summary['total_debits']):,.2f} | "
            f"Ending Balance: ${float(summary['ending_balance']):,.2f}"
        ))
        await asyncio.sleep(0)

        type_parts = [f"{k}: {v}" for k, v in summary["type_breakdown"].items()]
        await q.put(step_event(f"Transaction types — {' | '.join(type_parts)}"))
        await asyncio.sleep(0)

        await q.put({"type": "summary", "data": summary})
        await asyncio.sleep(0)

        # Write CSV
        await q.put(step_event("Generating CSV file..."))
        await asyncio.sleep(0)

        csv_path = UPLOAD_DIR / f"{job_id}.csv"
        write_csv(all_transactions, csv_path)
        job.csv_path = csv_path

        # Clean up uploaded PDF to save disk space
        if job.pdf_path and job.pdf_path.exists():
            job.pdf_path.unlink()

        await q.put(step_event("CSV file generated successfully!"))
        await asyncio.sleep(0)

        await q.put({"type": "done", "data": {"csv_url": f"/api/download/{job_id}"}})

    except Exception as e:
        await q.put({"type": "error", "data": {"message": f"Error: {str(e)}"}})
    finally:
        gc.collect()


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    job_id = str(uuid.uuid4())
    pdf_path = UPLOAD_DIR / f"{job_id}.pdf"

    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    jobs[job_id] = Job(pdf_path=pdf_path)
    asyncio.create_task(process_pdf_job(job_id))

    return {"job_id": job_id}


@app.get("/api/stream/{job_id}")
async def stream_events(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            event = await job.queue.get()
            yield {
                "event": event["type"],
                "data": json.dumps(event["data"]),
            }
            if event["type"] in ("done", "error"):
                break

    return EventSourceResponse(event_generator())


@app.get("/api/download/{job_id}")
async def download_csv(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.csv_path or not job.csv_path.exists():
        raise HTTPException(status_code=404, detail="CSV not ready or job not found")

    return FileResponse(
        path=str(job.csv_path),
        media_type="text/csv",
        filename="transactions.csv",
    )
