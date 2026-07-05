import httpx

r = httpx.post(
    'https://tenant-3628a54d-2ae4-4dd8-a7ed-ef65b8313126.aws.cognee.ai/api/v1/add',
    headers={'X-Api-Key': 'd8a4489e4ecd3bd23cd0ab64b5c83efeba26d52997796d61f0729943bf6a3992', 'Content-Type': 'application/json'},
    json={'data': 'test memory from sanity check', 'dataset_name': 'debug_test'}
)
print(r.status_code)
print(r.text)