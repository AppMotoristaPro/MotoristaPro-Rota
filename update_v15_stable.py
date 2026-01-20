import os
import shutil
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. CSS (Mantendo o estilo moderno)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background-color: #F8FAFC;
  color: #1E293B;
  -webkit-tap-highlight-color: transparent;
}

.modern-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  border: 1px solid #F1F5F9;
}

.fab {
  background: #0F172A;
  color: white;
  box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.4);
}
'''

# 2. APP.JSX (Blindado contra erros)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo } from 'react';
// Importando apenas ícones essenciais e seguros
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, RefreshCw
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// --- CONFIGURAÇÃO SEGURA ---
const STORAGE_KEY = 'motorista_pro_db_v15'; // Nova chave para limpar dados antigos

// --- HELPERS SEGUROS ---
const groupStopsSafe = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    
    stops.forEach(stop => {
        // Fallback para nomes e coordenadas
        const rawName = stop.name || 'Cliente Sem Nome';
        const safeName = rawName.trim();
        const lat = Number(stop.lat) || 0;
        const lng = Number(stop.lng) || 0;
        
        // Chave de agrupamento: Nome ou Coordenada
        const key = `${safeName}_${lat.toFixed(3)}`;

        if (!groups[key]) {
            groups[key] = {
                id: key,
                lat, lng,
                mainName: safeName,
                mainAddress: stop.address || 'Endereço não informado',
                items: [],
                status: 'pending'
            };
        }
        groups[key].items.push(stop);
    });

    // Calcular status do grupo
    return Object.values(groups).map(group => {
        const total = group.items.length;
        const success = group.items.filter(i => i.status === 'success').length;
        const failed = group.items.filter(i => i.status === 'failed').length;
        
        if (success === total) group.status = 'success';
        else if (failed === total) group.status = 'failed';
        else if (success + failed > 0) group.status = 'partial';
        else group.status = 'pending';
        
        return group;
    });
};

const calculateMetricsSafe = (stops) => {
    if (!Array.isArray(stops) || stops.length < 2) return { km: "0", time: "0h 0m" };
    
    let totalKm = 0;
    for (let i = 0; i < stops.length - 1; i++) {
        const p1 = stops[i];
        const p2 = stops[i+1];
        
        // Haversine Simples
        const R = 6371;
        const dLat = (p2.lat - p1.lat) * Math.PI / 180;
        const dLon = (p2.lng - p1.lng) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(p1.lat * Math.PI / 180) * Math.cos(p2.lat * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        totalKm += R * c;
    }

    const realKm = totalKm * 1.5; // Fator de correção
    const avgSpeed = 22; // km/h
    const serviceTime = stops.length * 4; // minutos
    const totalMinutes = (realKm / avgSpeed * 60) + serviceTime;
    
    const h = Math.floor(totalMinutes / 60);
    const m = Math.floor(totalMinutes % 60);

    return { km: realKm.toFixed(1), time: `${h}h ${m}m` };
};

export default function App() {
  // --- STATE ---
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); // home, create, details
  const [newRouteName, setNewRouteName] = useState('');
  const [tempStops, setTempStops] = useState([]);
  const [userPos, setUserPos] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});

  // --- INIT & PERSISTENCE ---
  useEffect(() => {
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const parsed = JSON.parse(saved);
            if (Array.isArray(parsed)) setRoutes(parsed);
        }
    } catch (e) {
        console.error("Erro ao carregar dados. Resetando.", e);
        localStorage.removeItem(STORAGE_KEY);
    }
    
    // Iniciar GPS silenciosamente
    try { Geolocation.requestPermissions().then(startGps); } 
    catch(e) { startGps(); }
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(routes));
  }, [routes]);

  const startGps = () => {
      Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 10000 }, (pos) => {
          if (pos) setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      });
  };

  const hardReset = () => {
      if(confirm("Isso apagará TODAS as rotas e corrigirá erros. Continuar?")) {
          localStorage.removeItem(STORAGE_KEY);
          setRoutes([]);
          setView('home');
          window.location.reload();
      }
  };

  // --- ACTIONS ---
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    const processData = (d, isBin) => {
        let data = [];
        try {
            if(isBin) {
                const wb = XLSX.read(d, {type:'binary'});
                data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
            } else {
                data = Papa.parse(d, {header:true, skipEmptyLines:true}).data;
            }
        } catch(err) {
            alert("Arquivo inválido ou corrompido.");
            return;
        }

        const norm = data.map((r, i) => {
            // Normalização Segura
            const k = {};
            Object.keys(r).forEach(key => k[key.trim().toLowerCase()] = r[key]);
            
            return {
                id: Date.now() + i,
                name: k['stop'] || k['parada'] || k['cliente'] || k['nome'] || `Entrega ${i+1}`,
                address: k['destination address'] || k['endereço'] || k['endereco'] || '---',
                lat: parseFloat(k['latitude'] || k['lat'] || 0),
                lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                status: 'pending'
            };
        }).filter(i => i.lat !== 0 && i.lng !== 0);

        if (norm.length > 0) setTempStops(norm);
        else alert("Não encontramos colunas de latitude/longitude.");
    };

    if(file.name.endsWith('.csv')) { reader.onload = e => processData(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = e => processData(e.target.result, true); reader.readAsBinaryString(file); }
  };

  const createRoute = () => {
      if(!newRouteName.trim() || tempStops.length === 0) return;
      const newRoute = {
          id: Date.now(),
          name: newRouteName,
          date: new Date().toLocaleDateString('pt-BR'),
          stops: tempStops,
          optimized: false
      };
      setRoutes([newRoute, ...routes]);
      setNewRouteName('');
      setTempStops([]);
      setView('home');
  };

  const deleteRoute = (id) => {
      if(confirm("Excluir rota?")) {
          setRoutes(routes.filter(r => r.id !== id));
          setView('home');
      }
  };

  const optimizeRoute = () => {
      if (!userPos) return alert("Aguardando sinal de GPS... Tente novamente em 10 segundos.");
      
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      const currentRoute = routes[rIdx];
      let pending = currentRoute.stops.filter(s => s.status === 'pending');
      let done = currentRoute.stops.filter(s => s.status !== 'pending');
      let optimized = [];
      let pointer = userPos;

      // Nearest Neighbor
      while(pending.length > 0) {
          let nearestIdx = -1;
          let minDist = Infinity;
          
          for(let i=0; i<pending.length; i++) {
              const d = Math.pow(pending[i].lat - pointer.lat, 2) + Math.pow(pending[i].lng - pointer.lng, 2);
              if (d < minDist) { minDist = d; nearestIdx = i; }
          }
          
          optimized.push(pending[nearestIdx]);
          pointer = pending[nearestIdx];
          pending.splice(nearestIdx, 1);
      }

      const updated = [...routes];
      updated[rIdx].stops = [...done, ...optimized];
      updated[rIdx].optimized = true;
      setRoutes(updated);
  };

  const setStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      
      const updated = [...routes];
      const sIdx = updated[rIdx].stops.findIndex(s => s.id === stopId);
      if (sIdx !== -1) {
          updated[rIdx].stops[sIdx].status = status;
          setRoutes(updated);
      }
  };

  const openNav = (lat, lng) => {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const toggleGroup = (id) => {
      setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));
  };

  // --- RENDER ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  
  // Segurança: Se estiver em details mas rota não existe, volta pra home
  if (view === 'details' && !activeRoute) {
      setView('home');
      return null;
  }

  // Agrupamento Seguro
  const groupedStops = useMemo(() => {
      if (!activeRoute) return [];
      return groupStopsSafe(activeRoute.stops);
  }, [activeRoute]);

  const metrics = useMemo(() => {
      if (!activeRoute) return { km: "0", time: "0h 0m" };
      return calculateMetricsSafe(activeRoute.stops);
  }, [activeRoute]);

  const nextGroup = groupedStops.find(g => g.status === 'pending');

  // 1. HOME VIEW
  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10">
          <div className="flex justify-between items-center mb-8">
              <div>
                  <h1 className="text-3xl font-bold text-slate-900">Rotas</h1>
                  <p className="text-slate-400 text-sm">Gerencie suas entregas</p>
              </div>
              <button onClick={hardReset} className="p-2 bg-slate-100 rounded-full text-slate-400 hover:bg-red-50 hover:text-red-500">
                  <Trash2 size={20} />
              </button>
          </div>

          {routes.length === 0 ? (
              <div className="flex flex-col items-center justify-center mt-32 text-center opacity-40">
                  <MapPin size={48} className="mb-4 text-slate-400" />
                  <p className="font-medium text-slate-600">Nenhuma rota ativa</p>
                  <p className="text-sm text-slate-400 mt-1">Toque no + para começar</p>
              </div>
          ) : (
              <div className="space-y-4">
                  {routes.map(r => (
                      <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} 
                           className="modern-card p-5 cursor-pointer active:scale-98 transition-transform">
                          <div className="flex justify-between items-start mb-2">
                              <h3 className="font-bold text-lg text-slate-800 line-clamp-1">{r.name}</h3>
                              <span className="text-xs font-bold text-slate-400 bg-slate-100 px-2 py-1 rounded-full">{r.date}</span>
                          </div>
                          <div className="flex items-center gap-2 text-sm text-slate-500">
                              <Box size={14}/> {r.stops?.length || 0} entregas
                          </div>
                      </div>
                  ))}
              </div>
          )}

          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab flex items-center justify-center text-white active:scale-90 transition">
              <Plus size={32} />
          </button>
      </div>
  );

  // 2. CREATE VIEW
  if (view === 'create') return (
      <div className="min-h-screen bg-white flex flex-col p-6">
          <button onClick={() => setView('home')} className="self-start mb-6 -ml-2 p-2 text-slate-600">
              <ArrowLeft />
          </button>
          
          <h2 className="text-2xl font-bold text-slate-900 mb-8">Nova Rota</h2>
          
          <div className="space-y-6 flex-1">
              <div>
                  <label className="block text-xs font-bold text-slate-400 mb-2 uppercase">Nome da Rota</label>
                  <input 
                      type="text" 
                      className="w-full p-4 bg-slate-50 rounded-xl font-medium outline-none focus:ring-2 focus:ring-slate-900"
                      placeholder="Ex: Entrega Zona Sul"
                      value={newRouteName}
                      onChange={e => setNewRouteName(e.target.value)}
                  />
              </div>

              <div>
                  <label className="block text-xs font-bold text-slate-400 mb-2 uppercase">Arquivo de Endereços</label>
                  <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50 cursor-pointer">
                      <Upload className="text-slate-400 mb-2" />
                      <span className="text-sm font-bold text-slate-500">Importar Planilha</span>
                      <span className="text-xs text-slate-400 mt-1">.csv ou .xlsx</span>
                      <input type="file" onChange={handleFileUpload} accept=".csv,.xlsx" className="hidden" />
                  </label>
              </div>

              {tempStops.length > 0 && (
                  <div className="p-4 bg-green-50 text-green-700 rounded-xl font-bold text-center border border-green-100 animate-in fade-in">
                      {tempStops.length} locais identificados!
                  </div>
              )}
          </div>

          <button onClick={createRoute} className="w-full bg-slate-900 text-white py-5 rounded-2xl font-bold text-lg mb-4 shadow-xl active:scale-95 transition">
              Salvar e Continuar
          </button>
      </div>
  );

  // 3. DETAILS VIEW
  return (
      <div className="flex flex-col h-screen bg-slate-50">
          {/* Header */}
          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft className="text-slate-800"/></button>
                  <h2 className="font-bold text-slate-800 truncate px-4 flex-1 text-center">{activeRoute.name}</h2>
                  <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 size={20} className="text-red-400"/></button>
              </div>

              {/* Métricas */}
              {activeRoute.optimized && (
                  <div className="flex justify-between bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4 text-slate-600">
                      <div className="flex items-center gap-1.5"><Navigation size={14} className="text-blue-500"/><span className="text-xs font-bold">{metrics.km} km</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-1.5"><Clock size={14} className="text-orange-500"/><span className="text-xs font-bold">{metrics.time}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-1.5"><Box size={14} className="text-green-500"/><span className="text-xs font-bold">{activeRoute.stops.length}</span></div>
                  </div>
              )}

              {/* Ações */}
              <div className="flex gap-3">
                  <button onClick={optimizeRoute} className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition ${!activeRoute.optimized ? 'bg-blue-600 text-white shadow-lg' : 'bg-slate-100 text-slate-600'}`}>
                      <Sliders size={16}/> {activeRoute.optimized ? 'Reotimizar' : 'Otimizar'}
                  </button>
                  {nextGroup && (
                      <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} disabled={!activeRoute.optimized} className={`flex-[2] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition ${activeRoute.optimized ? 'bg-slate-900 text-white shadow-lg animate-pulse' : 'bg-slate-100 text-slate-400 cursor-not-allowed'}`}>
                          <Navigation size={16}/> Navegar
                      </button>
                  )}
              </div>
          </div>

          {/* Lista */}
          <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-4">
              
              {/* Destaque Próximo */}
              {nextGroup && activeRoute.optimized && (
                  <div className="modern-card p-6 border-l-4 border-slate-900 relative">
                      <div className="absolute top-0 right-0 bg-slate-900 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRÓXIMO</div>
                      <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{nextGroup.mainName}</h3>
                      <p className="text-sm text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                      
                      {nextGroup.items.length > 1 && (
                          <div className="mb-4 bg-blue-50 text-blue-800 px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-2">
                              <Box size={14}/> {nextGroup.items.length} PACOTES
                          </div>
                      )}

                      <div className="space-y-2 border-t border-slate-100 pt-3">
                          {nextGroup.items.map(item => (
                              <div key={item.id} className="flex justify-between items-center">
                                  <span className="text-sm font-medium text-slate-700">{item.name}</span>
                                  <div className="flex gap-2">
                                      <button onClick={() => setStatus(item.id, 'failed')} className="p-1.5 bg-red-50 text-red-500 rounded"><AlertTriangle size={14}/></button>
                                      <button onClick={() => setStatus(item.id, 'success')} className="p-1.5 bg-green-500 text-white rounded"><Check size={14}/></button>
                                  </div>
                              </div>
                          ))}
                      </div>
                  </div>
              )}

              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Lista de Entregas</h4>

              {groupedStops.map((group, idx) => {
                  if (nextGroup && group.id === nextGroup.id && activeRoute.optimized) return null;
                  const isExpanded = expandedGroups[group.id];
                  const hasMulti = group.items.length > 1;

                  return (
                      <div key={group.id} className={`modern-card overflow-hidden ${group.status !== 'pending' ? 'opacity-50 grayscale' : ''}`}>
                          <div onClick={() => toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer">
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                  {group.status === 'success' ? <Check size={14}/> : idx + 1}
                              </div>
                              <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                      <h4 className="font-bold text-slate-800 text-sm truncate">{group.mainName}</h4>
                                      {hasMulti && <span className="bg-slate-800 text-white text-[10px] px-1.5 rounded-full">{group.items.length}</span>}
                                  </div>
                                  <p className="text-xs text-slate-400 truncate">{group.mainAddress}</p>
                              </div>
                              {hasMulti ? (isExpanded ? <ChevronUp size={16} className="text-slate-400"/> : <ChevronDown size={16} className="text-slate-400"/>) : (
                                  group.items[0].status === 'pending' && <button onClick={(e) => {e.stopPropagation(); setStatus(group.items[0].id, 'success')}} className="p-2 text-slate-300 hover:text-green-500"><Check size={18}/></button>
                              )}
                          </div>
                          
                          {(isExpanded || (hasMulti && isExpanded)) && (
                              <div className="bg-slate-50 px-4 py-2 space-y-2 border-t border-slate-100">
                                  {group.items.map(item => (
                                      <div key={item.id} className="flex justify-between items-center py-2 border-b border-slate-200 last:border-0">
                                          <span className="text-sm font-medium text-slate-700">{item.name}</span>
                                          <div className="flex gap-2">
                                              {item.status === 'pending' ? (
                                                  <>
                                                    <button onClick={() => setStatus(item.id, 'failed')} className="text-red-400"><AlertTriangle size={16}/></button>
                                                    <button onClick={() => setStatus(item.id, 'success')} className="text-green-500"><Check size={18}/></button>
                                                  </>
                                              ) : (
                                                  <span className={`text-[10px] font-bold ${item.status==='success'?'text-green-600':'text-red-600'}`}>{item.status === 'success' ? 'OK' : 'X'}</span>
                                              )}
                                          </div>
                                      </div>
                                  ))}
                              </div>
                          )}
                      </div>
                  )
              })}
              <div className="h-10"></div>
          </div>
      </div>
  );
}
'''

def main():
    print(f"🚀 ATUALIZAÇÃO V14 (STABILITY FIX) - {APP_NAME}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(f"{BACKUP_ROOT}/{ts}", exist_ok=True)
    
    print("\n📝 Escrevendo arquivos...")
    for f, c in files_content.items():
        if os.path.exists(f): 
            dest = f"{BACKUP_ROOT}/{ts}/{f}"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy(f, dest)
        d = os.path.dirname(f)
        if d: os.makedirs(d, exist_ok=True)
        with open(f, 'w', encoding='utf-8') as file: file.write(c)
        print(f"   ✅ {f}")
        
    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "fix: V14 Stability - Remove Gauge icon and Safe Data Loading"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


