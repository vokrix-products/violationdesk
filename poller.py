import os
import time
import sys
import json
import traceback
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import processor

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
PRODUCT_ID = os.environ["PRODUCT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

HEADERS = {
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "apikey": SUPABASE_SERVICE_KEY,
    "Content-Type": "application/json",
}

def download_file(bucket, file_path):
    if file_path.startswith(bucket + "/"):
        file_path = file_path[len(bucket) + 1:]
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{file_path}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}", "apikey": SUPABASE_SERVICE_KEY})
    resp.raise_for_status()
    return resp.content

def ensure_extract_text():
    if not hasattr(processor, "extract_text"):
        def extract_text(file_bytes):
            try:
                import pdfplumber, io
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    text = ""
                    for p in pdf.pages:
                        text += (p.extract_text() or "") + "\n"
                    if text.strip():
                        return text
            except Exception:
                pass
            return file_bytes.decode("utf-8", errors="ignore")
        processor.extract_text = extract_text

def notify(customer_id, success):
    try:
        payload = {
            "product_id": PRODUCT_ID,
            "customer_id": customer_id,
            "title": "Processing complete" if success else "Processing failed",
            "body": "Your upload has been processed successfully." if success else "There was an error processing your upload.",
            "type": "success" if success else "error",
            "read": False,
        }
        r = requests.post(f"{SUPABASE_URL}/rest/v1/notifications", headers=HEADERS, json=payload)
        r.raise_for_status()
    except Exception:
        pass

def update_job(job_id, status, output_file_path=None, result_summary=None):
    payload = {
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if output_file_path:
        payload["output_file_path"] = output_file_path
    if result_summary:
        payload["result_summary"] = result_summary
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/jobs?id=eq.{job_id}", headers=HEADERS, json=payload)
    r.raise_for_status()

def write_records(job, result):
    customer_id = job["customer_id"]
    items = result if isinstance(result, list) else [result]
    record_count = 0
    for item in items:
        if not isinstance(item, dict):
            item = {"raw": item}
        title = item.get("title") or item.get("record_title") or item.get("description") or "Violation"
        status = item.get("status") or "New:info"
        details = item.get("details", item)
        due_date = item.get("due_date") or item.get("dueDate")

        record_payload = {
            "product_id": PRODUCT_ID,
            "customer_id": customer_id,
            "title": title,
            "status": status,
            "details": details if isinstance(details, dict) else {},
            "source_file_path": job["input_file_path"],
        }
        if due_date:
            record_payload["due_date"] = due_date
        r = requests.post(f"{SUPABASE_URL}/rest/v1/records", headers=HEADERS, json=record_payload)
        r.raise_for_status()
        record_count += 1
    return record_count

def poll():
    ensure_extract_text()
    while True:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/jobs",
                headers=HEADERS,
                params={
                    "status": "eq.pending",
                    "job_type": "eq.process_upload",
                    "product_id": f"eq.{PRODUCT_ID}",
                    "select": "*",
                    "order": "created_at.asc",
                    "limit": "1",
                },
            )
            r.raise_for_status()
            jobs = r.json()
            if not jobs:
                time.sleep(60)
                continue

            job = jobs[0]
            job_id = job["id"]
            customer_id = job["customer_id"]
            input_file_path = job["input_file_path"]

            file_bytes = download_file("uploads", input_file_path)
            result = processor.process_file(file_bytes)
            record_count = write_records(job, result)

            result_doc = {
                "job_id": job_id,
                "product_id": PRODUCT_ID,
                "customer_id": customer_id,
                "source_file_path": input_file_path,
                "records_created": record_count,
                "result": result,
            }
            result_bytes = json.dumps(result_doc, default=str, indent=2).encode("utf-8")
            result_object_path = f"{job_id}.json"
            r = requests.post(
                f"{SUPABASE_URL}/storage/v1/object/results/{result_object_path}",
                headers={
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Content-Type": "application/json",
                },
                data=result_bytes,
            )
            r.raise_for_status()

            update_job(job_id, "completed", result_object_path, f"Created {record_count} records")
            notify(customer_id, True)
        except Exception as e:
            print("Poller error:", e)
            traceback.print_exc()
            try:
                if 'job_id' in locals() and 'customer_id' in locals():
                    update_job(job_id, "failed", None, str(e))
                    notify(customer_id, False)
            except Exception:
                pass
        time.sleep(60)

if __name__ == "__main__":
    print("Poller started")
    poll()
