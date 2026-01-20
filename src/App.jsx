import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v36_final_v2';
const GOOGLE_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU";

// --- HELPERS VISUAIS GOOGLE ---
const getMarkerIcon = (status, isCurrent, labelText) => {
    // SVG Path do pino padrao
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    
    let fillColor = "#3B82F6"; // Azul (Pendente)
    
    if (status === 'success') fillColor = "#10B981"; // Verde (Entregue)
    if (status === 'failed') fillColor = "#EF4444"; // Vermelho (Falha)
    if (status === 'partial') fillColor = "#F59E0B"; // Laranja (Parcial)
    
    // Se for o atual, destaca em Preto
    if (isCurrent) fillColor = "#0F172A";

    return {
        path: path,
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 1.5, // Borda mais fina
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2.2 : 1.8, 
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 } // Posição do número
    };
};

const mapContainerStyle = { width: '100%', height: '100%' };

const mapOptions = {
    disableDefaultUI: true,
    zoomControl: false,
    streetViewControl: false,
    mapTypeControl: false,
    fullscreenControl: false,
    clickableIcons: false
};

// --- LÓGICA DE DADOS ---
const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    
    stops.forEach(stop => {
        const rawName = stop.stopName ? String(stop.stopName) : 'Local Sem Nome';
        const key = rawName.trim().toLowerCase();

        if (!groups[key]) {
            groups[key] = {
                id: key,
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

    const orderedGroups = [];
    const seenKeys = new Set();

    stops.forEach(stop => {
        const rawName = stop.stopName ? String(stop.stopName) : 'Local Sem Nome';
        const key = rawName.trim().toLowerCase();
        
        if (!seenKeys.has(key)) {
            const group = groups[key];
            const total = group.items.length;
            const success = group.items.filter(i => i.status === 'success').length;
            const failed = group.items.filter(i => i.status === 'failed').length;
            
            if (success === total) group.status = 'success';
            else if (failed === total) group.status = 'failed';
            else if (success + failed > 0) group.status = 'partial';
            else group.status = 'pending';

            orderedGroups.push(group);
            seenKeys.add(key);
        }
    });
    return orderedGroups;
};

// AJUSTE 4: Tempo Estimado (Trajeto + 1m30s por pacote)
const calculateRemainingMetrics = (stops, userPos) => {
    if (!Array.isArray(stops) || stops.length === 0) return { km: "0", time: "0h 0m", remainingPackages: 0 };
    
    const pendingStops = stops.filter(s => s.status === 'pending');
    
    // Se acabou, retorna zero
    if (pendingStops.length === 0) return { km: "0", time: "Finalizado", remainingPackages: 0 };

    let totalKm = 0;
    let currentLat = userPos ? userPos.lat : pendingStops[0].lat;
    let currentLng = userPos ? userPos.lng : pendingStops[0].lng;

    const calcDist = (lat1, lon1, lat2, lon2) => {
        const R = 6371; 
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
        return R * c;
    };

    pendingStops.forEach(stop => {
        totalKm += calcDist(currentLat, currentLng, stop.lat, stop.lng);
        currentLat = stop.lat;
        currentLng = stop.lng;
    });

    // Fator de rota real (ruas não são retas)
    const realKm = totalKm * 1.5; 
    
    // Velocidade Média Urbana
    const avgSpeed = 25; // km/h
    
    // AJUSTE 4: 1.5 minutos (1m30s) por pacote
    const serviceTimePerPackage = 1.5;
    const serviceTimeTotal = pendingStops.length * serviceTimePerPackage;
    
    const travelTimeMin = (realKm / avgSpeed * 60);
    const totalMin = travelTimeMin + serviceTimeTotal;
    
    const h = Math.floor(totalMin / 60);
    const m = Math.floor(totalMin % 60);

    return { 
        km: realKm.toFixed(1), 
        time: `${h}h ${m}m`, 
        remainingPackages: pendingStops.length 
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
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  const [showStartModal, setShowStartModal] = useState(false);
  const [customStartAddr, setCustomStartAddr] = useState('');
  const [isGeocoding, setIsGeocoding] = useState(false);
  
  // Estado para InfoWindow do Mapa
  const [selectedMarker, setSelectedMarker] = useState(null);

  const { isLoaded } = useJsApiLoader({
    id: 'google-map-script',
    googleMapsApiKey: GOOGLE_KEY
  });
  
  const [mapInstance, setMapInstance] = useState(null);

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

  const showToast = (msg, type = 'success') => {
      setToast({ msg, type });
      setTimeout(() => setToast(null), 2000);
  };

  const getCurrentLocation = async (force = false) => {
      try {
          if (force) await Geolocation.requestPermissions();
          const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 5000 });
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
            
            return {
                id: Date.now() + i + Math.random(),
                name: String(k['stop'] || k['parada'] || k['cliente'] || k['nome'] || `Parada ${i+1}`),
                stopName: String(k['stop'] || k['parada'] || `Parada ${i+1}`), // Coluna STOP explícita
                recipient: String(k['recebedor'] || k['contato'] || k['cliente'] || 'Recebedor'),
                address: String(k['destination address'] || k['endereço'] || k['endereco'] || '---'),
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

  const handleOptimizeClick = () => setShowStartModal(true);

  const runOptimization = (startPos) => {
      setIsOptimizing(true);
      setShowStartModal(false);
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      const currentRoute = routes[rIdx];
      let pending = currentRoute.stops.filter(s => s.status === 'pending');
      let done = currentRoute.stops.filter(s => s.status !== 'pending');
      let optimized = [];
      let pointer = startPos;

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

      const updatedRoutes = [...routes];
      updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: [...done, ...optimized], optimized: true };
      setRoutes(updatedRoutes);
      setIsOptimizing(false);
      showToast("Rota Otimizada!");
  };

  const confirmGpsStart = async () => {
      let pos = userPos;
      if (!pos) pos = await getCurrentLocation(true);
      if (pos) runOptimization(pos);
      else alert("GPS indisponível.");
  };

  const confirmAddressStart = async () => {
      if(!customStartAddr) return;
      setIsGeocoding(true);
      try {
          const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(customStartAddr)}`);
          const data = await response.json();
          setIsGeocoding(false);
          if(data && data.length > 0) {
              runOptimization({ lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) });
          } else { alert("Endereço não encontrado."); }
      } catch(e) { setIsGeocoding(false); alert("Erro de conexão."); }
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
          if (status === 'success') showToast("Entrega OK!");
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
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  
  // AJUSTE 3: Destaque Automático
  // Sempre pega o primeiro grupo que tem status 'pending' ou 'partial'
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');
  
  const filteredGroups = useMemo(() => {
      if (!searchQuery) return groupedStops;
      const lower = searchQuery.toLowerCase();
      return groupedStops.filter(g => 
          g.mainName.toLowerCase().includes(lower) || 
          g.mainAddress.toLowerCase().includes(lower)
      );
  }, [groupedStops, searchQuery]);

  const metrics = useMemo(() => {
      if (!activeRoute) return { km: "0", time: "0h 0m", remainingPackages: 0 };
      return calculateRemainingMetrics(activeRoute.stops, userPos);
  }, [activeRoute, userPos, routes]);

  // Atualizar mapa quando nextGroup muda
  useEffect(() => {
      if (showMap && isLoaded && mapInstance && nextGroup) {
          mapInstance.panTo({ lat: nextGroup.lat, lng: nextGroup.lng });
          mapInstance.setZoom(16);
      }
  }, [nextGroup, showMap, isLoaded, mapInstance]);

  // VIEWS
  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <div className="flex justify-between items-center mb-8">
              <h1 className="text-3xl font-bold text-slate-900">Rotas</h1>
              <div className="bg-white p-2 rounded-full shadow-sm"><Package className="text-slate-400"/></div>
          </div>
          {routes.length === 0 ? (
              <div className="text-center mt-32 opacity-40"><MapPin size={48} className="mx-auto mb-4"/><p>Nenhuma rota</p></div>
          ) : (
              <div className="space-y-4">
                  {routes.map(r => (
                      <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="modern-card p-5 cursor-pointer">
                          <h3 className="font-bold text-lg">{r.name}</h3>
                          <div className="flex gap-4 text-sm text-slate-500 mt-2">
                              <span><Package size={14} className="inline mr-1"/>{r.stops.length} pacotes</span>
                              {r.optimized && <span className="text-green-600 font-bold"><Check size={14} className="inline mr-1"/>Otimizada</span>}
                          </div>
                      </div>
                  ))}
              </div>
          )}
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center"><Plus size={32}/></button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-white flex flex-col p-6">
          <button onClick={() => setView('home')} className="self-start mb-6"><ArrowLeft/></button>
          <h2 className="text-2xl font-bold mb-8">Nova Rota</h2>
          <div className="space-y-6 flex-1">
              <input type="text" className="w-full p-4 bg-slate-50 rounded-xl" placeholder="Nome da Rota" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
              <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl bg-slate-50">
                  <Upload className="mb-2 text-slate-400"/> <span className="text-sm font-bold text-slate-500">Importar Planilha</span>
                  <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/>
              </label>
              {tempStops.length > 0 && <div className="text-center text-green-600 font-bold">{tempStops.length} pacotes</div>}
          </div>
          <button onClick={createRoute} className="w-full bg-slate-900 text-white py-5 rounded-2xl font-bold">Salvar</button>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {{/* MODAL OTIMIZAÇÃO */}}
          {showStartModal && (
              <div className="absolute inset-0 bg-black/60 z-[3000] flex items-end sm:items-center justify-center p-4 backdrop-blur-sm animate-in fade-in">
                  <div className="bg-white w-full max-w-sm rounded-2xl p-6 shadow-2xl space-y-6">
                      <div className="flex justify-between items-center"><h3 className="text-xl font-bold">Partida</h3><button onClick={() => setShowStartModal(false)}><X/></button></div>
                      <button onClick={confirmGpsStart} className="w-full p-4 border rounded-xl flex items-center gap-3 hover:bg-slate-50"><Crosshair className="text-blue-600"/><div className="text-left"><span className="block font-bold">Usar GPS Atual</span></div></button>
                      <div className="flex gap-2"><input type="text" className="flex-1 p-3 bg-slate-50 rounded-xl border text-sm" placeholder="Ou digite endereço..." value={customStartAddr} onChange={e => setCustomStartAddr(e.target.value)}/><button onClick={confirmAddressStart} disabled={isGeocoding} className="bg-slate-900 text-white p-3 rounded-xl">{isGeocoding ? <Loader2 className="animate-spin"/> : <Check/>}</button></div>
                  </div>
              </div>
          )}

          {{/* HEADER */}}
          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-4 flex-1 text-center">{activeRoute.name}</h2>
                  <div className="flex gap-2">
                      <button onClick={() => setShowMap(!showMap)} className={`p-2 rounded-full ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'}`}>{showMap ? <List size={20}/> : <MapIcon size={20}/>}</button>
                      <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 size={20} className="text-red-400"/></button>
                  </div>
              </div>
              
              {!showMap && (
                  <div className="relative mb-4">
                      <Search size={18} className="absolute left-3 top-3 text-slate-400"/>
                      <input type="text" placeholder="Buscar..." className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-50 text-sm outline-none" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}/>
                      {searchQuery && <button onClick={() => setSearchQuery('')} className="absolute right-3 top-3 text-slate-400"><X size={16}/></button>}
                  </div>
              )}

              {activeRoute.optimized && !searchQuery && !showMap && (
                  <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4">
                      <div className="flex items-center gap-2"><MapIcon size={16} className="text-blue-500"/><span className="text-xs font-bold">{metrics.km} km</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Clock size={16} className="text-orange-500"/><span className="text-xs font-bold">{metrics.time}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Box size={16} className="text-green-500"/><span className="text-xs font-bold">{metrics.remainingPackages} rest.</span></div>
                  </div>
              )}
              
              {!searchQuery && !showMap && (
                  <div className="flex gap-3">
                      <button onClick={handleOptimizeClick} disabled={isOptimizing} className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 ${!activeRoute.optimized ? 'btn-gradient-blue animate-pulse' : 'btn-secondary'}`}>
                          {isOptimizing ? <Loader2 className="animate-spin" size={18}/> : <Sliders size={18}/>} {isOptimizing ? '...' : 'Otimizar'}
                      </button>
                      {nextGroup && (
                          <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} disabled={!activeRoute.optimized} className={`flex-[1.5] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 ${activeRoute.optimized ? 'btn-gradient-green shadow-lg' : 'bg-slate-100 text-slate-300'}`}>
                              <Navigation size={18}/> Navegar
                          </button>
                      )}
                  </div>
              )}
          </div>

          {{/* CONTEÚDO */}}
          {showMap ? (
              <div className="flex-1 relative bg-slate-100">
                  {isLoaded ? (
                      <GoogleMap
                          mapContainerStyle={mapContainerStyle}
                          center={userPos || { lat: -23.55, lng: -46.63 }}
                          zoom={15}
                          options={mapOptions}
                          onLoad={(map) => setMapInstance(map)}
                      >
                          {groupedStops.map((g, idx) => (
                              <MarkerF 
                                key={g.id} 
                                position={{ lat: g.lat, lng: g.lng }}
                                // AJUSTE 1: Label com Número e Ícones Menores
                                label={{
                                    text: String(idx + 1),
                                    color: "white",
                                    fontSize: "12px",
                                    fontWeight: "bold",
                                    className: "map-label"
                                }}
                                icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id)}
                                onClick={() => setSelectedMarker(g)}
                              />
                          ))}
                          {userPos && <MarkerF position={{ lat: userPos.lat, lng: userPos.lng }} icon={getMarkerIcon('current', true)} />}

                          {/* AJUSTE 2: InfoWindow ao Clicar */}
                          {selectedMarker && (
                            <InfoWindowF
                                position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }}
                                onCloseClick={() => setSelectedMarker(null)}
                            >
                                <div className="p-2 min-w-[200px]">
                                    <h3 className="font-bold text-slate-900 text-sm mb-1">{selectedMarker.mainName}</h3>
                                    <p className="text-xs text-slate-500 mb-2">{selectedMarker.mainAddress}</p>
                                    <div className="text-xs font-bold text-blue-600 mb-3">{selectedMarker.items.length} pacotes</div>
                                    <button 
                                        onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)}
                                        className="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold"
                                    >
                                        NAVEGAR AQUI
                                    </button>
                                </div>
                            </InfoWindowF>
                          )}
                      </GoogleMap>
                  ) : <div className="flex h-full items-center justify-center"><Loader2 className="animate-spin"/></div>}
              </div>
          ) : (
              <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3">
                  {!searchQuery && nextGroup && activeRoute.optimized && (
                      <div className="modern-card p-6 border-l-4 border-slate-900 bg-white relative mb-6 shadow-md">
                          <div className="absolute top-0 right-0 bg-slate-900 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRÓXIMO</div>
                          {/* AJUSTE 2: Título do Card */}
                          <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">Parada: {nextGroup.mainName}</h3>
                          {/* AJUSTE 2: Subtítulo */}
                          <p className="text-sm text-slate-500 mb-4">{nextGroup.items.length} pacotes a serem entregues nessa parada</p>
                          <div className="space-y-3 border-t border-slate-100 pt-3">
                              {nextGroup.items.map((item, idx) => {
                                  if (item.status !== 'pending') return null;
                                  return (
                                      <div key={item.id} className="flex flex-col bg-slate-50 p-3 rounded-lg border border-slate-100">
                                          <div className="mb-3">
                                              <span className="text-xs font-bold text-blue-600 block mb-1">PACOTE #{idx + 1}</span>
                                              <span className="text-sm font-bold text-slate-800 block leading-tight">{item.address}</span>
                                          </div>
                                          <div className="flex gap-2 w-full">
                                              <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 btn-action-lg btn-outline-red rounded-xl">Não Entregue</button>
                                              <button onClick={() => setStatus(item.id, 'success')} className="flex-1 btn-action-lg btn-gradient-green rounded-xl text-white shadow-md">ENTREGUE</button>
                                          </div>
                                      </div>
                                  )
                              })}
                          </div>
                      </div>
                  )}

                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Lista</h4>
                  {filteredGroups.map((group, idx) => {
                      if (!searchQuery && nextGroup && group.id === nextGroup.id && activeRoute.optimized) return null;
                      const isExpanded = expandedGroups[group.id];
                      const hasMulti = group.items.length > 1;
                      const statusClass = `border-l-status-${group.status}`;
                      return (
                          <div key={group.id} className={`modern-card overflow-hidden ${statusClass} ${group.status !== 'pending' && !searchQuery ? 'opacity-60 grayscale' : ''}`}>
                              <div onClick={() => toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer">
                                  <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>{group.status === 'success' ? <Check size={14}/> : (idx + 1)}</div>
                                  <div className="flex-1 min-w-0">
                                      {/* AJUSTE 2: Título do Card na Lista */}
                                      <div className="flex items-center gap-2"><h4 className="font-bold text-slate-800 text-sm truncate">Parada: {group.mainName}</h4>{hasMulti && <span className="bg-slate-800 text-white text-[10px] px-1.5 py-0.5 rounded-md font-bold">{group.items.length}</span>}</div>
                                      {/* AJUSTE 2: Subtítulo do Card na Lista */}
                                      <p className="text-xs text-slate-400 truncate">{group.items.length} pacotes a serem entregues nessa parada</p>
                                  </div>
                                  {hasMulti || isExpanded ? (isExpanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>) : (group.items[0].status === 'pending' && <button onClick={(e) => {e.stopPropagation(); setStatus(group.items[0].id, 'success')}} className="p-2 bg-slate-50 text-slate-400 rounded-full"><Check size={18}/></button>)}
                              </div>
                              {(isExpanded || (hasMulti && isExpanded)) && (
                                  <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-3">
                                      {group.items.map((item, subIdx) => (
                                          <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                              <div className="mb-2"><span className="text-[10px] font-bold text-blue-500 block">PACOTE #{subIdx + 1}</span><span className="text-sm font-bold text-slate-700 block">{item.address}</span></div>
                                              {item.status === 'pending' ? (<div className="flex gap-2 w-full"><button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-2 btn-outline-red rounded font-bold text-xs">NÃO ENTREGUE</button><button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-2 btn-gradient-green rounded font-bold text-xs text-white shadow-sm">ENTREGUE</button></div>) : (<span className="text-xs font-bold">{item.status === 'success' ? 'ENTREGUE' : 'NÃO ENTREGUE'}</span>)}
                                          </div>
                                      ))}
                                  </div>
                              )}
                          </div>
                      )
                  })}
                  <div className="h-10"></div>
              </div>
          )}
      </div>
  );
}
