import os
import shutil
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. CSS (Refinado para cards expansíveis e destaques)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: #F8FAFC;
  color: #0F172A;
  -webkit-tap-highlight-color: transparent;
}

/* Card Base */
.modern-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0,0,0,0.05);
  transition: transform 0.1s ease, box-shadow 0.2s ease;
  overflow: hidden;
}

.modern-card:active {
  transform: scale(0.99);
}

/* Card Agrupado (Indicador visual) */
.grouped-card {
  border-left: 4px solid #3B82F6; /* Azul */
}

/* Botões */
.btn-highlight {
  background-color: #2563EB; /* Azul Forte */
  color: white;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.btn-secondary {
  background-color: #F1F5F9; /* Cinza */
  color: #64748B;
}

.fab-main {
  background: #0F172A;
  color: white;
  box-shadow: 0 8px 25px rgba(15, 23, 42, 0.4);
}
'''

# 2. APP.JSX (Lógica de Grupo, Métricas e UX Flow)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map, MoreVertical
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// --- DATABASE KEY (V16 para limpar versões antigas) ---
const DB_KEY = 'mp_db_v16';

// --- HELPERS ---

// Agrupamento por Nome da Parada
const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    
    stops.forEach(stop => {
        // Chave de agrupamento: Nome da Parada (Stop)
        // Se não tiver nome da parada, usa o nome do cliente como fallback
        const rawName = stop.name || 'Parada Sem Nome';
        const key = rawName.trim().toLowerCase();

        if (!groups[key]) {
            groups[key] = {
                id: key,
                // Dados do grupo (assumimos que o primeiro item define o local do grupo)
                lat: stop.lat,
                lng: stop.lng,
                mainName: rawName, 
                mainAddress: stop.address,
                items: [],
                status: 'pending'
            };
        }
        groups[key].items.push(stop);
    });

    return Object.values(groups).map(group => {
        const allSuccess = group.items.every(i => i.status === 'success');
        const allFailed = group.items.every(i => i.status === 'failed');
        const anyPending = group.items.some(i => i.status === 'pending');
        
        if (allSuccess) group.status = 'success';
        else if (allFailed) group.status = 'failed';
        else if (!anyPending) group.status = 'partial';
        else group.status = 'pending';
        
        return group;
    });
};

// Cálculo de Métricas (Incluindo distância do usuário até o início)
const calculateRouteMetrics = (stops, userPos) => {
    if (!Array.isArray(stops) || stops.length === 0) return { km: "0", time: "0h 0m" };
    
    let totalKm = 0;
    // Ponto inicial: Usuário (se disponível) ou primeira parada
    let currentLat = userPos ? userPos.lat : stops[0].lat;
    let currentLng = userPos ? userPos.lng : stops[0].lng;

    // Haversine Formula
    const calcDist = (lat1, lon1, lat2, lon2) => {
        const R = 6371; 
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
        return R * c;
    };

    stops.forEach(stop => {
        totalKm += calcDist(currentLat, currentLng, stop.lat, stop.lng);
        currentLat = stop.lat;
        currentLng = stop.lng;
    });

    // Ajustes de Realismo
    const realKm = totalKm * 1.4; // Curvatura
    const avgSpeed = 20; // km/h (urbano com paradas)
    const serviceTime = stops.length * 4; // 4 min por pacote
    const totalMin = (realKm / avgSpeed * 60) + serviceTime;
    
    const h = Math.floor(totalMin / 60);
    const m = Math.floor(totalMin % 60);

    return { 
        km: realKm.toFixed(1), 
        time: `${h}h ${m}m`,
        totalPackages: stops.length
    };
};

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); 
  const [newRouteName, setNewRouteName] = useState('');
  const [tempStops, setTempStops] = useState([]);
  const [userPos, setUserPos] = useState(null);
  
  // Controle de quais grupos estão abertos na UI
  const [expandedGroups, setExpandedGroups] = useState({});

  // --- INIT ---
  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) { localStorage.removeItem(DB_KEY); }
    
    startGps();
  }, []);

  useEffect(() => {
    localStorage.setItem(DB_KEY, JSON.stringify(routes));
  }, [routes]);

  const startGps = async () => {
      try {
          await Geolocation.requestPermissions();
          Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 5000 }, (pos) => {
              if (pos) setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude });
          });
      } catch(e) {}
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
        } catch(err) { return alert("Arquivo inválido."); }

        const norm = data.map((r, i) => {
            const k = {};
            Object.keys(r).forEach(key => k[key.trim().toLowerCase()] = r[key]);
            
            return {
                id: Date.now() + i,
                // Prioridade: Stop -> Parada -> Cliente -> Nome
                name: k['stop'] || k['parada'] || k['cliente'] || k['nome'] || `Parada ${i+1}`,
                // Info extra para exibir dentro do grupo
                recipient: k['recebedor'] || k['contato'] || k['cliente'] || 'Recebedor',
                address: k['destination address'] || k['endereço'] || k['endereco'] || '---',
                lat: parseFloat(k['latitude'] || k['lat'] || 0),
                lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                status: 'pending'
            };
        }).filter(i => i.lat !== 0);

        if (norm.length > 0) setTempStops(norm);
        else alert("Erro: Sem coordenadas.");
    };

    if(file.name.endsWith('.csv')) { reader.onload = e => processData(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = e => processData(e.target.result, true); reader.readAsBinaryString(file); }
  };

  const createRoute = () => {
      if(!newRouteName.trim() || tempStops.length === 0) return;
      setRoutes([{ id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops, optimized: false }, ...routes]);
      setNewRouteName(''); setTempStops([]); setView('home');
  };

  const deleteRoute = (id) => {
      if(confirm("Excluir esta rota?")) {
          setRoutes(routes.filter(r => r.id !== id));
          if(activeRouteId === id) setView('home');
      }
  };

  const optimizeRoute = () => {
      if (!userPos) return alert("Aguardando GPS... Vá para uma área aberta.");
      
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      const currentRoute = routes[rIdx];
      let pending = currentRoute.stops.filter(s => s.status === 'pending');
      let done = currentRoute.stops.filter(s => s.status !== 'pending');
      let optimized = [];
      let pointer = userPos;

      // Vizinho Mais Próximo
      while(pending.length > 0) {
          let nearestIdx = -1, minDist = Infinity;
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
      updated[rIdx].optimized = true; // Flag de Destaque
      setRoutes(updated);
  };

  const setStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
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
  
  // Agrupamento
  const groupedStops = useMemo(() => {
      if (!activeRoute) return [];
      return groupStopsByStopName(activeRoute.stops);
  }, [activeRoute]);

  // Métricas
  const metrics = useMemo(() => {
      if (!activeRoute) return { km: "0", time: "0h 0m", totalPackages: 0 };
      return calculateRouteMetrics(activeRoute.stops, userPos);
  }, [activeRoute, userPos]); // Recalcula se userPos mudar

  // Próximo grupo para navegar
  const nextGroup = groupedStops.find(g => g.status === 'pending');

  // VIEW: HOME
  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <div className="flex justify-between items-center mb-8">
              <h1 className="text-3xl font-bold text-slate-900">Rotas</h1>
              <div className="bg-white p-2 rounded-full shadow-sm"><Package className="text-slate-400"/></div>
          </div>

          {routes.length === 0 ? (
              <div className="flex flex-col items-center justify-center mt-32 text-center opacity-40">
                  <MapPin size={48} className="mb-4 text-slate-400" />
                  <p>Nenhuma rota criada</p>
              </div>
          ) : (
              <div className="space-y-4">
                  {routes.map(r => (
                      <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} 
                           className="modern-card p-5 cursor-pointer active:scale-98">
                          <div className="flex justify-between items-start mb-2">
                              <h3 className="font-bold text-lg text-slate-800 line-clamp-1">{r.name}</h3>
                              <span className="text-xs font-bold text-slate-400 bg-slate-100 px-2 py-1 rounded-full">{r.date}</span>
                          </div>
                          <div className="flex items-center gap-4 text-sm text-slate-500">
                              <span className="flex items-center gap-1"><Package size={14}/> {r.stops.length} vols</span>
                              {r.optimized && <span className="flex items-center gap-1 text-green-600"><Check size={14}/> Otimizada</span>}
                          </div>
                      </div>
                  ))}
              </div>
          )}
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center active:scale-90 transition"><Plus size={32}/></button>
      </div>
  );

  // VIEW: CREATE
  if (view === 'create') return (
      <div className="min-h-screen bg-white flex flex-col p-6">
          <button onClick={() => setView('home')} className="self-start mb-6 -ml-2 p-2 text-slate-600"><ArrowLeft /></button>
          <h2 className="text-2xl font-bold text-slate-900 mb-8">Nova Rota</h2>
          <div className="space-y-6 flex-1">
              <input type="text" className="w-full p-4 bg-slate-50 rounded-xl font-medium outline-none focus:ring-2 focus:ring-slate-900" placeholder="Nome da Rota" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
              <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50 cursor-pointer">
                  <Upload className="text-slate-400 mb-2" />
                  <span className="text-sm font-bold text-slate-500">Importar Planilha</span>
                  <input type="file" onChange={handleFileUpload} accept=".csv,.xlsx" className="hidden" />
              </label>
              {tempStops.length > 0 && <div className="p-4 bg-green-50 text-green-700 rounded-xl font-bold text-center border border-green-100">{tempStops.length} pacotes carregados</div>}
          </div>
          <button onClick={createRoute} className="w-full bg-slate-900 text-white py-5 rounded-2xl font-bold text-lg mb-4 shadow-xl">Criar Rota</button>
      </div>
  );

  // VIEW: DETAILS
  return (
      <div className="flex flex-col h-screen bg-slate-50">
          {/* HEADER */}
          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft className="text-slate-800"/></button>
                  <h2 className="font-bold text-slate-800 truncate px-4 flex-1 text-center">{activeRoute.name}</h2>
                  <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 size={20} className="text-red-400"/></button>
              </div>

              {/* MÉTRICAS (Só aparece se otimizado ou se tiver userPos) */}
              <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4 animate-in fade-in">
                  <div className="flex flex-col items-center w-1/3 border-r border-slate-200">
                      <span className="text-[10px] uppercase font-bold text-slate-400">DISTÂNCIA</span>
                      <div className="flex items-center gap-1 font-bold text-slate-700">
                          <Map size={14} className="text-blue-500"/> {metrics.km} km
                      </div>
                  </div>
                  <div className="flex flex-col items-center w-1/3 border-r border-slate-200">
                      <span className="text-[10px] uppercase font-bold text-slate-400">TEMPO EST.</span>
                      <div className="flex items-center gap-1 font-bold text-slate-700">
                          <Clock size={14} className="text-orange-500"/> {metrics.time}
                      </div>
                  </div>
                  <div className="flex flex-col items-center w-1/3">
                      <span className="text-[10px] uppercase font-bold text-slate-400">PACOTES</span>
                      <div className="flex items-center gap-1 font-bold text-slate-700">
                          <Package size={14} className="text-green-500"/> {metrics.totalPackages}
                      </div>
                  </div>
              </div>

              {/* CONTROLES DE FLUXO (DESTAQUE INTELIGENTE) */}
              <div className="flex gap-3">
                  {/* Botão OTIMIZAR: Destaque se NÃO otimizado */}
                  <button 
                      onClick={optimizeRoute} 
                      className={`flex-1 py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all
                      ${!activeRoute.optimized ? 'btn-highlight animate-pulse' : 'btn-secondary'}`}
                  >
                      <Sliders size={18}/> {activeRoute.optimized ? 'Reotimizar' : 'Otimizar Rota'}
                  </button>
                  
                  {/* Botão NAVEGAR: Destaque se OTIMIZADO */}
                  <button 
                      onClick={() => nextGroup && openNav(nextGroup.lat, nextGroup.lng)} 
                      disabled={!activeRoute.optimized || !nextGroup}
                      className={`flex-[1.5] py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all
                      ${activeRoute.optimized ? 'btn-highlight shadow-lg' : 'bg-slate-100 text-slate-300 cursor-not-allowed'}`}
                  >
                      <Navigation size={18}/> Iniciar Rota
                  </button>
              </div>
          </div>

          {/* LISTA DE CARDS */}
          <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3">
              
              {/* CARD DE PRÓXIMO DESTINO (Destaque) */}
              {nextGroup && activeRoute.optimized && (
                  <div className="modern-card p-0 border-l-4 border-slate-900 bg-white relative mb-6 shadow-md overflow-visible">
                      <div className="bg-slate-900 text-white px-4 py-2 text-xs font-bold flex justify-between items-center">
                          <span>PRÓXIMA PARADA</span>
                          {nextGroup.items.length > 1 && <span className="bg-white/20 px-2 py-0.5 rounded text-[10px]">{nextGroup.items.length} PACOTES</span>}
                      </div>
                      
                      <div className="p-5">
                          <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{nextGroup.mainName}</h3>
                          <p className="text-sm text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                          
                          {/* Botões Rápidos do Destaque */}
                          <div className="space-y-2">
                              {nextGroup.items.map(item => (
                                  <div key={item.id} className="flex justify-between items-center py-2 border-t border-slate-100">
                                      <div className="flex-1 min-w-0 pr-2">
                                          <span className="text-sm font-bold text-slate-700 block truncate">{item.recipient}</span>
                                          <span className="text-xs text-slate-400">Pacote ID: {item.id.toString().slice(-4)}</span>
                                      </div>
                                      <div className="flex gap-2 shrink-0">
                                          <button onClick={() => setStatus(item.id, 'failed')} className="p-2 bg-red-50 text-red-500 rounded-lg hover:bg-red-100"><AlertTriangle size={16}/></button>
                                          <button onClick={() => setStatus(item.id, 'success')} className="p-2 bg-green-50 text-green-600 rounded-lg hover:bg-green-100"><Check size={16}/></button>
                                      </div>
                                  </div>
                              ))}
                          </div>
                      </div>
                  </div>
              )}

              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Sequência de Paradas</h4>

              {groupedStops.map((group, idx) => {
                  if (nextGroup && group.id === nextGroup.id && activeRoute.optimized) return null; // Já está no destaque

                  const isExpanded = expandedGroups[group.id];
                  const hasMulti = group.items.length > 1;

                  return (
                      <div key={group.id} className={`modern-card overflow-hidden ${group.status !== 'pending' ? 'opacity-50 grayscale' : ''}`}>
                          
                          {/* HEADER DO CARD (Clicável para expandir) */}
                          <div 
                              onClick={() => toggleGroup(group.id)}
                              className="p-4 flex items-center gap-4 cursor-pointer active:bg-slate-50 transition-colors"
                          >
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 
                                  ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                  {group.status === 'success' ? <Check size={14}/> : idx + 1}
                              </div>
                              
                              <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                      <h4 className="font-bold text-slate-800 text-sm truncate">{group.mainName}</h4>
                                      {hasMulti && <span className="bg-slate-800 text-white text-[10px] px-1.5 py-0.5 rounded-md font-bold">{group.items.length}</span>}
                                  </div>
                                  <p className="text-xs text-slate-400 truncate">{group.mainAddress}</p>
                              </div>

                              {/* Ícone Expansão ou Botão Único */}
                              {hasMulti || isExpanded ? (
                                  isExpanded ? <ChevronUp size={18} className="text-slate-400"/> : <ChevronDown size={18} className="text-slate-400"/>
                              ) : (
                                  group.items[0].status === 'pending' && (
                                    <button onClick={(e) => {e.stopPropagation(); setStatus(group.items[0].id, 'success')}} className="p-2 bg-slate-50 text-slate-400 hover:text-green-600 rounded-full">
                                        <Check size={18}/>
                                    </button>
                                  )
                              )}
                          </div>

                          {/* LISTA EXPANDIDA (Detalhes dos Pacotes) */}
                          {(isExpanded || (hasMulti && isExpanded)) && (
                              <div className="bg-slate-50 border-t border-slate-100 px-4 py-1 space-y-1 animate-in slide-in-from-top-2">
                                  {group.items.map(item => (
                                      <div key={item.id} className="flex justify-between items-center py-3 border-b border-slate-200 last:border-0">
                                          <div className="flex items-center gap-3 overflow-hidden">
                                              <Box size={14} className="text-slate-400 shrink-0"/>
                                              <div className="flex flex-col min-w-0">
                                                  <span className="text-sm font-bold text-slate-700 truncate">{item.recipient}</span>
                                                  {item.name !== group.mainName && <span className="text-[10px] text-slate-400 truncate">{item.name}</span>}
                                              </div>
                                          </div>
                                          
                                          <div className="flex gap-2 shrink-0 ml-2">
                                              {item.status === 'pending' ? (
                                                  <>
                                                    <button onClick={() => setStatus(item.id, 'failed')} className="text-red-400 p-1 hover:bg-red-100 rounded"><AlertTriangle size={16}/></button>
                                                    <button onClick={() => setStatus(item.id, 'success')} className="text-green-500 p-1 hover:bg-green-100 rounded"><Check size={18}/></button>
                                                  </>
                                              ) : (
                                                  <span className={`text-[10px] font-bold px-2 py-1 rounded ${item.status==='success'?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>
                                                      {item.status === 'success' ? 'OK' : 'X'}
                                                  </span>
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
    print(f"🚀 ATUALIZAÇÃO V16 (FINAL POLISH) - {APP_NAME}")
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
    subprocess.run('git commit -m "feat: V16 Group by Stop, Metrics & Button Logic"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


