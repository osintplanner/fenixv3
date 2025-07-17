import requests
import json
from decimal import Decimal, getcontext
import time

# Configura a precisão para operações com Decimal
getcontext().prec = 30

# --- URLs Base das APIs e Contratos USDT/Tokens ---
API_CONFIG = {
    "BTC": {
        "base_url": "https://blockstream.info/api",
        "explorer_link_base": "https://web3.okx.com/pt-br/explorer/bitcoin/address/" # URL corrigida
    },
    # PARA TODAS AS REDES EVM (ETH, BSC, MATIC, BASE, OPTIMISM, ARBITRUM)
    # A Etherscan V2 unifica o endpoint para api.etherscan.io/v2/api e usa o chainid
    "EVM_COMMON": {
        "base_url_v2_unified": "https://api.etherscan.io/v2/api", # URL UNIFICADA DA V2
        "explorer_link_base": { # Links de explorador ainda serão específicos
            "ETH": "https://etherscan.io/address/",
            "BSC": "https://bscscan.com/address/",
            "MATIC": "https://polygonscan.com/address/",
            "BASE": "https://basescan.org/address/",
            "OPTIMISM": "https://optimistic.etherscan.io/address/",
            "ARBITRUM": "https://arbiscan.io/address/",
        },
        "chain_ids": { # Chain IDs para o parâmetro 'chainid'
            "ETH": 1,
            "BSC": 56,
            "MATIC": 137,
            "BASE": 8453,
            "OPTIMISM": 10,
            "ARBITRUM": 42161,
        },
        "usdt_contracts": { # Contratos USDT específicos por chain
            "ETH": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "BSC": "0x55d398326f99059ff775485246999027b3197955",
            "MATIC": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
            "BASE": "0x833589fCD6eDb6E08f4c7C32D4f7B5ab9e6d09",
            "OPTIMISM": "0x94b008aa00579c1307b0ef2c499ad98a8a508789",
            "ARBITRUM": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", # Endereço corrigido
        }
    },
    "TRX": {
        "base_url": "https://api.trongrid.io", # Usando trongrid.io
        "explorer_link_base": "https://tronscan.org/#/address/", # Tronscan para explorer link
        "usdt_contract": "TR7NHqjeKQxGTCi8q8ZiFhgvdhB8zkEgJW" # USDT-TRC20
    }
}

# --- Preços Mockados (para conversão USD) ---
MOCKED_PRICES_USD = {
    "BTC": Decimal("70000.00"),
    "ETH": Decimal("3500.00"),
    "BSC": Decimal("600.00"), # BNB Price
    "MATIC": Decimal("0.70"), # MATIC Price
    "TRX": Decimal("0.12"),  # TRX Price
    "USDT": Decimal("1.00") # Preço do USDT para todos os tokens USDT
}

# --- Função Auxiliar para Requisições HTTP ---
def _fetch_data(url, params=None, api_key=None, headers=None):
    if params is None:
        params = {}
    
    # Adiciona a chave de API como parâmetro 'apikey' para Etherscan-like APIs (V1 e V2)
    # Garante que a api_key é uma string e remove espaços em branco
    if api_key and isinstance(api_key, str) and api_key.strip(): 
        params["apikey"] = api_key.strip() # A chave é passada no parâmetro 'apikey'
    
    # TronGrid API key (no header)
    if api_key and isinstance(api_key, str) and api_key.strip() and "trongrid.io" in url:
        headers = headers if headers is not None else {}
        headers["TRON-PRO-API-KEY"] = api_key.strip()
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status() # Levanta um HTTPError para 4xx/5xx responses
        
        if response.status_code == 204: # No Content
            print(f"DEBUG: No Content (204) from API for URL: {url}")
            return {"message": "No Content from API."} # Retorna como erro não-fatal para melhor tratamento
            
        data = response.json()
        print(f"DEBUG: API Response for {url} - {data}")

        # Tratamento de respostas de API com "status": "0" (Etherscan-like V1 e V2 com mensagens de erro)
        if isinstance(data, dict) and data.get("status") == "0":
            message = data.get("message", "").lower()
            # Se for uma mensagem de "sem dados", trata como sucesso com resultado vazio/zero
            if "no transactions found" in message or "no records found" in message or "zero balance" in message or "address not found" in message:
                print(f"DEBUG: Etherscan-like API status 0 treated as no data: {data.get('message')}")
                return {"status": "1", "result": "0"} # Trata como sucesso com resultado zero para saldo, ou lista vazia para tx
            else:
                # Outras mensagens com status 0 são erros reais da API (rate limit, chave inválida)
                print(f"WARNING: Etherscan-like API returned actual error (status 0): {data.get('message')}")
                return {"message": data.get("message", "Sem resultados ou limite de taxa excedido.")}
            
        # Tratamento de respostas TronGrid (success: false, ou sem 'data'/'total')
        if "trongrid.io" in url and isinstance(data, dict):
            if data.get("success") is False:
                print(f"WARNING: TronGrid API returned success: false: {data.get('message')}")
                return {"message": data.get("message", "Erro na API Tron.")}
            if "data" in data and len(data["data"]) == 0:
                print(f"DEBUG: TronGrid API returned empty data for URL: {url}")
                return {"message": "Conta Tron sem dados ou inexistente."} # Retorna como aviso/sem dados
        
        return data # Retorna os dados completos se tudo deu certo
    except requests.exceptions.Timeout:
        print(f"Erro de timeout ao conectar a {url}")
        return {"error_fatal": "Timeout na requisição da API."} 
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição para {url}: {e}")
        return {"error_fatal": f"Erro na requisição da API: {e}"} 
    except json.JSONDecodeError:
        print(f"Erro ao decodificar JSON de {url}. Resposta: {response.text[:200]}...")
        return {"error_fatal": "Resposta inválida da API (não é JSON)."}


# --- Funções de Consulta Específicas por Rede ---

def get_btc_data(address, api_key=None):
    """Obtém saldo e histórico para Bitcoin usando Blockstream.info."""
    config = API_CONFIG["BTC"]
    summary_url = f"{config['base_url']}/address/{address}"
    summary_data = _fetch_data(summary_url) # api_key é passado mas Blockstream.info não usa

    # Inicializa com 0
    balance_satoshi_received = Decimal(0)
    balance_satoshi_spent = Decimal(0)
    tx_count = 0
    
    has_transactions = False
    has_real_balance = False # Para indicar se há saldo real (recebido - gasto > 0)

    if isinstance(summary_data, dict) and summary_data.get("error_fatal"):
        print(f"Erro fatal BTC: {summary_data['error_fatal']}")
        return {"error_fatal": summary_data["error_fatal"]}
    
    if isinstance(summary_data, dict) and summary_data.get("message"):
        print(f"Aviso BTC: {summary_data['message']}")
        return {
            "balance_crypto": Decimal(0), "balance_usd": Decimal(0),
            "has_transactions": False, "explorer_link": f"{config['explorer_link_base']}{address}",
            "balance_satoshi": Decimal(0), "has_real_balance": False
        }
    
    if summary_data is None: 
        print(f"Aviso BTC: Sem dados de resumo para o endereço (pode ser novo/vazio).")
        return {
            "balance_crypto": Decimal(0), "balance_usd": Decimal(0),
            "has_transactions": False, "explorer_link": f"{config['explorer_link_base']}{address}",
            "balance_satoshi": Decimal(0), "has_real_balance": False
        }

    if isinstance(summary_data, dict): 
        chain_stats = summary_data.get("chain_stats", {})
        mempool_stats = summary_data.get("mempool_stats", {})
        
        balance_satoshi_received = Decimal(chain_stats.get("funded_txo_sum", 0)) + Decimal(mempool_stats.get("funded_txo_sum", 0))
        balance_satoshi_spent = Decimal(chain_stats.get("spent_txo_sum", 0)) + Decimal(mempool_stats.get("spent_txo_sum", 0))
        tx_count = chain_stats.get("tx_count", 0) + mempool_stats.get("tx_count", 0)

        if tx_count > 0:
            has_transactions = True
    
    balance_satoshi_net = balance_satoshi_received - balance_satoshi_spent
    if balance_satoshi_net > 0:
        has_real_balance = True

    balance_btc = balance_satoshi_net / Decimal("100000000")
    balance_usd = balance_btc * MOCKED_PRICES_USD["BTC"]

    return {
        "balance_crypto": balance_btc,
        "balance_usd": balance_usd,
        "has_transactions": has_transactions,
        "has_real_balance": has_real_balance,
        "explorer_link": f"{config['explorer_link_base']}{address}",
        "balance_satoshi": balance_satoshi_net
    }


def get_evm_data(address, network, api_key=None):
    """Obtém saldo (moeda nativa e USDT) e histórico para redes EVM usando Etherscan V2 API unificada."""
    evm_common_config = API_CONFIG["EVM_COMMON"]
    base_url_v2_unified = evm_common_config["base_url_v2_unified"]
    chain_id = evm_common_config["chain_ids"][network]
    usdt_contract_address = evm_common_config["usdt_contracts"][network]

    results = {
        "balance_crypto": Decimal(0),
        "balance_usd": Decimal(0),
        "has_transactions": False,
        "explorer_link": f"{evm_common_config['explorer_link_base'][network]}{address}",
        "has_real_balance": False
    }

    # Helper para parâmetros V2
    def _get_v2_params(action_name):
        return {
            "module": "account",
            "action": action_name,
            "address": address,
            "chainid": chain_id,
            "tag": "latest"
        }

    # 1. Obter saldo da moeda nativa (Etherscan V2)
    native_balance_params = _get_v2_params("balance")
    native_balance_data = _fetch_data(base_url_v2_unified, params=native_balance_params, api_key=api_key)

    if isinstance(native_balance_data, dict) and native_balance_data.get("error_fatal"):
        print(f"Erro fatal {network} (saldo nativo V2): {native_balance_data['error_fatal']}")
        return {"error_fatal": native_balance_data["error_fatal"]}
    elif isinstance(native_balance_data, dict) and native_balance_data.get("status") == "1":
        balance_wei_str = native_balance_data.get("result", "0")
        try:
            balance_wei = Decimal(balance_wei_str)
            balance_native = balance_wei / Decimal("1e18")
            results["balance_crypto"] += balance_native
            results["balance_usd"] += balance_native * MOCKED_PRICES_USD.get(network, MOCKED_PRICES_USD["ETH"])
            if balance_native > 0:
                results["has_real_balance"] = True
            print(f"DEBUG: {network} Saldo Nativo: {balance_native} (USD: {balance_native * MOCKED_PRICES_USD.get(network, MOCKED_PRICES_USD['ETH'])})")
        except Exception as e:
            print(f"WARNING: Erro ao converter saldo nativo para {network}: {balance_wei_str}. Erro: {e}")
    elif isinstance(native_balance_data, dict) and native_balance_data.get("message"):
        print(f"Aviso {network} (saldo nativo V2): {native_balance_data.get('message')}")

    # 2. Obter saldo de USDT (Etherscan V2)
    if usdt_contract_address:
        usdt_balance_params = _get_v2_params("tokenbalance")
        usdt_balance_params["contractaddress"] = usdt_contract_address
        usdt_balance_data = _fetch_data(base_url_v2_unified, params=usdt_balance_params, api_key=api_key)

        if isinstance(usdt_balance_data, dict) and usdt_balance_data.get("error_fatal"):
            print(f"Erro fatal {network} (saldo USDT V2): {usdt_balance_data['error_fatal']}")
            return {"error_fatal": usdt_balance_data["error_fatal"]}
        elif isinstance(usdt_balance_data, dict) and usdt_balance_data.get("status") == "1":
            balance_usdt_raw_str = usdt_balance_data.get("result", "0")
            try:
                balance_usdt_raw = Decimal(balance_usdt_raw_str)
                balance_usdt = balance_usdt_raw / Decimal("1e6") # USDT geralmente tem 6 decimais
                results["balance_crypto"] += balance_usdt
                results["balance_usd"] += balance_usdt * MOCKED_PRICES_USD["USDT"]
                if balance_usdt > 0:
                    results["has_real_balance"] = True
                print(f"DEBUG: {network} Saldo USDT: {balance_usdt} (USD: {balance_usdt * MOCKED_PRICES_USD['USDT']})")
            except Exception as e:
                print(f"WARNING: Erro ao converter saldo USDT para {network}: {balance_usdt_raw_str}. Erro: {e}")
        elif isinstance(usdt_balance_data, dict) and usdt_balance_data.get("message"):
            print(f"Aviso {network} (saldo USDT V2): {usdt_balance_data.get('message', 'Sem dados de saldo USDT (endereço pode ser novo/vazio).')}")


    # 3. Verificar histórico de transações (nativas e de token) (Etherscan V2)
    tx_params = _get_v2_params("txlist")
    tx_params["page"] = 1
    tx_params["offset"] = 1 # Apenas 1 para verificar existência
    tx_params["sort"] = "desc"
    
    tx_list_data = _fetch_data(base_url_v2_unified, params=tx_params, api_key=api_key)

    if isinstance(tx_list_data, dict) and tx_list_data.get("error_fatal"):
        print(f"Erro fatal {network} (histórico V2): {tx_list_data['error_fatal']}")
        # Not returning here, already handled balances. has_transactions will remain False if error.
    elif isinstance(tx_list_data, dict) and tx_list_data.get("status") == "1":
        if isinstance(tx_list_data.get("result"), list) and len(tx_list_data["result"]) > 0:
            results["has_transactions"] = True
            print(f"DEBUG: {network} Encontrado histórico de transações.")
        elif tx_list_data.get("result") == "0" or (isinstance(tx_list_data.get("result"), str) and "no transactions found" in tx_list_data.get("message", "").lower()):
            print(f"DEBUG: {network} Sem transações nativas encontradas (status 1, result 0 ou 'no transactions found').")
        else:
             print(f"DEBUG: {network} Resposta de histórico nativo inesperada: {tx_list_data}")
    elif isinstance(tx_list_data, dict) and tx_list_data.get("message"):
        print(f"Aviso {network} (histórico V2): {tx_list_data.get('message', 'Sem dados de histórico.')}")
    
    # Adicional: Verificar transações de token também para `has_transactions`
    # Pois um endereço pode não ter ETH mas ter USDT e transacionar USDT
    if usdt_contract_address:
        token_tx_params = _get_v2_params("tokentx")
        token_tx_params["contractaddress"] = usdt_contract_address
        token_tx_params["page"] = 1
        token_tx_params["offset"] = 1
        token_tx_params["sort"] = "desc"

        token_tx_list_data = _fetch_data(base_url_v2_unified, params=token_tx_params, api_key=api_key)
        if isinstance(token_tx_list_data, dict) and token_tx_list_data.get("status") == "1":
            if isinstance(token_tx_list_data.get("result"), list) and len(token_tx_list_data["result"]) > 0:
                results["has_transactions"] = True
                print(f"DEBUG: {network} Encontrado histórico de transações de token.")
            elif token_tx_list_data.get("result") == "0" or (isinstance(token_tx_list_data.get("result"), str) and "no transactions found" in token_tx_list_data.get("message", "").lower()):
                print(f"DEBUG: {network} Sem transações de token encontradas (status 1, result 0 ou 'no transactions found').")
            else:
                 print(f"DEBUG: {network} Resposta de histórico de token inesperada: {token_tx_list_data}")


    return results


def get_trx_data(address, api_key=None):
    """Obtém saldo (TRX nativo e USDT-TRC20) e histórico para Tron usando TronGrid."""
    config = API_CONFIG["TRX"]
    base_url = config["base_url"]
    
    results = {
        "balance_crypto": Decimal(0),
        "balance_usd": Decimal(0),
        "has_transactions": False,
        "explorer_link": f"{config['explorer_link_base']}{address}",
        "has_real_balance": False
    }

    # 1. Obter saldo nativo TRX e tokens (usando TronGrid API)
    account_info_url = f"{base_url}/v1/accounts/{address}"
    account_data = _fetch_data(account_info_url, api_key=api_key)

    if isinstance(account_data, dict) and account_data.get("error_fatal"):
        print(f"Erro fatal TRX (saldo nativo/tokens): {account_data['error_fatal']}")
        return {"error_fatal": account_data["error_fatal"]}
    elif isinstance(account_data, dict) and account_data.get("message"):
        print(f"Aviso TRX (saldo nativo/tokens): {account_data['message']}")
        return results 
    
    if isinstance(account_data, dict) and "data" in account_data and len(account_data["data"]) > 0:
        account_details = account_data["data"][0]

        balance_suns = Decimal(account_details.get("balance", 0))
        balance_trx = balance_suns / Decimal("1e6") # 1 TRX = 1,000,000 SUN
        results["balance_crypto"] += balance_trx
        results["balance_usd"] += balance_trx * MOCKED_PRICES_USD["TRX"]
        if balance_trx > 0:
            results["has_real_balance"] = True
        print(f"DEBUG: TRX Saldo Nativo: {balance_trx} (USD: {balance_trx * MOCKED_PRICES_USD['TRX']})")
        
        usdt_contract_address_trx = config.get("usdt_contract")
        if usdt_contract_address_trx and "trc20" in account_details:
            for trc20_token_info in account_details["trc20"]:
                if usdt_contract_address_trx in trc20_token_info:
                    balance_usdt_raw = Decimal(trc20_token_info[usdt_contract_address_trx])
                    balance_usdt = balance_usdt_raw / Decimal("1e6")
                    results["balance_crypto"] += balance_usdt
                    results["balance_usd"] += balance_usdt * MOCKED_PRICES_USD["USDT"]
                    if balance_usdt > 0:
                        results["has_real_balance"] = True
                    print(f"DEBUG: TRX Saldo USDT: {balance_usdt} (USD: {balance_usdt * MOCKED_PRICES_USD['USDT']})")
                    break
    
    # 3. Verificar histórico de transações (usando TronGrid API)
    tx_list_url = f"{base_url}/v1/accounts/{address}/transactions"
    params_tx_list = {
        "limit": 1,
        "order_by": "block_timestamp,desc"
    }
    tx_list_data = _fetch_data(tx_list_url, params=params_tx_list, api_key=api_key)

    if isinstance(tx_list_data, dict) and tx_list_data.get("error_fatal"):
        print(f"Erro fatal TRX (histórico): {tx_list_data['error_fatal']}")
        return {"error_fatal": tx_list_data["error_fatal"]}
    elif isinstance(tx_list_data, dict) and tx_list_data.get("message"):
        print(f"Aviso TRX (histórico): {tx_list_data.get('message', 'Sem dados de transação ou erro desconhecido.')}")
    elif isinstance(tx_list_data, dict) and "data" in tx_list_data and len(tx_list_data["data"]) > 0:
        results["has_transactions"] = True
        print(f"DEBUG: TRX Encontrado histórico de transações.")

    return results


def get_blockchain_data(address, network, api_key=None):
    """
    Função principal para obter dados da blockchain, roteando para a função correta.
    Retorna saldo, histórico de transações e link para o explorador.
    """
    mapped_api_key = api_key 

    try:
        if network == "BTC":
            return get_btc_data(address, mapped_api_key)
        elif network in ["ETH", "BSC", "MATIC", "BASE", "OPTIMISM", "ARBITRUM"]:
            return get_evm_data(address, network, mapped_api_key)
        elif network == "TRX":
            return get_trx_data(address, mapped_api_key)
        else:
            print(f"Aviso: Rede {network} não suportada para consulta de dados on-chain.")
            return {
                "balance_crypto": Decimal(0),
                "balance_usd": Decimal(0),
                "has_transactions": False,
                "explorer_link": "#",
                "error": "Rede não suportada para consulta de dados on-chain."
            }
    except Exception as e:
        print(f"Erro inesperado ao buscar dados para {address} na rede {network}: {str(e)}")
        return {
            "balance_crypto": Decimal(0),
            "balance_usd": Decimal(0),
            "has_transactions": False,
            "explorer_link": "#",
            "error_fatal": f"Erro interno ao consultar dados: {str(e)}"
        }
