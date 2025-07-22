# utils/pdf_generator.py

from weasyprint import HTML
from datetime import datetime
import os

def gerar_pdf(destino, datas, orcamento, roteiro_texto, session_id):
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                margin: 2em;
                color: #333;
            }}
            h1 {{
                color: #2e86de;
            }}
            .info {{
                margin-bottom: 1em;
                font-size: 14px;
            }}
            .roteiro {{
                white-space: pre-wrap;
                background: #f8f9fa;
                padding: 1em;
                border: 1px solid #ddd;
                border-radius: 5px;
            }}
        </style>
    </head>
    <body>
        <h1>Roteiro de Viagem: {destino}</h1>
        <div class="info"><strong>Datas:</strong> {datas}</div>
        <div class="info"><strong>Orçamento:</strong> {orcamento}</div>
        <div class="roteiro">{roteiro_texto}</div>
    </body>
    </html>
    """
    filename = f"roteiro_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = os.path.join("pdfs", filename)

    os.makedirs("pdfs", exist_ok=True)
    HTML(string=html_content).write_pdf(path)
    return path
