import os
import shutil
import datetime
import subprocess

# --- CONFIGURAÇÕES ---
BACKUP_DIR = "backup"
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
CURRENT_BACKUP_PATH = os.path.join(BACKUP_DIR, f"fix_v5_{TIMESTAMP}")

# --- ARQUIVOS CORRIGIDOS ---
FILES_TO_WRITE = {
    "src/components/RouteList.jsx": """import React, { useState } from 'react';
import { Check, ChevronUp, ChevronDown, Layers, Edit3, Save } from 'lucide-react';

export default function RouteList(props) {
    // Desestruturação segura das props
    const { 
        groupedStops = [], 
        nextGroup = null, 
        activeRoute = {}, 
        searchQuery = '', 
        expandedGroups = {}, 
        toggleGroup, 
        setStatus,
        onReorder 
    } = props;

    const [isEditing, setIsEditing] = useState(false);
    const [editValues, setEditValues] = useState({});

    const safeStr = (val) => val ? String(val).trim() : '';

    const setAllStatus = (items, status) => {
        items.forEach(item => {
            if (item.status === 'pending') setStatus(item.id, status);
        });
    };

    const filteredGroups = !searchQuery ? groupedStops : groupedStops.filter(g => 
        safeStr(g.mainName).toLowerCase().includes(searchQuery.toLowerCase()) || 
        safeStr(g.mainAddress).toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleInputChange = (groupId, value) => {
        setEditValues(prev => ({...prev, [groupId]: value}));
    };

    const handleInputBlur = (group, oldIndex) => {
        const newIndex = parseInt(editValues[group.id]);
        if (!isNaN(newIndex) && newIndex > 0 && newIndex <= groupedStops.length) {
            onReorder(oldIndex, newIndex - 1); 
        }
        setEditValues(prev => ({...prev, [group.id]: ''}));
    };

    // Função wrapper segura para evitar o crash ReferenceError
    const handleToggle = (id) => {
        if (typeof toggleGroup === 'function') {
            toggleGroup(id);
        } else {
            console.error("toggleGroup function is missing!");
        }
    };

    return (
        <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3 relative">
            
            {!searchQuery && (
                <div className="flex justify-end mb-2">
                    <button 
                        onClick={() => setIsEditing(!isEditing)} 
                        className={`text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-2 transition
                        ${isEditing ? 'bg-slate-900 text-white' : 'bg-slate-200 text-slate-600'}`}
                    >
                        {isEditing ? <Save size={14}/> : <Edit3 size={14}/>}
                        {isEditing ? 'SALVAR ORDEM' : 'EDITAR SEQUÊNCIA'}
                    </button>
                </div>
            )}

            {!isEditing && !searchQuery && nextGroup && activeRoute.optimized && (
                <div className="modern-card p-6 border-l-8 border-blue-600 bg-white relative mb-6 shadow-lg">
                    <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">ALVO ATUAL</div>
                    <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{nextGroup.mainName}</h3>
                    <p className="text-sm text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                    
                    {nextGroup.items.filter(i => i.status === 'pending').length > 1 && (
                        <button 
                            onClick={() => setAllStatus(nextGroup.items, 'success')}
                            className="w-full mb-4 py-2 bg-green-100 text-green-700 rounded-lg text-xs font-bold flex items-center justify-center gap-2 active:scale-95 transition"
                        >
                            <Layers size={14}/> ENTREGAR TODOS ({nextGroup.items.filter(i => i.status === 'pending').length})
                        </button>
                    )}

                    <div className="space-y-3 border-t border-slate-100 pt-3">
                        {nextGroup.items.map((item, idx) => (
                            item.status === 'pending' && (
                                <div key={item.id} className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                                    <span className="text-[10px] font-bold text-slate-400 block mb-1">VOLUME #{idx + 1}</span>
                                    <p className="text-sm font-bold text-slate-800 mb-3">{item.address}</p>
                                    <div className="flex gap-2">
                                        <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-3 bg-white border border-red-200 text-red-600 rounded-xl text-xs font-bold">FALHA</button>
                                        <button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-3 bg-green-600 text-white rounded-xl text-xs font-bold shadow-md">ENTREGUE</button>
                                    </div>
                                </div>
                            )
                        ))}
                    </div>
                </div>
            )}

            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">
                {isEditing ? 'Reordenar Paradas' : 'Sequência da Rota'}
            </h4>
            
            {filteredGroups.map((group, idx) => (
                (!isEditing && !searchQuery && nextGroup && group.id === nextGroup.id && activeRoute.optimized) ? null : (
                    <div key={group.id} className={`modern-card border-l-4 ${group.status === 'success' ? 'border-green-500 opacity-60' : 'border-slate-200'}`}>
                        <div onClick={() => !isEditing && handleToggle(group.id)} className="p-4 flex items-center gap-4 cursor-pointer">
                            
                            {isEditing ? (
                                <input 
                                    type="number" 
                                    className="w-12 h-10 bg-slate-100 rounded-lg text-center font-bold text-lg outline-none border-2 focus:border-blue-500"
                                    placeholder={idx + 1}
                                    value={editValues[group.id] !== undefined ? editValues[group.id] : ''}
                                    onChange={(e) => handleInputChange(group.id, e.target.value)}
                                    onBlur={() => handleInputBlur(group, idx)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleInputBlur(group, idx)}
                                    onClick={(e) => e.stopPropagation()}
                                />
                            ) : (
                                <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center font-bold text-xs shrink-0">
                                    {group.status === 'success' ? <Check size={14} className="text-green-600"/> : (idx + 1)}
                                </div>
                            )}

                            <div className="flex-1 min-w-0">
                                <h4 className="font-bold text-slate-800 text-sm truncate">{group.mainName}</h4>
                                <p className="text-xs text-slate-400 truncate">{group.items.length} pacote(s)</p>
                            </div>
                            
                            {!isEditing && group.items.length > 1 ? (expandedGroups[group.id] ? <ChevronUp/> : <ChevronDown/>) : null}
                        </div>
                        {(expandedGroups[group.id] || (isEditing === false && group.items.length > 1 && expandedGroups[group.id])) && (
                            <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-3">
                                {group.items.map((item) => (
                                    <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                        <div className="mb-2">
                                            <span className="text-[10px] font-bold text-blue-500 block">ENDEREÇO</span>
                                            <span className="text-sm font-bold text-slate-700 block">{item.address}</span>
                                        </div>
                                        {item.status === 'pending' ? (
                                            <div className="flex gap-2 w-full">
                                                <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-2 btn-outline-red rounded font-bold text-xs">NÃO ENTREGUE</button>
                                                <button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-2 btn-gradient-green rounded font-bold text-xs text-white shadow-sm">ENTREGUE</button>
                                            </div>
                                        ) : (
                                            <span className="text-xs font-bold">{item.status === 'success' ? 'ENTREGUE' : 'NÃO ENTREGUE'}</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )
            ))}
            <div className="h-10"></div>
        </div>
    );
}
""",

    "src/App.jsx": """import React, { useState, useEffect, useMemo } from 'react';
import { 
  Upload, Navigation, Trash2, Plus, ArrowLeft, Sliders, MapPin, 
  Package, Clock, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { useJsApiLoader } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

import MapView from './components/MapView';
import RouteList from './components/RouteList';

const DB_KEY = 'mp_db_v33_hotfix';
const GOOGLE_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

// --- HELPERS ---
const safeStr = (val) => val ? String(val).trim() : '';

const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    stops.forEach(stop => {
        const rawName = stop.name ? String(stop.name) : 'Sem Nome';
        const key = rawName.trim().toLowerCase();
        if (!groups[key]) {
            groups[key] = {
                id: key, lat: Number(stop.lat)||0, lng: Number(stop.lng)||0,
                mainName: rawName, mainAddress: safeStr(stop.address),
                items: [], status: 'pending'
            };
        }
        groups[key].items.push(stop);
    });
    
    const ordered = [];
    const seen = new Set();
    stops.forEach(stop => {
        const key = (safeStr(stop.name) || 'Sem Nome').toLowerCase();
        if (!seen.has(key)) {
            const g = groups[key];
            if(g) {
                const t = g.items.length;
                const s = g.items.filter(i => i.status === 'success').length;
                const f = g.items.filter(i => i.status === 'failed').length;
                if (s === t) g.status = 'success';
                else if (f === t) g.status = 'failed';
                else if (s+f > 0) g.status = 'partial';
                else g.status = 'pending';
                ordered.push(g);
                seen.add(key);
            }
        }
    });
    return ordered;
};

const optimizeRollingChain = async (allStops, startPos) => {
    let unvisited = [...allStops];
    let finalRoute = [];
    let currentPos = startPos;
    const service = new window.google.maps.DirectionsService();

    while (unvisited.length > 0) {
        unvisited.sort((a, b) => {
            const dA = Math.pow(a.lat - currentPos.lat, 2) + Math.pow(a.lng - currentPos.lng, 2);
            const dB = Math.pow(b.lat - currentPos.lat, 2) + Math.pow(b.lng - currentPos.lng, 2);
            return dA - dB;
        });

        const batch = unvisited.slice(0, 23);
        unvisited = unvisited.slice(23);
        const waypoints = batch.map(p => ({ location: { lat: p.lat, lng: p.lng }, stopover: true }));
        
        try {
            const res = await service.route({
                origin: currentPos,
                destination: batch[batch.length - 1], 
                waypoints: waypoints,
                optimizeWaypoints: true,
                travelMode: 'DRIVING'
            });
            const order = res.routes[0].waypoint_order;
            const orderedBatch = order.map(idx => batch[idx]);
            finalRoute.push(...orderedBatch);
            currentPos = orderedBatch[orderedBatch.length - 1];
            await new Promise(r => setTimeout(r, 400));
        } catch (e) {
            finalRoute.push(...batch);
            currentPos = batch[batch.length - 1];
        }
    }
    return finalRoute;
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
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  
  // Directions API Response & Metrics
  const [directionsResponse, setDirectionsResponse] = useState(null);
  const [realMetrics, setRealMetrics] = useState(null);

  const { isLoaded } = useJsApiLoader({ id: 'google-map-script', googleMapsApiKey: GOOGLE_KEY });

  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) {}
    getCurrentLocation();
  }, []);

  useEffect(() => { localStorage.setItem(DB_KEY, JSON.stringify(routes)); }, [routes]);

  const showToast = (msg, type = 'success') => {
      setToast({ msg, type });
      setTimeout(() => setToast(null), 2000);
  };

  const getCurrentLocation = async () => {
      try {
          await Geolocation.requestPermissions();
          const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true });
          const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserPos(p);
          return p;
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
            return {
                id: Date.now() + i + Math.random(),
                name: safeStr(k['stop'] || k['cliente'] || `Parada ${i+1}`),
                recipient: safeStr(k['recebedor'] || k['contato'] || 'Recebedor'),
                address: safeStr(k['destination address'] || k['endereço'] || '---'),
                lat: parseFloat(k['latitude'] || k['lat'] || 0),
                lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                status: 'pending'
            };
        }).filter(i => i.lat !== 0);
        if (norm.length > 0) setTempStops(norm);
    };
    if(file.name.endsWith('.csv')) { reader.onload = e => processData(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = e => processData(e.target.result, true); reader.readAsBinaryString(file); }
  };

  const createRoute = () => {
      if(!newRouteName.trim() || !tempStops.length) return;
      setRoutes([{ id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops, optimized: false }, ...routes]);
      setNewRouteName(''); setTempStops([]); setView('home');
  };

  const handleReorder = (oldGroupIndex, newGroupIndex) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      
      const currentStops = [...routes[rIdx].stops];
      const groups = groupStopsByStopName(currentStops); 
      
      if(newGroupIndex < 0 || newGroupIndex >= groups.length || oldGroupIndex < 0 || oldGroupIndex >= groups.length) return;

      const movingGroup = groups[oldGroupIndex];
      const remainingStops = currentStops.filter(s => !movingGroup.items.some(i => i.id === s.id));
      const targetGroup = groups[newGroupIndex];
      
      let newStopsList = [];
      if (newGroupIndex > oldGroupIndex) {
           const targetLastIndex = remainingStops.reduce((last, curr, idx) => targetGroup.items.some(i => i.id === curr.id) ? idx : last, -1);
           newStopsList = [...remainingStops.slice(0, targetLastIndex + 1), ...movingGroup.items, ...remainingStops.slice(targetLastIndex + 1)];
      } else {
           const targetFirstIndex = remainingStops.findIndex(s => targetGroup.items.some(i => i.id === s.id));
           newStopsList = [...remainingStops.slice(0, targetFirstIndex), ...movingGroup.items, ...remainingStops.slice(targetFirstIndex)];
      }

      const updatedRoutes = [...routes];
      updatedRoutes[rIdx].stops = newStopsList;
      setRoutes(updatedRoutes);
      showToast("Sequência Alterada!");
  };

  const optimizeRoute = async () => {
      setIsOptimizing(true);
      let pos = userPos || await getCurrentLocation();
      if (!pos) { setIsOptimizing(false); return alert("Sem GPS!"); }

      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const currentRoute = routes[rIdx];
      const pending = currentRoute.stops.filter(s => s.status === 'pending');
      const done = currentRoute.stops.filter(s => s.status !== 'pending');
      
      const groups = groupStopsByStopName(pending);
      const locations = groups.map(g => ({ lat: g.lat, lng: g.lng, items: g.items }));
      
      try {
          const optimizedLocs = await optimizeRollingChain(locations, pos);
          const flatOptimized = optimizedLocs.flatMap(l => l.items);
          
          const updated = [...routes];
          updated[rIdx] = { ...updated[rIdx], stops: [...done, ...flatOptimized], optimized: true };
          setRoutes(updated);
          showToast("Otimizado com Google Maps!");
      } catch(e) { alert("Erro ao otimizar: " + e); }
      setIsOptimizing(false);
  };

  const setStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      const updatedRoutes = [...routes];
      const route = updatedRoutes[rIdx];
      const stopIndex = route.stops.findIndex(s => s.id === stopId);
      if (stopIndex !== -1) {
          route.stops[stopIndex].status = status;
          setRoutes(updatedRoutes);
          if (status === 'success') showToast("Entregue!");
      }
  };

  const openNav = (lat, lng) => {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const toggleGroup = (id) => setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));

  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');

  // --- ITEM 5: MÉTRICAS REAIS ---
  useEffect(() => {
      if (isLoaded && nextGroup && userPos) {
          const service = new window.google.maps.DirectionsService();
          service.route({
              origin: userPos,
              destination: { lat: nextGroup.lat, lng: nextGroup.lng },
              travelMode: 'DRIVING'
          }, (res, status) => {
              if (status === 'OK') {
                  setDirectionsResponse(res);
                  const leg = res.routes[0].legs[0];
                  if(leg) {
                      setRealMetrics({
                          dist: leg.distance.text,
                          time: leg.duration.text
                      });
                  }
              }
          });
      }
  }, [nextGroup?.id, userPos, isLoaded]);

  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <div className="flex justify-between items-center mb-8">
              <h1 className="text-3xl font-bold text-slate-900">Rotas</h1>
              <div className="bg-white p-2 rounded-full shadow-sm"><Package className="text-slate-400"/></div>
          </div>
          {routes.length === 0 ? <div className="text-center mt-32 opacity-40"><MapIcon size={48} className="mx-auto mb-4"/><p>Nenhuma rota</p></div> : 
              <div className="space-y-4">
                  {routes.map(r => (
                      <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="modern-card p-5 cursor-pointer mb-4">
                          <h3 className="font-bold text-lg">{safeStr(r.name)}</h3>
                          <div className="flex gap-4 text-sm text-slate-500 mt-2">
                              <span>{r.stops.length} vols</span>
                              {r.optimized && <span className="text-green-600 font-bold">Otimizada</span>}
                          </div>
                      </div>
                  ))}
              </div>
          }
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center"><Plus size={32}/></button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-white flex flex-col p-6">
          <button onClick={() => setView('home')} className="self-start mb-6"><ArrowLeft/></button>
          <h2 className="text-2xl font-bold mb-8">Nova Rota</h2>
          <div className="space-y-6 flex-1">
              <input type="text" className="w-full p-4 bg-slate-50 rounded-xl" placeholder="Nome" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
              <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl bg-slate-50">
                  <Upload className="mb-2 text-slate-400"/> <span className="text-sm font-bold text-slate-500">Importar</span>
                  <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/>
              </label>
              {tempStops.length > 0 && <div className="text-center text-green-600 font-bold">{tempStops.length} pacotes</div>}
          </div>
          <button onClick={createRoute} className="w-full bg-slate-900 text-white py-5 rounded-2xl font-bold">Salvar</button>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {toast && <div className={`fixed top-4 left-4 right-4 p-4 rounded-xl shadow-2xl z-50 text-white text-center font-bold text-sm toast-anim ${toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>{toast.msg}</div>}
          
          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-4 flex-1 text-center">{safeStr(activeRoute.name)}</h2>
                  <div className="flex gap-2">
                      <button onClick={() => setShowMap(!showMap)} className={`p-2 rounded-full ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'}`}>{showMap ? <List size={20}/> : <MapIcon size={20}/>}</button>
                      <button onClick={() => {if(confirm("Excluir?")) { setRoutes(routes.filter(r => r.id !== activeRoute.id)); setView('home'); }}}><Trash2 size={20} className="text-red-400"/></button>
                  </div>
              </div>
              
              {activeRoute.optimized && realMetrics && !showMap && (
                  <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4">
                      <div className="flex items-center gap-2"><MapIcon size={16} className="text-blue-500"/><span className="text-xs font-bold">{realMetrics.dist}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Clock size={16} className="text-orange-500"/><span className="text-xs font-bold">{realMetrics.time}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Box size={16} className="text-green-500"/><span className="text-xs font-bold">{activeRoute.stops.filter(s => s.status === 'pending').length} rest.</span></div>
                  </div>
              )}
              
              {!showMap && (
                  <div className="flex gap-3">
                      <button onClick={optimizeRoute} disabled={isOptimizing} className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition ${!activeRoute.optimized ? 'btn-highlight animate-pulse' : 'btn-secondary'}`}>
                          {isOptimizing ? <Loader2 className="animate-spin" size={18}/> : <Sliders size={18}/>} {isOptimizing ? '...' : 'Otimizar'}
                      </button>
                      {nextGroup && (
                          <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} disabled={!activeRoute.optimized} className={`flex-[1.5] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition ${activeRoute.optimized ? 'btn-highlight shadow-lg' : 'bg-slate-100 text-slate-300'}`}>
                              <Navigation size={18}/> Iniciar Rota
                          </button>
                      )}
                  </div>
              )}
          </div>

          {showMap ? (
              <div className="flex-1 relative bg-slate-100">
                  <MapView 
                      userPos={userPos} 
                      groupedStops={groupedStops} 
                      directionsResponse={directionsResponse}
                      nextGroup={nextGroup}
                      openNav={openNav}
                      isLoaded={isLoaded}
                  />
              </div>
          ) : (
              <RouteList 
                  groupedStops={groupedStops}
                  nextGroup={nextGroup}
                  activeRoute={activeRoute}
                  searchQuery={searchQuery}
                  expandedGroups={expandedGroups}
                  toggleGroup={toggleGroup} // Passando explicitamente aqui
                  setStatus={setStatus}
                  onReorder={handleReorder}
              />
          )}
      </div>
  );
}
"""
}

def run_command(cmd):
    try:
        subprocess.run(cmd, check=True, shell=True)
    except Exception as e:
        print(f"Erro comando: {cmd}")

def main():
    print(f"--- Iniciando Correção Crítica (V5) ---")
    if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)
    os.makedirs(CURRENT_BACKUP_PATH)
    
    # Backup
    for f in ["src/components/RouteList.jsx", "src/App.jsx"]:
        if os.path.exists(f): shutil.copy2(f, CURRENT_BACKUP_PATH)

    # Escrevendo arquivos
    for path, content in FILES_TO_WRITE.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Arquivo corrigido: {path}")

    # Commit
    run_command("git add .")
    run_command(f'git commit -m "HOTFIX v5: Correção ReferenceError toggleGroup - {TIMESTAMP}"')
    run_command("git push")

    # Limpeza
    os.remove(__file__)
    print("Correção aplicada com sucesso.")

if __name__ == "__main__":
    main()


