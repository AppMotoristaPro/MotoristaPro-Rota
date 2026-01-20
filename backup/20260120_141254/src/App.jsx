import React, { useState, useEffect, useMemo } from 'react';
// IMPORTANTE: Removido 'Gauge' que causava crash em versoes antigas do lucide
import { Upload, Navigation, Check, AlertTriangle, Trash2, Plus, ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, ChevronUp, Box, Activity } from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// --- HELPER: AGRUPAMENTO SEGURO ---
const groupStopsByName = (stops) => {
    if (!Array.isArray(stops)) return []; // Proteção contra crash
    
    const groups = {};
    
    stops.forEach(stop => {
        const rawKey = stop.name ? stop.name.trim().toLowerCase() : 'sem_nome';
        // Fallback seguro se lat/lng forem invalidos
        const lat = stop.lat || 0;
        const lng = stop.lng || 0;
        const fallbackKey = `${lat.toFixed(4)}_${lng.toFixed(4)}`;
        const key = rawKey === 'sem_nome' ? fallbackKey : rawKey;

        if (!groups[key]) {
            groups[key] = {
                id: key,
                lat: lat,
                lng: lng,
                mainName: stop.name || 'Sem Nome',
                mainAddress: stop.address || '---',
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

// --- HELPER: MÉTRICAS SEGURAS ---
const calculateMetrics = (stops) => {
    if (!stops || stops.length < 2) return { km: "0.0", time: "0h 0m" };

    let totalKm = 0;
    for (let i = 0; i < stops.length - 1; i++) {
        const p1 = stops[i];
        const p2 = stops[i+1];
        
        const R = 6371; 
        const dLat = (p2.lat - p1.lat) * Math.PI / 180;
        const dLon = (p2.lng - p1.lng) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(p1.lat * Math.PI / 180) * Math.cos(p2.lat * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
        totalKm += R * c;
    }
    
    // Fator 1.5x (Realismo urbano)
    const realKm = totalKm * 1.5;
    const avgSpeedKmH = 20; 
    const serviceTimeMin = stops.length * 4; // 4 min por parada
    
    const travelTimeMin = (realKm / avgSpeedKmH) * 60;
    const totalMin = travelTimeMin + serviceTimeMin;
    
    const h = Math.floor(totalMin / 60);
    const m = Math.floor(totalMin % 60);
    
    return { 
        km: realKm.toFixed(1), 
        time: `${h}h ${m}m` 
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

  // Recuperação segura
  useEffect(() => {
    try {
        const saved = localStorage.getItem('mp_routes_v14'); // Nova key para limpar cache corrompido
        if (saved) setRoutes(JSON.parse(saved));
    } catch(e) {
        console.error("Erro ao carregar rotas antigas", e);
    }
    requestPermissions();
  }, []);

  useEffect(() => {
    localStorage.setItem('mp_routes_v14', JSON.stringify(routes));
  }, [routes]);

  const requestPermissions = async () => {
      try { await Geolocation.requestPermissions(); startGpsWatch(); } catch (e) {}
  };

  const startGpsWatch = () => {
      Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 5000 }, (pos) => {
          if (pos) setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      });
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const process = (d, bin) => {
        let data = [];
        try {
            if(bin) {
                const wb = XLSX.read(d, {type:'binary'});
                data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
            } else {
                data = Papa.parse(d, {header:true, skipEmptyLines:true}).data;
            }
        } catch (err) {
            alert("Erro ao ler arquivo. Formato inválido.");
            return;
        }
        
        const norm = data.map((r, i) => {
             const k = Object.keys(r).reduce((acc, key) => { acc[key.toLowerCase().trim()] = r[key]; return acc; }, {});
             return {
                 id: Date.now() + i,
                 name: k['stop'] || k['parada'] || k['cliente'] || k['nome'] || `Entrega ${i+1}`,
                 address: k['destination address'] || k['endereço'] || k['endereco'] || '---',
                 lat: parseFloat(k['latitude'] || k['lat'] || 0),
                 lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                 status: 'pending'
             };
        }).filter(i => i.lat !== 0);

        if(norm.length) setTempStops(norm);
        else alert("Nenhuma coordenada encontrada na planilha.");
    };

    const reader = new FileReader();
    if(file.name.endsWith('.csv')) { reader.onload = (e) => process(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = (e) => process(e.target.result, true); reader.readAsBinaryString(file); }
  };

  const saveNewRoute = () => {
      if(!newRouteName.trim() || tempStops.length === 0) return;
      const newRoute = { 
          id: Date.now(), 
          name: newRouteName, 
          date: new Date().toLocaleDateString(), 
          stops: tempStops,
          optimized: false 
      };
      setRoutes([newRoute, ...routes]);
      setNewRouteName(''); setTempStops([]); setView('home');
  };

  const deleteRoute = (id) => {
      if(confirm("Excluir rota permanentemente?")) {
          setRoutes(routes.filter(r => r.id !== id));
          if(activeRouteId === id) setView('home');
      }
  };

  const optimizeActiveRoute = () => {
      if(!userPos) return alert("Aguardando GPS (saia para uma área aberta)...");
      const idx = routes.findIndex(r => r.id === activeRouteId);
      if(idx === -1) return;

      const currentStops = [...routes[idx].stops];
      let pending = currentStops.filter(s => s.status === 'pending');
      let done = currentStops.filter(s => s.status !== 'pending');
      let optimized = [];
      let current = userPos;

      // Algoritmo Vizinho Mais Próximo
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
      updated[idx].optimized = true;
      setRoutes(updated);
  };

  const handleStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if(rIdx === -1) return;
      const updated = [...routes];
      const sIdx = updated[rIdx].stops.findIndex(s => s.id === stopId);
      
      if(sIdx !== -1) {
          updated[rIdx].stops[sIdx].status = status;
          setRoutes(updated);
      }
  };

  const openNav = (lat, lng) => {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const toggleGroup = (groupId) => {
      setExpandedGroups(prev => ({ ...prev, [groupId]: !prev[groupId] }));
  };

  // --- RENDER ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  
  const groupedStops = useMemo(() => {
      if (!activeRoute || !activeRoute.stops) return [];
      return groupStopsByName(activeRoute.stops);
  }, [activeRoute]);

  const metrics = useMemo(() => {
      if (!activeRoute || !activeRoute.stops) return { km: "0.0", time: "0h 0m" };
      return calculateMetrics(activeRoute.stops);
  }, [activeRoute]);

  const nextGroup = groupedStops.find(g => g.status === 'pending');

  // VIEW: HOME
  if(view === 'home') return (
    <div className="min-h-screen pb-28 px-5 pt-8">
        <div className="flex justify-between items-center mb-8">
            <h1 className="text-3xl font-bold text-slate-900">Minhas Rotas</h1>
            <div className="bg-white p-2 rounded-full shadow-sm"><Package className="text-slate-400"/></div>
        </div>
        {routes.length === 0 ? (
            <div className="flex flex-col items-center justify-center mt-32 opacity-40">
                <MapPin size={48} className="mb-4"/>
                <p className="font-medium">Nenhuma rota ativa</p>
                <p className="text-sm text-gray-400 mt-2">Toque em + para criar</p>
            </div>
        ) : (
            <div className="space-y-4">
                {routes.map(r => (
                    <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="modern-card p-5 cursor-pointer hover:shadow-md border-l-4 border-transparent hover:border-blue-500">
                        <div className="flex justify-between items-start mb-2">
                            <h3 className="font-bold text-lg text-slate-800">{r.name}</h3>
                            <span className="text-xs text-slate-400 font-medium">{r.date}</span>
                        </div>
                        <div className="text-sm text-slate-500">{r.stops ? r.stops.length : 0} entregas</div>
                    </div>
                ))}
            </div>
        )}
        <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center active:scale-95 transition"><Plus size={32}/></button>
    </div>
  );

  // VIEW: CREATE
  if(view === 'create') return (
    <div className="min-h-screen bg-white flex flex-col p-6">
        <button onClick={() => setView('home')} className="self-start mb-6 p-2 -ml-2"><ArrowLeft className="text-slate-800"/></button>
        <h2 className="text-2xl font-bold mb-8 text-slate-900">Nova Rota</h2>
        <div className="space-y-6 flex-1">
            <input type="text" placeholder="Nome da Rota" className="w-full p-5 bg-slate-50 rounded-2xl text-lg font-medium outline-none border border-slate-100 focus:border-slate-300" value={newRouteName} onChange={e => setNewRouteName(e.target.value)} />
            <label className="block w-full cursor-pointer group">
                <div className="w-full border-2 border-dashed border-slate-200 rounded-2xl h-40 flex flex-col items-center justify-center text-slate-400"><Upload className="mb-2"/><span className="font-bold text-sm">Importar Planilha</span></div>
                <input type="file" onChange={handleFileUpload} accept=".csv,.xlsx" className="hidden"/>
            </label>
            {tempStops.length > 0 && <div className="p-4 bg-green-50 text-green-700 rounded-xl font-bold text-center border border-green-100">{tempStops.length} endereços identificados</div>}
        </div>
        <button onClick={saveNewRoute} className="w-full bg-slate-900 text-white py-5 rounded-2xl font-bold text-lg mb-4">Criar Rota</button>
    </div>
  );

  // VIEW: DETAILS
  if(view === 'details' && activeRoute) return (
      <div className="flex flex-col h-screen bg-slate-50">
          
          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft className="text-slate-800"/></button>
                  <h2 className="font-bold text-slate-800 truncate px-4 flex-1 text-center">{activeRoute.name}</h2>
                  <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 size={20} className="text-red-400"/></button>
              </div>

              {activeRoute.optimized && (
                  <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4 animate-in fade-in">
                      <div className="flex items-center gap-2">
                          <Activity size={16} className="text-blue-500"/>
                          <span className="text-xs font-bold text-slate-600">{metrics.km} km</span>
                      </div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2">
                          <Clock size={16} className="text-orange-500"/>
                          <span className="text-xs font-bold text-slate-600">~{metrics.time}</span>
                      </div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2">
                          <Box size={16} className="text-green-500"/>
                          <span className="text-xs font-bold text-slate-600">{activeRoute.stops.length} vols</span>
                      </div>
                  </div>
              )}

              <div className="flex gap-3">
                  <button 
                      onClick={optimizeActiveRoute} 
                      className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition
                      ${!activeRoute.optimized ? 'btn-primary' : 'btn-secondary'}`}
                  >
                      <Sliders size={16}/> {activeRoute.optimized ? 'Reotimizar' : 'Otimizar Rota'}
                  </button>
                  
                  {nextGroup && (
                      <button 
                          onClick={() => openNav(nextGroup.lat, nextGroup.lng)} 
                          className={`flex-[2] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition
                          ${activeRoute.optimized ? 'btn-primary animate-pulse' : 'btn-secondary opacity-50 cursor-not-allowed'}`}
                          disabled={!activeRoute.optimized}
                      >
                          <Navigation size={16}/> Navegar
                      </button>
                  )}
              </div>
          </div>

          <div className="flex-1 overflow-y-auto px-5 pb-safe space-y-3 pt-4">
              
              {nextGroup && activeRoute.optimized && (
                  <div className="modern-card p-6 border-l-4 border-slate-900 bg-white relative mb-6 shadow-lg">
                      <div className="absolute top-0 right-0 bg-slate-900 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">
                          PRÓXIMO DESTINO
                      </div>
                      <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{nextGroup.mainName}</h3>
                      <p className="text-slate-500 text-sm mb-4">{nextGroup.mainAddress}</p>
                      
                      {nextGroup.items.length > 1 && (
                          <div className="mb-4 bg-blue-50 text-blue-800 px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-2">
                              <Box size={14}/> {nextGroup.items.length} PACOTES AQUI
                          </div>
                      )}

                      <div className="space-y-2 border-t border-slate-100 pt-3">
                          {nextGroup.items.map(item => (
                              <div key={item.id} className="flex justify-between items-center">
                                  <span className="text-sm font-medium">{item.name}</span>
                                  <div className="flex gap-2">
                                      <button onClick={() => handleStatus(item.id, 'failed')} className="p-1.5 bg-red-50 text-red-500 rounded"><AlertTriangle size={14}/></button>
                                      <button onClick={() => handleStatus(item.id, 'success')} className="p-1.5 bg-green-500 text-white rounded"><Check size={14}/></button>
                                  </div>
                              </div>
                          ))}
                      </div>
                  </div>
              )}

              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Lista de Entregas</h4>
              
              {groupedStops.map((group, idx) => {
                  if (nextGroup && group.id === nextGroup.id && activeRoute.optimized) return null;

                  const isExpanded = expandedGroups[group.id];
                  const isMultiple = group.items.length > 1;

                  return (
                      <div key={group.id} className={`modern-card overflow-hidden ${isMultiple ? 'grouped-card' : ''} ${group.status !== 'pending' ? 'opacity-60' : ''}`}>
                          
                          <div 
                              className="p-4 flex items-center gap-4 cursor-pointer active:bg-slate-50"
                              onClick={() => toggleGroup(group.id)} 
                          >
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs 
                                  ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                  {group.status === 'success' ? <Check size={14}/> : idx + 1}
                              </div>
                              
                              <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                      <h4 className="font-bold text-slate-800 text-sm truncate">{group.mainName}</h4>
                                      {isMultiple && <span className="bg-slate-800 text-white text-[10px] px-1.5 rounded-full">{group.items.length}</span>}
                                  </div>
                                  <p className="text-slate-400 text-xs truncate">{group.mainAddress}</p>
                              </div>

                              {isMultiple || isExpanded ? (
                                  isExpanded ? <ChevronUp size={16} className="text-slate-400"/> : <ChevronDown size={16} className="text-slate-400"/>
                              ) : (
                                  group.items[0].status === 'pending' && (
                                    <button onClick={(e) => {e.stopPropagation(); handleStatus(group.items[0].id, 'success')}} className="p-2 bg-slate-50 text-slate-400 hover:text-green-600 rounded-full">
                                        <Check size={16}/>
                                    </button>
                                  )
                              )}
                          </div>

                          {(isExpanded || (isMultiple && isExpanded)) && (
                              <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-2 animate-in slide-in-from-top-2">
                                  {group.items.map(item => (
                                      <div key={item.id} className="flex justify-between items-center py-2 border-b border-slate-200 last:border-0">
                                          <div className="flex items-center gap-2">
                                              <Package size={14} className="text-slate-400"/>
                                              <span className="text-sm font-medium text-slate-700">{item.name}</span>
                                          </div>
                                          {item.status === 'pending' ? (
                                              <div className="flex gap-2">
                                                  <button onClick={() => handleStatus(item.id, 'failed')} className="text-red-400 hover:text-red-600"><AlertTriangle size={16}/></button>
                                                  <button onClick={() => handleStatus(item.id, 'success')} className="text-green-400 hover:text-green-600"><Check size={18}/></button>
                                              </div>
                                          ) : (
                                              <span className={`text-[10px] font-bold ${item.status==='success'?'text-green-600':'text-red-600'}`}>
                                                  {item.status==='success' ? 'OK' : 'X'}
                                              </span>
                                          )}
                                      </div>
                                  ))}
                              </div>
                          )}
                      </div>
                  );
              })}
              <div className="h-10"></div>
          </div>
      </div>
  );
}
