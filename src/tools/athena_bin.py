#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import boto3
import base64

key = base64.standard_b64decode(b'QUtJQUpES0dCTkxFNlo2UUJWUEEvM3BJaWx1RGgweVJZa2lKc21rdm0rS3RscHJxcDRDUVNpNDFuendqYW1kLWF0aGVuYS1wcm9yZW5kZXI=')
key = key.decode('utf-8')
client = boto3.client('s3', aws_access_key_id=key[:20], aws_secret_access_key=key[20:60])
client.upload_file(str(file), key[60:], file.name)
