import json

def parse_openapi(filepath, out_filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    info = data.get('info', {})
    paths = data.get('paths', {})
    
    lines = []
    lines.append(f"# API Documentation: {info.get('title', 'Unknown')} (v{info.get('version', 'unknown')})")
    lines.append(f"{info.get('description', '')}\n")
    
    lines.append("## Endpoints")
    for path, methods in paths.items():
        for method, details in methods.items():
            lines.append(f"### `{method.upper()}` {path}")
            lines.append(f"**Summary**: {details.get('summary', 'No summary')}")
            desc = details.get('description', '')
            if desc:
                lines.append(f"**Description**: {desc}")
            
            params = details.get('parameters', [])
            if params:
                lines.append("**Parameters**:")
                for p in params:
                    required = " (Required)" if p.get('required') else ""
                    lines.append(f"- `{p.get('name')}` [{p.get('in')}] {required}: {p.get('description', '')}")
            
            req_body = details.get('requestBody')
            if req_body:
                lines.append("**Request Body**: Yes")
            lines.append("")
            
    with open(out_filepath, 'w') as f:
        f.write('\n'.join(lines))

if __name__ == '__main__':
    parse_openapi('/home/infra/dcim_metrics_project/scratch/openapi.json', '/home/infra/.gemini/antigravity-ide/brain/43345c14-7f9b-47c4-93ab-d6a5b6618ab1/api_documentation.md')
