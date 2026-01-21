import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Edit3, Save, Zap
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v55_restored';
const GOOGLE_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU";

// --- HELPERS ---
const safeStr = (val) => {
    if (!val) return '';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val).trim();
};

const getMarkerIcon = (status, isCurrent, isEditing) => {
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    let color = "#3B82F6"; 
    if (status === 'success') color = "#10B981";
    if (status === 'failed') color = "#EF4444";
    if (status === 'partial') color = "#F59E0B";
    if (isCurrent) color = "#0F172A"; // Preto Destaque
    if (isEditing) color = "#7C3AED"; // Roxo Edição

    return {
        path,
        fillColor: color,
        fillOpacity: 1,
        strokeWeight: 1.5,
        strokeColor: "#FFFFFF",
        scale: (isCurrent || isEditing) ? 2.2 : 1.4,
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = { disableDefaultUI: true, zoomControl: false, clickableIcons: false, styles: [{ featureType: "poi", stylers: [{ visibility: "off" }] }] };

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
  const [isEditing, setIsEditing] = useState(false); // Modo Edição Mapa
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [directions, setDirections] = useState(null);
  
  // Estados de Importação
  const [importSuccess, setImportSuccess] = useState(null); 
  const [isProcessing, setIsProcessing] = useState(false);

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
    
    setIsProcessing(true);

    const reader = new FileReader();
    reader.onload = (evt) => {
        setTimeout(() => { // Delay para animação
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
                    const stopsCount = new Set(norm.map(s => s.stopName)).size;
                    setImportSuccess({ pkgs: norm.length, stops: stopsCount });
                } else {
                    alert("Planilha sem coordenadas.");
                }
            } catch(e) { alert("Erro ao ler arquivo."); }
            setIsProcessing(false);
        }, 1000);
    };
    reader.readAsBinaryString(file);
  };

  const createRoute = () => {
      if(!newRouteName.trim() || !tempStops.length) return;
      setRoutes([{ id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops, optimized: false }, ...routes]);
      setNewRouteName(''); setTempStops([]); setImportSuccess(null); setView('home');
  };

  const deleteRoute = (id) => {
      if(confirm("Excluir rota?")) {
          setRoutes(routes.filter(r => r.id !== id));
          if(activeRouteId === id) setView('home');
      }
  };

  const optimizeRoute = async (startPos) => {
      setIsOptimizing(true);
      const start = startPos || userPos || (await getCurrentLocation());
      
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1 || !start) { setIsOptimizing(false); return; }

      setTimeout(() => {
          const currentRoute = routes[rIdx];
          const grouped = groupStops(currentRoute.stops);
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

  // EDIÇÃO MANUAL NO MAPA (V53/55)
  const handleMarkerEdit = (group, currentIdx) => {
      const newIndexStr = prompt(`Mover "${group.mainName}" para posição:`, String(currentIdx + 1));
      if (newIndexStr === null) return;
      
      const newIndex = parseInt(newIndexStr) - 1; 
      if (isNaN(newIndex) || newIndex < 0 || newIndex >= groupedStops.length) return alert("Inválido");

      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const currentRoute = routes[rIdx];
      const allGroups = groupStops(currentRoute.stops);
      
      const [movedGroup] = allGroups.splice(currentIdx, 1);
      allGroups.splice(newIndex, 0, movedGroup);
      
      const newStops = [];
      allGroups.forEach(g => newStops.push(...g.items));
      
      const updatedRoutes = [...routes];
      updatedRoutes[rIdx].stops = newStops;
      setRoutes(updatedRoutes);
      showToast(`Movido para #${newIndex + 1}`);
  };

  const handleDelivery = (item, status, isBulk = false) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
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

      // Auto-reotimizar
      const remainingInGroup = route.stops.filter(s => s.stopName === item.stopName && s.status === 'pending');
      if (remainingInGroup.length === 0 && route.optimized) {
          // Pequeno delay para a animação do toast não colidir
          setTimeout(() => optimizeRoute(), 500);
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
  const groupedStops = useMemo(() => activeRoute ? groupStops(activeRoute.stops) : [], [activeRoute]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');
  const metrics = useMemo(() => activeRoute ? calculateMetrics(activeRoute.stops, userPos) : {}, [activeRoute, userPos]);

  useEffect(() => {
      // Força o mapa a aparecer se entrar em modo edição
      if (isEditing) setShowMap(true);
  }, [isEditing]);

  // Loading Screen
  if (isProcessing) return (
      <div className="fixed inset-0 bg-white/95 z-50 flex flex-col items-center justify-center">
          <Loader2 size={48} className="text-blue-600 animate-spin mb-4"/>
          <p className="font-bold text-slate-700">Analisando dados...</p>
      </div>
  );
  
  if (importSuccess) return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
          <div className="bg-white rounded-3xl shadow-xl p-8 w-full max-w-sm text-center border border-slate-100">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Check size={32} className="text-green-600"/>
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-2">Sucesso!</h2>
              <div className="flex justify-center gap-4 mb-8 mt-4">
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex-1">
                      <span className="block text-2xl font-bold text-blue-600">{importSuccess.stops}</span>
                      <span className="text-[10px] text-slate-400 uppercase font-bold">Paradas</span>
                  </div>
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex-1">
                      <span className="block text-2xl font-bold text-purple-600">{importSuccess.pkgs}</span>
                      <span className="text-[10px] text-slate-400 uppercase font-bold">Pacotes</span>
                  </div>
              </div>
              <button onClick={createRoute} className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold text-lg shadow-lg">Confirmar</button>
              <button onClick={() => {setImportSuccess(null); setTempStops([]);}} className="mt-4 text-slate-400 text-sm font-bold">Cancelar</button>
          </div>
      </div>
  );

  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <h1 className="text-3xl font-bold text-slate-900 mb-8">Rotas</h1>
          {routes.length === 0 ? <div className="text-center mt-32 opacity-40"><MapIcon size={48} className="mx-auto mb-4"/><p>Sem rotas</p></div> : 
             routes.map(r => (
               <div key={r.id} onClick={() => {setActiveRouteId(r.id); setView('details')}} className="modern-card p-5 mb-4 cursor-pointer">
                 <h3 className="font-bold">{safeStr(r.name)}</h3>
                 <span className="text-sm text-slate-500">{r.stops.length} pacotes</span>
               </div>
             ))
          }
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center"><Plus/></button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-white p-6">
          <button onClick={() => setView('home')} className="mb-6"><ArrowLeft/></button>
          <h2 className="text-2xl font-bold mb-6">Nova Rota</h2>
          <input className="w-full p-4 bg-slate-50 rounded-xl mb-4" placeholder="Nome da Rota (Obrigatório)" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
          <label className={`block w-full p-8 border-2 border-dashed rounded-xl text-center bg-slate-50 mb-4 ${!newRouteName ? 'opacity-50 cursor-not-allowed' : ''}`}>
              Importar <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx" disabled={!newRouteName}/>
          </label>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {toast && <div className={`fixed top-4 left-4 right-4 p-4 rounded-xl shadow-2xl z-[3000] text-white text-center font-bold text-sm toast-anim ${toast.type==='success'?'bg-slate-900':'bg-red-600'}`}>{toast.msg}</div>}

          <div className="bg-white px-5 py-4 shadow-sm z-20">
              <div className="flex justify-between items-center mb-3">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-2">{safeStr(activeRoute.name)}</h2>
                  <button onClick={() => { setShowMap(!showMap); setIsEditing(false); }} className={`p-2 rounded-full ${showMap?'bg-blue-100 text-blue-600':'bg-slate-100 text-slate-600'}`}>{showMap?<List/>:<MapIcon/>}</button>
              </div>

              {!showMap && (
                  <div className="flex gap-2 mb-2">
                      {!isEditing ? (
                        <>
                           <button onClick={() => optimizeRoute()} disabled={isOptimizing} className={`flex-1 py-3 rounded-xl font-bold flex items-center justify-center gap-2 ${!activeRoute.optimized?'btn-optimize-highlight':'bg-slate-100 text-slate-600'}`}>
                                {isOptimizing ? <Loader2 className="animate-spin"/> : <Zap size={18} fill={activeRoute.optimized?"none":"white"}/>} 
                                {isOptimizing ? '...' : 'Otimizar'}
                           </button>
                           <button onClick={() => { setIsEditing(true); showToast("Toque no mapa para editar números", "info"); }} className="flex-1 py-3 bg-slate-100 text-slate-600 rounded-xl font-bold flex items-center justify-center gap-2"><Edit3 size={18}/> Editar</button>
                        </>
                      ) : (
                           <button onClick={() => setIsEditing(false)} className="w-full py-3 bg-green-600 text-white rounded-xl font-bold"><Save size={18}/> Salvar Ordem</button>
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
                   isLoaded && (
                      <GoogleMap
                          mapContainerStyle={mapContainerStyle}
                          center={userPos || {lat:-23.55, lng:-46.63}}
                          zoom={14}
                          options={mapOptions}
                      >
                          {groupedStops.map((g, i) => (
                              <MarkerF 
                                key={g.id} position={{lat:g.lat, lng:g.lng}} 
                                label={{text: String(i+1), color:'white', fontWeight:'bold'}}
                                icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id, isEditing)}
                                onClick={() => {
                                    if(isEditing) handleMarkerEdit(g, i); 
                                    else setSelectedMarker(g);
                                }}
                                zIndex={isEditing ? 1000 : 1}
                              />
                          ))}
                          {/* InfoWindow V53: Info Completa */}
                          {selectedMarker && !isEditing && (
                              <InfoWindowF position={{lat:selectedMarker.lat, lng:selectedMarker.lng}} onCloseClick={() => setSelectedMarker(null)}>
                                  <div className="p-2 min-w-[200px]">
                                      <h3 className="font-bold text-sm mb-1">Parada: {safeStr(selectedMarker.mainName)}</h3>
                                      <p className="text-xs text-gray-500 mb-2">{safeStr(selectedMarker.mainAddress)}</p>
                                      <div className="font-bold text-blue-600 text-xs mb-3">{selectedMarker.items.length} pacotes</div>
                                      <button onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} className="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold">NAVEGAR</button>
                                  </div>
                              </InfoWindowF>
                          )}
                      </GoogleMap>
                   ) : <Loader2 className="animate-spin m-auto"/>
              ) : (
                  <div className="h-full overflow-y-auto px-4 pt-4 pb-32 bg-slate-50">
                      
                      {/* CARD DESTAQUE */}
                      {!isEditing && nextGroup && activeRoute.optimized && (
                          <div className="highlight-card p-0 mb-6 bg-white">
                              <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRÓXIMO</div>
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
                                                  <button onClick={() => handleDelivery(item, 'failed')} className="flex-1 btn-action-lg btn-outline-red rounded-xl">NÃO ENTREGUE</button>
                                                  <button onClick={() => handleDeliveryClick(item, nextGroup.items)} className="flex-[1.5] btn-action-lg btn-gradient-green rounded-xl text-white shadow-md">ENTREGUE</button>
                                              </div>
                                          </div>
                                      )
                                  })}
                              </div>
                          </div>
                      )}

                      {/* LISTA COMPLETA */}
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1 mb-3">Lista de Paradas</h4>
                      <div className="space-y-3">
                          {groupedStops.map((g, idx) => {
                              const isExpanded = expandedGroups[g.id];
                              return (
                                  <div key={g.id} className={`modern-card status-bar-${g.status} ${g.status!=='pending' ? 'opacity-60' : ''}`}>
                                      <div onClick={() => toggleGroup(g.id)} className="p-4 flex items-center gap-3 cursor-pointer">
                                          <div className="font-bold text-slate-500 text-sm">#{idx+1}</div>
                                          <div className="flex-1">
                                              <h4 className="font-bold text-slate-800 text-sm">Parada: {safeStr(g.mainName)}</h4>
                                              <p className="text-xs text-slate-500">Esta parada possui {g.items.length} pacotes</p>
                                          </div>
                                          {isExpanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>}
                                      </div>
                                      {isExpanded && (
                                          <div className="bg-slate-50 border-t px-4 py-2 space-y-2">
                                              {g.items.map(item => (
                                                  <div key={item.id} className="flex justify-between items-center py-2 border-b last:border-0">
                                                      <div><span className="text-[10px] font-bold text-blue-500">ENDEREÇO</span><div className="text-sm font-bold text-slate-700">{safeStr(item.address)}</div></div>
                                                      {item.status !== 'pending' && <span className="text-xs font-bold text-slate-400">{item.status.toUpperCase()}</span>}
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
