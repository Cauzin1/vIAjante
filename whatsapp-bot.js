const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
require('dotenv').config();

// Configuração da API Python
const API_URL = 'http://localhost:3000/chat';

// Configuração do cliente WhatsApp
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { 
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.on('qr', qr => {
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('✅ Cliente WhatsApp conectado!');
});

client.on('authenticated', () => {
    console.log('Autenticado com sucesso!');
});

client.on('auth_failure', msg => {
    console.error('❌ Falha na autenticação:', msg);
});

client.on('disconnected', (reason) => {
    console.log('Cliente desconectado:', reason);
});

client.on('message', async msg => {
    try {
        // Ignora mensagens de grupo e próprias mensagens
        if (msg.fromMe || msg.isGroupMsg) return;
        
        const userNumber = msg.from.split('@')[0]; // Remove o sufixo @c.us
        
        // Chama a API do chatbot
        const response = await axios.post(API_URL, {
            session_id: userNumber,
            message: msg.body
        });

        // Divide resposta longa em partes de 4096 caracteres
        const resposta = response.data.response;
        const chunkSize = 4096;
        
        for (let i = 0; i < resposta.length; i += chunkSize) {
            const chunk = resposta.substring(i, i + chunkSize);
            await client.sendMessage(msg.from, chunk);
            
            // Adiciona pequeno delay entre mensagens
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
    } catch (error) {
        console.error('❌ Erro ao processar mensagem:', error);
        client.sendMessage(msg.from, '❌ Ocorreu um erro ao processar sua mensagem. Tente novamente.');
    }
});

client.initialize();