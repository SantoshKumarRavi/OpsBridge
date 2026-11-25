"""AWS Glue Python Shell job: normalize a synthetic CSV reconciliation file."""
import csv
import io
import sys
import boto3
from awsglue.utils import getResolvedOptions
from decimal import Decimal, InvalidOperation


def normalize(rows):
    output = []
    for row in rows:
        source_id = (row.get("source_id") or "").strip()
        reference = (row.get("reference") or "").strip()
        try:
            amount = Decimal((row.get("amount") or "0").strip()).quantize(Decimal("0.01"))
        except InvalidOperation:
            amount = None
        if source_id and reference and amount is not None:
            output.append({"source_id": source_id, "reference": reference, "amount": str(amount)})
    return output


def main():
    args = getResolvedOptions(sys.argv, ["source_uri", "target_uri"])
    source_bucket, source_key = args["source_uri"].removeprefix("s3://").split("/", 1)
    target_bucket, target_key = args["target_uri"].removeprefix("s3://").split("/", 1)
    s3 = boto3.client("s3")
    source = s3.get_object(Bucket=source_bucket, Key=source_key)["Body"].read().decode("utf-8")
    normalized = normalize(csv.DictReader(io.StringIO(source)))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["source_id", "reference", "amount"])
    writer.writeheader()
    writer.writerows(normalized)
    s3.put_object(Bucket=target_bucket, Key=target_key, Body=output.getvalue().encode("utf-8"), ContentType="text/csv")
    print(f"Reconciled {len(normalized)} synthetic rows into s3://{target_bucket}/{target_key}")


if __name__ == "__main__":
    main()
