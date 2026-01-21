import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Compass
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, DirectionsService, DirectionsRenderer } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v46_mapfix';
const GOOGLE_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU";

// --- HELPERS VISUAIS ---
const getMarkerIcon = (status, isCurrent) => {
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    let fillColor = "#3B82F6"; 
    if (status === 'success') fillColor = "#10B981";
    if (status === 'failed') fillColor = "#EF4444";
    if (status === 'partial') fillColor = "#F59E0B";
    if (isCurrent) fillColor = "#0F172A";

    return {
        path: path,
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 1.5,
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2.0 : 1.4,
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

const getUserIcon = (heading) => {
    return {
        path: "M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z", 
        fillColor: "#4285F4",
        fillOpacity: 1,
        strokeWeight: 2,
        strokeColor: "#FFFFFF",
        rotation: heading || 0,
        scale: 1.5,
        anchor: { x: 12, y: 12 }
    };
};

const mapContainerStyle = { width: '100%', height: '100%' };

// DEFINIÇÃO CORRETA DAS OPÇÕES DO MAPA
const defaultMapOptions = {
    disableDefaultUI: true,
    zoomControl: false,
    clickableIcons: false,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false
};

// --- HELPERS DADOS ---
const safeStr = (val) => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val).trim();
};

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
        const key = (safeStr(stop.stopName) || 'Sem Nome').toLowerCase();
        if (!seen.has(key)) {
            const g = groups[key];
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
    });
    return ordered;
};

// Algoritmo de Otimização em Cadeia (Rolling Chain)
const optimizeRollingChain = async (allStops, startPos) => {
    let unvisited = [...allStops];
    let finalRoute = [];
    let currentPos = startPos;
    const service = new window.google.maps.DirectionsService();

    while (unvisited.length > 0) {
        // Encontra os 23 mais próximos
        unvisited.sort((a, b) => {
            const dA = Math.pow(a.lat - currentPos.lat, 2) + Math.pow(a.lng - currentPos.lng, 2);
            const dB = Math.pow(b.lat - currentPos.lat, 2) + Math.pow(b.lng - currentPos.lng, 2);
            return dA - dB;
        });

        const batch = unvisited.slice(0, 23);
        unvisited = unvisited.slice(23);

        const waypoints = batch.map(p => ({ location: { lat: p.lat, lng: p.lng }, stopover: true }));
        
        try {
            const result = await new Promise((resolve, reject) => {
                service.route({
                    origin: currentPos,
                    destination: batch[batch.length - 1], 
                    waypoints: waypoints,
                    optimizeWaypoints: true,
                    travelMode: 'DRIVING'
                }, (res, status) => {
                    if (status === 'OK') resolve(res);
                    else reject(status);
                });
            });

            const order = result.routes[0].waypoint_order;
            const orderedBatch = order.map(idx => batch[idx]);
            finalRoute.push(...orderedBatch);
            currentPos = orderedBatch[orderedBatch.length - 1];
            await new Promise(r => setTimeout(r, 300));

        } catch (e) {
            console.warn("Falha Google Batch:", e);
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
  const [userHeading, setUserHeading] = useState(0);
  const [isNavigating, setIsNavigating] = useState(false);
  
  const [expandedGroups, setExpandedGroups] = useState({});
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  const [showStartModal, setShowStartModal] = useState(false);
  const [customStartAddr, setCustomStartAddr] = useState('');
  const [isGeocoding, setIsGeocoding] = useState(false);
  const [selectedMarker, setSelectedMarker] = useState(null);

  const [directionsResponse, setDirectionsResponse] = useState(null);
  const mapRef = useRef(null);

  const { isLoaded } = useJsApiLoader({
    id: 'google-map-script',
    googleMapsApiKey: GOOGLE_KEY
  });

  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) { localStorage.removeItem(DB_KEY); }
    startGps();
  }, []);

  useEffect(() => { localStorage.setItem(DB_KEY, JSON.stringify(routes)); }, [routes]);

  const showToast = (msg, type = 'success') => {
      setToast({ msg, type });
      setTimeout(() => setToast(null), 2000);
  };

  const startGps = async () => {
      try {
          await Geolocation.requestPermissions();
          Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 5000 }, (pos) => {
              if (pos) {
                  setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude });
                  if (pos.coords.heading !== null && !isNaN(pos.coords.heading)) {
                      setUserHeading(pos.coords.heading);
                  }
              }
          });
      } catch (e) { console.error(e); }
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
                name: safeStr(k['stop'] || k['parada'] || k['cliente'] || `Parada ${i+1}`),
                stopName: safeStr(k['stop'] || k['parada'] || `Parada ${i+1}`), 
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

  const deleteRoute = (id) => {
      if(confirm("Excluir rota?")) {
          setRoutes(routes.filter(r => r.id !== id));
          if(activeRouteId === id) setView('home');
      }
  };

  const handleOptimizeClick = () => setShowStartModal(true);

  const runSmartOptimization = async (startPos) => {
      setIsOptimizing(true);
      setShowStartModal(false);
      
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      const currentRoute = routes[rIdx];
      
      const pending = currentRoute.stops.filter(s => s.status === 'pending');
      const done = currentRoute.stops.filter(s => s.status !== 'pending');
      
      try {
          const locationMap = new Map();
          pending.forEach(s => {
              const key = `${s.lat.toFixed(5)}_${s.lng.toFixed(5)}`;
              if(!locationMap.has(key)) locationMap.set(key, []);
              locationMap.get(key).push(s);
          });
          
          let uniqueLocations = Array.from(locationMap.values()).map(items => ({
              lat: items[0].lat, lng: items[0].lng, items: items
          }));

          const optimizedNodes = await optimizeRollingChain(uniqueLocations, startPos);
          
          const finalStops = [];
          optimizedNodes.forEach(node => finalStops.push(...node.items));

          const updatedRoutes = [...routes];
          updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: [...done, ...finalStops], optimized: true };
          setRoutes(updatedRoutes);
          showToast("Rota Otimizada!");
      } catch (err) {
          alert("Erro otimização: " + err.message);
      }
      setIsOptimizing(false);
  };

  const confirmGpsStart = async () => {
      let pos = userPos;
      if (!pos) pos = await getCurrentLocation(true);
      if (pos) runSmartOptimization(pos);
      else alert("Ative o GPS.");
  };

  const confirmAddressStart = async () => {
      if(!customStartAddr) return;
      setIsGeocoding(true);
      try {
          const response = await fetch(`https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(customStartAddr)}&key=${GOOGLE_KEY}`);
          const data = await response.json();
          setIsGeocoding(false);
          if (data.status === 'OK' && data.results.length > 0) {
              const loc = data.results[0].geometry.location;
              runSmartOptimization({ lat: loc.lat, lng: loc.lng });
          } else { alert("Endereço não encontrado."); }
      } catch(e) { setIsGeocoding(false); alert("Erro conexão."); }
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

  const toggleGroup = (id) => setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));

  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');
  
  const filteredGroups = useMemo(() => {
      if (!searchQuery) return groupedStops;
      const lower = searchQuery.toLowerCase();
      return groupedStops.filter(g => 
          safeStr(g.mainName).toLowerCase().includes(lower) || 
          safeStr(g.mainAddress).toLowerCase().includes(lower)
      );
  }, [groupedStops, searchQuery]);

  // DIRECTIONS SERVICE (Desenho da Rota)
  useEffect(() => {
      if (isLoaded && nextGroup && userPos) {
          const service = new window.google.maps.DirectionsService();
          service.route({
              origin: userPos,
              destination: { lat: nextGroup.lat, lng: nextGroup.lng },
              travelMode: 'DRIVING'
          }, (res, status) => {
              if (status === 'OK') setDirectionsResponse(res);
          });
      } else {
          setDirectionsResponse(null);
      }
  }, [nextGroup?.id, userPos?.lat, userPos?.lng, isLoaded]);

  // FOLLOW ME (Giro do Mapa)
  useEffect(() => {
      if (isLoaded && mapRef.current && userPos && isNavigating) {
          mapRef.current.panTo(userPos);
          mapRef.current.setZoom(18);
          mapRef.current.setHeading(userHeading);
          mapRef.current.setTilt(45);
      }
  }, [userPos, userHeading, isNavigating, isLoaded]);

  // VIEWS
  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <div className="flex justify-between items-center mb-8">
              <h1 className="text-3xl font-bold text-slate-900">Rotas</h1>
              <div className="bg-white p-2 rounded-full shadow-sm"><Package className="text-slate-400"/></div>
          </div>
          {routes.length === 0 ? <div className="text-center mt-32 opacity-40"><MapPin size={48} className="mx-auto mb-4"/><p>Nenhuma rota</p></div> : 
              <div className="space-y-4">
                  {routes.map(r => (
                      <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="modern-card p-5 cursor-pointer">
                          <h3 className="font-bold text-lg">{safeStr(r.name)}</h3>
                          <div className="flex gap-4 text-sm text-slate-500 mt-2">
                              <span><Package size={14} className="inline mr-1"/>{r.stops.length} vols</span>
                              {r.optimized && <span className="text-green-600 font-bold"><Check size={14} className="inline mr-1"/>Otimizada</span>}
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
          {toast && <div className={`fixed top-4 left-4 right-4 p-4 rounded-xl shadow-2xl z-50 text-white text-center font-bold text-sm toast-anim ${toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>{toast.msg}</div>}
          
          {showStartModal && (
              <div className="absolute inset-0 bg-black/60 z-[3000] flex items-center justify-center p-4">
                  <div className="bg-white w-full max-w-sm rounded-2xl p-6 shadow-2xl space-y-6">
                      <h3 className="text-xl font-bold">Otimizar Rota</h3>
                      <button onClick={confirmGpsStart} className="w-full p-4 border rounded-xl flex items-center gap-3 hover:bg-slate-50"><Crosshair className="text-blue-600"/><span className="font-bold">Usar GPS Atual</span></button>
                      <div className="flex gap-2"><input type="text" className="flex-1 p-3 bg-slate-50 rounded-xl border text-sm" placeholder="Ou digite endereço..." value={customStartAddr} onChange={e => setCustomStartAddr(e.target.value)}/><button onClick={confirmAddressStart} disabled={isGeocoding} className="bg-slate-900 text-white p-3 rounded-xl">{isGeocoding ? <Loader2 className="animate-spin"/> : <Check/>}</button></div>
                      <button onClick={() => setShowStartModal(false)} className="w-full text-slate-400 font-bold">Cancelar</button>
                  </div>
              </div>
          )}

          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-4 flex-1 text-center">{safeStr(activeRoute.name)}</h2>
                  <div className="flex gap-2">
                      <button onClick={() => { setShowMap(!showMap); setIsNavigating(false); }} className={`p-2 rounded-full ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'}`}>{showMap ? <List size={20}/> : <MapIcon size={20}/>}</button>
                      <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 size={20} className="text-red-400"/></button>
                  </div>
              </div>
              
              {!showMap && (
                  <div className="flex gap-3">
                      <button onClick={handleOptimizeClick} disabled={isOptimizing} className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 ${!activeRoute.optimized ? 'btn-gradient-blue animate-pulse' : 'btn-secondary'}`}>
                          {isOptimizing ? <Loader2 className="animate-spin" size={18}/> : <Sliders size={18}/>} {isOptimizing ? '...' : 'Otimizar'}
                      </button>
                      {nextGroup && (
                          <button onClick={() => { setShowMap(true); setIsNavigating(true); }} disabled={!activeRoute.optimized} className={`flex-[1.5] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 ${activeRoute.optimized ? 'btn-gradient-green shadow-lg' : 'bg-slate-100 text-slate-300'}`}>
                              <Navigation size={18}/> Navegar
                          </button>
                      )}
                  </div>
              )}
          </div>

          {showMap ? (
              <div className="flex-1 relative bg-slate-100">
                  {isLoaded ? (
                      <GoogleMap
                          mapContainerStyle={mapContainerStyle}
                          center={userPos || { lat: -23.55, lng: -46.63 }}
                          zoom={16}
                          options={{ ...defaultMapOptions, heading: userHeading, tilt: isNavigating ? 45 : 0 }}
                          onLoad={(map) => { setMapInstance(map); mapRef.current = map; }}
                      >
                          {directionsResponse && <DirectionsRenderer directions={directionsResponse} options={{ suppressMarkers: true, polylineOptions: { strokeColor: "#2563EB", strokeWeight: 5 } }} />}
                          
                          {groupedStops.map((g, idx) => (
                              <MarkerF 
                                key={g.id} 
                                position={{ lat: g.lat, lng: g.lng }}
                                label={{ text: String(idx + 1), color: "white", fontSize: "12px", fontWeight: "bold" }}
                                icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id)}
                                onClick={() => setSelectedMarker(g)}
                              />
                          ))}
                          {userPos && <MarkerF position={{ lat: userPos.lat, lng: userPos.lng }} icon={getUserIcon(userHeading)} zIndex={2000} />}

                          {selectedMarker && (
                            <InfoWindowF position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }} onCloseClick={() => setSelectedMarker(null)}>
                                <div className="p-2 min-w-[200px]">
                                    <h3 className="font-bold text-sm mb-1">Parada: {safeStr(selectedMarker.mainName)}</h3>
                                    <p className="text-xs text-slate-500 mb-2">{safeStr(selectedMarker.mainAddress)}</p>
                                    <button onClick={() => { setIsNavigating(true); setSelectedMarker(null); }} className="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold">NAVEGAR AQUI</button>
                                </div>
                            </InfoWindowF>
                          )}
                      </GoogleMap>
                  ) : <div className="flex h-full items-center justify-center"><Loader2 className="animate-spin"/></div>}
                  
                  {nextGroup && (
                      <div className="absolute bottom-6 left-4 right-4 bg-white p-4 rounded-xl shadow-xl z-[1000]">
                          <div className="flex justify-between items-start">
                              <div>
                                  <h3 className="font-bold truncate">{nextGroup.mainName}</h3>
                                  <p className="text-xs text-slate-500 mb-2">{nextGroup.mainAddress}</p>
                              </div>
                              <button onClick={() => setIsNavigating(!isNavigating)} className={`p-3 rounded-full ${isNavigating ? 'bg-blue-600 text-white' : 'bg-slate-100'}`}>
                                  <Navigation size={20} className={isNavigating ? 'animate-pulse' : ''} />
                              </button>
                          </div>
                      </div>
                  )}
              </div>
          ) : (
              <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3">
                  {!searchQuery && nextGroup && activeRoute.optimized && (
                      <div className="modern-card p-6 border-l-4 border-slate-900 bg-white relative mb-6 shadow-md">
                          <div className="absolute top-0 right-0 bg-slate-900 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRÓXIMO</div>
                          <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{safeStr(nextGroup.mainName)}</h3>
                          <p className="text-sm text-slate-500 mb-4">{nextGroup.items.length} pacotes</p>
                          <div className="space-y-3 border-t border-slate-100 pt-3">
                              {nextGroup.items.map((item, idx) => {
                                  if (item.status !== 'pending') return null;
                                  return (
                                      <div key={item.id} className="flex flex-col bg-slate-50 p-3 rounded-lg border border-slate-100">
                                          <div className="mb-3">
                                              <span className="text-xs font-bold text-blue-600 block mb-1">PACOTE #{idx + 1}</span>
                                              <span className="text-sm font-bold text-slate-800 block leading-tight">{safeStr(item.address)}</span>
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
                                      <div className="flex items-center gap-2"><h4 className="font-bold text-slate-800 text-sm truncate">{safeStr(group.mainName)}</h4>{hasMulti && <span className="bg-slate-800 text-white text-[10px] px-1.5 py-0.5 rounded-md font-bold">{group.items.length}</span>}</div>
                                      <p className="text-xs text-slate-400 truncate">{group.mainAddress}</p>
                                  </div>
                                  {hasMulti || isExpanded ? (isExpanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>) : (group.items[0].status === 'pending' && <button onClick={(e) => {e.stopPropagation(); setStatus(group.items[0].id, 'success')}} className="p-2 bg-slate-50 text-slate-400 rounded-full"><Check size={18}/></button>)}
                              </div>
                              {(isExpanded || (hasMulti && isExpanded)) && (
                                  <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-3">
                                      {group.items.map((item, subIdx) => (
                                          <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                              <div className="mb-2"><span className="text-[10px] font-bold text-blue-500 block">PARADA #{subIdx + 1}</span><span className="text-sm font-bold text-slate-700 block">{safeStr(item.address)}</span></div>
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