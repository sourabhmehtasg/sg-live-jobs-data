
import json

from pathlib import Path
from datetime import datetime, timezone, timedelta


# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

PUBLIC_FILE = BASE_DIR / "sg-live-jobs.jsonl"

RETENTION_DAYS = 21


# ------------------------------------------------------------
# TIMESTAMP PARSING
# ------------------------------------------------------------

def parse_timestamp(value):

    if not value:
        return None

    try:

        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except (ValueError, TypeError, AttributeError):
        return None


# ------------------------------------------------------------
# CLEANUP
# ------------------------------------------------------------

def cleanup_public_dataset():

    if not PUBLIC_FILE.exists():

        raise FileNotFoundError(
            f"Public dataset not found: {PUBLIC_FILE}"
        )

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=RETENTION_DAYS)
    )

    latest_jobs = {}
    records_without_timestamp = []

    total_records = 0
    invalid_timestamps = 0
    duplicate_records = 0

    print("\n========== DAILY PUBLIC DATA CLEANUP ==========")

    print("Dataset:", PUBLIC_FILE)

    print("Retention period:", RETENTION_DAYS, "days")

    print("Cutoff:", cutoff.isoformat())

    # --------------------------------------------------------
    # Read existing public dataset
    # --------------------------------------------------------

    with PUBLIC_FILE.open("r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            total_records += 1

            try:

                job = json.loads(line)

            except json.JSONDecodeError as error:

                # Fail safely. Do not replace the original file
                # if it contains malformed JSON.
                raise ValueError(
                    f"Invalid JSON at line {line_number}: {error}"
                ) from error

            if not isinstance(job, dict):

                raise ValueError(
                    f"Expected JSON object at line {line_number}."
                )

            job_id = job.get("job_id")

            posted_at = parse_timestamp(
                job.get("posted_at")
            )

            # Keep records whose age cannot be determined.
            if not job_id or posted_at is None:

                invalid_timestamps += 1

                records_without_timestamp.append(job)

                continue

            existing = latest_jobs.get(job_id)

            # Keep the newest version of each job.
            if existing is None:

                latest_jobs[job_id] = (
                    posted_at,
                    job
                )

            else:

                duplicate_records += 1

                if posted_at >= existing[0]:

                    latest_jobs[job_id] = (
                        posted_at,
                        job
                    )

    # --------------------------------------------------------
    # Apply rolling 21-day filter
    # --------------------------------------------------------

    retained_jobs = []
    removed_jobs = 0

    for posted_at, job in latest_jobs.values():

        if posted_at >= cutoff:

            retained_jobs.append(
                (posted_at, job)
            )

        else:

            removed_jobs += 1

    # Newest first.
    retained_jobs.sort(
        key=lambda item: item[0],
        reverse=True
    )

    # Records without a reliable timestamp are retained.
    final_jobs = [
        job
        for posted_at, job in retained_jobs
    ]

    final_jobs.extend(records_without_timestamp)

    # --------------------------------------------------------
    # Write atomically
    # --------------------------------------------------------

    temp_file = PUBLIC_FILE.with_suffix(
        ".jsonl.tmp"
    )

    with temp_file.open("w", encoding="utf-8") as file:

        for job in final_jobs:

            file.write(
                json.dumps(
                    job,
                    ensure_ascii=False
                ) + "\n"
            )

    temp_file.replace(PUBLIC_FILE)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n========== CLEANUP SUMMARY ==========")

    print("Original records:", total_records)

    print("Duplicate records found:", duplicate_records)

    print("Old jobs removed:", removed_jobs)

    print("Records with unknown timestamps retained:", invalid_timestamps)

    print("Final records:", len(final_jobs))

    print("Updated file:", PUBLIC_FILE)

    print("\nCleanup completed successfully.")


# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------

if __name__ == "__main__":

    cleanup_public_dataset()
