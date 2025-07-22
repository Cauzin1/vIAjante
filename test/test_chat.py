import requests

# URL do seu servidor Flask local
URL = "http://localhost:3000/chat"
session_id = "teste_console"

print("💬 Simulador de Chat iniciado!")
print("Digite 'sair' para encerrar o teste.\n")

while True:
    message = input("Você: ")
    
    if message.lower() == "sair":
        print("🔚 Encerrando teste...")
        break

    response = requests.post(URL, json={"session_id": session_id, "message": message})
    
    if response.ok:
        print(f"Bot: {response.json()['response']}\n")
    else:
        print("❌ Erro ao enviar mensagem para o servidor.")
