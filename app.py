# app.py - Versão Final para Deploy com Telegram (Sintaxe Moderna)

import os
import re
import traceback
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import google.generativeai as genai

# Importações da nova versão da biblioteca do Telegram
import telegram
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Seus outros imports (utils)
from utils.pdf_generator import gerar_pdf
from utils.csv_generator import csv_generator
from utils.validators import validar_destino, validar_data, validar_orcamento, remover_acentos

# ========================
# Configuração e Constantes
# ========================
load_dotenv()

# Carrega as chaves do ambiente - ESSENCIAL PARA O RENDER
GEMINI_KEY = os.getenv("GEMINI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # Ex: https://seu-app.onrender.com

if not os.path.exists('arquivos'):
    os.makedirs('arquivos')

try:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini configurado com sucesso!")
except Exception as e:
    print(f"❌ Erro na configuração do Gemini: {str(e)}")
    exit(1)

app = Flask(__name__)
sessoes = {} # Armazenamento de sessões

# ========================
# LÓGICA DO BOT (CÉREBRO)
# ========================

def extrair_tabela(texto: str) -> str:
    """Extrai tabelas Markdown do texto de forma robusta."""
    linhas_tabela = []
    for linha in texto.split('\n'):
        linha = linha.strip()
        if linha.startswith('|') and linha.count('|') > 2:
            if re.match(r'^[|: -]+$', linha.replace(" ", "")): continue
            linhas_tabela.append(linha)
    if not linhas_tabela:
        return ""
    return '\n'.join(linhas_tabela)

def processar_mensagem(session_id: str, texto: str) -> str:
    """
    Esta função é o "cérebro" do bot. Ela gerencia os estados da conversa 
    e gera as respostas de forma síncrona.
    """
    # Garante que a sessão exista
    if session_id not in sessoes:
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}

    estado = sessoes[session_id]['estado']
    dados_usuario = sessoes[session_id]['dados']
    texto_normalizado = texto.strip().lower()

    if texto_normalizado == "reiniciar":
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
        return "🔄 Certo! Vamos começar uma nova viagem. Para onde na Europa você quer viajar?"

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
            prompt = (f"Você é um especialista em viagens para a Europa chamado vIAjante. "
                      f"Crie um roteiro detalhado para {dados_usuario['destino']} entre as datas {dados_usuario['datas']} "
                      f"com um orçamento de {dados_usuario['orcamento']}. "
                      f"**É obrigatório incluir um itinerário dia a dia em uma tabela Markdown com as colunas 'DATA', 'DIA' e 'LOCAL'.**")
            response = model.generate_content(prompt)
            resposta_completa = response.text
            tabela_itinerario = extrair_tabela(resposta_completa)
            descricao_detalhada = resposta_completa.replace(tabela_itinerario, "").strip() if tabela_itinerario else resposta_completa

            dados_usuario.update({
                'tabela_itinerario': tabela_itinerario,
                'descricao_detalhada': descricao_detalhada,
            })
            sessoes[session_id]['estado'] = "ROTEIRO_GERADO"
            resumo_tabela = tabela_itinerario if tabela_itinerario else "**Não foi possível extrair o resumo do itinerário.**"

            return (f"🎉 *Prontinho! Acabei de finalizar seu roteiro para {dados_usuario['destino']}!*\n\n"
                    f"{resumo_tabela}\n\n"
                    "📌 *O que gostaria de fazer agora?*\n- Digite `pdf` para receber o roteiro completo\n- Digite `csv` para o itinerário em planilha\n- Digite `reiniciar` para uma nova viagem")
        except Exception as e:
            traceback.print_exc()
            sessoes[session_id]['estado'] = "AGUARDANDO_DESTINO"
            return f"❌ Opa! Algo deu errado ao gerar o roteiro: {str(e)}\n\nVamos recomeçar?"

    elif estado == "ROTEIRO_GERADO":
        # Esta rota usa `request.host_url` que só está disponível no contexto de uma requisição Flask
        # Por isso, vamos precisar passar a URL base para a função
        base_url = dados_usuario.get("base_url", "")

        if texto_normalizado == "pdf":
            try:
                caminho_pdf = gerar_pdf(
                    destino=dados_usuario['destino'], datas=dados_usuario['datas'],
                    tabela=dados_usuario['tabela_itinerario'], descricao=dados_usuario['descricao_detalhada'],
                    session_id=session_id
                )
                pdf_url = f"{base_url}arquivos/{os.path.basename(caminho_pdf)}"
                return f"📄 *Seu PDF está pronto!* ✅\nClique para baixar: {pdf_url}"
            except ValueError as e:
                return "❌ Desculpe, não consegui gerar o PDF. O itinerário parece incompleto. Tente `reiniciar`."

        elif texto_normalizado == "csv":
            try:
                caminho_csv = csv_generator(
                    tabela=dados_usuario['tabela_itinerario'],
                    session_id=session_id
                )
                csv_url = f"{base_url}arquivos/{os.path.basename(caminho_csv)}"
                return f"📊 *Seu arquivo CSV está pronto!* ✅\nClique para baixar: {csv_url}"
            except ValueError as e:
                return "❌ Desculpe, não consegui gerar o CSV. O itinerário parece incompleto. Tente `reiniciar`."
        else:
            return "🤔 Não entendi... Digite `pdf`, `csv` ou `reiniciar`."

    return "Desculpe, não entendi o que você quis dizer." # Resposta padrão


# ========================
# INTEGRAÇÃO COM TELEGRAM (SINTAXE MODERNA)
# ========================

# Constrói a aplicação do bot com o token
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Esta é a função principal que o Telegram chama. Ela é assíncrona.
async def handle_telegram_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.message.chat_id)
    texto_recebido = update.message.text
    
    # Se for a primeira mensagem, criamos a sessão e enviamos a saudação
    if session_id not in sessoes:
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
        resposta = ("🌟 Olá! ✈️ Eu sou o vIAjante, seu especialista em viagens pela Europa.\n\n"
                    "Pra começar, me conta: pra qual *país* você quer viajar?")
    else:
        # Passa a URL base para a sessão, para que os links de download funcionem
        sessoes[session_id]['dados']['base_url'] = WEBHOOK_URL or request.host_url

        # Chama a nossa função de lógica síncrona
        resposta = processar_mensagem(session_id, texto_recebido)

    # Envia a resposta de volta para o usuário
    await context.bot.send_message(
        chat_id=session_id, 
        text=resposta, 
        parse_mode=telegram.constants.ParseMode.MARKDOWN
    )

# Função para logar erros
async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} causou o erro {context.error}")

# Registra os handlers (gerenciadores de mensagem e erro) na aplicação
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_message))
application.add_error_handler(handle_error)


# ========================
# ROTAS FLASK (SERVIDOR WEB)
# ========================

@app.route('/arquivos/<filename>')
def download_file(filename):
    return send_from_directory('arquivos', filename, as_attachment=True)

@app.route('/telegram_webhook', methods=['POST'])
async def telegram_webhook():
    await application.update_queue.put(Update.de_json(request.get_json(force=True), application.bot))
    return "ok", 200

@app.route('/set_webhook', methods=['GET'])
async def set_webhook():
    if WEBHOOK_URL:
        # A URL do webhook DEVE ser a rota /telegram_webhook
        webhook_full_url = f"{WEBHOOK_URL}/telegram_webhook"
        await application.bot.set_webhook(webhook_full_url)
        return f"Webhook configurado para: {webhook_full_url}"
    return "WEBHOOK_URL não configurado nas variáveis de ambiente.", 400

@app.route('/')
def index():
    return "Servidor do vIAjante está no ar e pronto para receber webhooks!", 200

# ========================
# INICIALIZAÇÃO
# ========================
if __name__ == '__main__':
    # Usado apenas para testes locais (não é usado no Render)
    app.run(host='0.0.0.0', port=os.getenv("PORT", 3000), debug=True)