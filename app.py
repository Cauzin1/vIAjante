""" # app.py - Versão de Teste de Eliminação (Sem chamada à API Gemini)

import os
import re
import traceback
import asyncio
from flask import Flask, request, send_from_directory
from dotenv import load_dotenv
import google.generativeai as genai

import telegram
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from utils.pdf_generator import gerar_pdf
from utils.csv_generator import csv_generator
from utils.validators import validar_destino, validar_data, validar_orcamento, remover_acentos

# --- Configuração ---
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
app = Flask(__name__)
sessoes = {}

print("DEBUG: Iniciando a configuração do servidor...")
if not os.path.exists('arquivos'): os.makedirs('arquivos')
try:
    if not GEMINI_KEY:
        print("!!!!!!!!!! ERRO CRÍTICO: GEMINI_KEY não encontrada! !!!!!!!!!!")
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini configurado com sucesso!")
except Exception as e:
    print(f"❌ Erro na configuração do Gemini: {str(e)}"); exit(1)

# --- Lógica do Bot (Cérebro) ---
def extrair_tabela(texto: str) -> str:
    linhas_tabela = []
    for linha in texto.split('\n'):
        linha = linha.strip()
        if linha.startswith('|') and linha.count('|') > 2:
            if re.match(r'^[|: -]+$', linha.replace(" ", "")): continue
            linhas_tabela.append(linha)
    if not linhas_tabela: return ""
    return '\n'.join(linhas_tabela)

def processar_mensagem(session_id: str, texto: str, base_url: str) -> str:
    print(f"DEBUG: [processar_mensagem] Iniciando processamento para session_id: {session_id}")
    if session_id not in sessoes:
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
    
    sessoes[session_id]['dados']['base_url'] = base_url
    estado = sessoes[session_id]['estado']
    dados_usuario = sessoes[session_id]['dados']
    texto_normalizado = texto.strip().lower()
    print(f"DEBUG: [processar_mensagem] Estado atual: {estado}, Texto recebido: '{texto_normalizado}'")

    if texto_normalizado == "reiniciar":
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
        return "🔄 Certo! Vamos começar uma nova viagem. Para onde na Europa você quer viajar?"

    if estado == "AGUARDANDO_DESTINO":
        print("DEBUG: [Estado AGUARDANDO_DESTINO]")
        if not validar_destino(texto_normalizado):
            print("DEBUG: Destino inválido.")
            return "❌ *País não reconhecido* 😟\nPor favor, informe um *país europeu válido* (ex: Itália, França...)."
        
        dados_usuario["destino"] = texto.strip().title()
        sessoes[session_id]['estado'] = "AGUARDANDO_DATAS"
        print(f"DEBUG: Destino '{dados_usuario['destino']}' salvo. Novo estado: AGUARDANDO_DATAS.")
        return (f"✈️ *{dados_usuario['destino']} é uma ótima escolha!* \n"
                "Agora me conta: *quando* você vai viajar?\n\n"
                "📅 Por favor, informe as datas no formato: `DD/MM a DD/MM`")

    elif estado == "AGUARDANDO_DATAS":
        print("DEBUG: [Estado AGUARDANDO_DATAS]")
        if not validar_data(texto_normalizado):
            print("DEBUG: Data inválida.")
            return "❌ *Formato incorreto* ⚠️\nPor favor, use o formato: `DD/MM a DD/MM`."
        
        dados_usuario["datas"] = texto_normalizado
        sessoes[session_id]['estado'] = "AGUARDANDO_ORCAMENTO"
        print(f"DEBUG: Datas '{dados_usuario['datas']}' salvas. Novo estado: AGUARDANDO_ORCAMENTO.")
        return "💰 *Quase lá!* Agora me fale sobre o orçamento total da viagem em Reais (R$):"

    elif estado == "AGUARDANDO_ORCAMENTO":
        print("DEBUG: [Estado AGUARDANDO_ORCAMENTO]")
        if not validar_orcamento(texto_normalizado):
            print("DEBUG: Orçamento inválido.")
            return "❌ *Valor inválido* ⚠️\nPor favor, informe um valor numérico válido (ex: 15000)."
        
        valor_str = texto_normalizado.replace("r$", "").replace(" ", "").replace(".", "").replace(",", ".")
        valor = float(valor_str.replace("mil", "")) * 1000 if "mil" in valor_str else float(valor_str)
        dados_usuario["orcamento"] = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        sessoes[session_id]['estado'] = "GERANDO_ROTEIRO"
        print(f"DEBUG: Orçamento '{dados_usuario['orcamento']}' salvo. Novo estado: GERANDO_ROTEIRO.")
        return (f"⏱️ *Perfeito! Estou preparando seu roteiro para {dados_usuario['destino']}...*\n"
                "Isso pode levar alguns segundos. Para continuar e gerar, pode me mandar um `ok`.")

    # >>> ALTERAÇÃO PARA TESTE AQUI <<<
    elif estado == "GERANDO_ROTEIRO":
        print("DEBUG: [Estado GERANDO_ROTEIRO] - MODO DE TESTE SEM API")
        sessoes[session_id]['estado'] = "ROTEIRO_GERADO"
        # Simula uma resposta sem chamar a API do Gemini
        resposta_fixa = f"🎉 *TESTE BEM-SUCEDIDO!* Se você está vendo isso, o bot está funcionando. O problema é a chamada para a API do Gemini. Por favor, verifique sua chave de API e a configuração de faturamento no Google Cloud."
        return resposta_fixa
    # >>> FIM DA ALTERAÇÃO PARA TESTE <<<

    elif estado == "ROTEIRO_GERADO":
        print("DEBUG: [Estado ROTEIRO_GERADO]")
        base_url_para_links = dados_usuario.get("base_url", "")
        if not base_url_para_links:
            print("AVISO: base_url não encontrada na sessão para gerar links de download.")
        
        if texto_normalizado == "pdf":
            try:
                print("DEBUG: Gerando PDF...")
                caminho_pdf = gerar_pdf(
                    destino=dados_usuario['destino'], datas=dados_usuario['datas'],
                    tabela=dados_usuario.get('tabela_itinerario', ''), descricao=dados_usuario.get('descricao_detalhada', 'Não disponível.'),
                    session_id=session_id)
                pdf_url = f"{base_url_para_links}/arquivos/{os.path.basename(caminho_pdf)}"
                return f"📄 *Seu PDF está pronto!* ✅\nClique para baixar: {pdf_url}"
            except ValueError as e:
                print(f"DEBUG: Erro ao gerar PDF (ValueError): {e}")
                return "❌ Desculpe, não consegui gerar o PDF. O itinerário parece incompleto."

        elif texto_normalizado == "csv":
            try:
                print("DEBUG: Gerando CSV...")
                caminho_csv = csv_generator(
                    tabela=dados_usuario.get('tabela_itinerario', ''),
                    session_id=session_id)
                csv_url = f"{base_url_para_links}/arquivos/{os.path.basename(caminho_csv)}"
                return f"📊 *Seu arquivo CSV está pronto!* ✅\nClique para baixar: {csv_url}"
            except ValueError as e:
                print(f"DEBUG: Erro ao gerar CSV (ValueError): {e}")
                return "❌ Desculpe, não consegui gerar o CSV. O itinerário parece incompleto."
        else:
            return "🤔 Não entendi... Digite `pdf`, `csv` ou `reiniciar`."

    return "DEBUG: Fim da função, nenhuma condição atendida."

# --- Integração com Telegram ---
if not TELEGRAM_TOKEN: raise ValueError("Token do Telegram não encontrado!")
application = Application.builder().token(TELEGRAM_TOKEN).build()

async def handle_telegram_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.message.chat_id)
    texto_recebido = update.message.text
    print(f"--- 1. MENSAGEM RECEBIDA --- Chat ID: {session_id}, Texto: '{texto_recebido}'")

    try:
        base_url = WEBHOOK_URL or "http://localhost:3000"
        if session_id not in sessoes:
            sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
            print("--- 2a. Nova sessão criada. Enviando saudação. ---")
            resposta = ("🌟 Olá! ✈️ Eu sou o vIAjante...\n\nPra começar, pra qual *país* você quer viajar?")
        else:
            print(f"--- 2b. Sessão existente. Estado: {sessoes[session_id]['estado']}. Processando... ---")
            resposta = processar_mensagem(session_id, texto_recebido, base_url)
        
        print(f"--- 3. Resposta gerada: '{resposta[:70]}...' ---")
        if resposta:
            await context.bot.send_message(chat_id=session_id, text=resposta, parse_mode=telegram.constants.ParseMode.MARKDOWN)
            print("--- 4. Resposta enviada com sucesso para o Telegram. ---")
        else:
            print("--- 4. ERRO: Resposta gerada estava vazia! Nada foi enviado. ---")

    except Exception as e:
        print(f"!!!!!!!!!! ERRO GERAL NO HANDLE: {e} !!!!!!!!!!")
        traceback.print_exc()
        await context.bot.send_message(chat_id=session_id, text="Desculpe, encontrei um erro interno grave.")

async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} causou o erro {context.error}")

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_message))
application.add_error_handler(handle_error)

# --- Rotas Flask ---
@app.route('/arquivos/<filename>')
def download_file(filename): return send_from_directory('arquivos', filename, as_attachment=True)
@app.route('/telegram_webhook', methods=['POST'])
async def telegram_webhook():
    await application.update_queue.put(Update.de_json(request.get_json(force=True), application.bot))
    return "ok", 200
@app.route('/')
def index(): return "Servidor do vIAjante está no ar!", 200

# --- Inicialização ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv("PORT", 3000), debug=True) """

# app.py - TESTE FINAL: BOT ECO

import os
import traceback
from flask import Flask, request
from dotenv import load_dotenv

import telegram
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- Configuração ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
app = Flask(__name__)

# --- Lógica do Bot Eco ---
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN não foi encontrado nas variáveis de ambiente!")

# Constrói a aplicação do bot com o token
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Esta é a única função do bot: responder com a mesma mensagem
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.message.chat_id)
    texto_recebido = update.message.text
    
    # Imprime no log para sabermos que a mensagem chegou
    print(f"--- MENSAGEM RECEBIDA --- Chat ID: {session_id}, Texto: '{texto_recebido}'")
    
    try:
        # Tenta enviar a mensagem de volta
        await context.bot.send_message(
            chat_id=session_id,
            text=f"Eco: {texto_recebido}" # Simplesmente responde com a mensagem recebida
        )
        print(f"--- RESPOSTA ECO ENVIADA COM SUCESSO ---")
    except Exception as e:
        # Se falhar ao enviar, o erro aparecerá aqui
        print(f"!!!!!!!!!! ERRO AO ENVIAR MENSAGEM DE ECO: {e} !!!!!!!!!!")
        traceback.print_exc()

# Adiciona o gerenciador de mensagens à aplicação
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


# --- Rotas Flask ---
@app.route('/telegram_webhook', methods=['POST'])
async def telegram_webhook():
    # Processa a atualização recebida do Telegram
    await application.update_queue.put(Update.de_json(request.get_json(force=True), application.bot))
    return "ok", 200

@app.route('/')
def index():
    # Uma página simples para sabermos que o servidor está no ar
    return "Servidor do Bot Eco está no ar!", 200