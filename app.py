import os
import re
import time
import traceback
import requests
import telegram
from telegram.ext import Dispatcher, MessageHandler, Filters
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

# Carrega as chaves do ambiente - ESSENCIAL PARA O RENDER
GEMINI_KEY = os.getenv("GEMINI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

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
CORS(app)

sessoes = {} # Armazenamento de sessões de usuários

# ========================
# LÓGICA DO BOT (INTACTA)
# ========================

def extrair_tabela(texto: str) -> str:
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
    # Esta função é o "cérebro" do bot e permanece a mesma que já corrigimos.
    # Ela gerencia os estados e gera as respostas.
    estado = sessoes[session_id]['estado']
    dados_usuario = sessoes[session_id]['dados']
    texto_normalizado = texto.strip().lower()

    if texto_normalizado == "reiniciar":
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
        return "🔄 Certo! Vamos começar uma nova viagem. Para onde na Europa você quer viajar?"

    # ... (O resto da sua lógica de estados: AGUARDANDO_DESTINO, DATAS, ORCAMENTO, etc.)
    # >>> INÍCIO DA LÓGICA DE ESTADOS <<<
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
                return "❌ Desculpe, não consegui gerar o PDF. O itinerário parece incompleto. Tente `reiniciar`."

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
                return "❌ Desculpe, não consegui gerar o CSV. O itinerário parece incompleto. Tente `reiniciar`."
        else:
            return "🤔 Não entendi... Digite `pdf`, `csv` ou `reiniciar`."

    return "Desculpe, não entendi o que você quis dizer." # Resposta padrão
    # >>> FIM DA LÓGICA DE ESTADOS <<<


# ========================
# INTEGRAÇÃO COM TELEGRAM
# ========================

# Esta função será a ponte entre o Telegram e o nosso "cérebro" (processar_mensagem)
def handle_telegram_message(update, context):
    session_id = str(update.message.chat_id)
    texto_recebido = update.message.text
    
    # Se for a primeira mensagem do usuário, criamos a sessão para ele
    if session_id not in sessoes:
        sessoes[session_id] = {'estado': 'AGUARDANDO_DESTINO', 'dados': {}}
        # E enviamos a saudação inicial
        resposta = ("🌟 Olá! ✈️ Eu sou o vIAjante, seu especialista em viagens pela Europa.\n\n"
                    "Pra começar, me conta: pra qual *país* você quer viajar?")
    else:
        # Se a sessão já existe, apenas processamos a mensagem
        resposta = processar_mensagem(session_id, texto_recebido)

    # Envia a resposta de volta para o usuário no Telegram
    # parse_mode=telegram.ParseMode.MARKDOWN é essencial para formatar o texto (*, `, etc.)
    context.bot.send_message(chat_id=session_id, text=resposta, parse_mode=telegram.ParseMode.MARKDOWN)

def handle_error(update, context):
    """Loga os erros causados pelas atualizações."""
    print(f"Update {update} causou o erro {context.error}")


# ========================
# ROTAS FLASK (SERVIDOR WEB)
# ========================

# Rota para servir os arquivos gerados (PDF, CSV)
@app.route('/arquivos/<filename>')
def download_file(filename):
    return send_from_directory('arquivos', filename, as_attachment=True)

# Rota para o Webhook do Telegram
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
    
    # Define que a função handle_telegram_message deve ser chamada para qualquer mensagem de texto
    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_telegram_message))
    dispatcher.add_error_handler(handle_error)

    try:
        dispatcher.process_update(telegram.Update.de_json(request.get_json(force=True), bot))
    except Exception as e:
        print(f"Erro ao processar o webhook do Telegram: {e}")

    return "ok", 200

# Rota de "saúde" para verificar se o servidor está no ar
@app.route('/')
def index():
    return "Servidor do vIAjante está no ar!", 200

# ========================
# INICIALIZAÇÃO
# ========================
if __name__ == '__main__':
    # Esta parte é usada apenas para testes locais.
    # Em produção (no Render), o Gunicorn será usado.
    app.run(host='0.0.0.0', port=3000, debug=True)