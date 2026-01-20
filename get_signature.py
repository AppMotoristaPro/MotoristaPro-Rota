import os
import subprocess
import re

# --- CONFIGURAÇÕES ---
KEYSTORE_PATH = "android/app/debug.keystore"
GRADLE_PATH = "android/app/build.gradle"
PACKAGE_NAME = "com.motoristapro.app"

def run_command(command):
    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return result.decode('utf-8')
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar: {command}")
        print(e.output.decode('utf-8'))
        return None

def install_java():
    print("📦 Verificando Java (necessário para gerar chaves)...")
    if run_command("which keytool"):
        print("✅ Java já instalado.")
        return True
    
    print("⬇️ Instalando OpenJDK...")
    run_command("pkg install openjdk-17 -y")
    return True

def generate_keystore():
    print("\n🔑 Gerando Keystore Fixa...")
    if os.path.exists(KEYSTORE_PATH):
        os.remove(KEYSTORE_PATH)
    
    # Gera uma chave padrão Android Debug
    cmd = f'keytool -genkey -v -keystore {KEYSTORE_PATH} -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US"'
    run_command(cmd)
    
    if os.path.exists(KEYSTORE_PATH):
        print("✅ Keystore criada com sucesso em android/app/debug.keystore")
        return True
    else:
        print("❌ Falha ao criar keystore.")
        return False

def configure_gradle():
    print("\n⚙️ Configurando Gradle para usar a chave fixa...")
    if not os.path.exists(GRADLE_PATH):
        print("❌ Arquivo build.gradle não encontrado.")
        return False

    with open(GRADLE_PATH, 'r') as f:
        content = f.read()

    # Verifica se já tem a config
    if "signingConfigs {" in content and "debug.keystore" in content:
        print("✅ Gradle já configurado.")
        return True

    # Injeta a configuração de assinatura antes de buildTypes
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
    
    # Garante que o buildType debug use a assinatura
    if "signingConfig signingConfigs.debug" not in new_content:
        # Tenta injetar dentro do bloco debug se existir, ou cria um simples
        # Abordagem simplificada: O default do android debug já tenta usar a config se o nome for 'debug'
        pass

    with open(GRADLE_PATH, 'w') as f:
        f.write(new_content)
    
    print("✅ Gradle atualizado.")
    return True

def get_sha1():
    print("\n🔍 Lendo Impressão Digital SHA-1...")
    output = run_command(f'keytool -list -v -keystore {KEYSTORE_PATH} -storepass android')
    
    if not output: return None

    # Procura por "SHA1: XX:XX:..."
    match = re.search(r'SHA1: ([0-9A-F:]+)', output)
    if match:
        return match.group(1)
    return None

def main():
    print("🚀 CONFIGURANDO ASSINATURA PARA GOOGLE MAPS")
    
    install_java()
    generate_keystore()
    configure_gradle()
    
    sha1 = get_sha1()
    
    print("\n" + "="*40)
    print("📋 DADOS PARA O GOOGLE CLOUD CONSOLE")
    print("="*40)
    print(f"\n📦 Nome do Pacote:\n{PACKAGE_NAME}")
    print(f"\n🔑 Impressão Digital SHA-1:\n{sha1}")
    print("\n" + "="*40)
    
    print("\n☁️ Salvando chave fixa no GitHub...")
    run_command("git add .")
    run_command('git commit -m "chore: Add Fixed Keystore for Google Maps"')
    run_command("git push origin main")
    print("✅ Salvo! Agora o SHA-1 será sempre o mesmo.")

if __name__ == "__main__":
    main()


