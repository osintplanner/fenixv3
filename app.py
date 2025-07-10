import sys
import os
import webbrowser
import threading
import time
import traceback
from flask import Flask, render_template, request, jsonify

# Importar módulos utilitários
from utils.wallet_derivation import derive_addresses
from utils.blockchain_api import get_blockchain_data

# --- Configurações da Aplicação ---
DEBUG_MODE = True
FLASK_PORT = 5000
FLASK_HOST = '127.0.0.1'

# --- Inicialização do Flask ---
app = Flask(__name__)

# --- Rotas da Aplicação ---

@app.route('/')
def index():
    """
    Rota principal que renderiza a interface HTML.
    """
    return render_template('index.html')

@app.route('/derive_and_check', methods=['POST'])
def derive_and_check():
    """
    Rota para receber os dados da seed, derivar endereços e consultar APIs.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Dados JSON inválidos ou vazios."}), 400

        seed_phrase = data.get('seed_phrase')
        selected_networks = data.get('selected_networks', [])
        account_indices_str = data.get('account_indices', '0')
        address_indices_str = data.get('address_indices', '0-10')
        bitcoin_address_types = data.get('bitcoin_address_types', [])
        api_keys = data.get('api_keys', {}) 
        change_types = data.get('change_types', [])

        if not seed_phrase:
            return jsonify({"error": "Seed phrase é obrigatória."}), 400

        print(f"Recebida seed: {seed_phrase[:10]}...")
        print(f"Redes selecionadas: {selected_networks}")
        print(f"Contas: {account_indices_str}")
        print(f"Índices: {address_indices_str}")
        print(f"Tipos BTC: {bitcoin_address_types}")
        print(f"Tipos de Cadeia (Change): {change_types}")

        # Chama derive_addresses para obter a lista COMPLETA de carteiras derivadas
        derived_wallets_full_list = derive_addresses(
            seed_phrase,
            selected_networks,
            account_indices_str,
            address_indices_str,
            bitcoin_address_types,
            change_types
        )
        print(f"Total de endereços derivados (lista completa): {len(derived_wallets_full_list)}")

        results_filtered = [] # Esta será a lista filtrada para exibição na tabela
        for i, wallet_info in enumerate(derived_wallets_full_list): # Itera sobre a lista COMPLETA
            address = wallet_info['address']
            network = wallet_info['network']
            derivation_path = wallet_info['derivation_path']
            private_key = wallet_info['private_key']
            address_type = wallet_info.get('address_type', 'N/A')

            print(f"Consultando dados para endereço {address} na rede {network}")

            # Mapeia as chaves de API do objeto api_keys (vindo do JS)
            api_key_for_network = None
            if network == "BTC":
                api_key_for_network = api_keys.get('bitcoin')
            elif network in ["ETH", "BSC", "MATIC", "BASE", "OPTIMISM", "ARBITRUM"]:
                api_key_for_network = api_keys.get('ethereum')
            elif network == "TRX":
                api_key_for_network = api_keys.get('tron')

            blockchain_data = get_blockchain_data(address, network, api_key_for_network)


            # Verifica se há error_fatal na resposta da blockchain_api
            if blockchain_data and not blockchain_data.get("error_fatal"): 
                balance_crypto = blockchain_data.get('balance_crypto', 0)
                balance_usd = blockchain_data.get('balance_usd', 0)
                has_transactions = blockchain_data.get('has_transactions', False)
                explorer_link = blockchain_data.get('explorer_link', '#')
                has_real_balance = blockchain_data.get('has_real_balance', False)

                # Saldo em satoshis para BTC
                balance_satoshi = blockchain_data.get('balance_satoshi', 0)

                # O filtro agora usa has_real_balance ou has_transactions
                if has_real_balance or has_transactions:
                    result_item = {
                        "address": address,
                        "network": network,
                        "balance_crypto": balance_crypto,
                        "balance_usd": balance_usd,
                        "has_transactions": has_transactions,
                        "has_real_balance": has_real_balance,
                        "derivation_path": derivation_path,
                        "address_type": address_type,
                        "private_key": private_key,
                        "explorer_link": explorer_link
                    }
                    if network == "BTC":
                        result_item["balance_satoshi"] = balance_satoshi 
                    results_filtered.append(result_item)
            elif blockchain_data and blockchain_data.get("error_fatal"):
                print(f"AVISO: Endereço {address} na rede {network} não adicionado devido a erro fatal da API: {blockchain_data['error_fatal']}")
            
            # Pausa para evitar rate limits
            if i % 5 == 0 and network != "BTC": 
                time.sleep(0.5)
            elif network == "BTC": 
                time.sleep(0.05)
            
        # Retorna a lista filtrada para exibição E a lista completa para exportação
        return jsonify({"success": True, "results": results_filtered, "all_derived_wallets": derived_wallets_full_list})

    except ValueError as e:
        error_msg = f"Erro de validação/parsing: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        error_msg = f"Erro inesperado no backend: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({"error": "Ocorreu um erro inesperado no servidor"}), 500

# --- Funções de Inicialização ---

def open_browser_after_delay(url):
    """
    Abre o navegador padrão do usuário após um pequeno atraso.
    """
    time.sleep(2)
    try:
        webbrowser.open_new(url)
    except Exception as e:
        print(f"Erro ao abrir navegador: {e}")
        print(f"Por favor, acesse manualmente: {url}")

def run_flask_app_in_thread():
    """
    Inicia o servidor Flask.
    """
    url = f"http://{FLASK_HOST}:{FLASK_PORT}"
    print(f"Servidor Flask rodando em {url}")
    from werkzeug.serving import run_simple
    run_simple(FLASK_HOST, FLASK_PORT, app, use_reloader=False, use_debugger=False)

# --- Ponto de Entrada Principal ---
if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask_app_in_thread)
    flask_thread.daemon = True
    flask_thread.start()

    open_browser_after_delay(f"http://{FLASK_HOST}:{FLASK_PORT}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nAplicação encerrada pelo usuário.")
        os._exit(0)