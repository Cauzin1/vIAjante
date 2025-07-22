import google.generativeai as genai
from dotenv import load_dotenv
import os
import re
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from utils.pdf_generator import gerar_pdf

load_dotenv()

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

PAISES_EUROPA = [
    "alemanha", "albania", "andorra", "armenia", "austria", "azerbaijao",
    "belgica", "bielorrussia", "bosnia", "bulgaria",
    "chipre", "croacia", "dinamarca",
    "eslovaquia", "eslovenia", "espanha", "estonia",
    "finlandia", "franca",
    "georgia", "grecia", "holanda", "hungria",
    "irlanda", "islandia", "italia",
    "letonia", "liechtenstein", "lituania", "luxemburgo",
    "macedonia", "malta", "moldavia", "monaco", "montenegro",
    "noruega",
    "polonia", "portugal",
    "reino unido", "romenia", "russia",
    "san marino", "servia", "suecia", "suica",
    "turquia", "ucrania", "vaticano"
]

# Dicas contextuais para cada etapa
DICAS = {
    "DESTINO": "\n💡 Dica: Países como Itália e França são ótimos para primeira viagem!",
    "DATAS": "\n💡 Dica: Evite alta temporada (julho/agosto) para economizar!",
    "ORCAMENTO": "\n💡 Dica: Lembre-se de incluir 20% extra para imprevistos!",
    "GERANDO_ROTEIRO": "\n⏱️ Isso pode levar alguns segundos enquanto preparo tudo com carinho..."
}

# Palavras de agradecimento
AGRADECIMENTOS = ["obrigado", "obrigada", "valeu", "agradeço", "thanks", "grato", "obgd"]

def validar_destino(texto: str) -> bool:
    texto_limpo = texto.lower().strip()
    return any(pais in texto_limpo for pais in PAISES_EUROPA)

def validar_data(texto: str) -> bool:
    pattern = r"\d{2}/\d{2}\s*a\s*\d{2}/\d{2}"
    return re.match(pattern, texto) is not None

def validar_orcamento(texto: str) -> bool:
    texto = texto.lower().strip().replace("r$", "").replace(" ", "")
    texto = texto.replace(".", "").replace(",", ".")
    if "mil" in texto:
        texto = texto.replace("mil", "")
        try:
            valor = float(texto) * 1000
            return valor > 0
        except ValueError:
            return False
    try:
        valor = float(texto)
        return valor > 0
    except ValueError:
        return False

def formatar_resposta_gemini(texto: str) -> str:
    texto = texto.replace("**", "*")
    texto = texto.replace("\u2022", " -")
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    if len(texto) > 3000:
        texto = texto[:3000] + "\n[...] (continua no roteiro completo)"
    return texto

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    session_id = data.get('session_id')
    message = data.get('message', '').strip()
    if session_id not in sessoes:
        sessoes[session_id] = {
            'estado': 'SAUDACAO',
            'dados': {}
        }
    resposta = processar_mensagem(session_id, message)
    return jsonify({'response': resposta})

def processar_mensagem(session_id: str, texto: str) -> str:
    estado = sessoes[session_id]['estado']
    dados_usuario = sessoes[session_id]['dados']
    texto = texto.strip().lower()

    # Reconhecer agradecimentos
    if any(palavra in texto for palavra in AGRADECIMENTOS):
        return "😊 De nada! Estou aqui para ajudar. O que mais posso fazer por você?"
    
    # Reconhecer saudações
    if texto in ["oi", "ola", "olá", "bom dia", "boa tarde", "boa noite"] and estado != "SAUDACAO":
        return f"Olá! 😊 Como posso te ajudar com sua viagem para *{dados_usuario.get('destino', 'a Europa')}*?"

    if texto == "reiniciar":
        sessoes[session_id] = {'estado': 'SAUDACAO', 'dados': {}}
        return "🔄 Certo! Vamos começar uma nova viagem. Para onde na Europa você quer viajar?"

    if estado == "SAUDACAO":
        sessoes[session_id]['estado'] = "DESTINO"
        return (f"🌟 Olá! ✈️ Eu sou o vIAjante, seu especialista em viagens pela Europa. "
                f"Estou aqui para criar a viagem dos seus sonhos!\n\n"
                f"Pra começar, me conta: pra qual *país* você quer viajar? "
                f"(Itália, França, Espanha, Portugal...)\n\n"
                f"💡 Se precisar recomeçar a qualquer momento, é só dizer 'reiniciar'")

    elif estado == "DESTINO":
        if not validar_destino(texto):
            return ("❌ *País não reconhecido* 😟\n"
                    "Por favor, informe um *país europeu válido*. Alguns exemplos:\n"
                    "```\n"
                    "- Itália\n"
                    "- França\n"
                    "- Espanha\n"
                    "- Portugal\n"
                    "- Alemanha\n"
                    "```\n"
                    "ℹ️ No momento atendemos apenas países da Europa.")
        
        pais_formatado = texto.title()
        dados_usuario["destino"] = pais_formatado
        sessoes[session_id]['estado'] = "DATAS"
        
        resposta = (f"✈️ *{pais_formatado} é uma ótima escolha!* Já visitei várias vezes 🗺️\n"
                    f"Agora me conta: *quando* você vai viajar?\n\n"
                    f"📅 Por favor, informe as datas no formato:\n`DD/MM a DD/MM`\n"
                    f"Exemplo: `15/08 a 30/08`")
        
        # Adicionar dica contextual
        resposta += DICAS.get(estado, "")
        return resposta

    elif estado == "DATAS":
        if texto == "voltar":
            sessoes[session_id]['estado'] = "DESTINO"
            return "🔙 Voltando à escolha do país... Qual país você escolheu?"
        
        if not validar_data(texto):
            return ("❌ *Formato incorreto* ⚠️\n"
                    "Por favor, use o formato: `DD/MM a DD/MM`\n\n"
                    "Exemplo: `15/08 a 30/08`\n\n"
                    "Ou digite `voltar` para escolher outro país.")
        
        dados_usuario["datas"] = texto
        sessoes[session_id]['estado'] = "ORCAMENTO"
        
        resposta = ("💰 *Quase lá!* Agora me fale sobre o orçamento da viagem:\n\n"
                    "💵 Por favor, informe o valor total em Reais (R$):\n"
                    "```\n"
                    "Exemplos:\n"
                    "15000\n"
                    "R$ 15.000\n"
                    "20 mil\n"
                    "```")
        
        # Adicionar dica contextual
        resposta += DICAS.get(estado, "")
        return resposta

    elif estado == "ORCAMENTO":
        if texto == "voltar":
            sessoes[session_id]['estado'] = "DATAS"
            return "🔙 Voltando às datas... Qual o período da viagem?"
        
        if not validar_orcamento(texto):
            return ("❌ *Valor inválido* ⚠️\n"
                    "Por favor, informe um valor numérico válido:\n"
                    "```\n"
                    "Exemplos:\n"
                    "15000\n"
                    "R$ 15.000\n"
                    "20 mil\n"
                    "```\n\n"
                    "Ou digite `voltar` para ajustar as datas.")
        
        # Extrai e formata o valor
        valor_str = texto.lower().strip().replace("r$", "").replace(" ", "")
        valor_str = valor_str.replace(".", "").replace(",", ".")
        if "mil" in valor_str:
            valor_str = valor_str.replace("mil", "")
            valor = float(valor_str) * 1000
        else:
            valor = float(valor_str)
            
        # Formatação bonita para exibição
        valor_formatado = f"R${valor:,.2f}"
        valor_formatado = valor_formatado.replace(",", "X").replace(".", ",").replace("X", ".")
        dados_usuario["orcamento"] = valor_formatado

        # Pequeno delay para simular processamento
        time.sleep(1)
        
        sessoes[session_id]['estado'] = "GERANDO_ROTEIRO"
        resposta = (f"⏱️ *Perfeito! Estou preparando seu roteiro personalizado para {dados_usuario['destino']}...*\n\n"
                    f"🔹 Consultando melhores atrações\n"
                    f"🔹 Analisando opções de hospedagem\n"
                    f"🔹 Calculando rotas ideais\n\n"
                    f"Fique tranquilo(a), em instantes seu planejamento completo estará pronto! ✨")
        
        # Adicionar dica contextual
        resposta += DICAS.get(estado, "")
        return resposta

    elif estado == "GERANDO_ROTEIRO":
        try:
            # Simular "digitação" humana
            time.sleep(2)
            
            prompt = f"""
            Você é um especialista em viagens para Europa chamado Rogério. Crie um roteiro detalhado com base nestas informações:
            - Destino: {dados_usuario['destino']}
            - Período: {dados_usuario['datas']}
            - Orçamento total: {dados_usuario['orcamento']}
            
            Inclua:
            1. Itinerário diário com atrações principais (use emojis)
            2. Sugestões de transporte entre cidades (com dicas locais)
            3. Opções de hospedagem em 3 categorias (econômica, média, luxo)
            4. Dicas pessoais de quem conhece bem o destino
            5. Estimativa de custos por categoria
            
            Formate de forma amigável e pessoal, como se estivesse conversando com um amigo.
            Assine como "Rogério - Seu Especialista em Viagens"
            """
            response = model.generate_content(prompt)
            resposta_formatada = formatar_resposta_gemini(response.text)
            dados_usuario['roteiro'] = resposta_formatada
            sessoes[session_id]['estado'] = "ROTEIRO_GERADO"
            
            # Pequeno delay final
            time.sleep(0.5)
            
            return (f"🎉 *Prontinho! Acabei de finalizar seu roteiro para {dados_usuario['destino']}!*\n\n"
                    f"Espero que goste das minhas sugestões - selecionei lugares incríveis pensando em você:\n\n"
                    f"{resposta_formatada}\n\n"
                    f"📌 *O que gostaria de fazer agora?*\n"
                    f"- Digite `pdf` para receber este roteiro em PDF\n"
                    f"- Digite `ajuda` para outras opções\n"
                    f"- Digite `reiniciar` para criar uma nova viagem")
        except Exception as e:
            sessoes[session_id]['estado'] = "SAUDACAO"
            return (f"❌ *Opa! Algo deu errado aqui.* 😟\n"
                    f"Erro: {str(e)}\n\n"
                    f"Vamos recomeçar? Digite `iniciar`.")

    elif estado == "ROTEIRO_GERADO":
        if texto == "ajuda":
            return (f"ℹ️ *Como posso te ajudar com seu roteiro para {dados_usuario['destino']}?*\n\n"
                    f"✈️ `destino` - Alterar o país de destino\n"
                    f"📅 `datas` - Alterar as datas da viagem\n"
                    f"💵 `orçamento` - Ajustar o valor do orçamento\n"
                    f"📄 `pdf` - Receber seu roteiro completo em PDF\n"
                    f"🔄 `reiniciar` - Começar um novo planejamento\n\n"
                    f"É só me dizer o que precisa! 😊")
        
        elif texto == "destino":
            sessoes[session_id]['estado'] = "DESTINO"
            return "🔙 Vamos alterar o destino. Para qual país você quer viajar?"
        
        elif texto == "datas":
            sessoes[session_id]['estado'] = "DATAS"
            return f"🔙 Vamos alterar as datas. Qual o novo período para *{dados_usuario['destino']}*?"
        
        elif texto == "orçamento":
            sessoes[session_id]['estado'] = "ORCAMENTO"
            return "🔙 Vamos alterar o orçamento. Qual o novo valor?"
        
        elif texto == "pdf":
            try:
                caminho_pdf = gerar_pdf(
                    destino=dados_usuario['destino'],
                    datas=dados_usuario['datas'],
                    orcamento=dados_usuario['orcamento'],
                    roteiro_texto=dados_usuario['roteiro'],
                    session_id=session_id
                )
                return (f"📄 *Seu PDF está pronto!* ✅\n"
                        f"Você pode acessá-lo aqui: `{caminho_pdf}`\n\n"
                        f"Precisa de mais alguma coisa? Digite `ajuda` para ver opções.")
            except Exception as e:
                return (f"❌ *Opa, tive um problema ao gerar o PDF* 😟\n"
                        f"Erro: {str(e)}\n\n"
                        f"Posso tentar novamente ou te ajudar com outra coisa?")
        
        elif texto == "reiniciar":
            sessoes[session_id] = {'estado': 'SAUDACAO', 'dados': {}}
            return "🔄 Beleza! Vamos começar uma nova aventura. Para onde na Europa você quer viajar?"
        
        else:
            return (f"🤔 *Não entendi bem...*\n"
                    f"Você já tem um roteiro para {dados_usuario['destino']} pronto!\n\n"
                    f"Digite `ajuda` para ver o que posso fazer por você.")

    return "❌ *Ops! Algo deu errado.* 😟\nPor favor, digite `reiniciar` para começar de novo."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)