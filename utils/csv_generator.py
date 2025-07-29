import csv
import os
import re
import uuid
from datetime import datetime

def csv_generator(tabela: str, session_id: str) -> str:
    """Gera um arquivo CSV a partir da tabela de itinerário"""
    if not tabela:
        raise ValueError("Tabela de itinerário vazia")
    
    # Criar nome de arquivo único
    nome_arquivo = f"itinerario_{session_id[:6]}_{uuid.uuid4().hex[:4]}.csv"
    caminho_completo = os.path.join('arquivos', nome_arquivo)
    
    ano_atual = datetime.now().year
    linhas = tabela.split('\n')
    
    with open(caminho_completo, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')
        
        # Escrever cabeçalho
        if linhas and '|' in linhas[0]:
            cabecalho = [col.strip() for col in linhas[0].split('|')[1:-1]]
            writer.writerow(cabecalho)
        
        # Escrever dados
        for linha in linhas[2:]:  # Pular linha de cabeçalho e separador
            if '|' in linha:
                celulas = [col.strip() for col in linha.split('|')[1:-1]]
                
                # Formatar data com ano (ex: 19-set -> 19-set-2025)
                if celulas and '-' in celulas[0]:
                    partes = celulas[0].split('-')
                    if len(partes) == 2:
                        celulas[0] = f"{partes[0]}-{partes[1]}-{ano_atual}"
                
                writer.writerow(celulas)
    
    return caminho_completo