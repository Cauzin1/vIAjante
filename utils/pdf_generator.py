# utils/pdf_generator.py

from weasyprint import HTML
from datetime import datetime
import os

def gerar_pdf(destino: str, datas: str, tabela: str, descricao: str, session_id: str) -> str:
    # Converter tabela Markdown para HTML
    tabela_html = ""
    if tabela:
        linhas = tabela.split('\n')
        tabela_html = "<table border='1' cellpadding='5' style='border-collapse: collapse; width: 100%; margin-bottom: 20px;'>"
        for i, linha in enumerate(linhas):
            if '|' in linha:
                cells = [cell.strip() for cell in linha.split('|') if cell.strip()]
                if i == 0:  # Cabeçalho
                    tabela_html += "<thead><tr>"
                    for cell in cells:
                        tabela_html += f"<th class='cabecalho-itinerario'>{cell}</th>"
                    tabela_html += "</tr></thead><tbody>"
                else:  # Linhas de dados
                    tabela_html += "<tr>"
                    for cell in cells:
                        tabela_html += f"<td>{cell}</td>"
                    tabela_html += "</tr>"
        tabela_html += "</tbody></table>"
    
    # Criar conteúdo HTML
    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                margin: 2em;
                color: #333;
                line-height: 1.6;
            }}
            h1 {{
                color: #2e86de;
                border-bottom: 2px solid #2e86de;
                padding-bottom: 10px;
            }}
            .header-info {{
                background-color: #f1f0fa;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .section {{
                margin-bottom: 25px;
            }}
            .section-title {{
                color: #e74c3c;
                border-left: 4px solid #e74c3c;
                padding-left: 10px;
                margin-top: 25px;
            }}
            .itinerario {{
                margin-top: 20px;
            }}
            table {{
                width: 100%;
                margin-bottom: 20px;
                border-collapse: collapse;
            }}
            th,
            .cabecalho-itinerario {{
                background-color: #e74c3c;
                color: white;
                text-align: left;
                padding: 10px;
            }}
            td {{
                padding: 8px;
                border-bottom: 1px solid #ddd;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .footer {{
                margin-top: 40px;
                text-align: center;
                font-size: 12px;
                color: #777;
            }}
        </style>
    </head>
    <body>
        <h1>Roteiro de Viagem: {destino}</h1>
        
        <div class="header-info">
            <p><strong>Período:</strong> {datas}</p>
            <p><strong>Gerado em:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        
        <div class="section">
            <h2 class="section-title">Itinerário</h2>
            <div class="itinerario">
                {tabela_html}
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Detalhes da Viagem</h2>
            <div class="descricao">
                {descricao.replace('\n', '<br>')}
            </div>
        </div>
        
        <div class="footer">
            <p>Roteiro gerado por vIAjante - Seu assistente de viagens</p>
            <p>ID da Sessão: {session_id}</p>
        </div>
    </body>
    </html>
    """
    
    # Criar nome do arquivo
    nome_arquivo = f"roteiro_{destino}_{session_id[:6]}.pdf"
    caminho = os.path.join('arquivos', nome_arquivo)
    
    # Garantir que o diretório existe
    os.makedirs('arquivos', exist_ok=True)
    
    # Gerar PDF
    HTML(string=html_content).write_pdf(caminho)
    return caminho

