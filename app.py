import os
import re
import time
import traceback
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai

# Utils
from utils.pdf_generator import gerar_pdf
from utils.csv_generator import csv_generator
from utils.validators import validar_destino, validar_data, validar_orcamento, remover_acentos

# ========================
# Configuração e Constantes
# ========================
load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")

if not os.path.exists('arquivos'):
    os.makedirs('arquivos')

try:
    genai.configure(api_key=os.getenv("GEMINI_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini configurado com sucesso!")
except Exception as e:
    print(f"❌ Erro na configuração do Gemini: {str(e)}")
    exit(1)

app = Flask(__name__)
CORS(app)

sessoes = {}

DICAS = {
    "DESTINO": "\n💡 Dica: Países como Itália e França são ótimos para primeira viagem!",
    "DATAS": "\n💡 Dica: Evite alta temporada (julho/agosto) para economizar!",
    "ORCAMENTO": "\n💡 Dica: Lembre-se de incluir 20% extra para imprevistos!",
}

AGRADECIMENTOS = ["obrigado", "obrigada", "valeu", "agradeço", "thanks", "grato", "obgd"]


# ========================
# Funções Auxiliares
# ========================

def extrair_tabela(texto: str) -> str:
    """
    Versão final e super robusta para extrair tabelas.
    Procura por linhas que contenham múltiplos '|' e as trata como tabela.
    """
    linhas_tabela = []
    for linha in texto.split('\n'):
        linha = linha.strip()
        # Uma linha de tabela Markdown deve começar com '|' e ter pelo menos 2 '|' (para 1 coluna)
        if linha.startswith('|') and linha.count('|') > 2:
            # Ignora a linha de separação do markdown (ex: |:---|:---|)
            if re.match(r'^[|: -]+$', linha.replace(" ", "")):
                continue
            linhas_tabela.append(linha)
            
    if not linhas_tabela:
        print("⚠️  Aviso: Nenhuma linha de tabela válida foi extraída da resposta.")
        return ""
        
    return '\n'.join(linhas_tabela)


# ========================
# Processador Principal de Mensagens
# ========================
def processar_mensagem(session_id: str, texto: str) -> str:
    estado = sessoes[session_id]['estado']
    dados_usuario = sessoes[session_id]['dados']
    texto_normalizado = texto.strip().lower()

    if texto_normalizado == "reiniciar":
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
        return "🔄 Certo! Vamos começar uma nova viagem. Para onde na Europa você quer viajar?"

    if any(palavra in texto_normalizado for palavra in AGRADECIMENTOS):
        return "😊 De nada! Estou aqui para ajudar."
    
    if estado == "AGUARDANDO_DESTINO":
        if not validar_destino(texto_normalizado):
            return "❌ *País não reconhecido* 😟\nPor favor, informe um *país europeu válido* (ex: Itália, França...)."
        
        dados_usuario["destino"] = texto.strip().title()
        sessoes[session_id]['estado'] = "AGUARDANDO_DATAS"
        return (f"✈️ *{dados_usuario['destino']} é uma ótima escolha!* \n"
                "Agora me conta: *quando* você vai viajar?\n\n"
                "📅 Por favor, informe as datas no formato: `DD/MM a DD/MM`")

    elif estado == "AGUARDANDO_DATAS":
        if not validar_data(texto_normalizado):
            return "❌ *Formato incorreto* ⚠️\nPor favor, use o formato: `DD/MM a DD/MM`."
        
        dados_usuario["datas"] = texto_normalizado
        sessoes[session_id]['estado'] = "AGUARDANDO_ORCAMENTO"
        return "💰 *Quase lá!* Agora me fale sobre o orçamento total da viagem em Reais (R$):"

    elif estado == "AGUARDANDO_ORCAMENTO":
        if not validar_orcamento(texto_normalizado):
            return "❌ *Valor inválido* ⚠️\nPor favor, informe um valor numérico válido (ex: 15000)."
        
        valor_str = texto_normalizado.replace("r$", "").replace(" ", "").replace(".", "").replace(",", ".")
        valor = float(valor_str.replace("mil", "")) * 1000 if "mil" in valor_str else float(valor_str)
        dados_usuario["orcamento"] = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        sessoes[session_id]['estado'] = "GERANDO_ROTEIRO"
        return (f"⏱️ *Perfeito! Estou preparando seu roteiro para {dados_usuario['destino']}...*\n"
                "Isso pode levar alguns segundos. Para continuar e gerar, pode me mandar um `ok`.")

    elif estado == "GERANDO_ROTEIRO":
        try:
            # Prompt mais explícito pedindo uma tabela
            prompt = (f"Você é um especialista em viagens para a Europa chamado vIAjante. "
                      f"Crie um roteiro detalhado para {dados_usuario['destino']} entre as datas {dados_usuario['datas']} "
                      f"com um orçamento de {dados_usuario['orcamento']}. "
                      f"**É obrigatório incluir um itinerário dia a dia em uma tabela Markdown com as colunas 'DATA', 'DIA' e 'LOCAL'.**")

            response = model.generate_content(prompt)
            
            # ATENÇÃO: Se ainda falhar, descomente as linhas abaixo
            # print("\n\n--- RESPOSTA COMPLETA DO GEMINI ---\n")
            # print(response.text)
            # print("\n--- FIM DA RESPOSTA ---\n")

            resposta_completa = response.text
            tabela_itinerario = extrair_tabela(resposta_completa)
            
            descricao_detalhada = resposta_completa
            if tabela_itinerario:
                descricao_detalhada = resposta_completa.replace(tabela_itinerario, "").strip()

            dados_usuario.update({
                'tabela_itinerario': tabela_itinerario,
                'descricao_detalhada': descricao_detalhada,
            })
            
            sessoes[session_id]['estado'] = "ROTEIRO_GERADO"
            
            resumo_tabela = tabela_itinerario if tabela_itinerario else "**Não foi possível extrair o resumo do itinerário.**"

            return (f"🎉 *Prontinho! Acabei de finalizar seu roteiro para {dados_usuario['destino']}!*\n\n"
                    f"{resumo_tabela}\n\n"
                    "📌 *O que gostaria de fazer agora?*\n"
                    "- Digite `pdf` para receber o roteiro completo\n"
                    "- Digite `csv` para o itinerário em planilha\n"
                    "- Digite `reiniciar` para uma nova viagem")
        except Exception as e:
            traceback.print_exc()
            sessoes[session_id]['estado'] = "AGUARDANDO_DESTINO"
            return f"❌ Opa! Algo deu errado ao gerar o roteiro: {str(e)}\n\nVamos recomeçar?"

    elif estado == "ROTEIRO_GERADO":
        if texto_normalizado == "pdf":
            try:
                caminho_pdf = gerar_pdf(
                    destino=dados_usuario['destino'], datas=dados_usuario['datas'],
                    tabela=dados_usuario['tabela_itinerario'], descricao=dados_usuario['descricao_detalhada'],
                    session_id=session_id
                )
                base_url = request.host_url
                pdf_url = f"{base_url}arquivos/{os.path.basename(caminho_pdf)}"
                return f"📄 *Seu PDF está pronto!* ✅\nClique para baixar: {pdf_url}"
            except ValueError as e:
                print(f"LOG: Falha ao gerar PDF - {e}")
                return "❌ Desculpe, não consegui gerar o PDF. O itinerário retornado parece incompleto. Tente `reiniciar`."

        elif texto_normalizado == "csv":
            try:
                caminho_csv = csv_generator(
                    tabela=dados_usuario['tabela_itinerario'],
                    session_id=session_id
                )
                base_url = request.host_url
                csv_url = f"{base_url}arquivos/{os.path.basename(caminho_csv)}"
                return f"📊 *Seu arquivo CSV está pronto!* ✅\nClique para baixar: {csv_url}"
            except ValueError as e:
                print(f"LOG: Falha ao gerar CSV - {e}")
                return "❌ Desculpe, não consegui gerar o CSV. O itinerário retornado parece incompleto. Tente `reiniciar`."
        else:
            return "🤔 Não entendi... Digite `pdf`, `csv` ou `reiniciar`."

# O resto do arquivo (rotas e inicialização) permanece igual...
@app.route('/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    session_id = data.get('session_id')
    message = data.get('message', '').strip()

    if not session_id or not message:
        return jsonify({'response': "ID da sessão ou mensagem ausente."}), 400

    if session_id not in sessoes:
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
        resposta = ("🌟 Olá! ✈️ Eu sou o vIAjante, seu especialista em viagens pela Europa.\n\n"
                    "Pra começar, me conta: pra qual *país* você quer viajar?")
        
        if validar_destino(message.lower()):
            return jsonify({'response': processar_mensagem(session_id, message)})
        else:
            return jsonify({'response': resposta})
    
    resposta = processar_mensagem(session_id, message)
    return jsonify({'response': resposta})

@app.route('/arquivos/<filename>')
def download_file(filename):
    return send_from_directory('arquivos', filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)