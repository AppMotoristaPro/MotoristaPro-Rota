import os
import shutil
import subprocess

# --- CONFIGURAÇÕES ---
APP_NAME = "MotoristaPro-Rota"
GOOGLE_MAPS_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

files_content = {}

# 1. CSS (Layout Limpo + Botão Fixo Inferior)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;
@import 'maplibre-gl/dist/maplibre-gl.css';

body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: #F1F5F9; /* Cinza de fundo mais profissional */
  color: #0F172A;
  -webkit-tap-highlight-color: transparent;
  padding-bottom: env(safe-area-inset-bottom);
}

/* Container do Mapa */
.map-container { width: 100%; height: 100%; }

/* Card Estilo Clássico (Limpo) */
.route-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  border: 1px solid #E2E8F0;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}
.route-card:active { transform: scale(0.99); background-color: #F8FAFC; }

/* Status Lateral */
.status-bar-pending { border-left: 5px solid #3B82F6; }
.status-bar-success { border-left: 5px solid #10B981; background-color: #F0FDF4; }
.status-bar-failed { border-left: 5px solid #EF4444; background-color: #FEF2F2; }
.status-bar-partial { border-left: 5px solid #F59E0B; background-color: #FFFBEB; }

/* Botão Fixo Inferior (Floating Action) */
.bottom-action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  padding: 16px;
  padding-bottom: max(16px, env(safe-area-inset-bottom));
  box-shadow: 0 -4px 20px rgba(0,0,0,0.08);
  z-index: 50;
  display: flex;
  gap: 10px;
}

.btn-primary {
  background: #2563EB;
  color: white;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}
.btn-secondary {
  background: #F8FAFC;
  color: #475569;
  border: 1px solid #E2E8F0;
  font-weight: 600;
}

/* Toast */
.toast-anim { animation: slideDown 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
@keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
'''

# 2. APP.JSX (Lógica V50)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Edit3, Save
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v50_classic';
const GOOGLE_KEY = "__GOOGLE_KEY__";

// --- HELPERS ---
const safeStr = (val) => {
    if (!val) return '';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val).trim();
};

const getMarkerIcon = (status, isCurrent) => {
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    let color = "#3B82F6"; // Azul
    if (status === 'success') color = "#10B981";
    if (status === 'failed') color = "#EF4444";
    if (status === 'partial') color = "#F59E0B";
    if (isCurrent) color = "#0F172A"; // Preto

    return {
        path,
        fillColor: color,
        fillOpacity: 1,
        strokeWeight: 1.5,
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2 : 1.4,
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = { disableDefaultUI: true, zoomControl: false, clickableIcons: false };

// --- LOGICA DE GRUPO ---
const groupStops = (stops) => {
    if (!stops) return [];
    const groupsMap = new Map();
    stops.forEach(s => {
        const key = safeStr(s.stopName).toLowerCase() || 'sem_nome';
        if (!groupsMap.has(key)) {
            groupsMap.set(key, {
                id: key,
                lat: s.lat,
                lng: s.lng,
                mainName: s.stopName,
                mainAddress: s.address,
                items: [],
                status: 'pending'
            });
        }
        groupsMap.get(key).items.push(s);
    });

    return Array.from(groupsMap.values()).map(g => {
        const total = g.items.length;
        const success = g.items.filter(i => i.status === 'success').length;
        const failed = g.items.filter(i => i.status === 'failed').length;
        if (success === total) g.status = 'success';
        else if (failed === total) g.status = 'failed';
        else if (success + failed > 0) g.status = 'partial';
        else g.status = 'pending';
        return g;
    });
};

// --- OTIMIZAÇÃO (2-OPT REFINADO) ---
const solveTSP = (stops, startPos) => {
    // Adiciona start como ponto fixo
    const points = [{ lat: startPos.lat, lng: startPos.lng, isStart: true }, ...stops];
    const n = points.length;
    const dist = (p1, p2) => Math.sqrt(Math.pow(p1.lat - p2.lat, 2) + Math.pow(p1.lng - p2.lng, 2));
    
    // 1. Nearest Neighbor
    let path = [0];
    let visited = new Set([0]);
    while (path.length < n) {
        let last = points[path[path.length - 1]];
        let bestDist = Infinity, bestIdx = -1;
        for (let i = 1; i < n; i++) {
            if (!visited.has(i)) {
                let d = dist(last, points[i]);
                if (d < bestDist) { bestDist = d; bestIdx = i; }
            }
        }
        path.push(bestIdx);
        visited.add(bestIdx);
    }
    
    // 2. 2-Opt (Mais iterações para evitar voltas)
    let improved = true;
    let iterations = 0;
    while (improved && iterations < 3000) { 
        improved = false;
        iterations++;
        for (let i = 1; i < n - 2; i++) { 
            for (let j = i + 1; j < n; j++) {
                if (j - i === 1) continue;
                const d1 = dist(points[path[i-1]], points[path[i]]) + dist(points[path[j-1]], points[path[j]]);
                const d2 = dist(points[path[i-1]], points[path[j-1]]) + dist(points[path[i]], points[path[j]]);
                if (d2 < d1) {
                    const newSeg = path.slice(i, j).reverse();
                    path.splice(i, j - i, ...newSeg);
                    improved = true;
                }
            }
        }
    }
    path.shift(); // Remove start
    return path.map(idx => points[idx]);
};

const calculateMetrics = (stops, userPos) => {
    if (!stops.length) return { km: "0", time: "0h 0m", remainingPackages: 0 };
    const pending = stops.filter(s => s.status === 'pending');
    if (!pending.length) return { km: "0", time: "Finalizado", remainingPackages: 0 };

    let km = 0;
    let lat = userPos ? userPos.lat : pending[0].lat;
    let lng = userPos ? userPos.lng : pending[0].lng;
    
    const deg2rad = (deg) => deg * (Math.PI/180);
    const getD = (lat2,lon2) => {
        const R = 6371; 
        const dLat = deg2rad(lat2-lat);
        const dLon = deg2rad(lon2-lng); 
        const a = Math.sin(dLat/2)**2 + Math.cos(deg2rad(lat)) * Math.cos(deg2rad(lat2)) * Math.sin(dLon/2)**2; 
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    };

    pending.forEach(s => { km += getD(s.lat, s.lng); lat = s.lat; lng = s.lng; });
    const realKm = km * 1.5;
    const min = (realKm/25*60) + (pending.length * 1.5);
    
    return { 
        km: realKm.toFixed(1), 
        time: `${Math.floor(min/60)}h ${Math.floor(min%60)}m`,
        remainingPackages: pending.length
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
  const [isEditing, setIsEditing] = useState(false);
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [directions, setDirections] = useState(null);
  
  // Estado para modal de partida
  const [showStartModal, setShowStartModal] = useState(false);

  const { isLoaded } = useJsApiLoader({ id: 'gmaps', googleMapsApiKey: GOOGLE_KEY });

  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) { localStorage.removeItem(DB_KEY); }
    getCurrentLocation();
  }, []);

  useEffect(() => { localStorage.setItem(DB_KEY, JSON.stringify(routes)); }, [routes]);

  const showToast = (msg, type = 'success') => {
      setToast({ msg, type });
      setTimeout(() => setToast(null), 3000);
  };

  const getCurrentLocation = async () => {
      try {
          await Geolocation.requestPermissions();
          const pos = await Geolocation.getCurrentPosition();
          setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude });
          return { lat: pos.coords.latitude, lng: pos.coords.longitude };
      } catch (e) { return null; }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
        try {
            const wb = XLSX.read(evt.target.result, {type:'binary'});
            const data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
            const norm = data.map((r, i) => {
                const k = {};
                Object.keys(r).forEach(key => k[String(key).trim().toLowerCase()] = r[key]);
                return {
                    id: Date.now() + i + Math.random(),
                    stopName: safeStr(k['stop'] || k['parada'] || `Parada ${i+1}`),
                    recipient: safeStr(k['recebedor'] || k['cliente'] || 'Recebedor'),
                    address: safeStr(k['destination address'] || k['endereço'] || '---'),
                    lat: parseFloat(k['latitude'] || k['lat'] || 0),
                    lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                    status: 'pending'
                };
            }).filter(i => i.lat !== 0);
            if(norm.length) {
                setTempStops(norm);
                // Mensagem de Sucesso
                const stopsCount = new Set(norm.map(s => s.stopName)).size;
                showToast(`Sucesso! ${norm.length} pacotes em ${stopsCount} paradas.`, 'success');
            }
        } catch(e) { alert("Erro arquivo."); }
    };
    reader.readAsBinaryString(file);
  };

  const createRoute = () => {
      if(!newRouteName.trim() || !tempStops.length) return;
      setRoutes([{ id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops, optimized: false }, ...routes]);
      setNewRouteName(''); setTempStops([]); setView('home');
  };

  const deleteRoute = (id) => {
      if(confirm("Excluir rota?")) {
          setRoutes(routes.filter(r => r.id !== id));
          if(activeRouteId === id) setView('home');
      }
  };

  const optimizeRoute = (startPos) => {
      setIsOptimizing(true);
      setShowStartModal(false);
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      const currentRoute = routes[rIdx];
      const grouped = groupStops(currentRoute.stops);
      let pendingGroups = grouped.filter(g => g.status !== 'success' && g.status !== 'failed');
      let doneGroups = grouped.filter(g => g.status === 'success' || g.status === 'failed');

      // Otimiza grupos (locais) e não pacotes individuais
      // Transforma grupos em pontos para o TSP
      const pointsToOptimize = pendingGroups.map(g => ({ lat: g.lat, lng: g.lng, group: g }));
      
      const optimizedPoints = solveTSP(pointsToOptimize, startPos);
      
      // Desagrupa de volta para stops
      const finalStops = [];
      // Mantém os já feitos no topo? Ou reordena tudo? 
      // Geralmente mantemos o histórico.
      doneGroups.forEach(g => finalStops.push(...g.items));
      optimizedPoints.forEach(p => finalStops.push(...p.group.items));

      const updatedRoutes = [...routes];
      updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: finalStops, optimized: true };
      setRoutes(updatedRoutes);
      setIsOptimizing(false);
      showToast("Rota Reorganizada!");
  };

  const confirmGpsStart = async () => {
      let pos = userPos;
      if (!pos) pos = await getCurrentLocation();
      if (pos) optimizeRoute(pos);
      else alert("GPS indisponível.");
  };

  const onDragEnd = (result) => {
      if (!result.destination) return;
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const currentRoute = routes[rIdx];
      const grouped = groupStops(currentRoute.stops);
      const [reorderedGroup] = grouped.splice(result.source.index, 1);
      grouped.splice(result.destination.index, 0, reorderedGroup);
      const newStops = [];
      grouped.forEach(g => newStops.push(...g.items));
      const updatedRoutes = [...routes];
      updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: newStops };
      setRoutes(updatedRoutes);
  };

  const setStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      const updated = [...routes];
      const sIdx = updated[rIdx].stops.findIndex(s => s.id === stopId);
      if (sIdx !== -1) {
          updated[rIdx].stops[sIdx].status = status;
          setRoutes(updated);
          if(status === 'success') showToast("Entrega OK!");
      }
  };

  const openNav = (lat, lng) => {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const toggleGroup = (id) => setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));

  // --- RENDER ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStops(activeRoute.stops) : [], [activeRoute]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');
  
  const filteredGroups = useMemo(() => {
      if (!searchQuery) return groupedStops;
      const lower = searchQuery.toLowerCase();
      return groupedStops.filter(g => 
          safeStr(g.mainName).toLowerCase().includes(lower) || 
          safeStr(g.mainAddress).toLowerCase().includes(lower)
      );
  }, [groupedStops, searchQuery]);

  const metrics = useMemo(() => activeRoute ? calculateMetrics(activeRoute.stops, userPos) : {}, [activeRoute, userPos]);

  useEffect(() => {
      if (isLoaded && activeRoute && userPos && nextGroup) {
          const service = new window.google.maps.DirectionsService();
          service.route({
              origin: userPos,
              destination: { lat: nextGroup.lat, lng: nextGroup.lng },
              travelMode: 'DRIVING'
          }, (res, status) => { if (status === 'OK') setDirections(res); });
      }
  }, [nextGroup?.id, userPos, isLoaded]);

  if (view === 'home') return (
      <div className="min-h-screen px-6 pt-10 pb-32">
          <h1 className="text-3xl font-bold mb-8">Rotas</h1>
          {routes.length === 0 ? <div className="text-center mt-32 opacity-40"><MapPin size={48} className="mx-auto mb-4"/><p>Sem rotas</p></div> : 
              <div className="space-y-4">
                  {routes.map(r => (
                      <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="route-card p-5 cursor-pointer">
                          <h3 className="font-bold text-lg">{safeStr(r.name)}</h3>
                          <div className="flex gap-4 text-sm text-slate-500 mt-2">
                              <span><Package size={14} className="inline mr-1"/>{r.stops.length} vols</span>
                              {r.optimized && <span className="text-green-600 font-bold"><Check size={14} className="inline mr-1"/>Otimizada</span>}
                          </div>
                      </div>
                  ))}
              </div>
          }
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full bg-blue-600 text-white shadow-xl flex items-center justify-center"><Plus/></button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-white p-6">
          <button onClick={() => setView('home')} className="mb-6"><ArrowLeft/></button>
          <h2 className="text-2xl font-bold mb-6">Nova Rota</h2>
          <input className="w-full p-4 bg-slate-50 rounded-xl mb-4" placeholder="Nome" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
          <label className="block w-full p-8 border-2 border-dashed rounded-xl text-center bg-slate-50 mb-4">
              Importar <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/>
          </label>
          <button onClick={createRoute} className="w-full btn-primary py-4 rounded-xl">Salvar</button>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {toast && <div className={`fixed top-4 left-4 right-4 p-4 rounded-xl shadow-2xl z-[3000] text-white text-center font-bold text-sm toast-anim ${toast.type === 'success' ? 'bg-green-600' : 'bg-slate-800'}`}>{toast.msg}</div>}
          
          {showStartModal && (
              <div className="absolute inset-0 bg-black/60 z-[3000] flex items-center justify-center p-4">
                  <div className="bg-white w-full max-w-sm rounded-2xl p-6 shadow-2xl space-y-4">
                      <h3 className="text-xl font-bold">Otimizar Rota</h3>
                      <button onClick={confirmGpsStart} className="w-full p-4 border rounded-xl flex items-center gap-3"><Crosshair className="text-blue-600"/><span className="font-bold">Usar Meu GPS</span></button>
                      <button onClick={() => setShowStartModal(false)} className="w-full text-slate-400">Cancelar</button>
                  </div>
              </div>
          )}

          <div className="bg-white px-5 py-4 shadow-sm z-20">
              <div className="flex justify-between items-center mb-3">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-2">{safeStr(activeRoute.name)}</h2>
                  <div className="flex gap-2">
                    <button onClick={() => setShowMap(!showMap)} className={`p-2 rounded-full ${showMap?'bg-blue-100':'bg-slate-100'}`}>{showMap?<List/>:<MapIcon/>}</button>
                    <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 className="text-red-400"/></button>
                  </div>
              </div>
              
              {!showMap && (
                  <div className="flex gap-2 mb-2">
                      {!isEditing ? (
                        <>
                           <button onClick={() => setShowStartModal(true)} className="flex-1 py-2 bg-slate-100 rounded-lg text-sm font-bold flex items-center justify-center gap-2 text-slate-700">
                                {isOptimizing ? <Loader2 className="animate-spin"/> : <Sliders size={16}/>} Otimizar
                           </button>
                           <button onClick={() => setIsEditing(true)} className="flex-1 py-2 bg-slate-100 rounded-lg text-sm font-bold flex items-center justify-center gap-2 text-slate-700">
                                <Edit3 size={16}/> Editar Ordem
                           </button>
                        </>
                      ) : (
                           <button onClick={() => setIsEditing(false)} className="w-full py-2 bg-green-600 text-white rounded-lg font-bold flex items-center justify-center gap-2">
                                <Save size={16}/> Salvar Ordem
                           </button>
                      )}
                  </div>
              )}
              
              {!showMap && activeRoute.optimized && (
                  <div className="flex justify-between bg-slate-50 p-2 rounded-lg border text-xs font-bold text-slate-600">
                      <div className="flex items-center gap-1"><MapIcon size={12} className="text-blue-500"/> {metrics.km} km</div>
                      <div className="flex items-center gap-1"><Clock size={12} className="text-orange-500"/> {metrics.time}</div>
                      <div className="flex items-center gap-1"><Box size={12} className="text-green-500"/> {metrics.remainingPackages} rest.</div>
                  </div>
              )}
          </div>

          <div className="flex-1 overflow-hidden relative">
              {showMap ? (
                   isLoaded ? (
                      <GoogleMap
                          mapContainerStyle={mapContainerStyle}
                          center={userPos || {lat:-23.55, lng:-46.63}}
                          zoom={14}
                          options={mapOptions}
                      >
                          {directions && <DirectionsRenderer directions={directions} options={{suppressMarkers:true, polylineOptions:{strokeColor:"#2563EB", strokeWeight:5}}}/>}
                          {groupedStops.map((g, i) => (
                              <MarkerF 
                                key={g.id} position={{lat:g.lat, lng:g.lng}} 
                                label={{text: String(i+1), color:'white', fontWeight:'bold'}}
                                icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id)}
                                onClick={() => setSelectedMarker(g)}
                              />
                          ))}
                          {selectedMarker && (
                              <InfoWindowF position={{lat:selectedMarker.lat, lng:selectedMarker.lng}} onCloseClick={() => setSelectedMarker(null)}>
                                  <div className="p-2">
                                      <h3 className="font-bold text-sm">{selectedMarker.mainName}</h3>
                                      <button onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} className="mt-2 w-full bg-blue-600 text-white py-1 rounded text-xs">Navegar</button>
                                  </div>
                              </InfoWindowF>
                          )}
                      </GoogleMap>
                   ) : <Loader2 className="animate-spin m-auto"/>
              ) : (
                  <div className="h-full overflow-y-auto px-4 pt-4 pb-32">
                      {isEditing ? (
                          <DragDropContext onDragEnd={onDragEnd}>
                              <Droppable droppableId="list">
                                  {(provided) => (
                                      <div {...provided.droppableProps} ref={provided.innerRef} className="space-y-3">
                                          {groupedStops.map((g, idx) => (
                                              <Draggable key={g.id} draggableId={g.id} index={idx}>
                                                  {(provided) => (
                                                      <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps} className="route-card p-4 flex gap-3 items-center bg-white shadow-sm">
                                                          <div className="text-gray-400 font-bold">#{idx+1}</div>
                                                          <div className="flex-1"><h4 className="font-bold text-sm">{g.mainName}</h4></div>
                                                          <List className="text-gray-300"/>
                                                      </div>
                                                  )}
                                              </Draggable>
                                          ))}
                                          {provided.placeholder}
                                      </div>
                                  )}
                              </Droppable>
                          </DragDropContext>
                      ) : (
                          <div className="space-y-3">
                              {groupedStops.map((g, idx) => {
                                  const isExpanded = expandedGroups[g.id];
                                  return (
                                      <div key={g.id} className={`route-card status-bar-${g.status} ${g.status!=='pending' ? 'opacity-60' : ''}`}>
                                          <div onClick={() => toggleGroup(g.id)} className="p-4 flex items-center gap-3 cursor-pointer">
                                              <div className="font-bold text-slate-500 text-sm">#{idx+1}</div>
                                              <div className="flex-1">
                                                  <h4 className="font-bold text-slate-800 text-sm">Parada: {g.mainName}</h4>
                                                  <p className="text-xs text-slate-500">{g.items.length} pacotes a serem entregues nessa parada</p>
                                              </div>
                                              {isExpanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>}
                                          </div>
                                          {isExpanded && (
                                              <div className="bg-slate-50 border-t px-4 py-2 space-y-2">
                                                  {g.items.map(item => (
                                                      <div key={item.id} className="flex justify-between items-center py-2 border-b last:border-0">
                                                          <div>
                                                              <span className="text-[10px] font-bold text-blue-500">ENDEREÇO</span>
                                                              <div className="text-sm font-bold text-slate-700">{item.address}</div>
                                                          </div>
                                                          {item.status === 'pending' ? (
                                                              <div className="flex gap-2">
                                                                  <button onClick={() => setStatus(item.id, 'failed')} className="p-2 border border-red-200 text-red-500 rounded"><AlertTriangle size={14}/></button>
                                                                  <button onClick={() => setStatus(item.id, 'success')} className="p-2 bg-green-500 text-white rounded"><Check size={14}/></button>
                                                              </div>
                                                          ) : <span className="text-xs font-bold text-slate-400">{item.status.toUpperCase()}</span>}
                                                      </div>
                                                  ))}
                                              </div>
                                          )}
                                      </div>
                                  )
                              })}
                          </div>
                      )}
                  </div>
              )}
          </div>

          {/* BOTÃO FIXO DE NAVEGAÇÃO (Só aparece se tiver rota pendente) */}
          {!isEditing && !showMap && nextGroup && (
              <div className="bottom-action-bar">
                   <button 
                      onClick={() => openNav(nextGroup.lat, nextGroup.lng)} 
                      className="flex-1 btn-primary py-4 rounded-xl flex items-center justify-center gap-2 text-lg shadow-xl"
                   >
                      <Navigation size={24}/> Iniciar Rota
                   </button>
              </div>
          )}
      </div>
  );
}
'''

def main():
    print(f"🚀 ATUALIZAÇÃO V50 (LAYOUT CLÁSSICO) - {APP_NAME}")
    final_app_jsx = files_content['src/App.jsx'].replace("__GOOGLE_KEY__", GOOGLE_MAPS_KEY)
    
    print("\n📝 Atualizando arquivos...")
    with open("src/App.jsx", 'w', encoding='utf-8') as f:
        f.write(final_app_jsx)
        
    with open("src/index.css", 'w', encoding='utf-8') as f:
        f.write(files_content['src/index.css'])

    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "feat: V50 Classic Layout Restored, Fixed Action Bar & Import Toast"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


