import os
import shutil
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. PACKAGE.JSON (Adicionando Plugin de Notificações)
files_content['package.json'] = '''{
  "name": "motorista-pro-rota",
  "private": true,
  "version": "1.5.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.263.1",
    "papaparse": "^5.4.1",
    "xlsx": "^0.18.5",
    "@capacitor/geolocation": "^5.0.0",
    "@capacitor/local-notifications": "^5.0.0",
    "@capacitor/core": "^5.0.0",
    "@capacitor/android": "^5.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.15",
    "@types/react-dom": "^18.2.7",
    "@vitejs/plugin-react": "^4.0.3",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.27",
    "tailwindcss": "^3.3.3",
    "vite": "^4.4.5",
    "@capacitor/cli": "^5.0.0"
  }
}'''

# 2. CSS (Visual Moderno e Limpo)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: #F3F4F6; /* Cinza muito suave */
  color: #1F2937;
  -webkit-tap-highlight-color: transparent;
}

/* Scrollbar escondida para visual clean */
::-webkit-scrollbar {
  display: none;
}

/* Card Moderno */
.modern-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  border: 1px solid rgba(0,0,0,0.02);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.modern-card:active {
  transform: scale(0.98);
}

/* Status Indicators */
.status-indicator {
  width: 4px;
  border-radius: 4px;
  height: 100%;
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
}
.indicator-pending { background-color: #3B82F6; } /* Azul */
.indicator-success { background-color: #10B981; } /* Verde Esmeralda */
.indicator-failed { background-color: #F59E0B; }  /* Âmbar */

/* Botão Flutuante (FAB) */
.fab-main {
  background: #111827; /* Preto suave (Slate 900) */
  color: white;
  box-shadow: 0 8px 30px rgba(0,0,0,0.3);
}
'''

# 3. APP.JSX (Lógica de Geofencing + Visual Novo)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useRef } from 'react';
import { Upload, Navigation, Check, AlertTriangle, Trash2, Plus, ArrowLeft, Sliders, MapPin, Package, Clock, MoreVertical } from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { LocalNotifications } from '@capacitor/local-notifications';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

export default function App() {
  const [routes, setRoutes] = useState([]); 
  const [activeRouteId, setActiveRouteId] = useState(null); 
  const [view, setView] = useState('home'); 
  const [newRouteName, setNewRouteName] = useState('');
  const [tempStops, setTempStops] = useState([]);
  const [userPos, setUserPos] = useState(null);
  const [isNavigating, setIsNavigating] = useState(false);
  const [arrivalNotified, setArrivalNotified] = useState(false);

  // --- PERSISTÊNCIA ---
  useEffect(() => {
    const saved = localStorage.getItem('mp_routes_v11');
    if (saved) setRoutes(JSON.parse(saved));
    requestPermissions();
  }, []);

  useEffect(() => {
    localStorage.setItem('mp_routes_v11', JSON.stringify(routes));
  }, [routes]);

  // --- PERMISSÕES E SERVIÇOS ---
  const requestPermissions = async () => {
      try {
          await Geolocation.requestPermissions();
          await LocalNotifications.requestPermissions();
          startGpsWatch();
      } catch (e) { console.error(e); }
  };

  const startGpsWatch = () => {
      // Monitora GPS em tempo real
      Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 5000 }, (pos) => {
          if (pos) {
              const newPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
              setUserPos(newPos);
              checkGeofence(newPos);
          }
      });
  };

  // --- GEOFENCING (DETECÇÃO DE CHEGADA) ---
  const checkGeofence = (currentLocation) => {
      if (!isNavigating || !activeRouteId || arrivalNotified) return;

      const route = routes.find(r => r.id === activeRouteId);
      if (!route) return;

      const nextStop = route.stops.find(s => s.status === 'pending');
      if (!nextStop) return;

      // Distância Euclidiana aproximada (mais leve para loop continuo)
      // 0.0015 graus ~ 150 metros
      const latDiff = Math.abs(currentLocation.lat - nextStop.lat);
      const lngDiff = Math.abs(currentLocation.lng - nextStop.lng);

      if (latDiff < 0.0015 && lngDiff < 0.0015) {
          triggerArrivalNotification(nextStop.name);
          setArrivalNotified(true); // Evita spam de notificação
      }
  };

  const triggerArrivalNotification = async (stopName) => {
      await LocalNotifications.schedule({
          notifications: [{
              title: "📍 Você chegou!",
              body: `Chegando em: ${stopName}. Toque para confirmar entrega.`,
              id: 1,
              schedule: { at: new Date(Date.now() + 100) },
              sound: 'beep.wav',
              actionTypeId: "",
              extra: null
          }]
      });
  };

  // --- IMPORTAÇÃO ---
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const process = (d, bin) => {
        let data = [];
        if(bin) {
            const wb = XLSX.read(d, {type:'binary'});
            data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
        } else {
            data = Papa.parse(d, {header:true, skipEmptyLines:true}).data;
        }
        
        const norm = data.map((r, i) => {
             const k = Object.keys(r).reduce((acc, key) => { acc[key.toLowerCase().trim()] = r[key]; return acc; }, {});
             return {
                 id: Date.now() + i,
                 // Prioridade explícita para coluna 'stop'
                 name: k['stop'] || k['parada'] || k['cliente'] || k['nome'] || `Cliente sem nome`,
                 address: k['destination address'] || k['endereço'] || k['endereco'] || '---',
                 lat: parseFloat(k['latitude'] || k['lat'] || 0),
                 lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                 status: 'pending'
             };
        }).filter(i => i.lat !== 0);

        if(norm.length) setTempStops(norm);
        else alert("Erro: Planilha sem coordenadas.");
    };

    const reader = new FileReader();
    if(file.name.endsWith('.csv')) { reader.onload = (e) => process(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = (e) => process(e.target.result, true); reader.readAsBinaryString(file); }
  };

  // --- LÓGICA DE ROTAS ---
  const saveNewRoute = () => {
      if(!newRouteName.trim() || tempStops.length === 0) return;
      const newRoute = { id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops };
      setRoutes([newRoute, ...routes]);
      setNewRouteName(''); setTempStops([]); setView('home');
  };

  const optimizeActiveRoute = () => {
      if(!userPos) return alert("Aguardando GPS...");
      const idx = routes.findIndex(r => r.id === activeRouteId);
      if(idx === -1) return;

      const currentStops = [...routes[idx].stops];
      let pending = currentStops.filter(s => s.status === 'pending');
      let done = currentStops.filter(s => s.status !== 'pending');
      let optimized = [];
      let current = userPos;

      while(pending.length > 0) {
          let nearIdx = -1, min = Infinity;
          for(let i=0; i<pending.length; i++) {
              const d = (pending[i].lat - current.lat)**2 + (pending[i].lng - current.lng)**2;
              if(d < min) { min = d; nearIdx = i; }
          }
          optimized.push(pending[nearIdx]);
          current = pending[nearIdx];
          pending.splice(nearIdx, 1);
      }
      
      const updated = [...routes];
      updated[idx].stops = [...done, ...optimized];
      setRoutes(updated);
      alert("Rota reordenada com sucesso!");
  };

  const handleStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const updated = [...routes];
      const sIdx = updated[rIdx].stops.findIndex(s => s.id === stopId);
      
      if(sIdx !== -1) {
          updated[rIdx].stops[sIdx].status = status;
          setRoutes(updated);
          setArrivalNotified(false); // Reseta notificação para o próximo

          const next = updated[rIdx].stops.find(s => s.status === 'pending');
          if(next) {
              // Auto-Launch opcional, aqui apenas preparamos o botão
          } else {
              setIsNavigating(false);
              alert("Rota Finalizada!");
          }
      }
  };

  const openNav = (stop) => {
      setIsNavigating(true);
      setArrivalNotified(false); // Prepara para detectar chegada neste novo ponto
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lng}&travelmode=driving`, '_system');
  };

  // --- RENDER ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  const nextStop = activeRoute?.stops.find(s => s.status === 'pending');

  // VIEW: HOME
  if(view === 'home') return (
    <div className="min-h-screen pb-28 px-5 pt-8">
        <div className="flex justify-between items-center mb-8">
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Rotas</h1>
            <div className="bg-white p-2 rounded-full shadow-sm"><Package className="text-slate-400"/></div>
        </div>

        {routes.length === 0 ? (
            <div className="flex flex-col items-center justify-center mt-32 opacity-40">
                <MapPin size={48} className="mb-4"/>
                <p className="font-medium">Nenhuma rota ativa</p>
            </div>
        ) : (
            <div className="space-y-4">
                {routes.map(r => {
                    const done = r.stops.filter(s => s.status !== 'pending').length;
                    const total = r.stops.length;
                    return (
                        <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} 
                             className="modern-card p-5 relative overflow-hidden cursor-pointer">
                            <div className="flex justify-between items-start mb-4">
                                <div>
                                    <h3 className="font-bold text-lg text-slate-800">{r.name}</h3>
                                    <span className="text-xs text-slate-400 font-medium">{r.date}</span>
                                </div>
                                <div className="bg-slate-100 px-3 py-1 rounded-full text-xs font-bold text-slate-600">
                                    {done}/{total}
                                </div>
                            </div>
                            <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                                <div className="bg-slate-900 h-full transition-all duration-500" style={{width: `${(done/total)*100}%`}}></div>
                            </div>
                        </div>
                    )
                })}
            </div>
        )}

        <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center active:scale-95 transition">
            <Plus size={32} />
        </button>
    </div>
  );

  // VIEW: CREATE
  if(view === 'create') return (
    <div className="min-h-screen bg-white flex flex-col p-6">
        <button onClick={() => setView('home')} className="self-start mb-6 p-2 -ml-2"><ArrowLeft className="text-slate-800"/></button>
        <h2 className="text-2xl font-bold mb-8 text-slate-900">Nova Rota</h2>
        
        <div className="space-y-6 flex-1">
            <input type="text" placeholder="Nome da Rota (ex: Centro)" 
                   className="w-full p-5 bg-slate-50 rounded-2xl text-lg font-medium outline-none focus:ring-2 focus:ring-slate-900 transition"
                   value={newRouteName} onChange={e => setNewRouteName(e.target.value)} />
            
            <label className="block w-full cursor-pointer group">
                <div className="w-full border-2 border-dashed border-slate-200 rounded-2xl h-40 flex flex-col items-center justify-center text-slate-400 group-hover:border-slate-400 group-hover:text-slate-600 transition">
                    <Upload className="mb-2"/>
                    <span className="font-bold text-sm">Importar Planilha</span>
                </div>
                <input type="file" onChange={handleFileUpload} accept=".csv,.xlsx" className="hidden"/>
            </label>

            {tempStops.length > 0 && (
                <div className="p-4 bg-green-50 text-green-700 rounded-xl font-bold text-center border border-green-100">
                    {tempStops.length} endereços carregados
                </div>
            )}
        </div>

        <button onClick={saveNewRoute} className="w-full bg-slate-900 text-white py-5 rounded-2xl font-bold text-lg mb-4">
            Criar Rota
        </button>
    </div>
  );

  // VIEW: DETAILS
  if(view === 'details' && activeRoute) return (
      <div className="flex flex-col h-screen bg-slate-50">
          {/* Header Fixo */}
          <div className="bg-white px-5 py-4 shadow-sm z-10 sticky top-0 flex items-center justify-between">
              <button onClick={() => setView('home')}><ArrowLeft className="text-slate-800"/></button>
              <h2 className="font-bold text-slate-800">{activeRoute.name}</h2>
              <button onClick={optimizeActiveRoute} className="bg-slate-100 p-2 rounded-full"><Sliders size={20} className="text-slate-600"/></button>
          </div>

          {/* Área de Destaque (Próxima Parada) */}
          {nextStop ? (
              <div className="p-5 pb-2">
                  <div className="modern-card p-6 border-l-4 border-slate-900 relative overflow-hidden">
                      <div className="absolute top-0 right-0 bg-slate-900 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRÓXIMA</div>
                      <h3 className="text-2xl font-bold text-slate-900 leading-tight mb-1">{nextStop.name}</h3>
                      <p className="text-slate-500 text-sm mb-6">{nextStop.address}</p>
                      
                      <button onClick={() => openNav(nextStop)} className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg shadow-blue-200 flex items-center justify-center gap-2 mb-4 active:scale-95 transition">
                          <Navigation size={20}/> Navegar
                      </button>

                      <div className="grid grid-cols-2 gap-3">
                          <button onClick={() => handleStatus(nextStop.id, 'failed')} className="py-3 bg-red-50 text-red-600 font-bold rounded-xl text-xs">FALHA</button>
                          <button onClick={() => handleStatus(nextStop.id, 'success')} className="py-3 bg-green-50 text-green-600 font-bold rounded-xl text-xs">ENTREGUE</button>
                      </div>
                  </div>
              </div>
          ) : (
              <div className="p-5 text-center">
                  <div className="modern-card p-8 flex flex-col items-center">
                      <Check size={48} className="text-green-500 mb-4"/>
                      <h3 className="font-bold text-xl">Rota Finalizada!</h3>
                  </div>
              </div>
          )}

          {/* Lista Completa (Scroll) */}
          <div className="flex-1 overflow-y-auto px-5 pb-safe space-y-3 pt-2">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 mt-2">Todas as Paradas</h4>
              {activeRoute.stops.map((stop) => {
                  if(nextStop && stop.id === nextStop.id) return null; // Já mostrado no destaque
                  
                  let statusClass = "indicator-pending";
                  if(stop.status === 'success') statusClass = "indicator-success";
                  if(stop.status === 'failed') statusClass = "indicator-failed";

                  return (
                      <div key={stop.id} className={`modern-card p-4 pl-5 relative flex items-center justify-between ${stop.status !== 'pending' ? 'opacity-60 grayscale' : ''}`}>
                          <div className={`status-indicator ${statusClass}`}></div>
                          <div className="flex-1 min-w-0 pr-4">
                              <h4 className="font-bold text-slate-800 text-sm truncate">{stop.name}</h4>
                              <p className="text-slate-400 text-xs truncate">{stop.address}</p>
                          </div>
                          {stop.status === 'success' && <Check size={16} className="text-green-500"/>}
                          {stop.status === 'pending' && <button onClick={() => openNav(stop)} className="bg-slate-100 p-2 rounded-lg"><Navigation size={14} className="text-slate-600"/></button>}
                      </div>
                  );
              })}
              <div className="h-8"></div>
          </div>
      </div>
  );
}
'''

def main():
    print(f"🚀 ATUALIZAÇÃO V11 (MODERN PRO) - {APP_NAME}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_base = f"{BACKUP_ROOT}/{ts}"
    os.makedirs(backup_base, exist_ok=True)
    
    print("\n📝 Escrevendo arquivos...")
    for f, c in files_content.items():
        if os.path.exists(f): 
            dest = f"{backup_base}/{f}"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy(f, dest)
        
        d = os.path.dirname(f)
        if d: os.makedirs(d, exist_ok=True)
        with open(f, 'w', encoding='utf-8') as file: file.write(c)
        print(f"   ✅ {f}")
        
    print("\n📦 Instalando Plugins de Notificação...")
    subprocess.run("npm install @capacitor/local-notifications", shell=True)
    subprocess.run("npx cap sync", shell=True)

    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "feat: V11 Modern UI + Geofencing Notifications"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


