import os
import shutil
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. CSS (Adicionar animação de Toast)
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

.modern-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0,0,0,0.05);
  transition: transform 0.1s ease;
  overflow: hidden;
}

.modern-card:active { transform: scale(0.995); }
.grouped-card { border-left: 4px solid #3B82F6; }

.btn-action-lg {
  height: 56px;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  line-height: 1.1;
}

.fab-main {
  background: #0F172A;
  color: white;
  box-shadow: 0 8px 25px rgba(15, 23, 42, 0.4);
}

.btn-highlight {
  background-color: #2563EB;
  color: white;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.btn-secondary {
  background-color: #F1F5F9;
  color: #64748B;
}

/* Toast Notification */
.toast-enter {
  transform: translateY(-100%);
  opacity: 0;
}
.toast-enter-active {
  transform: translateY(0);
  opacity: 1;
  transition: all 300ms ease-out;
}
'''

# 2. APP.JSX (Lógica Corrigida de Otimização e Status)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map, Loader2
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v20_fix';

// --- HELPERS ---

const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    
    // Mantém a ordem original do array 'stops' (que já deve vir otimizado)
    stops.forEach(stop => {
        const rawName = stop.name ? String(stop.name) : 'Parada Sem Nome';
        const key = rawName.trim().toLowerCase();

        if (!groups[key]) {
            groups[key] = {
                id: key,
                lat: stop.lat,
                lng: stop.lng,
                mainName: rawName, 
                mainAddress: stop.address,
                items: [], // A ordem dos itens aqui respeitará a ordem de inserção
                status: 'pending'
            };
        }
        groups[key].items.push(stop);
    });

    // Retorna array de grupos preservando a ordem da primeira aparição na lista otimizada
    // (Object.values não garante ordem, então vamos reconstruir baseado na lista original)
    const orderedGroups = [];
    const processedKeys = new Set();

    stops.forEach(stop => {
        const rawName = stop.name ? String(stop.name) : 'Parada Sem Nome';
        const key = rawName.trim().toLowerCase();
        if (!processedKeys.has(key)) {
            // Calcula status do grupo
            const group = groups[key];
            const allSuccess = group.items.every(i => i.status === 'success');
            const allFailed = group.items.every(i => i.status === 'failed');
            const anyPending = group.items.some(i => i.status === 'pending');
            
            if (allSuccess) group.status = 'success';
            else if (allFailed) group.status = 'failed';
            else if (!anyPending) group.status = 'partial';
            else group.status = 'pending';

            orderedGroups.push(group);
            processedKeys.add(key);
        }
    });

    return orderedGroups;
};

const calculateRouteMetrics = (stops, userPos) => {
    if (!Array.isArray(stops) || stops.length === 0) return { km: "0", time: "0h 0m", totalPackages: 0 };
    
    let totalKm = 0;
    let currentLat = userPos ? userPos.lat : stops[0].lat;
    let currentLng = userPos ? userPos.lng : stops[0].lng;

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
        // Só conta distância para paradas pendentes para estimativa restante
        // Mas para total inicial conta tudo. Aqui vamos mostrar total da rota.
        totalKm += calcDist(currentLat, currentLng, stop.lat, stop.lng);
        currentLat = stop.lat;
        currentLng = stop.lng;
    });

    const realKm = totalKm * 1.6; 
    const avgSpeed = 18; 
    const serviceTime = stops.length * 4; 
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
  const [expandedGroups, setExpandedGroups] = useState({});
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [toastMsg, setToastMsg] = useState(null);

  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) { localStorage.removeItem(DB_KEY); }
    getCurrentLocation(false);
  }, []);

  useEffect(() => {
    localStorage.setItem(DB_KEY, JSON.stringify(routes));
  }, [routes]);

  const showToast = (msg) => {
      setToastMsg(msg);
      setTimeout(() => setToastMsg(null), 3000);
  };

  const getCurrentLocation = async (force = false) => {
      try {
          if (force) await Geolocation.requestPermissions();
          const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 10000 });
          const newPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserPos(newPos);
          return newPos;
      } catch (e) { return null; }
  };

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
            Object.keys(r).forEach(key => k[String(key).trim().toLowerCase()] = r[key]);
            const safeString = (val) => val ? String(val) : '';

            return {
                id: Date.now() + i + Math.random(), // ID ÚNICO REAL
                name: safeString(k['stop'] || k['parada'] || k['cliente'] || k['nome'] || `Parada ${i+1}`),
                recipient: safeString(k['recebedor'] || k['contato'] || k['cliente'] || 'Recebedor'),
                address: safeString(k['destination address'] || k['endereço'] || k['endereco'] || '---'),
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
      if(confirm("Excluir rota?")) {
          setRoutes(routes.filter(r => r.id !== id));
          if(activeRouteId === id) setView('home');
      }
  };

  // --- OTIMIZAÇÃO REAL ---
  const optimizeRoute = async () => {
      setIsOptimizing(true);
      
      let currentPos = userPos;
      if (!currentPos) currentPos = await getCurrentLocation(true);

      if (!currentPos) {
          setIsOptimizing(false);
          alert("Erro GPS: Ative a localização e tente novamente.");
          return;
      }

      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      // Separa o que já foi feito do que falta
      const currentRoute = routes[rIdx];
      let pending = currentRoute.stops.filter(s => s.status === 'pending');
      let done = currentRoute.stops.filter(s => s.status !== 'pending');
      
      let optimized = [];
      let pointer = currentPos;

      // Algoritmo: Nearest Neighbor
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

      // IMPORTANTE: Atualiza o estado global com a NOVA ORDEM
      const updatedRoutes = [...routes];
      updatedRoutes[rIdx] = {
          ...updatedRoutes[rIdx],
          stops: [...done, ...optimized], // Coloca os feitos em cima, e os novos ordenados
          optimized: true
      };
      
      setRoutes(updatedRoutes);
      setIsOptimizing(false);
      showToast("Rota Otimizada com Sucesso!");
  };

  // --- MUDAR STATUS (CORREÇÃO) ---
  const setStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      
      const updatedRoutes = [...routes];
      const route = updatedRoutes[rIdx];
      
      // Busca pelo ID único no array de paradas
      const stopIndex = route.stops.findIndex(s => s.id === stopId);
      
      if (stopIndex !== -1) {
          route.stops[stopIndex].status = status;
          setRoutes(updatedRoutes); // Salva mudança
          if (status === 'success') showToast("Entrega Realizada!");
      } else {
          console.error("Parada não encontrada ID:", stopId);
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
  
  // Agrupamento deve ser recalculado sempre que a ordem ou status muda
  const groupedStops = useMemo(() => {
      if (!activeRoute) return [];
      return groupStopsByStopName(activeRoute.stops);
  }, [activeRoute]); // Dependência crucial: activeRoute

  const metrics = useMemo(() => {
      if (!activeRoute) return { km: "0", time: "0h 0m", totalPackages: 0 };
      return calculateRouteMetrics(activeRoute.stops, userPos);
  }, [activeRoute, userPos]);

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
                      <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="modern-card p-5 cursor-pointer active:scale-98">
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
          {/* TOAST MESSAGE */}
          {toastMsg && (
              <div className="fixed top-4 left-4 right-4 bg-slate-900 text-white p-3 rounded-lg shadow-xl z-50 text-center font-bold text-sm animate-in fade-in slide-in-from-top-5">
                  {toastMsg}
              </div>
          )}

          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft className="text-slate-800"/></button>
                  <h2 className="font-bold text-slate-800 truncate px-4 flex-1 text-center">{activeRoute.name}</h2>
                  <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 size={20} className="text-red-400"/></button>
              </div>
              {activeRoute.optimized && (
                  <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4 animate-in fade-in">
                      <div className="flex items-center gap-2"><Map size={16} className="text-blue-500"/><span className="text-xs font-bold text-slate-600">{metrics.km} km</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Clock size={16} className="text-orange-500"/><span className="text-xs font-bold text-slate-600">~{metrics.time}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Box size={16} className="text-green-500"/><span className="text-xs font-bold text-slate-600">{metrics.totalPackages} vols</span></div>
                  </div>
              )}
              <div className="flex gap-3">
                  <button onClick={optimizeRoute} disabled={isOptimizing} className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition ${!activeRoute.optimized ? 'btn-highlight animate-pulse' : 'btn-secondary'}`}>
                      {isOptimizing ? <Loader2 className="animate-spin" size={18}/> : <Sliders size={18}/>} 
                      {isOptimizing ? 'Calculando...' : (activeRoute.optimized ? 'Reotimizar' : 'Otimizar Rota')}
                  </button>
                  {nextGroup && (
                      <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} disabled={!activeRoute.optimized} className={`flex-[1.5] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition ${activeRoute.optimized ? 'btn-highlight shadow-lg' : 'bg-slate-100 text-slate-300 cursor-not-allowed'}`}>
                          <Navigation size={18}/> Iniciar Rota
                      </button>
                  )}
              </div>
          </div>

          <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3">
              {nextGroup && activeRoute.optimized && (
                  <div className="modern-card p-6 border-l-4 border-slate-900 bg-white relative mb-6 shadow-md">
                      <div className="absolute top-0 right-0 bg-slate-900 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRÓXIMO</div>
                      <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{nextGroup.mainName}</h3>
                      <p className="text-sm text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                      
                      {nextGroup.items.length > 1 && <div className="mb-4 bg-blue-50 text-blue-800 px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-2"><Box size={14}/> {nextGroup.items.length} PACOTES</div>}

                      <div className="space-y-3 border-t border-slate-100 pt-3">
                          {nextGroup.items.map(item => (
                              <div key={item.id} className="flex flex-col bg-slate-50 p-3 rounded-lg">
                                  <div className="mb-2">
                                      <span className="text-sm font-bold text-slate-800 block leading-tight">{item.address}</span>
                                      <span className="text-[10px] text-slate-400 block mt-1">{item.name} • {item.recipient}</span>
                                  </div>
                                  <div className="flex gap-2 w-full">
                                      <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 btn-action-lg bg-white border border-red-200 text-red-600 rounded-lg hover:bg-red-50"><AlertTriangle size={18} className="mb-1"/> Não Entregue</button>
                                      <button onClick={() => setStatus(item.id, 'success')} className="flex-1 btn-action-lg bg-green-600 text-white rounded-lg shadow-sm active:scale-95"><Check size={20} className="mb-1"/> ENTREGUE</button>
                                  </div>
                              </div>
                          ))}
                      </div>
                  </div>
              )}

              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Sequência de Paradas</h4>

              {groupedStops.map((group, idx) => {
                  if (nextGroup && group.id === nextGroup.id && activeRoute.optimized) return null;
                  const isExpanded = expandedGroups[group.id];
                  const hasMulti = group.items.length > 1;

                  return (
                      <div key={group.id} className={`modern-card overflow-hidden ${group.status !== 'pending' ? 'opacity-50 grayscale' : ''}`}>
                          <div onClick={() => toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer active:bg-slate-50 transition-colors">
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>{group.status === 'success' ? <Check size={14}/> : idx + 1}</div>
                              <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2"><h4 className="font-bold text-slate-800 text-sm truncate">{group.mainName}</h4>{hasMulti && <span className="bg-slate-800 text-white text-[10px] px-1.5 py-0.5 rounded-md font-bold">{group.items.length}</span>}</div>
                                  <p className="text-xs text-slate-400 truncate">{group.mainAddress}</p>
                              </div>
                              {hasMulti || isExpanded ? (isExpanded ? <ChevronUp size={18} className="text-slate-400"/> : <ChevronDown size={18} className="text-slate-400"/>) : (group.items[0].status === 'pending' && <button onClick={(e) => {e.stopPropagation(); setStatus(group.items[0].id, 'success')}} className="p-2 bg-slate-50 text-slate-400 hover:text-green-600 rounded-full"><Check size={18}/></button>)}
                          </div>
                          {(isExpanded || (hasMulti && isExpanded)) && (
                              <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-3 animate-in slide-in-from-top-2">
                                  {group.items.map(item => (
                                      <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                          <div className="mb-2"><span className="text-sm font-bold text-slate-700 block">{item.address}</span><span className="text-[10px] text-slate-400">{item.name}</span></div>
                                          {item.status === 'pending' ? (<div className="flex gap-2 w-full"><button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-2 bg-white border border-red-200 text-red-500 rounded font-bold text-xs">FALHA</button><button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-2 bg-green-500 text-white rounded font-bold text-xs shadow-sm">ENTREGUE</button></div>) : (<span className={`text-[10px] font-bold px-2 py-1 rounded w-fit ${item.status==='success'?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>{item.status === 'success' ? 'ENTREGUE' : 'NÃO ENTREGUE'}</span>)}
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
    print(f"🚀 ATUALIZAÇÃO V20 (FUNCTIONAL FIX) - {APP_NAME}")
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
    subprocess.run('git commit -m "fix: V20 Fix Optimization Logic and Status Buttons"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


