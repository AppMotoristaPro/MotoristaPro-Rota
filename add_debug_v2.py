import os
import subprocess

# --- CONFIGURAÇÕES ---
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. ERROR BOUNDARY COM COPY-PASTE (Funciona 100% no Android)
files_content['src/ErrorBoundary.jsx'] = r'''import React from 'react';
import { AlertTriangle, Copy, Trash2, RefreshCw, Eye } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, showRaw: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ERRO CRÍTICO:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  getLogText = () => {
      const { error, errorInfo } = this.state;
      const debugInfo = {
        TIME: new Date().toLocaleString(),
        USER_AGENT: navigator.userAgent,
        ERROR: error?.toString(),
        STACK: errorInfo?.componentStack,
        LOCAL_STORAGE_KEYS: Object.keys(localStorage),
        DB_V16: localStorage.getItem('mp_db_v16')?.substring(0, 200) + '...' // Preview
      };
      return JSON.stringify(debugInfo, null, 2);
  }

  copyLog = () => {
    const text = this.getLogText();
    navigator.clipboard.writeText(text).then(() => {
        alert("Log copiado! Cole no chat do Gemini.");
    }).catch(err => {
        alert("Erro ao copiar. Use o botão 'Ver Texto' e copie manualmente.");
    });
  };

  hardReset = () => {
      if(confirm("ATENÇÃO: Isso apagará TODOS os dados para recuperar o app. Confirmar?")) {
          localStorage.clear();
          window.location.reload();
      }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-red-50 flex flex-col items-center justify-center p-6 text-red-900 font-sans">
          <div className="bg-white p-6 rounded-2xl shadow-xl w-full max-w-md border border-red-100">
              <div className="flex flex-col items-center text-center mb-6">
                  <div className="bg-red-100 p-4 rounded-full mb-4">
                    <AlertTriangle size={48} className="text-red-600" />
                  </div>
                  <h1 className="text-2xl font-bold text-slate-900">App Travou</h1>
                  <p className="text-slate-500 mt-2 text-sm">Erro inesperado. Precisamos do log abaixo para corrigir.</p>
              </div>
              
              <div className="bg-slate-900 text-red-300 p-4 rounded-lg text-xs font-mono overflow-auto max-h-32 mb-4 border border-slate-700">
                <p className="font-bold text-white mb-1">ERRO:</p>
                {this.state.error && this.state.error.toString()}
              </div>

              {this.state.showRaw && (
                  <textarea 
                    readOnly 
                    className="w-full h-40 bg-gray-100 text-xs font-mono p-2 rounded border mb-4"
                    value={this.getLogText()}
                  />
              )}

              <div className="space-y-3">
                  <button 
                    onClick={this.copyLog}
                    className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg active:scale-95 transition"
                  >
                    <Copy size={20} /> Copiar Log para Área de Transferência
                  </button>

                  <button 
                    onClick={() => this.setState({showRaw: !this.state.showRaw})}
                    className="w-full bg-slate-100 text-slate-700 py-3 rounded-xl font-bold flex items-center justify-center gap-2"
                  >
                    <Eye size={20} /> {this.state.showRaw ? 'Ocultar Texto' : 'Ver Texto Completo'}
                  </button>
                  
                  <button 
                    onClick={this.hardReset}
                    className="w-full text-red-500 py-2 text-sm font-bold flex items-center justify-center gap-1 mt-4 border-t border-gray-100 pt-4"
                  >
                    <Trash2 size={14} /> Resetar Dados (Fábrica)
                  </button>
              </div>
          </div>
        </div>
      );
    }

    return this.props.children; 
  }
}
'''

# 2. MAIN.JSX
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
    print(f"🚀 INJETANDO DEBUG V2 (CLIPBOARD) - {APP_NAME}")
    
    print("\n📝 Atualizando ErrorBoundary...")
    for f, c in files_content.items():
        dir_name = os.path.dirname(f)
        if dir_name: os.makedirs(dir_name, exist_ok=True)
        with open(f, 'w', encoding='utf-8') as file: file.write(c)
        print(f"   ✅ {f}")
        
    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "chore: Debug V2 using Clipboard instead of File"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


