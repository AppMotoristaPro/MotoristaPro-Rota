import os
import sys

# --- CONFIGURAÇÕES ---

# Nome do arquivo final que será salvo em Downloads
NOME_ARQUIVO_SAIDA = "codigo_projeto_completo.txt"

# Caminho para a pasta de Downloads do Android (Padrão do Termux após setup-storage)
CAMINHO_DOWNLOADS = "/storage/emulated/0/Download"

# Pastas para IGNORAR (não queremos enviar isso para a IA, pois é lixo ou pesado)
IGNORAR_PASTAS = {
    '.git', '.gradle', '.idea', 'build', 'app/build', 
    'gradle', 'captures', '.cxx', 'node_modules', '__pycache__', '.dart_tool'
}

# Extensões de arquivos para IGNORAR (binários, imagens, etc)
IGNORAR_EXTENSOES = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp', '.svg', # Imagens
    '.jar', '.apk', '.aab', '.dex', '.class', '.so', # Binários Android/Java
    '.zip', '.tar', '.gz', '.rar', '.7z', # Compactados
    '.pdf', '.doc', '.docx', # Documentos
    '.lock', '.keystore', '.jks' # Outros
}

def is_text_file(filepath):
    """Tenta ler um pedaço do arquivo para ver se é texto ou binário."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            f.read(1024)
            return True
    except (UnicodeDecodeError,  UnicodeError):
        return False
    except Exception:
        return False

def main():
    # Pega o diretório atual onde o script está sendo rodado
    diretorio_projeto = os.getcwd()
    arquivo_saida = os.path.join(CAMINHO_DOWNLOADS, NOME_ARQUIVO_SAIDA)

    print(f"--- INICIANDO EXPORTAÇÃO ---")
    print(f"Lendo projeto em: {diretorio_projeto}")
    print(f"Ignorando pastas: {', '.join(IGNORAR_PASTAS)}")
    
    arquivos_processados = 0
    
    try:
        with open(arquivo_saida, 'w', encoding='utf-8') as out_f:
            # Cabeçalho do arquivo geral
            out_f.write(f"EXPORTAÇÃO DO PROJETO\n")
            out_f.write(f"Raiz: {os.path.basename(diretorio_projeto)}\n")
            out_f.write("="*50 + "\n\n")

            # Caminha por todas as pastas e subpastas
            for root, dirs, files in os.walk(diretorio_projeto):
                
                # Modifica a lista 'dirs' in-place para pular pastas ignoradas
                # Isso impede que o script entre dentro de .git ou build, economizando tempo
                dirs[:] = [d for d in dirs if d not in IGNORAR_PASTAS]

                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, diretorio_projeto)
                    
                    # Checa extensão ignorada
                    _, ext = os.path.splitext(file)
                    if ext.lower() in IGNORAR_EXTENSOES:
                        continue

                    # Checa se é o próprio script (não queremos copiar o script)
                    if file == os.path.basename(__file__) or file == NOME_ARQUIVO_SAIDA:
                        continue

                    # Tenta verificar se é arquivo de texto
                    if not is_text_file(file_path):
                        print(f"[PULADO - BINÁRIO] {rel_path}")
                        continue

                    # Escreve no arquivo final
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as in_f:
                            conteudo = in_f.read()
                            
                            # Formatação para a IA entender onde começa e termina cada arquivo
                            out_f.write(f"\n{'='*20} INICIO DO ARQUIVO: {rel_path} {'='*20}\n")
                            out_f.write(f"Caminho: {rel_path}\n")
                            out_f.write("-" * 50 + "\n")
                            out_f.write(conteudo)
                            out_f.write(f"\n{'='*20} FIM DO ARQUIVO: {rel_path} {'='*20}\n\n")
                            
                            print(f"[OK] {rel_path}")
                            arquivos_processados += 1

                    except Exception as e:
                        print(f"[ERRO AO LER] {rel_path}: {e}")

        print("\n" + "="*50)
        print(f"CONCLUÍDO! {arquivos_processados} arquivos processados.")
        print(f"Arquivo salvo em: {arquivo_saida}")
        print("Agora você pode enviar este arquivo pelo WhatsApp/Email para a IA.")

    except PermissionError:
        print("\n[ERRO CRÍTICO] Permissão negada!")
        print("Você esqueceu de dar permissão de armazenamento ao Termux.")
        print("Execute o comando: termux-setup-storage")
        print("E tente novamente.")
    except FileNotFoundError:
        print("\n[ERRO] A pasta de Downloads não foi encontrada ou o caminho está incorreto.")

if __name__ == "__main__":
    main()


