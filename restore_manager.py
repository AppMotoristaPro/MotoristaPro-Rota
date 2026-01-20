import os
import shutil
import subprocess
import re

# --- CONFIGURAÇÕES ---
BACKUP_ROOT = "backup"
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"

def get_backups():
    if not os.path.exists(BACKUP_ROOT):
        return []
    # Lista todas as pastas dentro de backup/ e ordena por nome (data)
    backups = [d for d in os.listdir(BACKUP_ROOT) if os.path.isdir(os.path.join(BACKUP_ROOT, d))]
    backups.sort(reverse=True) # Mais recentes primeiro
    return backups

def restore_backup(backup_folder):
    source = os.path.join(BACKUP_ROOT, backup_folder)
    print(f"\n♻️ Restaurando arquivos de: {backup_folder}...")
    
    # Copia recursivamente
    for root, dirs, files in os.walk(source):
        # Determina o caminho relativo para replicar na raiz
        rel_path = os.path.relpath(root, source)
        dest_dir = rel_path if rel_path != "." else "."
        
        # Cria diretórios se não existirem
        if dest_dir != "." and not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            
        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(dest_dir, file)
            shutil.copy2(src_file, dest_file)
            print(f"   └── Restaurado: {os.path.join(dest_dir, file)}")

    print("\n✅ Arquivos restaurados com sucesso.")
    
    # --- CORREÇÃO AUTOMÁTICA PÓS-RESTAURAÇÃO ---
    # Para evitar que dados antigos corrompidos travem a versão restaurada,
    # vamos forçar o App a usar um novo banco de dados local.
    app_jsx_path = 'src/App.jsx'
    if os.path.exists(app_jsx_path):
        print("🔧 Aplicando vacina contra tela branca (Reset de Cache)...")
        with open(app_jsx_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Substitui chaves de localStorage antigas por uma nova única
        new_key = f"mp_restored_{backup_folder}"
        # Regex para encontrar padrões de localStorage.getItem('...')
        content = re.sub(r"localStorage\.getItem\(['\"].*?['\"]\)", f"localStorage.getItem('{new_key}')", content)
        content = re.sub(r"localStorage\.setItem\(['\"].*?['\"],", f"localStorage.setItem('{new_key}',", content)
        
        with open(app_jsx_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("   └── Banco de dados local renovado.")

def push_changes(version_name):
    print("\n☁️ Enviando versão restaurada para o GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run(f'git commit -m "revert: Restored backup form {version_name}"', shell=True)
    subprocess.run("git push origin main", shell=True)

def main():
    print("="*40)
    print("🛠️  GERENCIADOR DE RESTAURAÇÃO  🛠️")
    print("="*40)
    
    backups = get_backups()
    
    if not backups:
        print("❌ Nenhum backup encontrado na pasta 'backup/'.")
        print("Você precisará recriar o app do zero com um script anterior.")
        return

    print(f"\nEncontramos {len(backups)} versões anteriores:")
    print("-" * 30)
    for i, backup in enumerate(backups):
        # Tenta formatar a data para ficar legível
        try:
            display_name = f"Versão de {backup[6:8]}/{backup[4:6]}/{backup[0:4]} às {backup[9:11]}:{backup[11:13]}"
        except:
            display_name = backup
        print(f"[{i+1}] {display_name}  (Pasta: {backup})")
    print("-" * 30)
    print("[0] Cancelar e Sair")

    try:
        choice = int(input("\nQual versão você quer restaurar? Digite o número: "))
        if choice == 0:
            print("Operação cancelada.")
            return
        
        selected_backup = backups[choice - 1]
        
        print(f"\n⚠️  ATENÇÃO: Isso vai substituir todo o código atual pela versão {selected_backup}.")
        confirm = input("Tem certeza? (s/n): ")
        
        if confirm.lower() == 's':
            restore_backup(selected_backup)
            push_changes(selected_backup)
            print("\n🎉 CONCLUÍDO! A versão antiga foi enviada para o GitHub.")
            print("Aguarde a compilação do APK e instale novamente.")
        else:
            print("Cancelado.")
            
    except (ValueError, IndexError):
        print("\n❌ Opção inválida.")

if __name__ == "__main__":
    main()


