import os
import shutil
import subprocess

# --- CONFIGURAÇÕES ---
APP_NAME = "MotoristaPro-Rota"
GOOGLE_MAPS_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

files_content = {}

# 1. APP.JSX (Com Sanitização de Dados e Proteção de Render)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// NOVA CHAVE PARA LIMPAR DADOS CORROMPIDOS
const DB_KEY = 'mp_db_v37_clean';
const GOOGLE_KEY = "__GOOGLE_KEY__";

// --- HELPERS SEGUROS ---
// Garante que qualquer valor vire string segura para renderizar
const safeStr = (val) => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'object') return JSON.stringify(val); // Se for objeto, vira texto
    return String(val).trim();
};

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
        scale: isCurrent ? 2.2 : 1.8, 
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = {
    disableDefaultUI: true,
    zoomControl: false,
    clickableIcons: false
};

const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    
    stops.forEach(stop => {
        // Sanitização na leitura
        const rawName = safeStr(stop.stopName) || 'Local Sem Nome';
        const key = rawName.toLowerCase();

        if (!groups[key]) {
            groups[key] = {
                id: key,
                lat: Number(stop.lat) || 0,
                lng: Number(stop.lng) || 0,
                mainName: rawName,
                mainAddress: safeStr(stop.address),
                items: [],
                status: 'pending'
            };
        }
        groups[key].items.push(stop);
    });

    const orderedGroups = [];
    const seenKeys = new Set();

    stops.forEach(stop => {
        const rawName = safeStr(stop.stopName) || 'Local Sem Nome';
        const key = rawName.toLowerCase();
        
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

const calculateMetrics = (stops, userPos) => {
    if (!Array.isArray(stops) || stops.length === 0) return { km: "0", time: "0h 0m", remainingPackages: 0 };
    const pendingStops = stops.filter(s => s.status === 'pending');
    
    if (pendingStops.length === 0) return { km: "0", time: "Finalizado", remainingPackages: 0 };

    let totalKm = 0;
    let currentLat = userPos ? userPos.lat : (pendingStops[0]?.lat || 0);
    let currentLng = userPos ? userPos.lng : (pendingStops[0]?.lng || 0);

    const calcDist = (lat1, lon1, lat2, lon2) => {
        const R = 6371; 
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
        return R * c;
    };

    pendingStops.forEach(stop => {
        totalKm += calcDist(currentLat, currentLng, stop.lat, stop.lng);
        currentLat = stop.lat;
        currentLng = stop.lng;
    });

    const realKm = totalKm * 1.5; 
    const avgSpeed = 25; 
    const serviceTimeTotal = pendingStops.length * 1.5;
    const travelTimeMin = (realKm / avgSpeed * 60);
    const totalMin = travelTimeMin + serviceTimeTotal;
    
    return { 
        km: realKm.toFixed(1), 
        time: `${Math.floor(totalMin / 60)}h ${Math.floor(totalMin % 60)}m`, 
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
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
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
            
            // SANITIZAÇÃO DE DADOS (CRUCIAL PARA EVITAR ERRO #31)
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

  const optimizeRoute = async () => {
      setIsOptimizing(true);
      let currentPos = userPos;
      if (!currentPos) currentPos = await getCurrentLocation(true);
      if (!currentPos) { setIsOptimizing(false); alert("Ative o GPS."); return; }

      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      const currentRoute = routes[rIdx];
      let pending = currentRoute.stops.filter(s => s.status === 'pending');
      let done = currentRoute.stops.filter(s => s.status !== 'pending');
      let optimized = [];
      let pointer = currentPos;

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
      }
  };

  const openNav = (lat, lng) => {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const toggleGroup = (id) => {
      setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));
  };

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

  const metrics = useMemo(() => {
      if (!activeRoute) return { km: "0", time: "0h 0m", remainingPackages: 0 };
      return calculateMetrics(activeRoute.stops, userPos);
  }, [activeRoute, userPos, routes]);

  useEffect(() => {
      if (showMap && isLoaded && mapInstance && nextGroup) {
          mapInstance.panTo({ lat: nextGroup.lat, lng: nextGroup.lng });
          mapInstance.setZoom(16);
      }
  }, [nextGroup, showMap, isLoaded, mapInstance]);

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
                          <h3 className="font-bold text-lg">{safeStr(r.name)}</h3>
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
          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-4 flex-1 text-center">{safeStr(activeRoute.name)}</h2>
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
                      <button onClick={optimizeRoute} disabled={isOptimizing} className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 ${!activeRoute.optimized ? 'btn-gradient-blue animate-pulse' : 'btn-secondary'}`}>
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
                                label={{ text: String(idx + 1), color: "white", fontSize: "12px", fontWeight: "bold" }}
                                icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id)}
                                onClick={() => setSelectedMarker(g)}
                              />
                          ))}
                          {userPos && <MarkerF position={{ lat: userPos.lat, lng: userPos.lng }} icon={getMarkerIcon('current', true)} />}

                          {selectedMarker && (
                            <InfoWindowF position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }} onCloseClick={() => setSelectedMarker(null)}>
                                <div className="p-2 min-w-[200px]">
                                    <h3 className="font-bold text-slate-900 text-sm mb-1">{safeStr(selectedMarker.mainName)}</h3>
                                    <p className="text-xs text-slate-500 mb-2">{safeStr(selectedMarker.mainAddress)}</p>
                                    <div className="text-xs font-bold text-blue-600 mb-3">{selectedMarker.items.length} pacotes</div>
                                    <button onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} className="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold">NAVEGAR AQUI</button>
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
                                              <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 btn-action-lg bg-white border border-red-200 text-red-600 rounded-xl">Não Entregue</button>
                                              <button onClick={() => setStatus(item.id, 'success')} className="flex-1 btn-action-lg bg-green-600 text-white rounded-xl shadow-md">ENTREGUE</button>
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
                                      <div className="flex items-center gap-2"><h4 className="font-bold text-slate-800 text-sm truncate">{safeStr(group.mainName)}</h4></div>
                                      <p className="text-xs text-slate-400 truncate">{group.items.length} pacotes</p>
                                  </div>
                                  {hasMulti || isExpanded ? (isExpanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>) : (group.items[0].status === 'pending' && <button onClick={(e) => {e.stopPropagation(); setStatus(group.items[0].id, 'success')}} className="p-2 bg-slate-50 text-slate-400 rounded-full"><Check size={18}/></button>)}
                              </div>
                              {(isExpanded || (hasMulti && isExpanded)) && (
                                  <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-3">
                                      {group.items.map((item, subIdx) => (
                                          <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                              <div className="mb-2"><span className="text-[10px] font-bold text-blue-500 block">PACOTE #{subIdx + 1}</span><span className="text-sm font-bold text-slate-700 block">{safeStr(item.address)}</span></div>
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
}'''

def main():
    print(f"🚀 ATUALIZAÇÃO V37 (CRASH FIX & DATA SANITIZER) - {APP_NAME}")
    
    # 1. Substituir a chave no código
    final_app_jsx = files_content['src/App.jsx'].replace("__GOOGLE_KEY__", GOOGLE_MAPS_KEY)
    
    print("\n📝 Atualizando App.jsx...")
    with open("src/App.jsx", 'w', encoding='utf-8') as f:
        f.write(final_app_jsx)

    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "fix: V37 Safe Data Handling & Render Protection"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


