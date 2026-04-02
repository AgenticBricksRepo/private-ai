"""S3-compatible storage client. Works with AWS S3 and MinIO."""

import boto3


class S3Client:
    def __init__(self, bucket: str, endpoint_url: str, region: str):
        self.bucket = bucket
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
        )

    def upload(self, key: str, data: str | bytes, content_type: str = "application/json"):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def download(self, key: str) -> bytes:
        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete(self, key: str):
        self.s3.delete_object(Bucket=self.bucket, Key=key)
