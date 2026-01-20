import os
import shutil
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. CSS (Botões Gradientes e Mapa)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;
@import 'leaflet/dist/leaflet.css';

body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: #F8FAFC;
  color: #0F172A;
  -webkit-tap-highlight-color: transparent;
}

/* MAPA LEAFLET ORIGINAL */
.leaflet-container {
  width: 100%;
  height: 100%;
  z-index: 0;
  background: #f0f0f0;
}
.leaflet-control-zoom, .leaflet-control-attribution { display: none !important; }

/* Botões Premium */
.btn-gradient-blue {
  background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
  color: white;
  box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4);
  border: none;
}
.btn-gradient-green {
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
  color: white;
  box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
  border: none;
}
.btn-outline-red {
  background: white;
  color: #EF4444;
  border: 2px solid #FEE2E2;
}

/* Cards */
.modern-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(0,0,0,0.05);
  transition: all 0.3s ease;
  overflow: hidden;
}
.modern-card:active { transform: scale(0.98); }

/* Cores de Status */
.border-l-status-pending { border-left: 6px solid #3B82F6; }
.border-l-status-success { border-left: 6px solid #10B981; background-color: #F0FDF4; opacity: 0.7; }
.border-l-status-failed { border-left: 6px solid #EF4444; background-color: #FEF2F2; opacity: 0.7; }
.border-l-status-partial { border-left: 6px solid #F59E0B; background-color: #FFFBEB; }

/* Pinos do Mapa */
.custom-marker-pin {
  width: 32px;
  height: 32px;
  border-radius: 50% 50% 50% 0;
  background: #3B82F6;
  position: absolute;
  transform: rotate(-45deg);
  left: 50%;
  top: 50%;
  margin: -16px 0 0 -16px;
  box-shadow: 0 3px 10px rgba(0,0,0,0.3);
  border: 3px solid white;
}
.custom-marker-pin::after {
  content: ''; width: 12px; height: 12px; margin: 8px 0 0 8px;
  background: white; position: absolute; border-radius: 50%;
}
.pin-success { background: #10B981; }
.pin-failed { background: #EF4444; }
.pin-current { background: #0F172A; transform: scale(1.3) rotate(-45deg); z-index: 1000 !important; }

/* Toast */
.toast-anim { animation: slideIn 0.3s ease-out forwards; }
@keyframes slideIn { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
'''

# 2. APP.JSX (Lógica de Geocoding + Fluxo Novo)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Pencil
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { MapContainer, TileLayer, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v32_refined';

// --- HELPERS VISUAIS ---
const createLeafletIcon = (status, isCurrent) => {
    let className = 'custom-marker-pin';
    if (status === 'success') className += ' pin-success';
    else if (status === 'failed') className += ' pin-failed';
    else if (isCurrent) className += ' pin-current';

    return L.divIcon({
        className: 'custom-icon-container',
        html: `<div class="${className}"></div>`,
        iconSize: [32, 44],
        iconAnchor: [16, 44]
    });
};

const MapController = ({ center }) => {
    const map = useMap();
    useEffect(() => {
        if (center) map.flyTo(center, 16, { animate: true, duration: 1.5 });
    }, [center, map]);
    return null;
};

// --- LOGICA DE NEGÓCIO ---
const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    
    stops.forEach(stop => {
        const rawName = stop.name ? String(stop.name) : 'Sem Nome';
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
        const rawName = stop.name ? String(stop.name) : 'Sem Nome';
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

const calculateRemainingMetrics = (stops, userPos) => {
    if (!Array.isArray(stops) || stops.length === 0) return { km: "0", time: "0h 0m", remainingPackages: 0 };
    const pendingStops = stops.filter(s => s.status === 'pending');
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

    const realKm = totalKm * 1.6; 
    const avgSpeed = 18; 
    const serviceTime = pendingStops.length * 4; 
    const totalMin = (realKm / avgSpeed * 60) + serviceTime;
    
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
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  
  // Estados do Modal de Partida
  const [showStartModal, setShowStartModal] = useState(false);
  const [customStartAddr, setCustomStartAddr] = useState('');
  const [isGeocoding, setIsGeocoding] = useState(false);

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
        } catch(err) { return alert("Erro no arquivo."); }

        const norm = data.map((r, i) => {
            const k = {};
            Object.keys(r).forEach(key => k[String(key).trim().toLowerCase()] = r[key]);
            const safeString = (val) => val ? String(val) : '';
            return {
                id: Date.now() + i + Math.random(),
                name: safeString(k['stop'] || k['parada'] || k['cliente'] || k['nome'] || `Parada ${i+1}`),
                recipient: safeString(k['recebedor'] || k['contato'] || k['cliente'] || 'Recebedor'),
                address: safeString(k['destination address'] || k['endereço'] || k['endereco'] || '---'),
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

  // --- GEOCODING (Endereço -> Lat/Lng) ---
  const geocodeAddress = async (address) => {
      setIsGeocoding(true);
      try {
          const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}`, {
              headers: { 'User-Agent': 'MotoristaPro/1.0' }
          });
          const data = await response.json();
          setIsGeocoding(false);
          if(data && data.length > 0) {
              return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
          } else {
              alert("Endereço não encontrado.");
              return null;
          }
      } catch(e) {
          setIsGeocoding(false);
          alert("Erro de conexão.");
          return null;
      }
  };

  // --- OTIMIZAÇÃO (CORE) ---
  const runOptimization = async (startPos) => {
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
      showToast("Rota Organizada!", "success");
  };

  // Handler do Botão Otimizar
  const handleOptimizeClick = () => {
      setShowStartModal(true);
  };

  // Handler da Modal (GPS)
  const confirmGpsStart = async () => {
      let pos = userPos;
      if (!pos) pos = await getCurrentLocation(true);
      if (pos) runOptimization(pos);
      else alert("GPS Indisponível. Tente digitar o endereço.");
  };

  // Handler da Modal (Endereço)
  const confirmAddressStart = async () => {
      if(!customStartAddr) return;
      const pos = await geocodeAddress(customStartAddr);
      if(pos) runOptimization(pos);
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
          if (status === 'success') showToast("Entrega OK!", "success");
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
                              <span className="flex items-center gap-1"><Package size={14}/> {r.stops.length} pacotes</span>
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
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {toast && (
              <div className={`fixed top-4 left-4 right-4 p-4 rounded-xl shadow-2xl z-50 text-white text-center font-bold text-sm toast-anim ${toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>
                  {toast.msg}
              </div>
          )}

          {/* MODAL DE OTIMIZAÇÃO */}
          {showStartModal && (
              <div className="absolute inset-0 bg-black/60 z-[3000] flex items-end sm:items-center justify-center p-4 backdrop-blur-sm animate-in fade-in">
                  <div className="bg-white w-full max-w-sm rounded-2xl p-6 shadow-2xl space-y-6">
                      <div className="flex justify-between items-center">
                          <h3 className="text-xl font-bold text-slate-900">Onde a rota começa?</h3>
                          <button onClick={() => setShowStartModal(false)}><X className="text-slate-400"/></button>
                      </div>
                      
                      <button onClick={confirmGpsStart} className="w-full p-4 border border-slate-200 rounded-xl flex items-center gap-3 hover:bg-slate-50 active:scale-95 transition">
                          <div className="bg-blue-100 p-2 rounded-full"><Crosshair className="text-blue-600"/></div>
                          <div className="text-left">
                              <span className="block font-bold text-slate-800">Usar Localização Atual</span>
                              <span className="text-xs text-slate-500">GPS do celular (Recomendado)</span>
                          </div>
                      </button>

                      <div className="relative">
                          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-200"></div></div>
                          <div className="relative flex justify-center text-xs uppercase"><span className="bg-white px-2 text-slate-400">Ou digite endereço</span></div>
                      </div>

                      <div className="flex gap-2">
                          <input 
                            type="text" 
                            className="flex-1 p-3 bg-slate-50 rounded-xl outline-none border focus:border-blue-500 text-sm" 
                            placeholder="Ex: Rua das Flores, 100"
                            value={customStartAddr}
                            onChange={e => setCustomStartAddr(e.target.value)}
                          />
                          <button onClick={confirmAddressStart} disabled={isGeocoding} className="bg-slate-900 text-white p-3 rounded-xl">
                              {isGeocoding ? <Loader2 className="animate-spin"/> : <Check/>}
                          </button>
                      </div>
                  </div>
              </div>
          )}

          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft className="text-slate-800"/></button>
                  <h2 className="font-bold text-slate-800 truncate px-4 flex-1 text-center">{activeRoute.name}</h2>
                  <div className="flex gap-2">
                      <button onClick={() => setShowMap(!showMap)} className={`p-2 rounded-full ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'}`}>
                          {showMap ? <List size={20}/> : <MapIcon size={20}/>}
                      </button>
                      <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 size={20} className="text-red-400"/></button>
                  </div>
              </div>
              
              {!showMap && (
                  <div className="relative mb-4">
                      <Search size={18} className="absolute left-3 top-3 text-slate-400"/>
                      <input type="text" placeholder="Buscar..." className="w-full pl-10 pr-4 py-2.5 rounded-xl search-input text-sm font-medium outline-none" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}/>
                      {searchQuery && <button onClick={() => setSearchQuery('')} className="absolute right-3 top-3 text-slate-400"><X size={16}/></button>}
                  </div>
              )}

              {activeRoute.optimized && !searchQuery && !showMap && (
                  <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4 animate-in fade-in">
                      <div className="flex items-center gap-2"><MapIcon size={16} className="text-blue-500"/><span className="text-xs font-bold text-slate-600">{metrics.km} km</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Clock size={16} className="text-orange-500"/><span className="text-xs font-bold text-slate-600">~{metrics.time}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Box size={16} className="text-green-500"/><span className="text-xs font-bold text-slate-600">{metrics.remainingPackages} rest.</span></div>
                  </div>
              )}
              
              {!searchQuery && !showMap && (
                  <div className="flex gap-3">
                      <button 
                          onClick={handleOptimizeClick} 
                          disabled={isOptimizing} 
                          className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition 
                          ${!activeRoute.optimized ? 'btn-gradient-blue animate-pulse' : 'btn-secondary'}`}
                      >
                          {isOptimizing ? <Loader2 className="animate-spin" size={18}/> : <Sliders size={18}/>} 
                          {isOptimizing ? '...' : 'Otimizar'}
                      </button>
                      
                      {nextGroup && (
                          <button 
                              onClick={() => openNav(nextGroup.lat, nextGroup.lng)} 
                              disabled={!activeRoute.optimized} 
                              className={`flex-[1.5] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition 
                              ${activeRoute.optimized ? 'btn-gradient-green shadow-lg' : 'bg-slate-100 text-slate-300 cursor-not-allowed'}`}
                          >
                              <Navigation size={18}/> Navegar
                          </button>
                      )}
                  </div>
              )}
          </div>

          {showMap ? (
              <div className="flex-1 relative bg-slate-100">
                  <MapContainer center={userPos || [-23.55, -46.63]} zoom={13} style={{ height: '100%', width: '100%' }}>
                      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap' />
                      {nextGroup && <MapController center={[nextGroup.lat, nextGroup.lng]} />}
                      {userPos && <Marker position={[userPos.lat, userPos.lng]} />}
                      {groupedStops.map((g) => {
                          const isNext = nextGroup && g.id === nextGroup.id;
                          if (!isNext && g.status !== 'pending' && g.status !== 'partial') return null;
                          return (
                              <Marker 
                                key={g.id} 
                                position={[g.lat, g.lng]} 
                                icon={createLeafletIcon(g.status, isNext)}
                                zIndexOffset={isNext ? 1000 : 0}
                              />
                          )
                      })}
                  </MapContainer>
                  
                  {nextGroup && (
                      <div className="absolute bottom-6 left-4 right-4 z-[1000] bg-white p-4 rounded-xl shadow-xl border border-slate-200">
                          <h3 className="font-bold text-slate-900 truncate">{nextGroup.mainName}</h3>
                          <p className="text-xs text-slate-500 mb-2">{nextGroup.mainAddress}</p>
                          <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} className="w-full btn-gradient-green py-3 rounded-lg font-bold">Navegar</button>
                      </div>
                  )}
              </div>
          ) : (
              <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3">
                  
                  {!searchQuery && nextGroup && activeRoute.optimized && (
                      <div className="modern-card p-6 border-l-4 border-slate-900 bg-white relative mb-6 shadow-md transition-all duration-500">
                          <div className="absolute top-0 right-0 bg-slate-900 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">EM ANDAMENTO</div>
                          <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{nextGroup.mainName}</h3>
                          <p className="text-sm text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                          
                          {nextGroup.items.length > 1 && <div className="mb-4 bg-blue-50 text-blue-800 px-3 py-2 rounded-lg text-xs font-bold flex items-center gap-2"><Box size={14}/> {nextGroup.items.length} PACOTES</div>}

                          <div className="space-y-3 border-t border-slate-100 pt-3">
                              {nextGroup.items.map((item, idx) => {
                                  if (item.status !== 'pending') return null;
                                  return (
                                      <div key={item.id} className="flex flex-col bg-slate-50 p-3 rounded-lg border border-slate-100 animate-in fade-in">
                                          <div className="mb-3">
                                              <span className="text-xs font-bold text-blue-600 block mb-1">PARADA #{idx + 1}</span>
                                              <span className="text-sm font-bold text-slate-800 block leading-tight">{item.address}</span>
                                          </div>
                                          <div className="flex gap-2 w-full">
                                              <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 btn-action-lg btn-outline-red rounded-lg hover:bg-red-50"><AlertTriangle size={18} className="mb-1"/> Não Entregue</button>
                                              <button onClick={() => setStatus(item.id, 'success')} className="flex-1 btn-action-lg btn-gradient-green rounded-lg shadow-sm active:scale-95"><Check size={20} className="mb-1"/> ENTREGUE</button>
                                          </div>
                                      </div>
                                  )
                              })}
                          </div>
                      </div>
                  )}

                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">{searchQuery ? 'Resultados' : 'Sequência de Paradas'}</h4>

                  {filteredGroups.map((group, idx) => {
                      if (!searchQuery && nextGroup && group.id === nextGroup.id && activeRoute.optimized) return null;
                      
                      const isExpanded = expandedGroups[group.id];
                      const hasMulti = group.items.length > 1;
                      const statusClass = `border-l-status-${group.status}`;

                      return (
                          <div key={group.id} className={`modern-card overflow-hidden ${statusClass} ${group.status !== 'pending' && !searchQuery ? 'opacity-60 grayscale' : ''}`}>
                              <div onClick={() => toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer active:bg-slate-50 transition-colors">
                                  <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>{group.status === 'success' ? <Check size={14}/> : (idx + 1)}</div>
                                  <div className="flex-1 min-w-0"><div className="flex items-center gap-2"><h4 className="font-bold text-slate-800 text-sm truncate">{group.mainName}</h4>{hasMulti && <span className="bg-slate-800 text-white text-[10px] px-1.5 py-0.5 rounded-md font-bold">{group.items.length}</span>}</div><p className="text-xs text-slate-400 truncate">{group.mainAddress}</p></div>
                                  {hasMulti || isExpanded ? (isExpanded ? <ChevronUp size={18} className="text-slate-400"/> : <ChevronDown size={18} className="text-slate-400"/>) : (group.items[0].status === 'pending' && <button onClick={(e) => {e.stopPropagation(); setStatus(group.items[0].id, 'success')}} className="p-2 bg-slate-50 text-slate-400 hover:text-green-600 rounded-full"><Check size={18}/></button>)}
                              </div>
                              {(isExpanded || (hasMulti && isExpanded)) && (
                                  <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-3 animate-in slide-in-from-top-2">
                                      {group.items.map((item, subIdx) => (
                                          <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                              <div className="mb-2">
                                                  <span className="text-[10px] font-bold text-blue-500 block">PARADA #{subIdx + 1}</span>
                                                  <span className="text-sm font-bold text-slate-700 block">{item.address}</span>
                                              </div>
                                              {item.status === 'pending' ? (<div className="flex gap-2 w-full"><button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-2 btn-outline-red rounded font-bold text-xs">NÃO ENTREGUE</button><button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-2 btn-gradient-green rounded font-bold text-xs shadow-sm">ENTREGUE</button></div>) : (<span className={`text-[10px] font-bold px-2 py-1 rounded w-fit ${item.status==='success'?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>{item.status === 'success' ? 'ENTREGUE' : 'NÃO ENTREGUE'}</span>)}
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
'''

def main():
    print(f"🚀 ATUALIZAÇÃO V32 (REFINEMENT) - {APP_NAME}")
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
        
    print("\n📦 Revertendo para Leaflet & Instalando Dependências...")
    # Garante que Leaflet está instalado e MapLibre removido (se ainda existir)
    subprocess.run("npm install leaflet react-leaflet", shell=True)
    subprocess.run("npm uninstall maplibre-gl react-map-gl", shell=True)
    subprocess.run("npx cap sync", shell=True)

    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "feat: V32 UI Polish, Classic Map & Optimization Modal"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


