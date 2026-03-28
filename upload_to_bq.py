"""
Upload DCWP delivery worker data to BigQuery.
Run this once before the demo to populate the dataset.

Usage:
  export GOOGLE_CLOUD_PROJECT=nyu-hack
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/nyu-hack-2efba7ef5aee.json
  python upload_to_bq.py
"""

import os
import sys

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "nyu-hack")

from data_tool import upload_to_bigquery, query_bigquery_avg

def main():
    print("📦 Uploading DCWP data to BigQuery...")
    try:
        table = upload_to_bigquery()
        print(f"✅ Data uploaded to: {table}")

        print("\n🔍 Verifying with query...")
        result = query_bigquery_avg("Q2_2025")
        print(f"   Q2 2025 data: {result}")

        print("\n✅ BigQuery is ready for GigNav!")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure you have:")
        print("  1. Set GOOGLE_APPLICATION_CREDENTIALS")
        print("  2. Set GOOGLE_CLOUD_PROJECT")
        print("  3. Enabled BigQuery API in your project")
        sys.exit(1)

if __name__ == "__main__":
    main()
