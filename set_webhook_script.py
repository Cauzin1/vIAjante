# set_webhook_script.py
import os
import asyncio
from dotenv import load_dotenv
from telegram.ext import Application

# Carrega as variáveis do arquivo .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # Ex: https://viajante.onrender.com

# Função assíncrona para configurar o webhook
async def main():
    if not TELEGRAM_TOKEN or not WEBHOOK_URL:
        print("❌ Erro: Certifique-se de que TELEGRAM_TOKEN e WEBHOOK_URL estão no arquivo .env")
        return

    # Constrói a aplicação do bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Monta a URL completa do webhook
    webhook_full_url = f"{WEBHOOK_URL}/telegram_webhook"

    try:
        # Envia o comando para a API do Telegram
        await application.bot.set_webhook(webhook_full_url)
        print("✅ Webhook configurado com sucesso!")
        print(f"   Seu bot agora está apontando para: {webhook_full_url}")
    except Exception as e:
        print(f"❌ Falha ao configurar o webhook: {e}")

# Executa a função principal
if __name__ == '__main__':
    print("Iniciando configuração do webhook...")
    asyncio.run(main())