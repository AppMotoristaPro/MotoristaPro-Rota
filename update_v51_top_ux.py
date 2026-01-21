import os
import shutil
import subprocess

# --- CONFIGURAÇÕES ---
APP_NAME = "MotoristaPro-Rota"
GOOGLE_MAPS_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

files_content = {}

# 1. CSS (Animações e Estilos de Destaque)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;
@import 'maplibre-gl/dist/maplibre-gl.css';

body {
  margin: 0;
  font-family: 'Inter', sans-serif;
  background-color: #F8FAFC;
  color: #0F172A;
  -webkit-tap-highlight-color: transparent;
  padding-bottom: env(safe-area-inset-bottom);
}

.map-container { width: 100%; height: 100%; }

/* Card de Destaque (Próxima Parada) */
.highlight-card {
  background: white;
  border-radius: 20px;
  box-shadow: 0 10px 30px -5px rgba(37, 99, 235, 0.15); /* Sombra Azulada */
  border: 2px solid #3B82F6;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}

/* Card Normal */
.route-card {
  background: white;
  border-radius: 14px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.03);
  border: 1px solid #E2E8F0;
  transition: all 0.2s ease;
}
.route-card:active { transform: scale(0.98); }

/* Cores de Status */
.status-bar-pending { border-left: 5px solid #CBD5E1; }
.status-bar-success { border-left: 5px solid #10B981; opacity: 0.6; background: #F0FDF4; }
.status-bar-failed { border-left: 5px solid #EF4444; opacity: 0.6; background: #FEF2F2; }

/* Botões de Ação (Destaque) */
.btn-action-success {
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
  color: white;
  box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3);
}
.btn-action-fail {
  background: white;
  color: #EF4444;
  border: 2px solid #FEE2E2;
}

/* Animação de Loading (Overlay) */
.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(5px);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* Botão Otimizar Pulsante */
.btn-optimize-highlight {
  background: #0F172A;
  color: white;
  box-shadow: 0 0 0 0 rgba(15, 23, 42, 0.7);
  animation: pulse-black 2s infinite;
}
@keyframes pulse-black {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(15, 23, 42, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(15, 23, 42, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(15, 23, 42, 0); }
}
'''

# 2. APP.JSX (Lógica V51 Completa)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Edit3, Save, FileCheck
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v51_top_ux';
const GOOGLE_KEY = "__GOOGLE_KEY__";

// --- HELPERS ---
const safeStr = (val) => {
    if (!val) return '';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val).trim();
};

const getMarkerIcon = (status, isCurrent) => {
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    let color = "#3B82F6"; 
    if (status === 'success') color = "#10B981";
    if (status === 'failed') color = "#EF4444";
    if (status === 'partial') color = "#F59E0B";
    if (isCurrent) color = "#0F172A";

    return {
        path,
        fillColor: color,
        fillOpacity: 1,
        strokeWeight: 1.5,
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2.2 : 1.4,
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = { disableDefaultUI: true, zoomControl: false, clickableIcons: false };

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

const solveTSP = (stops, startPos) => {
    const points = [{ lat: startPos.lat, lng: startPos.lng, isStart: true }, ...stops];
    const n = points.length;
    const dist = (p1, p2) => Math.sqrt(Math.pow(p1.lat - p2.lat, 2) + Math.pow(p1.lng - p2.lng, 2));
    
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
    path.shift();
    return path.map(idx => points[idx]);
};

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); 
  const [newRouteName, setNewRouteName] = useState('');
  const [tempStops, setTempStops] = useState([]);
  const [userPos, setUserPos] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});
  
  // Estados de Processamento
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isImporting, setIsImporting] = useState(false); // Animação de Importação
  const [isEditing, setIsEditing] = useState(false);
  
  const [showMap, setShowMap] = useState(false);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [toast, setToast] = useState(null);

  const { isLoaded } = useJsApiLoader({ id: 'gmaps', googleMapsApiKey: GOOGLE_KEY });

  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) { localStorage.removeItem(DB_KEY); }
    getCurrentLocation();
  }, []);

  useEffect(() => { localStorage.setItem(DB_KEY, JSON.stringify(routes)); }, [routes]);

  const showToast = (msg) => {
      setToast(msg);
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
    
    setIsImporting(true); // Inicia Animação

    const reader = new FileReader();
    reader.onload = (evt) => {
        setTimeout(() => { // Delay artificial para mostrar a animação (UX)
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
                    showToast(`Sucesso! ${norm.length} pacotes identificados.`);
                }
            } catch(e) { alert("Erro ao ler arquivo."); }
            setIsImporting(false); // Para Animação
        }, 1500);
    };
    reader.readAsBinaryString(file);
  };

  const createRoute = () => {
      if(!newRouteName.trim() || !tempStops.length) return;
      setRoutes([{ id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops, optimized: false }, ...routes]);
      setNewRouteName(''); setTempStops([]); setView('home');
  };

  const optimizeRoute = async () => {
      setIsOptimizing(true);
      let startPos = userPos;
      if (!startPos) startPos = await getCurrentLocation();
      
      // Delay simulado para "trabalho pesado"
      setTimeout(() => {
        const rIdx = routes.findIndex(r => r.id === activeRouteId);
        if (rIdx === -1 || !startPos) { setIsOptimizing(false); return; }

        const currentRoute = routes[rIdx];
        const grouped = groupStops(currentRoute.stops);
        let pendingGroups = grouped.filter(g => g.status !== 'success' && g.status !== 'failed');
        let doneGroups = grouped.filter(g => g.status === 'success' || g.status === 'failed');

        const pointsToOptimize = pendingGroups.map(g => ({ lat: g.lat, lng: g.lng, group: g }));
        const optimizedPoints = solveTSP(pointsToOptimize, startPos);
        
        const finalStops = [];
        doneGroups.forEach(g => finalStops.push(...g.items));
        optimizedPoints.forEach(p => finalStops.push(...p.group.items));

        const updatedRoutes = [...routes];
        updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: finalStops, optimized: true };
        setRoutes(updatedRoutes);
        setIsOptimizing(false);
        showToast("Rota Otimizada!");
      }, 1000);
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
      const updated = [...routes];
      const sIdx = updated[rIdx].stops.findIndex(s => s.id === stopId);
      if (sIdx !== -1) {
          updated[rIdx].stops[sIdx].status = status;
          setRoutes(updated);
      }
  };

  const openNav = (lat, lng) => {
      const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
      window.open(url, '_system');
  };

  const toggleGroup = (id) => setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));

  // --- RENDER ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStops(activeRoute.stops) : [], [activeRoute]);
  
  // Encontrar PRÓXIMA PARADA (Destaque)
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');

  // Loading Overlay
  if (isImporting) return (
      <div className="loading-overlay">
          <Loader2 size={64} className="text-blue-600 animate-spin mb-4"/>
          <h2 className="text-xl font-bold text-slate-800">Analisando Planilha...</h2>
          <p className="text-slate-500">Organizando endereços</p>
      </div>
  );

  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <h1 className="text-3xl font-bold mb-8">Rotas</h1>
          {routes.map(r => (
              <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="route-card p-5 mb-4">
                  <h3 className="font-bold text-lg">{safeStr(r.name)}</h3>
                  <span className="text-sm text-gray-500">{r.stops.length} entregas</span>
              </div>
          ))}
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center"><Plus/></button>
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
          <button onClick={createRoute} className="w-full btn-primary py-4 rounded-xl font-bold">Salvar</button>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50">
          {toast && <div className="fixed top-5 left-5 right-5 bg-green-600 text-white p-4 rounded-xl shadow-xl z-50 text-center font-bold toast-anim">{toast}</div>}
          
          <div className="bg-white px-4 py-3 shadow-sm z-20">
              <div className="flex justify-between items-center mb-3">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-2">{safeStr(activeRoute.name)}</h2>
                  <button onClick={() => setShowMap(!showMap)} className="p-2 bg-slate-100 rounded-full">{showMap?<List/>:<MapIcon/>}</button>
              </div>

              {!showMap && (
                  <div className="flex gap-2">
                      {!isEditing ? (
                        <>
                           {/* BOTÃO OTIMIZAR PULSANTE SE NÃO OTIMIZADO */}
                           <button 
                                onClick={optimizeRoute} 
                                disabled={isOptimizing}
                                className={`flex-1 py-3 rounded-xl font-bold flex items-center justify-center gap-2 
                                ${!activeRoute.optimized ? 'btn-optimize-highlight' : 'bg-slate-100 text-slate-700'}`}
                           >
                                {isOptimizing ? <Loader2 className="animate-spin"/> : <Sliders size={18}/>} 
                                {isOptimizing ? 'Processando...' : 'Otimizar'}
                           </button>
                           <button onClick={() => setIsEditing(true)} className="flex-1 py-3 bg-slate-100 rounded-xl font-bold flex items-center justify-center gap-2"><Edit3 size={18}/> Editar</button>
                        </>
                      ) : (
                           <button onClick={() => setIsEditing(false)} className="w-full py-3 bg-green-600 text-white rounded-xl font-bold"><Save size={18}/> Salvar</button>
                      )}
                  </div>
              )}
          </div>

          <div className="flex-1 overflow-hidden relative">
              {showMap ? (
                   isLoaded && (
                      <GoogleMap
                          mapContainerStyle={{width:'100%', height:'100%'}}
                          center={userPos || {lat:-23.55, lng:-46.63}}
                          zoom={14}
                          options={mapOptions}
                      >
                          {groupedStops.map((g, i) => (
                              <MarkerF 
                                key={g.id} 
                                position={{lat:g.lat, lng:g.lng}} 
                                label={{text: String(i+1), color:'white', fontWeight:'bold'}}
                                icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id)}
                                onClick={() => setSelectedMarker(g)}
                              />
                          ))}
                          {selectedMarker && (
                              <InfoWindowF position={{lat:selectedMarker.lat, lng:selectedMarker.lng}} onCloseClick={() => setSelectedMarker(null)}>
                                  <div className="p-2 min-w-[200px]">
                                      <h3 className="font-bold text-sm mb-1">{selectedMarker.mainName}</h3>
                                      <p className="text-xs text-gray-500 mb-2">{selectedMarker.mainAddress}</p>
                                      <div className="font-bold text-blue-600 text-xs mb-3">{selectedMarker.items.length} pacotes</div>
                                      <button onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} className="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold">NAVEGAR</button>
                                  </div>
                              </InfoWindowF>
                          )}
                      </GoogleMap>
                   )
              ) : (
                  <div className="h-full overflow-y-auto px-4 pt-4 pb-32">
                      
                      {/* CARD DE DESTAQUE (PRÓXIMA PARADA) */}
                      {!isEditing && nextGroup && activeRoute.optimized && (
                          <div className="highlight-card p-5 mb-6">
                              <div className="flex justify-between items-start mb-4">
                                  <div>
                                      <div className="bg-blue-600 text-white text-[10px] font-bold px-2 py-1 rounded inline-block mb-1">PRÓXIMA PARADA</div>
                                      <h2 className="text-xl font-bold text-slate-800">{nextGroup.mainName}</h2>
                                      <p className="text-sm text-gray-500">{nextGroup.mainAddress}</p>
                                  </div>
                                  <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} className="bg-slate-100 p-3 rounded-full text-blue-600"><Navigation/></button>
                              </div>
                              
                              {/* Lista de Pacotes da Parada */}
                              <div className="space-y-3 border-t border-slate-100 pt-3">
                                  {nextGroup.items.map((item, idx) => {
                                      if (item.status !== 'pending') return null;
                                      return (
                                          <div key={item.id} className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                                              <div className="mb-3">
                                                  <span className="text-xs font-bold text-blue-600 block">PACOTE #{idx+1}</span>
                                                  <span className="text-sm font-bold text-slate-700">{item.address}</span>
                                              </div>
                                              <div className="flex gap-3">
                                                  <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 h-12 rounded-xl font-bold text-xs btn-action-fail flex items-center justify-center gap-2"><AlertTriangle size={16}/> NÃO ENTREGUE</button>
                                                  <button onClick={() => setStatus(item.id, 'success')} className="flex-[1.5] h-12 rounded-xl font-bold text-xs btn-action-success flex items-center justify-center gap-2 text-white"><Check size={18}/> ENTREGUE</button>
                                              </div>
                                          </div>
                                      )
                                  })}
                              </div>
                          </div>
                      )}

                      {isEditing ? (
                          <DragDropContext onDragEnd={onDragEnd}>
                              <Droppable droppableId="list">
                                  {(provided) => (
                                      <div {...provided.droppableProps} ref={provided.innerRef} className="space-y-3">
                                          {groupedStops.map((g, index) => (
                                              <Draggable key={g.id} draggableId={g.id} index={index}>
                                                  {(provided) => (
                                                      <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps} className="route-card p-4 flex gap-3 items-center bg-white shadow-sm">
                                                          <div className="text-gray-400 font-bold">#{index+1}</div>
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
                                  // Se já estiver no destaque, não mostra na lista (opcional, aqui mantemos tudo na lista abaixo para referencia)
                                  const isExpanded = expandedGroups[g.id];
                                  return (
                                      <div key={g.id} className={`route-card status-bar-${g.status} ${g.status!=='pending' ? 'opacity-60' : ''}`}>
                                          <div onClick={() => toggleGroup(g.id)} className="p-4 flex items-center gap-3 cursor-pointer">
                                              <div className="font-bold text-slate-500 text-sm">#{idx+1}</div>
                                              <div className="flex-1">
                                                  <h4 className="font-bold text-slate-800 text-sm">Parada: {g.mainName}</h4>
                                                  <p className="text-xs text-slate-500">{g.items.length} pacotes nesta parada</p>
                                              </div>
                                              {isExpanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>}
                                          </div>
                                          {isExpanded && (
                                              <div className="bg-slate-50 border-t px-4 py-2 space-y-2">
                                                  {g.items.map((item, subIdx) => (
                                                      <div key={item.id} className="flex justify-between items-center py-2 border-b last:border-0">
                                                          <div><span className="text-[10px] font-bold text-blue-500">PACOTE #{subIdx+1}</span><div className="text-sm font-bold text-slate-700">{item.address}</div></div>
                                                          {item.status !== 'pending' && <span className="text-xs font-bold text-slate-400">{item.status.toUpperCase()}</span>}
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
      </div>
  );
}
'''

def main():
    print(f"🚀 ATUALIZAÇÃO V51 (TOP TIER UX) - {APP_NAME}")
    
    final_app_jsx = files_content['src/App.jsx'].replace("__GOOGLE_KEY__", GOOGLE_MAPS_KEY)
    
    print("\n📝 Atualizando arquivos...")
    with open("src/App.jsx", 'w', encoding='utf-8') as f:
        f.write(final_app_jsx)
        
    with open("src/index.css", 'w', encoding='utf-8') as f:
        f.write(files_content['src/index.css'])

    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "feat: V51 Animation, Highlight Card, Import UX"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


