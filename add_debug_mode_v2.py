import os
import subprocess

# --- CONFIGURAÇÕES ---
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. CRIAR COMPONENTE DE DEBUG (ErrorBoundary.jsx)
# Este componente captura erros em qualquer lugar da árvore de componentes
files_content['src/ErrorBoundary.jsx'] = r'''import React from 'react';
import { AlertTriangle, Copy, Trash2, RefreshCw, Eye } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, showRaw: false };
  }

  static getDerivedStateFromError(error) {
    // Atualiza o state para que a próxima renderização mostre a UI alternativa.
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Você também pode registrar o erro em um serviço de relatório de erros
    console.error("ERRO CRÍTICO CAPTURADO:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  getLogText = () => {
      const { error, errorInfo } = this.state;
      
      // Coleta dados vitais
      const debugInfo = {
        TIMESTAMP: new Date().toLocaleString(),
        USER_AGENT: navigator.userAgent,
        ERROR_NAME: error?.name,
        ERROR_MESSAGE: error?.message,
        COMPONENT_STACK: errorInfo?.componentStack,
        // Tenta ler o localStorage para ver se há dados corrompidos
        LOCAL_STORAGE_KEYS: Object.keys(localStorage),
        DB_V36_PREVIEW: localStorage.getItem('mp_db_v36_final_v2')?.substring(0, 500) + '...'
      };
      
      return JSON.stringify(debugInfo, null, 2);
  }

  copyLog = () => {
    const text = this.getLogText();
    navigator.clipboard.writeText(text).then(() => {
        alert("LOG COPIADO! Cole no chat do suporte.");
    }).catch(err => {
        alert("Erro ao copiar automaticamente. Use o botão 'Ver Texto' e copie manualmente.");
    });
  };

  hardReset = () => {
      if(confirm("ISSO APAGARÁ TODAS AS ROTAS E DADOS LOCAIS. Continuar?")) {
          localStorage.clear();
          window.location.reload();
      }
  };

  render() {
    if (this.state.hasError) {
      // UI de Erro Personalizada
      return (
        <div className="min-h-screen bg-red-50 flex flex-col items-center justify-center p-6 text-red-900 font-sans">
          <div className="bg-white p-6 rounded-2xl shadow-xl w-full max-w-lg border border-red-200">
              <div className="flex flex-col items-center text-center mb-6">
                  <div className="bg-red-100 p-4 rounded-full mb-4">
                    <AlertTriangle size={48} className="text-red-600" />
                  </div>
                  <h1 className="text-2xl font-bold text-slate-900">O App Travou</h1>
                  <p className="text-slate-500 mt-2 text-sm">Ocorreu um erro inesperado. Por favor, copie o log abaixo e envie para o suporte.</p>
              </div>
              
              <div className="bg-slate-900 text-red-300 p-4 rounded-lg text-xs font-mono overflow-auto max-h-48 mb-4 border border-slate-700 shadow-inner">
                <p className="font-bold text-white mb-1 border-b border-slate-700 pb-1">ERRO TÉCNICO:</p>
                <div className="whitespace-pre-wrap break-all">
                    {this.state.error && this.state.error.toString()}
                </div>
              </div>

              {this.state.showRaw && (
                  <div className="mb-4">
                    <p className="text-xs font-bold text-slate-500 mb-1">LOG COMPLETO (Selecione e Copie):</p>
                    <textarea 
                        readOnly 
                        className="w-full h-40 bg-gray-100 text-[10px] font-mono p-2 rounded border border-gray-300 focus:outline-none"
                        value={this.getLogText()}
                    />
                  </div>
              )}

              <div className="space-y-3">
                  <button 
                    onClick={this.copyLog}
                    className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg hover:bg-blue-700 active:scale-95 transition"
                  >
                    <Copy size={20} /> COPIAR LOG DE ERRO
                  </button>

                  <div className="flex gap-2">
                      <button 
                        onClick={() => this.setState({showRaw: !this.state.showRaw})}
                        className="flex-1 bg-slate-100 text-slate-700 py-3 rounded-xl font-bold flex items-center justify-center gap-2 border border-slate-200"
                      >
                        <Eye size={18} /> {this.state.showRaw ? 'Ocultar' : 'Ver Texto'}
                      </button>
                      
                      <button 
                        onClick={() => window.location.reload()}
                        className="flex-1 bg-slate-100 text-slate-700 py-3 rounded-xl font-bold flex items-center justify-center gap-2 border border-slate-200"
                      >
                        <RefreshCw size={18} /> Recarregar
                      </button>
                  </div>

                  <button 
                    onClick={this.hardReset}
                    className="w-full text-red-500 py-3 text-xs font-bold flex items-center justify-center gap-1 mt-4 border-t border-gray-100 pt-4 hover:bg-red-50 rounded-xl transition"
                  >
                    <Trash2 size={14} /> RESETAR DADOS DE FÁBRICA
                  </button>
              </div>
          </div>
          <p className="mt-8 text-[10px] text-red-300 font-mono">MotoristaPro Debug Mode v2.0</p>
        </div>
      );
    }

    return this.props.children; 
  }
}
'''

# 2. ATUALIZAR MAIN.JSX PARA USAR O ERROR BOUNDARY
files_content['src/main.jsx'] = r'''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import ErrorBoundary from './ErrorBoundary.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
'''

def main():
    print(f"🚀 INJETANDO MODO DEBUG V2 - {APP_NAME}")
    
    print("\n📝 Criando componente de diagnóstico...")
    for f, c in files_content.items():
        dir_name = os.path.dirname(f)
        if dir_name: os.makedirs(dir_name, exist_ok=True)
        with open(f, 'w', encoding='utf-8') as file: file.write(c)
        print(f"   ✅ {f}")
        
    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "chore: Add Robust ErrorBoundary for White Screen Diagnosis"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    print("\n✅ DEBUG ATIVO!")
    print("1. Aguarde o APK ser gerado.")
    print("2. Instale e abra o app.")
    print("3. Quando der a TELA BRANCA, aparecerá a tela de erro vermelha.")
    print("4. Clique em 'COPIAR LOG DE ERRO' e cole aqui.")
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


