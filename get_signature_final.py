import os
import subprocess
import re

# --- CONFIGURAÇÕES ---
# Caminho relativo padrão do Capacitor Android
KEYSTORE_DIR = "android/app"
KEYSTORE_FILE = "debug.keystore"
KEYSTORE_PATH = os.path.join(KEYSTORE_DIR, KEYSTORE_FILE)
GRADLE_PATH = "android/app/build.gradle"
PACKAGE_NAME = "com.motoristapro.app"

def run_command(command, show_error=True):
    try:
        # shell=True para reconhecer comandos do sistema
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return result.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        if show_error:
            print(f"❌ Erro ao executar: {command}")
            print(f"   Detalhes: {e.output.decode('utf-8')}")
        return None

def check_java():
    print("☕ Verificando Java...")
    # Tenta rodar keytool direto
    version = run_command("keytool -help", show_error=False)
    if version:
        print("✅ Keytool encontrado.")
        return True
    
    print("⚠️ Keytool não encontrado. Tentando instalar Java...")
    run_command("pkg install openjdk-17 -y")
    return True

def generate_keystore():
    print(f"\n🔑 Gerando Keystore em: {KEYSTORE_PATH}...")
    
    # Garante que a pasta existe
    if not os.path.exists(KEYSTORE_DIR):
        os.makedirs(KEYSTORE_DIR)
        print(f"   Pasta criada: {KEYSTORE_DIR}")

    # Se já existe, remove para criar uma nova limpa
    if os.path.exists(KEYSTORE_PATH):
        os.remove(KEYSTORE_PATH)
        print("   Keystore antiga removida.")

    # Comando Keytool (Uma linha só)
    cmd = (
        f'keytool -genkey -v -keystore "{KEYSTORE_PATH}" '
        f'-storepass android -alias androiddebugkey -keypass android '
        f'-keyalg RSA -keysize 2048 -validity 10000 '
        f'-dname "CN=Android Debug,O=Android,C=US"'
    )
    
    result = run_command(cmd)
    
    if os.path.exists(KEYSTORE_PATH):
        print("✅ Keystore criada com sucesso!")
        return True
    else:
        print("❌ Falha crítica ao criar keystore.")
        return False

def get_sha1():
    print("\n🔍 Extraindo SHA-1...")
    cmd = f'keytool -list -v -keystore "{KEYSTORE_PATH}" -storepass android'
    output = run_command(cmd)
    
    if output:
        # Regex para achar o SHA1 (formato XX:XX:XX...)
        match = re.search(r'SHA1:\s*([0-9A-F:]+)', output, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def configure_gradle():
    print("\n⚙️ Configurando Gradle...")
    if not os.path.exists(GRADLE_PATH):
        print(f"⚠️ Aviso: {GRADLE_PATH} não encontrado. (Isso é normal se você não rodou 'npx cap add android' localmente, o GitHub fará isso).")
        print("   Vamos pular essa etapa e confiar no GitHub Actions.")
        return

    with open(GRADLE_PATH, 'r') as f:
        content = f.read()

    # Se já tem config, sai
    if "signingConfigs {" in content and "debug.keystore" in content:
        print("✅ Gradle já estava configurado.")
        return

    # Injeta configuração de assinatura
    signing_config = '''
    signingConfigs {
        debug {
            storeFile file("debug.keystore")
            storePassword "android"
            keyAlias "androiddebugkey"
            keyPassword "android"
        }
    }
    buildTypes {'''
    
    new_content = content.replace("buildTypes {", signing_config)
    
    with open(GRADLE_PATH, 'w') as f:
        f.write(new_content)
    print("✅ Gradle atualizado com assinatura.")

def main():
    print("🚀 SCRIPT DE ASSINATURA FIXA - MOTORISTAPRO")
    
    if not check_java():
        print("❌ Erro: Java não pôde ser instalado. Tente rodar 'pkg install openjdk-17' manualmente.")
        return

    if generate_keystore():
        sha1 = get_sha1()
        
        print("\n" + "="*50)
        print("📋 DADOS PARA O GOOGLE CLOUD CONSOLE")
        print("="*50)
        print(f"\n📦 Nome do Pacote:\n{PACKAGE_NAME}")
        print(f"\n🔑 Impressão Digital SHA-1 (Copie isso):\n{sha1}")
        print("\n" + "="*50)
        
        if sha1:
            print("\n☁️ Enviando Keystore para o GitHub...")
            # Força a adição do arquivo binário
            run_command(f'git add -f "{KEYSTORE_PATH}"')
            run_command("git add .")
            run_command('git commit -m "chore: Add Fixed Debug Keystore"')
            run_command("git push origin main")
            print("✅ Sucesso! A chave foi enviada.")
            print("   Agora configure o Google Cloud e gere o novo APK.")
        else:
            print("❌ Erro: Não foi possível ler o SHA-1 da chave gerada.")

if __name__ == "__main__":
    main()


