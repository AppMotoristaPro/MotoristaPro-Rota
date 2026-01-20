import React from 'react';
import { AlertTriangle, Download, Trash2, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ERRO CAPTURADO:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  downloadLogs = () => {
    const { error, errorInfo } = this.state;
    
    // Coleta dados vitais para entender o erro
    const debugInfo = {
        timestamp: new Date().toLocaleString(),
        userAgent: navigator.userAgent,
        errorName: error?.name,
        errorMessage: error?.message,
        componentStack: errorInfo?.componentStack,
        // Tenta ler o banco de dados atual para ver se está corrompido
        localStorageDump: {
            v16: localStorage.getItem('mp_db_v16'),
            v15: localStorage.getItem('motorista_pro_db_v15'),
            v13: localStorage.getItem('mp_routes_v13')
        }
    };

    const blob = new Blob([JSON.stringify(debugInfo, null, 2)], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `debug_motoristapro_${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    alert("Log salvo! Verifique sua pasta de Downloads.");
  };

  hardReset = () => {
      if(confirm("Isso apagará TODOS os dados locais do app para tentar recuperá-lo. Continuar?")) {
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
                  <h1 className="text-2xl font-bold text-slate-900">Ocorreu um erro</h1>
                  <p className="text-slate-500 mt-2 text-sm">O aplicativo encontrou um problema inesperado e precisou parar.</p>
              </div>
              
              <div className="bg-slate-900 text-green-400 p-4 rounded-lg text-xs font-mono overflow-auto max-h-40 mb-6 border border-slate-700">
                <p className="font-bold text-white mb-1">ERRO TÉCNICO:</p>
                {this.state.error && this.state.error.toString()}
              </div>

              <div className="space-y-3">
                  <button 
                    onClick={this.downloadLogs}
                    className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg active:scale-95 transition"
                  >
                    <Download size={20} /> Baixar Log de Erro
                  </button>
                  
                  <button 
                    onClick={() => window.location.reload()}
                    className="w-full bg-white border border-slate-200 text-slate-700 py-3 rounded-xl font-bold flex items-center justify-center gap-2 active:scale-95 transition"
                  >
                    <RefreshCw size={18} /> Tentar Recarregar
                  </button>

                  <button 
                    onClick={this.hardReset}
                    className="w-full text-red-500 py-2 text-sm font-bold flex items-center justify-center gap-1 mt-2"
                  >
                    <Trash2 size={14} /> Limpar Dados e Resetar
                  </button>
              </div>
          </div>
          <p className="mt-8 text-xs text-red-300">MotoristaPro Debug Mode</p>
        </div>
      );
    }

    return this.props.children; 
  }
}
