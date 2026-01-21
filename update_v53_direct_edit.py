import os
import shutil
import subprocess

# --- CONFIGURAÇÕES ---
APP_NAME = "MotoristaPro-Rota"
GOOGLE_MAPS_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

files_content = {}

# 1. APP.JSX (Lógica V53 Completa)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Edit3, Save, Zap
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v53_direct';
const GOOGLE_KEY = "__GOOGLE_KEY__";

// --- HELPERS ---
const safeStr = (val) => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val).trim();
};

const getMarkerIcon = (status, isCurrent, isEditing) => {
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    
    let fillColor = "#3B82F6"; // Azul (Pendente)
    
    // ITEM 6: Lógica de Cor (Verde se concluído)
    if (status === 'success') fillColor = "#10B981"; 
    if (status === 'failed') fillColor = "#EF4444"; 
    if (status === 'partial') fillColor = "#F59E0B";
    
    if (isCurrent) fillColor = "#0F172A"; // Preto (Foco atual)
    if (isEditing) fillColor = "#7C3AED"; // Roxo (Modo Edição)

    return {
        path: path,
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 1.5,
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2.2 : 1.6, 
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = { disableDefaultUI: true, zoomControl: false, clickableIcons: false, styles: [{ featureType: "poi", stylers: [{ visibility: "off" }] }] };

const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    stops.forEach(stop => {
        const rawName = stop.stopName ? String(stop.stopName) : 'Local Sem Nome';
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

    const orderedGroups = [];
    const seenKeys = new Set();
    stops.forEach(stop => {
        const rawName = stop.stopName ? String(stop.stopName) : 'Local Sem Nome';
        const key = rawName.trim().toLowerCase();
        if (!seenKeys.has(key)) {
            const g = groups[key];
            const total = g.items.length;
            const success = g.items.filter(i => i.status === 'success').length;
            const failed = g.items.filter(i => i.status === 'failed').length;
            if (success === total) g.status = 'success';
            else if (failed === total) g.status = 'failed';
            else if (success + failed > 0) g.status = 'partial';
            else g.status = 'pending';
            orderedGroups.push(g);
            seenKeys.add(key);
        }
    });
    return orderedGroups;
};

// Algoritmo 2-Opt
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
    while (improved && iterations < 1500) { 
        improved = false;
        iterations++;
        for (let i = 1; i < n - 2; i++) { 
            for (let j = i + 1; j < n; j++) {
                if (j - i === 1) continue;
                const pA = points[path[i-1]], pB = points[path[i]], pC = points[path[j-1]], pD = points[path[j]];
                if (dist(pA, pC) + dist(pB, pD) < dist(pA, pB) + dist(pC, pD)) {
                    path.splice(i, j - i, ...path.slice(i, j).reverse());
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
  const [isProcessing, setIsProcessing] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [toast, setToast] = useState(null);
  const [showMap, setShowMap] = useState(false);
  const [isEditingMap, setIsEditingMap] = useState(false);
  const [selectedMarker, setSelectedMarker] = useState(null);

  const { isLoaded } = useJsApiLoader({ id: 'gmaps', googleMapsApiKey: GOOGLE_KEY });
  const [mapInstance, setMapInstance] = useState(null);

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
      setTimeout(() => setToast(null), 2500);
  };

  const getCurrentLocation = async () => {
      try {
          await Geolocation.requestPermissions();
          const pos = await Geolocation.getCurrentPosition();
          const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserPos(coords);
          return coords;
      } catch (e) { return null; }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setIsProcessing(true);
    const reader = new FileReader();
    reader.onload = (evt) => {
        setTimeout(() => {
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
                    showToast(`Sucesso! ${norm.length} pacotes encontrados.`);
                }
            } catch(e) { alert("Erro arquivo."); }
            setIsProcessing(false);
        }, 1000);
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

  // --- OTIMIZAÇÃO AUTO ---
  const runOptimization = async () => {
      setIsOptimizing(true);
      const start = userPos || (await getCurrentLocation());
      
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1 || !start) { setIsOptimizing(false); return; }

      setTimeout(() => {
          const currentRoute = routes[rIdx];
          const grouped = groupStopsByStopName(currentRoute.stops);
          let pendingGroups = grouped.filter(g => g.status !== 'success' && g.status !== 'failed');
          let doneGroups = grouped.filter(g => g.status === 'success' || g.status === 'failed');

          const pointsToOptimize = pendingGroups.map(g => ({ lat: g.lat, lng: g.lng, group: g }));
          const optimizedPoints = solveTSP(pointsToOptimize, start);
          
          const finalStops = [];
          doneGroups.forEach(g => finalStops.push(...g.items));
          optimizedPoints.forEach(p => finalStops.push(...p.group.items));

          const updatedRoutes = [...routes];
          updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: finalStops, optimized: true };
          setRoutes(updatedRoutes);
          setIsOptimizing(false);
          showToast("Rota Otimizada!");
      }, 500);
  };

  // --- ITEM 5: REORDENAÇÃO NUMÉRICA DIRETA ---
  const handleMarkerEdit = (group, currentIdx) => {
      const newIndexStr = prompt(`Mover "${group.mainName}" para qual posição? (1 - ${groupedStops.length})`, String(currentIdx + 1));
      if (newIndexStr === null) return;
      
      const newIndex = parseInt(newIndexStr) - 1; // 0-based
      if (isNaN(newIndex) || newIndex < 0 || newIndex >= groupedStops.length) {
          return alert("Número inválido.");
      }

      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const currentRoute = routes[rIdx];
      const allGroups = groupStopsByStopName(currentRoute.stops);
      
      // Remove do índice antigo e insere no novo
      const [movedGroup] = allGroups.splice(currentIdx, 1);
      allGroups.splice(newIndex, 0, movedGroup);
      
      // Reconstrói lista plana
      const newStops = [];
      allGroups.forEach(g => newStops.push(...g.items));
      
      const updatedRoutes = [...routes];
      updatedRoutes[rIdx].stops = newStops;
      setRoutes(updatedRoutes);
      showToast(`Movido para posição ${newIndex + 1}`);
  };

  const handleDelivery = (item, status, isBulk = false) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const updatedRoutes = [...routes];
      const route = updatedRoutes[rIdx];
      
      if (isBulk) {
          route.stops.forEach(s => {
              if (s.stopName === item.stopName && s.status === 'pending') s.status = status;
          });
      } else {
          const idx = route.stops.findIndex(s => s.id === item.id);
          if (idx !== -1) route.stops[idx].status = status;
      }
      
      setRoutes(updatedRoutes);
      showToast(status === 'success' ? "Entregue!" : "Ocorrência", status === 'success' ? 'success' : 'error');

      // Auto-reotimizar se acabou o grupo
      const remainingInGroup = route.stops.filter(s => s.stopName === item.stopName && s.status === 'pending');
      if (remainingInGroup.length === 0 && route.optimized) {
          runOptimization();
      }
  };

  const handleDeliveryClick = (item, groupItems) => {
      const pending = groupItems.filter(i => i.status === 'pending');
      if (pending.length > 1) {
          if (confirm(`Baixar todos os ${pending.length} pacotes deste local?`)) handleDelivery(item, 'success', true);
          else handleDelivery(item, 'success', false);
      } else {
          handleDelivery(item, 'success', false);
      }
  };

  const openNav = (lat, lng) => {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const toggleGroup = (id) => setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));

  // --- RENDER ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');

  useEffect(() => {
      if (showMap && isLoaded && mapInstance && nextGroup) {
          mapInstance.panTo({ lat: nextGroup.lat, lng: nextGroup.lng });
          mapInstance.setZoom(16);
      }
  }, [nextGroup, showMap, isLoaded, mapInstance]);

  // Loading
  if (isProcessing) return <div className="fixed inset-0 bg-white/90 z-50 flex flex-col items-center justify-center"><Loader2 size={48} className="animate-spin text-blue-600"/><p className="font-bold mt-2">Processando...</p></div>;

  // HOME
  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <h1 className="text-3xl font-bold text-slate-900 mb-8">Rotas</h1>
          {routes.map(r => (
              <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="enterprise-card p-5 mb-4 cursor-pointer">
                  <h3 className="font-bold text-lg">{safeStr(r.name)}</h3>
                  <div className="flex justify-between mt-2 text-sm text-slate-500">
                     <span>{r.stops.length} pacotes</span>
                     {r.optimized && <span className="text-green-600 font-bold flex gap-1"><Zap size={14}/> Otimizada</span>}
                  </div>
              </div>
          ))}
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full bg-slate-900 text-white shadow-2xl flex items-center justify-center"><Plus size={32}/></button>
      </div>
  );

  // CREATE (ITEM 1: NOME OBRIGATÓRIO)
  if (view === 'create') return (
      <div className="min-h-screen bg-white p-6 flex flex-col">
          <button onClick={() => setView('home')} className="mb-6"><ArrowLeft/></button>
          <h2 className="text-3xl font-bold mb-8">Nova Rota</h2>
          <input className="w-full p-5 bg-slate-50 rounded-2xl text-lg mb-6 outline-none focus:ring-2 focus:ring-blue-500" placeholder="Nome da Rota (Obrigatório)" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
          
          <label className={`flex-1 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center text-slate-400 ${!newRouteName ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer border-slate-300'}`}>
              <Upload size={32} className="mb-2"/> <span className="font-bold">Toque para importar</span>
              <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx" disabled={!newRouteName}/>
          </label>
          {!newRouteName && <p className="text-center text-red-400 text-sm mt-2">Digite o nome para liberar a importação</p>}
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {toast && <div className={`fixed top-6 left-6 right-6 p-4 rounded-xl shadow-2xl z-[9999] text-white text-center font-bold text-sm toast-anim ${toast.type==='success'?'bg-slate-900':'bg-red-600'}`}>{toast.msg}</div>}

          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex justify-between items-center mb-3">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-4">{safeStr(activeRoute.name)}</h2>
                  <button onClick={() => { setShowMap(!showMap); setIsEditingMap(false); }} className={`p-2 rounded-full ${showMap?'bg-blue-100 text-blue-600':'bg-slate-100 text-slate-600'}`}>{showMap?<List/>:<MapIcon/>}</button>
              </div>

              {!showMap && (
                  <div className="flex gap-2">
                      {!isEditingMap ? (
                        <>
                           <button onClick={() => runOptimization()} disabled={isOptimizing} className={`flex-1 py-3 rounded-xl font-bold flex items-center justify-center gap-2 ${!activeRoute.optimized?'btn-optimize-highlight':'bg-slate-100 text-slate-600'}`}>
                                {isOptimizing ? <Loader2 className="animate-spin"/> : <Zap size={18} fill={activeRoute.optimized?"none":"white"}/>} {isOptimizing ? '...' : 'Otimizar'}
                           </button>
                           <button onClick={() => { setShowMap(true); setIsEditingMap(true); showToast("Toque num pino para mudar o número", "info"); }} className="flex-1 py-3 bg-slate-100 text-slate-600 rounded-xl font-bold flex items-center justify-center gap-2"><Edit3 size={18}/> Editar Ordem</button>
                        </>
                      ) : null}
                  </div>
              )}
              {isEditingMap && showMap && <div className="bg-blue-50 text-blue-700 p-2 text-center text-xs font-bold rounded-lg mb-2">MODO EDIÇÃO: Toque no pino para digitar a nova posição</div>}
          </div>

          <div className="flex-1 overflow-hidden relative">
              {showMap ? (
                   isLoaded && (
                      <GoogleMap
                          mapContainerStyle={{width:'100%', height:'100%'}}
                          center={userPos || {lat:-23.55, lng:-46.63}}
                          zoom={15}
                          options={mapOptions}
                          onLoad={setMapInstance}
                      >
                          {groupedStops.map((g, i) => (
                              <MarkerF 
                                key={g.id} position={{lat:g.lat, lng:g.lng}} 
                                label={{text: String(i+1), color:'white', fontWeight:'bold', fontSize:'12px'}}
                                icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id, isEditingMap)}
                                onClick={() => {
                                    // ITEM 5: Edição Numérica
                                    if(isEditingMap) handleMarkerEdit(g, i);
                                    else setSelectedMarker(g);
                                }}
                                zIndex={isEditingMap ? 1000 : 1}
                              />
                          ))}
                          {selectedMarker && !isEditingMap && (
                              <InfoWindowF position={{lat:selectedMarker.lat, lng:selectedMarker.lng}} onCloseClick={() => setSelectedMarker(null)}>
                                  <div className="p-2 min-w-[200px]">
                                      {/* ITEM 4: InfoWindow Completa */}
                                      <h3 className="font-bold text-sm mb-1">Parada: {selectedMarker.mainName}</h3>
                                      <p className="text-xs text-gray-500 mb-1">{selectedMarker.mainAddress}</p>
                                      <div className="text-xs font-bold text-blue-600 mb-2">{selectedMarker.items.length} pacotes</div>
                                      <button onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} className="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold">NAVEGAR</button>
                                  </div>
                              </InfoWindowF>
                          )}
                      </GoogleMap>
                   )
              ) : (
                  <div className="h-full overflow-y-auto px-4 pt-4 pb-32 bg-slate-50">
                      
                      {/* CARD DESTAQUE */}
                      {!isEditingMap && nextGroup && activeRoute.optimized && (
                          <div className="highlight-card p-0 mb-6 bg-white">
                              <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRÓXIMA</div>
                              <div className="p-6 pb-4">
                                  <div className="text-xs font-bold text-blue-600 mb-1">PARADA #{groupedStops.findIndex(g => g.id === nextGroup.id) + 1}</div>
                                  <h2 className="text-2xl font-bold text-slate-900 leading-tight mb-2">{safeStr(nextGroup.mainName)}</h2>
                                  <div className="flex items-center gap-2 text-slate-500 text-sm mb-6"><MapPin size={16}/><span className="truncate">{safeStr(nextGroup.mainAddress)}</span></div>
                                  <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg active:scale-95 transition"><Navigation size={20}/> INICIAR ROTA</button>
                              </div>
                              <div className="bg-slate-50 p-4 border-t border-slate-100 space-y-3">
                                  {nextGroup.items.map((item, idx) => {
                                      if (item.status !== 'pending') return null;
                                      return (
                                          <div key={item.id} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                                              <div className="mb-4"><span className="text-[10px] font-bold text-slate-400 block mb-1">PACOTE</span><div className="font-bold text-slate-800">{safeStr(item.address)}</div></div>
                                              <div className="flex gap-3">
                                                  <button onClick={() => handleDelivery(item, 'failed')} className="flex-1 btn-delivery btn-fail"><AlertTriangle size={20}/> Falha</button>
                                                  <button onClick={() => handleDeliveryClick(item, nextGroup.items)} className="flex-[1.5] btn-delivery btn-success"><Check size={24}/> Entregue</button>
                                              </div>
                                          </div>
                                      )
                                  })}
                              </div>
                          </div>
                      )}

                      {/* ITEM 2 e 3: LISTA COMPLETA */}
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1 mb-3">Lista de Paradas</h4>
                      <div className="space-y-3">
                          {groupedStops.map((g, idx) => {
                              if (nextGroup && g.id === nextGroup.id && activeRoute.optimized) return null;
                              const isExpanded = expandedGroups[g.id];
                              return (
                                  <div key={g.id} className={`enterprise-card ${g.status!=='pending'?'opacity-50 grayscale':''}`}>
                                      <div className={`status-bar bg-status-${g.status}`}></div>
                                      <div className="p-4 pl-6 cursor-pointer" onClick={() => toggleGroup(g.id)}>
                                          <div className="flex justify-between items-start">
                                              <div>
                                                  <div className="text-xs font-bold text-slate-400 mb-1">PARADA #{idx+1}</div>
                                                  <h4 className="font-bold text-sm text-slate-800">{g.mainName}</h4>
                                                  <p className="text-xs text-slate-500 mt-1">Esta parada possui {g.items.length} pacotes</p>
                                              </div>
                                              {isExpanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>}
                                          </div>
                                      </div>
                                      
                                      {/* ITEM 3: EXPANSÃO DOS ENDEREÇOS */}
                                      {isExpanded && (
                                          <div className="bg-slate-50 border-t px-6 py-3 space-y-3">
                                              {g.items.map(item => (
                                                  <div key={item.id} className="text-sm border-b border-slate-200 pb-2 last:border-0">
                                                      <span className="font-bold text-slate-700 block">{item.address}</span>
                                                      <span className="text-xs text-slate-400 block">{item.status.toUpperCase()}</span>
                                                  </div>
                                              ))}
                                          </div>
                                      )}
                                  </div>
                              )
                          })}
                      </div>
                  </div>
              )}
          </div>
      </div>
  );
}
'''

def main():
    print(f"🚀 ATUALIZAÇÃO V53 (DIRECT CONTROL) - {APP_NAME}")
    
    # 1. Substituir a chave no código
    final_app_jsx = files_content['src/App.jsx'].replace("__GOOGLE_KEY__", GOOGLE_MAPS_KEY)
    
    print("\n📝 Atualizando App.jsx...")
    with open("src/App.jsx", 'w', encoding='utf-8') as f:
        f.write(final_app_jsx)

    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "feat: V53 Numeric Edit, Strict Import & Detailed Cards"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


