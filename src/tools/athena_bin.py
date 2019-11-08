import boto3
import base64

key = base64.standard_b64decode(b'QUtJQUpES0dCTkxFNlo2UUJWUEEvM3BJaWx1RGgweVJZa2lKc21rdm0rS3RscHJxcDRDUVNpNDFuendqYW1kLWF0aGVuYS1wcm9yZW5kZXI=')
key = key.decode('utf-8')
client = boto3.client('s3', aws_access_key_id=key[:20], aws_secret_access_key=key[20:60])
client.upload_file(str(file), key[60:], file.name)
