// Variável global para armazenar todos os endereços derivados
let allDerivedWalletsData = [];

async function searchAddresses() {
    const seedPhrase = document.getElementById('seedPhrase').value.trim();
    if (!seedPhrase) {
        alert('Por favor, insira a seed mnemônica.');
        return;
    }

    const selectedNetworks = Array.from(document.querySelectorAll('input[name="network"]:checked'))
                               .map(checkbox => checkbox.value);
    
    if (selectedNetworks.length === 0) {
        alert('Por favor, selecione pelo menos uma rede/blockchain para análise.');
        return;
    }

    // Coleta os tipos de endereço Bitcoin selecionados
    let btcAddressTypes = [];
    if (selectedNetworks.includes('BTC')) {
        btcAddressTypes = Array.from(document.querySelectorAll('input[name="btcAddressType"]:checked'))
                               .map(checkbox => checkbox.value);
        if (btcAddressTypes.length === 0) {
            alert('Você selecionou Bitcoin. Por favor, selecione pelo menos um tipo de endereço Bitcoin (Legacy, SegWit, etc.).');
            return;
        }
    }

    const accountRange = document.getElementById('accountRange').value;
    const indexRange = document.getElementById('indexRange').value;

    // Coleta os tipos de cadeia (change) selecionados
    let changeTypes = Array.from(document.querySelectorAll('input[name="changeType"]:checked'))
                             .map(checkbox => parseInt(checkbox.value)); // Converter para inteiro

    if (changeTypes.length === 0) {
        alert('Por favor, selecione pelo menos um tipo de cadeia de endereços (Externa/Interna).');
        return;
    }
    
    // INÍCIO DA ALTERAÇÃO
    const usePassphrase = document.getElementById('usePassphrase').checked;
    const passphrase = usePassphrase ? document.getElementById('passphrase').value : '';
    // FIM DA ALTERAÇÃO

    // Safely get API keys, defaulting to empty string if element is null
    const apiKeyEthereumElement = document.getElementById('apiKeyEthereum');
    const apiKeyTronElement = document.getElementById('apiKeyTron');

    const apiKeys = {
        ethereum: apiKeyEthereumElement ? apiKeyEthereumElement.value.trim() : '',
        tron: apiKeyTronElement ? apiKeyTronElement.value.trim() : ''
    };

    // Exibir spinner e área de resultados, esconder mensagens de erro
    document.getElementById('loadingSpinner').style.display = 'inline';
    document.querySelector('.results-area').style.display = 'block';
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('errorMessage').textContent = '';
    
    // Limpa tbody e atualiza total USD para 0 antes de cada nova busca
    document.getElementById('resultsTable').querySelector('tbody').innerHTML = ''; 
    document.getElementById('totalUsdValue').textContent = '$0.00'; 
    document.getElementById('foundCount').textContent = '0';
    allDerivedWalletsData = []; // Limpa a lista de todos os endereços antes de uma nova busca

    document.getElementById('searchButton').disabled = true; // Desabilita o botão para evitar cliques múltiplos
    document.getElementById('searchButton').textContent = 'Buscando...';


    try {
        const response = await fetch('/derive_and_check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            // INÍCIO DA ALTERAÇÃO
            body: JSON.stringify({
                seed_phrase: seedPhrase,
                passphrase: passphrase, // Passphrase adicionada
                selected_networks: selectedNetworks,
                account_indices: accountRange,
                address_indices: indexRange,
                bitcoin_address_types: btcAddressTypes,
                api_keys: apiKeys, 
                change_types: changeTypes
            })
            // FIM DA ALTERAÇÃO
        });

        const result = await response.json();

        if (response.ok) {
            displayResults(result.results);
            allDerivedWalletsData = result.all_derived_wallets || []; 
        } else {
            document.getElementById('errorMessage').textContent = `Erro: ${result.error || 'Ocorreu um erro desconhecido.'}`;
            document.getElementById('errorMessage').style.display = 'block';
        }

    } catch (error) {
        console.error('Erro na requisição:', error);
        document.getElementById('errorMessage').textContent = `Erro de conexão: ${error.message}. Verifique o console do navegador para detalhes.`;
        document.getElementById('errorMessage').style.display = 'block';
    } finally {
        document.getElementById('loadingSpinner').style.display = 'none';
        document.getElementById('searchButton').disabled = false; // Reabilita o botão
        document.getElementById('searchButton').textContent = 'Buscar Endereços';
    }
}

function displayResults(results) {
    const tbody = document.getElementById('resultsTable').querySelector('tbody');
    tbody.innerHTML = ''; // Limpa qualquer resultado anterior
    document.getElementById('foundCount').textContent = results.length;

    let totalUsdSum = 0; // Variável para somar os USD

    if (results.length === 0) {
        const row = tbody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 7; // Ajustado para o novo número de colunas (7)
        cell.textContent = 'Nenhum endereço com saldo ou histórico encontrado para os parâmetros informados.';
        cell.style.textAlign = 'center';
        cell.style.fontStyle = 'italic';
        cell.style.color = 'var(--text-secondary)';
    } else {
        results.forEach(item => {
            const row = tbody.insertRow();
            
            const addressCell = row.insertCell();
            addressCell.textContent = item.address;
            addressCell.style.wordBreak = 'break-all';

            const networkCell = row.insertCell();
            networkCell.textContent = item.network;
            
            const balanceCryptoNum = parseFloat(item.balance_crypto);
            const balanceUsdNum = parseFloat(item.balance_usd);

            let balanceDisplay = '';
            let statusClass = '';

            if (item.has_real_balance) {
                if (item.network === 'BTC' && typeof item.balance_satoshi !== 'undefined') {
                    balanceDisplay = `${item.balance_satoshi} Satoshis`; 
                } else {
                    balanceDisplay = `${balanceCryptoNum.toFixed(8)} ${item.network || ''}`; 
                }
                statusClass = 'indicator-saldo';
            } else if (item.has_transactions) {
                balanceDisplay = `0 ${item.network || ''} (Histórico)`;
                statusClass = 'indicator-historico';
            } else {
                balanceDisplay = `0 ${item.network || ''} (Vazio)`;
                statusClass = 'indicator-vazio';
            }
            
            const balanceCell = row.insertCell();
            balanceCell.textContent = balanceDisplay;
            balanceCell.classList.add(statusClass);

            const usdCell = row.insertCell();
            const displayUsd = !isNaN(balanceUsdNum) && balanceUsdNum > 0 ? `$${balanceUsdNum.toFixed(2)}` : 'N/A';
            usdCell.textContent = displayUsd;
            if (!isNaN(balanceUsdNum) && balanceUsdNum > 0) {
                totalUsdSum += balanceUsdNum;
            }
            
            const pathCell = row.insertCell();
            pathCell.textContent = item.derivation_path;
            
            const pkCell = row.insertCell();
            pkCell.classList.add('private-key-cell');
            const pkTextSpan = document.createElement('span');
            pkTextSpan.textContent = item.private_key;

            const copyButton = document.createElement('button');
            copyButton.textContent = '📋';
            copyButton.title = 'Copiar chave privada';
            copyButton.classList.add('copy-btn');
            copyButton.onclick = async () => {
                try {
                    await navigator.clipboard.writeText(item.private_key);
                    copyButton.textContent = '✅';
                    setTimeout(() => { copyButton.textContent = '📋'; }, 2000);
                } catch (err) {
                    console.error('Falha ao copiar:', err);
                    alert('Erro ao copiar a chave privada.');
                }
            };

            pkCell.appendChild(pkTextSpan);
            pkCell.appendChild(copyButton);

            const explorerCell = row.insertCell();
            const explorerLink = document.createElement('a');
            explorerLink.href = item.explorer_link;
            explorerLink.target = '_blank';
            explorerLink.textContent = '🔍';
            explorerLink.title = 'Ver no explorador';
            explorerCell.appendChild(explorerLink);
            explorerCell.style.textAlign = 'center';
        });
    }

    document.getElementById('totalUsdValue').textContent = `$${totalUsdSum.toFixed(2)}`;
}

function exportResults(format) {
    if (format === 'csv') {
        const table = document.getElementById('resultsTable');
        const rows = table.querySelectorAll('tr');
        let csvContent = "";

        csvContent += "\ufeff"; 

        const headers = [];
        table.querySelectorAll('thead th').forEach(th => {
            headers.push(`"${th.textContent.trim()}"`);
        });
        csvContent += headers.join(',') + '\n';

        rows.forEach((row, rowIndex) => {
            if (rowIndex === 0 || row.closest('tfoot')) {
                return; 
            }

            const rowData = [];
            row.querySelectorAll('td').forEach((cell, cellIndex) => {
                let text;
                if (cell.classList.contains('private-key-cell')) {
                    const pkSpan = cell.querySelector('span');
                    text = pkSpan ? pkSpan.textContent.trim() : '';
                } else if (cellIndex === 6) {
                    const linkElement = cell.querySelector('a');
                    text = linkElement ? linkElement.href : '';
                }
                else {
                    text = cell.textContent.trim();
                }
                
                rowData.push(`"${text.replace(/"/g, '""')}"`);
            });
            if (rowData.length > 0) {
                csvContent += rowData.join(',') + '\n';
            }
        });

        const totalUsdValue = document.getElementById('totalUsdValue').textContent;
        csvContent += `\n"",,,,"Total USD","${totalUsdValue}"\n`; 


        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', 'fenix_resultados_filtrados.csv');
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } else {
            alert('Seu navegador não suporta download automático de arquivos. Por favor, copie o conteúdo e salve como .csv manualmente.');
            console.log(csvContent);
        }
    } else {
        alert(`Formato de exportação ${format.toUpperCase()} não suportado.`);
    }
}

function exportAllResultsToCsv() {
    if (allDerivedWalletsData.length === 0) {
        alert('Não há endereços derivados para exportar. Por favor, execute uma busca primeiro.');
        return;
    }

    let csvContent = "";

    csvContent += "\ufeff"; 

    const headers = ["Endereço", "Rede", "Caminho Derivação", "Chave Privada", "Tipo de Endereço"];
    csvContent += headers.map(h => `"${h}"`).join(',') + '\n';

    allDerivedWalletsData.forEach(item => {
        const rowData = [
            item.address,
            item.network,
            item.derivation_path,
            item.private_key,
            item.address_type || 'N/A'
        ].map(data => `"${String(data).replace(/"/g, '""')}"`);
        csvContent += rowData.join(',') + '\n';
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', 'fenix_todos_enderecos.csv');
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } else {
        alert('Seu navegador não suporta download automático de arquivos. Por favor, copie o conteúdo e salve como .csv manualmente.');
        console.log(csvContent);
    }
}


function uploadApiKeys() {
    const fileInput = document.getElementById('apiKeyUpload');
    const file = fileInput.files[0];

    if (!file) {
        alert('Por favor, selecione um arquivo .txt para carregar.');
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const lines = content.split('\n');
        let keysLoadedCount = 0;
        lines.forEach(line => {
            const trimmedLine = line.trim();
            if (trimmedLine && trimmedLine.includes('=')) {
                const parts = trimmedLine.split('=', 2);
                const keyName = parts[0].trim().toLowerCase();
                const keyValue = parts[1].trim();

                const targetElement = document.getElementById(`apiKey${keyName.charAt(0).toUpperCase() + keyName.slice(1)}`);
                if (targetElement) {
                    targetElement.value = keyValue;
                    keysLoadedCount++;
                }
            }
        });
        alert(`Chaves carregadas do arquivo: ${keysLoadedCount} chave(s) preenchida(s).`);
        fileInput.value = '';
    };
    reader.readAsText(file);
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelector('.results-area').style.display = 'none';
    
    const btcCheckbox = document.getElementById('btcCheckbox');
    const btcAddressTypesDiv = document.querySelector('.btc-address-types');
    
    if (btcCheckbox && btcAddressTypesDiv) {
        btcCheckbox.addEventListener('change', () => {
            btcAddressTypesDiv.style.display = btcCheckbox.checked ? 'block' : 'none';
            if (!btcCheckbox.checked) {
                document.querySelectorAll('.btc-address-types input[type="checkbox"]').forEach(cb => cb.checked = false);
            }
        });
    }
    
    // INÍCIO DA ALTERAÇÃO
    const usePassphraseCheckbox = document.getElementById('usePassphrase');
    const passphraseGroup = document.getElementById('passphraseGroup');

    if (usePassphraseCheckbox && passphraseGroup) {
        usePassphraseCheckbox.addEventListener('change', () => {
            if (usePassphraseCheckbox.checked) {
                passphraseGroup.style.display = 'block';
            } else {
                passphraseGroup.style.display = 'none';
                document.getElementById('passphrase').value = '';
            }
        });
    }
    // FIM DA ALTERAÇÃO
    
    const searchButton = document.getElementById('searchButton');
    const resultsArea = document.querySelector('.results-area');
    
    if (searchButton && resultsArea) {
        searchButton.addEventListener('click', () => {
            if (resultsArea.style.display === 'block') {
                resultsArea.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }
});
