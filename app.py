import google.generativeai as genai
from dotenv import load_dotenv
import os
import re

load_dotenv() 

# Configuração do Gemini
try:
    genai.configure(api_key=os.getenv("GEMINI_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"❌ Erro na configuração do Gemini: {str(e)}")
    exit(1)

# Sistema de estados para o chatbot
ESTADO = "SAUDACAO"
dados_usuario = {}

def validar_data(texto: str) -> bool:
    """Valida o formato DD/MM a DD/MM"""
    pattern = r"\d{2}/\d{2}\s*a\s*\d{2}/\d{2}"
    return re.match(pattern, texto) is not None

def validar_orcamento(texto: str) -> bool:
    """Valida se é um número válido"""
    try:
        float(texto.replace("R$", "").replace(".", "").replace(",", ".").strip())
        return True
    except ValueError:
        return False

def processar_mensagem(texto: str) -> str:
    global ESTADO, dados_usuario
    
    texto = texto.strip()
    
    # Reiniciar conversa
    if texto.lower() == "reiniciar":
        ESTADO = "SAUDACAO"
        dados_usuario = {}
        return "🌟 Conversa reiniciada! Para onde na Europa você quer viajar?"
    
    if ESTADO == "SAUDACAO":
        ESTADO = "DESTINO"
        return "🌟 Olá! Sou seu assistente de viagens. Para qual país da Europa você vai? (Ex: Itália, França)\n(Digite 'reiniciar' a qualquer momento para começar de novo)"
    
    elif ESTADO == "DESTINO":
        if len(texto) < 2:
            return "❌ Por favor, informe um destino válido (ex: Espanha)"
        
        dados_usuario["destino"] = texto
        ESTADO = "DATAS"
        return f"✈️ Ótimo destino! Quando será sua viagem para {texto}? (Formato: DD/MM a DD/MM)"
    
    elif ESTADO == "DATAS":
        if not validar_data(texto):
            return "❌ Formato inválido! Use DD/MM a DD/MM (ex: 15/08 a 30/08)"
        
        dados_usuario["datas"] = texto
        ESTADO = "ORCAMENTO"
        return "💰 Qual o orçamento total da viagem? (Em R$, ex: 15000)"
    
    elif ESTADO == "ORCAMENTO":
        if not validar_orcamento(texto):
            return "❌ Valor inválido! Informe um número (ex: 15000 ou R$15.000)"
        
        # Formata o orçamento
        valor = float(texto.replace("R$", "").replace(".", "").replace(",", ".").strip())
        dados_usuario["orcamento"] = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        ESTADO = "GERAR_ROTEIRO"
        
        try:
            # Monta prompt para o Gemini
            prompt = f"""
            Você é um especialista em viagens para Europa. Crie um roteiro detalhado com base nestas informações:
            
            - Destino: {dados_usuario['destino']}
            - Período: {dados_usuario['datas']}
            - Orçamento total: {dados_usuario['orcamento']}
            
            Inclua:
            1. Itinerário diário com atrações principais
            2. Sugestões de transporte entre cidades
            3. Opções de hospedagem em 3 categorias (econômica, média, luxo)
            4. Dicas locais e estimativa de custos
            
            Formate a resposta em tópicos claros.
            """
            
            response = model.generate_content(prompt)
            return f"✅ Roteiro gerado com sucesso!\n\n{response.text}\n\nDigite 'reiniciar' para uma nova consulta."
        
        except Exception as e:
            return f"❌ Erro ao gerar roteiro: {str(e)}"

# Teste no console
if __name__ == "__main__":
    print("--- Chatbot Viajando Bem ---")
    print(processar_mensagem("iniciar"))
    
    while True:
        user_input = input("\nVocê: ")
        if user_input.lower() == "sair":
            print("Até logo! ✈️")
            break
            
        resposta = processar_mensagem(user_input)
        print("\nBot:", resposta)