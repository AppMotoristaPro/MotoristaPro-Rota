import os
import shutil
import subprocess

# --- CONFIGURAÇÕES ---
APP_NAME = "MotoristaPro-Rota"
GOOGLE_MAPS_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

files_content = {}

# 1. CSS (Visual Enterprise & Animações)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;
@import 'maplibre-gl/dist/maplibre-gl.css';

body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: #F1F5F9;
  color: #1E293B;
  -webkit-tap-highlight-color: transparent;
  padding-bottom: env(safe-area-inset-bottom);
}

.map-container { width: 100%; height: 100%; }

/* Cards Enterprise */
.enterprise-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
  border: 1px solid #E2E8F0;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s;
  overflow: hidden;
}
.enterprise-card:active { transform: scale(0.98); }

/* Highlight Card (Próxima Parada) */
.highlight-card {
  background: white;
  border-radius: 24px;
  box-shadow: 0 20px 40px -5px rgba(37, 99, 235, 0.15);
  border: 2px solid #2563EB;
  position: relative;
  overflow: hidden;
}
.highlight-badge {
  background: #2563EB;
  color: white;
  font-weight: 800;
  font-size: 11px;
  letter-spacing: 0.05em;
  padding: 6px 12px;
  border-bottom-left-radius: 16px;
  text-transform: uppercase;
}

/* Botões de Ação Premium */
.btn-delivery {
  height: 64px;
  border-radius: 16px;
  font-weight: 700;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}
.btn-success {
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
  color: white;
  box-shadow: 0 8px 20px rgba(16, 185, 129, 0.3);
  border: none;
}
.btn-success:active { transform: scale(0.96); box-shadow: 0 4px 10px rgba(16, 185, 129, 0.2); }

.btn-fail {
  background: #FFF1F2;
  color: #BE123C;
  border: 2px solid #FECDD3;
}
.btn-fail:active { background: #FFE4E6; transform: scale(0.96); }

/* Animação de Loading (Brain) */
.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.98);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.pulse-ring {
  border: 4px solid #2563EB;
  border-radius: 50%;
  animation: ring-pulse 2s infinite;
}
@keyframes ring-pulse {
  0% { width: 0; height: 0; opacity: 1; }
  100% { width: 100px; height: 100px; opacity: 0; }
}

/* Status Bar Lateral */
.status-bar { width: 6px; height: 100%; position: absolute; left: 0; top: 0; }
.bg-status-pending { background-color: #3B82F6; }
.bg-status-success { background-color: #10B981; }
.bg-status-failed { background-color: #EF4444; }
.bg-status-partial { background-color: #F59E0B; }

/* Edit Mode Selection */
.edit-selected {
  border: 3px solid #2563EB !important;
  transform: scale(1.1) !important;
  z-index: 1000 !important;
}
'''

# 2. APP.JSX (Lógica V52: Edit Map, Auto-Opt, Import Animation)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, 
  ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Edit3, Save, Zap, HelpCircle
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v52_enterprise';
const GOOGLE_KEY = "__GOOGLE_KEY__";

// --- HELPERS VISUAIS ---
const getMarkerIcon = (status, isCurrent, isSelected, labelText) => {
    // Design de Pino Moderno (SVG)
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    
    let fillColor = "#3B82F6"; // Azul
    if (status === 'success') fillColor = "#10B981";
    if (status === 'failed') fillColor = "#EF4444";
    if (status === 'partial') fillColor = "#F59E0B";
    if (isCurrent) fillColor = "#0F172A"; // Preto (Atual)
    if (isSelected) fillColor = "#7C3AED"; // Roxo (Edição)

    return {
        path: path,
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 2,
        strokeColor: "#FFFFFF",
        scale: (isCurrent || isSelected) ? 2.2 : 1.5, 
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = { disableDefaultUI: true, zoomControl: false, clickableIcons: false, styles: [{ featureType: "poi", stylers: [{ visibility: "off" }] }] };

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

    // IMPORTANTE: Respeitar a ordem do array 'stops' original
    const orderedGroups = [];
    const seenKeys = new Set();
    stops.forEach(stop => {
        const key = (safeStr(stop.stopName) || 'Local Sem Nome').toLowerCase();
        if (!seenKeys.has(key)) {
            const g = groups[key];
            // Recalcula status do grupo
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

// Algoritmo 2-Opt (Otimização)
const solveTSP = (stops, startPos) => {
    const points = [{ lat: startPos.lat, lng: startPos.lng, isStart: true }, ...stops];
    const n = points.length;
    const dist = (p1, p2) => Math.sqrt(Math.pow(p1.lat - p2.lat, 2) + Math.pow(p1.lng - p2.lng, 2));
    
    let path = [0];
    let visited = new Set([0]);
    
    // Nearest Neighbor
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
    
    // 2-Opt
    let improved = true;
    let iterations = 0;
    while (improved && iterations < 2000) { 
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
    path.shift(); // Remove start
    return path.map(idx => points[idx]);
};

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); 
  const [newRouteName, setNewRouteName] = useState('');
  const [tempStops, setTempStops] = useState([]);
  const [userPos, setUserPos] = useState(null);
  
  // UX States
  const [expandedGroups, setExpandedGroups] = useState({});
  const [isProcessing, setIsProcessing] = useState(false); // Animação de Importação
  const [processingStep, setProcessingStep] = useState('');
  const [importSummary, setImportSummary] = useState(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Modos de Mapa e Edição
  const [showMap, setShowMap] = useState(false);
  const [isEditingMap, setIsEditingMap] = useState(false); // Modo de Edição no Mapa
  const [editSelection, setEditSelection] = useState(null); // ID do pino selecionado para troca

  const [directions, setDirections] = useState(null);
  const [mapInstance, setMapInstance] = useState(null);
  const mapRef = useRef(null);

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
          const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserPos(coords);
          return coords;
      } catch (e) { return null; }
  };

  // --- IMPORTAÇÃO COM ANIMAÇÃO ---
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    setIsProcessing(true);
    setProcessingStep('Lendo arquivo...');

    const reader = new FileReader();
    reader.onload = (evt) => {
        setTimeout(() => {
            setProcessingStep('Identificando endereços...');
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
                
                setTimeout(() => {
                    if(norm.length > 0) {
                        setTempStops(norm);
                        const stopsCount = new Set(norm.map(s => s.stopName)).size;
                        setImportSummary({ pkgs: norm.length, stops: stopsCount });
                        setIsProcessing(false);
                    } else {
                        alert("Nenhuma coordenada encontrada.");
                        setIsProcessing(false);
                    }
                }, 800);
            } catch(e) { 
                alert("Erro ao processar."); 
                setIsProcessing(false);
            }
        }, 800);
    };
    reader.readAsBinaryString(file);
  };

  const createRoute = () => {
      if(!newRouteName.trim() || !tempStops.length) return;
      setRoutes([{ id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops, optimized: false }, ...routes]);
      setNewRouteName(''); setTempStops([]); setImportSummary(null); setView('home');
  };

  // --- OTIMIZAÇÃO AUTOMÁTICA (AUTO-PILOT) ---
  const runOptimization = async (customStart) => {
      setIsOptimizing(true);
      const start = customStart || userPos || (await getCurrentLocation());
      
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1 || !start) { setIsOptimizing(false); return; }

      // Simula delay para feedback visual
      setTimeout(() => {
          const currentRoute = routes[rIdx];
          const grouped = groupStopsByStopName(currentRoute.stops);
          let pendingGroups = grouped.filter(g => g.status !== 'success' && g.status !== 'failed');
          let doneGroups = grouped.filter(g => g.status === 'success' || g.status === 'failed');

          // Otimiza apenas os pendentes
          const pointsToOptimize = pendingGroups.map(g => ({ lat: g.lat, lng: g.lng, group: g }));
          const optimizedPoints = solveTSP(pointsToOptimize, start);
          
          const finalStops = [];
          doneGroups.forEach(g => finalStops.push(...g.items)); // Mantém histórico
          optimizedPoints.forEach(p => finalStops.push(...p.group.items)); // Novos ordenados

          const updatedRoutes = [...routes];
          updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: finalStops, optimized: true };
          setRoutes(updatedRoutes);
          setIsOptimizing(false);
          showToast("Rota Otimizada!");
      }, 600);
  };

  // --- EDIÇÃO VISUAL NO MAPA (SWAP) ---
  const handleMarkerClick = (group) => {
      if (!isEditingMap) return;

      if (!editSelection) {
          // Seleciona o primeiro
          setEditSelection(group);
          showToast("Selecione outro pino para trocar", "info");
      } else {
          // Troca a ordem dos grupos na lista
          const rIdx = routes.findIndex(r => r.id === activeRouteId);
          const currentRoute = routes[rIdx];
          const allGroups = groupStopsByStopName(currentRoute.stops);
          
          const idxA = allGroups.findIndex(g => g.id === editSelection.id);
          const idxB = allGroups.findIndex(g => g.id === group.id);
          
          if (idxA !== -1 && idxB !== -1) {
              // Troca no array de grupos
              const temp = allGroups[idxA];
              allGroups[idxA] = allGroups[idxB];
              allGroups[idxB] = temp;
              
              // Reconstrói lista plana de stops
              const newStops = [];
              allGroups.forEach(g => newStops.push(...g.items));
              
              const updatedRoutes = [...routes];
              updatedRoutes[rIdx].stops = newStops;
              setRoutes(updatedRoutes);
              showToast("Ordem alterada!", "success");
          }
          setEditSelection(null);
      }
  };

  // --- FLUXO DE ENTREGA ---
  const handleDelivery = (item, status, isBulk = false) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      const updatedRoutes = [...routes];
      const route = updatedRoutes[rIdx];
      
      if (isBulk) {
          // Baixa em todos do grupo
          route.stops.forEach(s => {
              if (s.stopName === item.stopName && s.status === 'pending') s.status = status;
          });
      } else {
          // Baixa individual
          const idx = route.stops.findIndex(s => s.id === item.id);
          if (idx !== -1) route.stops[idx].status = status;
      }
      
      setRoutes(updatedRoutes);
      showToast(status === 'success' ? "Entregue!" : "Ocorrência Registrada", status === 'success' ? 'success' : 'error');

      // AUTO-OTIMIZAR APÓS FINALIZAR (ITEM 1 DO PEDIDO)
      // Verifica se o grupo inteiro acabou
      const remainingInGroup = route.stops.filter(s => s.stopName === item.stopName && s.status === 'pending');
      if (remainingInGroup.length === 0) {
          runOptimization(); // Recalcula rota a partir daqui
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

  // --- RENDER ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');
  
  // Directions
  useEffect(() => {
      if (isLoaded && nextGroup && userPos) {
          const service = new window.google.maps.DirectionsService();
          service.route({
              origin: userPos,
              destination: { lat: nextGroup.lat, lng: nextGroup.lng },
              travelMode: 'DRIVING'
          }, (res, status) => { if (status === 'OK') setDirections(res); });
      } else { setDirections(null); }
  }, [nextGroup?.id, isLoaded]);

  // --- LOADING SCREEN ---
  if (isProcessing) return (
      <div className="loading-overlay">
          <div className="pulse-ring absolute"></div>
          <Loader2 size={48} className="text-blue-600 animate-spin z-10 mb-4"/>
          <h2 className="text-xl font-bold text-slate-800 z-10">{processingStep}</h2>
      </div>
  );

  // --- IMPORT SUMMARY MODAL ---
  if (importSummary) return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
          <div className="bg-white rounded-3xl shadow-xl p-8 w-full max-w-sm text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Check size={32} className="text-green-600"/>
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-2">Sucesso!</h2>
              <div className="flex justify-center gap-8 my-6">
                  <div>
                      <span className="block text-3xl font-bold text-blue-600">{importSummary.stops}</span>
                      <span className="text-xs text-slate-400 uppercase font-bold">Paradas</span>
                  </div>
                  <div>
                      <span className="block text-3xl font-bold text-purple-600">{importSummary.pkgs}</span>
                      <span className="text-xs text-slate-400 uppercase font-bold">Pacotes</span>
                  </div>
              </div>
              <button onClick={createRoute} className="w-full btn-success py-4 rounded-xl font-bold text-lg">Confirmar Rota</button>
          </div>
      </div>
  );

  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <h1 className="text-3xl font-bold text-slate-900 mb-8 tracking-tight">Rotas</h1>
          {routes.length === 0 ? <div className="text-center mt-32 opacity-40"><MapPin size={48} className="mx-auto mb-4"/><p>Sem rotas ativas</p></div> : 
             routes.map(r => (
               <div key={r.id} onClick={() => {setActiveRouteId(r.id); setView('details')}} className="enterprise-card p-5 mb-4 active:scale-98 cursor-pointer">
                 <h3 className="font-bold text-lg text-slate-800">{r.name}</h3>
                 <div className="flex justify-between mt-3 text-sm text-slate-500">
                    <span>{r.stops.length} pacotes</span>
                    {r.optimized && <span className="text-green-600 font-bold flex items-center gap-1"><Zap size={14}/> Otimizada</span>}
                 </div>
               </div>
             ))
          }
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full bg-slate-900 text-white shadow-2xl flex items-center justify-center hover:scale-105 transition"><Plus size={32}/></button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-white p-6 flex flex-col">
          <button onClick={() => setView('home')} className="mb-6"><ArrowLeft/></button>
          <h2 className="text-3xl font-bold mb-8 text-slate-900">Nova Rota</h2>
          <input className="w-full p-5 bg-slate-50 rounded-2xl text-lg outline-none focus:ring-2 focus:ring-blue-500 mb-6" placeholder="Nome da Rota" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
          <label className="flex-1 border-2 border-dashed border-slate-200 rounded-2xl flex flex-col items-center justify-center text-slate-400 bg-slate-50/50">
              <Upload size={32} className="mb-2"/> <span className="font-bold">Toque para importar</span>
              <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/>
          </label>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {toast && <div className={`fixed top-6 left-6 right-6 p-4 rounded-xl shadow-2xl z-[9999] text-white text-center font-bold text-sm toast-anim ${toast.type==='success'?'bg-slate-900':'bg-red-600'}`}>{toast.msg}</div>}

          {/* HEADER */}
          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex justify-between items-center mb-3">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-4">{safeStr(activeRoute.name)}</h2>
                  <button onClick={() => { setShowMap(!showMap); setIsEditingMap(false); }} className={`p-2 rounded-full ${showMap?'bg-blue-100 text-blue-600':'bg-slate-100 text-slate-600'}`}>{showMap?<List/>:<MapIcon/>}</button>
              </div>

              {/* CONTROLES */}
              {!showMap && (
                  <div className="flex gap-2">
                      <button onClick={() => runOptimization()} disabled={isOptimizing} 
                          className={`flex-1 py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all
                          ${!activeRoute.optimized ? 'btn-optimize-highlight' : 'bg-slate-100 text-slate-600'}`}>
                          {isOptimizing ? <Loader2 className="animate-spin"/> : <Zap size={18} fill={activeRoute.optimized?"none":"white"}/>} 
                          {isOptimizing ? 'Calculando...' : (activeRoute.optimized ? 'Reotimizar' : 'Otimizar')}
                      </button>
                      <button onClick={() => { setShowMap(true); setIsEditingMap(true); showToast("Toque em 2 pinos para trocar", "info"); }} className="flex-1 py-3 bg-slate-100 text-slate-600 rounded-xl font-bold flex items-center justify-center gap-2">
                          <Edit3 size={18}/> Editar Mapa
                      </button>
                  </div>
              )}
              {isEditingMap && showMap && (
                  <div className="bg-blue-50 text-blue-700 p-2 text-center text-xs font-bold rounded-lg mb-2">MODO EDIÇÃO: Toque em 2 pinos para trocar a ordem</div>
              )}
          </div>

          <div className="flex-1 overflow-hidden relative">
              {showMap ? (
                   isLoaded ? (
                      <GoogleMap
                          mapContainerStyle={{width:'100%', height:'100%'}}
                          center={userPos || {lat:-23.55, lng:-46.63}}
                          zoom={15}
                          options={mapOptions}
                          onLoad={setMapInstance}
                      >
                          {!isEditingMap && directions && <DirectionsRenderer directions={directions} options={{suppressMarkers:true, polylineOptions:{strokeColor:"#2563EB", strokeWeight:5}}}/>}
                          
                          {groupedStops.map((g, i) => {
                              const isNext = nextGroup && g.id === nextGroup.id;
                              const isSelected = editSelection && editSelection.id === g.id;
                              // Em modo edição mostra todos. Em modo nav mostra pendentes.
                              if (!isEditingMap && g.status !== 'pending' && !isNext) return null;

                              return (
                                  <MarkerF 
                                    key={g.id} position={{lat:g.lat, lng:g.lng}} 
                                    label={{text: String(i+1), color:'white', fontWeight:'bold', fontSize:'12px'}}
                                    icon={getMarkerIcon(g.status, isNext, isSelected)}
                                    onClick={() => isEditingMap ? handleMarkerClick(g) : null} // Clique muda dependendo do modo
                                    zIndex={isNext || isSelected ? 1000 : 1}
                                  />
                              )
                          })}
                          {userPos && <MarkerF position={userPos} icon={{path: window.google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: "#4285F4", fillOpacity: 1, strokeColor: "white", strokeWeight: 2}}/>}
                      </GoogleMap>
                   ) : <Loader2 className="animate-spin m-auto"/>
              ) : (
                  <div className="h-full overflow-y-auto px-4 pt-4 pb-32 bg-slate-50">
                      
                      {/* CARD DESTAQUE (PRÓXIMO) */}
                      {!searchQuery && nextGroup && activeRoute.optimized && (
                          <div className="highlight-card p-0 mb-6 bg-white">
                              <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRIORIDADE</div>
                              <div className="p-6 pb-4">
                                  <div className="text-xs font-bold text-blue-600 mb-1">PRÓXIMA PARADA</div>
                                  <h2 className="text-2xl font-bold text-slate-900 leading-tight mb-2">{safeStr(nextGroup.mainName)}</h2>
                                  <div className="flex items-center gap-2 text-slate-500 text-sm mb-6">
                                      <MapPin size={16}/>
                                      <span className="truncate">{safeStr(nextGroup.mainAddress)}</span>
                                  </div>
                                  
                                  <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg active:scale-95 transition">
                                      <Navigation size={20}/> INICIAR ROTA
                                  </button>
                              </div>

                              <div className="bg-slate-50 p-4 border-t border-slate-100 space-y-3">
                                  {nextGroup.items.map((item, idx) => {
                                      if (item.status !== 'pending') return null;
                                      return (
                                          <div key={item.id} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                                              <div className="flex justify-between items-start mb-4">
                                                  <div>
                                                      <span className="text-[10px] font-bold text-slate-400 block mb-1">PACOTE #{idx+1}</span>
                                                      <div className="font-bold text-slate-800">{safeStr(item.address)}</div>
                                                      <div className="text-xs text-slate-500 mt-1">{safeStr(item.recipient)}</div>
                                                  </div>
                                              </div>
                                              <div className="flex gap-3">
                                                  <button onClick={() => handleDelivery(item, 'failed')} className="flex-1 btn-delivery btn-fail"><AlertTriangle size={20} className="mb-1"/> Falha</button>
                                                  <button onClick={() => handleDeliveryClick(item, nextGroup.items)} className="flex-[1.5] btn-delivery btn-success"><Check size={24} className="mb-1"/> Entregue</button>
                                              </div>
                                          </div>
                                      )
                                  })}
                              </div>
                          </div>
                      )}

                      {/* LISTA COMPLETA */}
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1 mb-3">Próximos Locais</h4>
                      <div className="space-y-3">
                          {groupedStops.map((g, idx) => {
                              if (nextGroup && g.id === nextGroup.id && activeRoute.optimized) return null;
                              return (
                                  <div key={g.id} className={`enterprise-card p-4 flex gap-4 items-center bg-white ${g.status!=='pending'?'opacity-50 grayscale':''}`}>
                                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${g.status==='success'?'bg-green-100 text-green-700':'bg-slate-100 text-slate-600'}`}>
                                          {g.status==='success'?<Check size={14}/>:idx+1}
                                      </div>
                                      <div className="flex-1 min-w-0">
                                          <h4 className="font-bold text-sm text-slate-800 truncate">{g.mainName}</h4>
                                          <p className="text-xs text-slate-500 truncate">{g.items.length} pacotes</p>
                                      </div>
                                      <div className={`h-2 w-2 rounded-full ${g.status==='pending'?'bg-blue-500':'bg-slate-300'}`}></div>
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
    print(f"🚀 ATUALIZAÇÃO V52 (ENTERPRISE EDITION) - {APP_NAME}")
    
    final_app_jsx = files_content['src/App.jsx'].replace("__GOOGLE_KEY__", GOOGLE_MAPS_KEY)
    
    print("\n📝 Atualizando arquivos...")
    with open("src/App.jsx", 'w', encoding='utf-8') as f:
        f.write(final_app_jsx)
        
    with open("src/index.css", 'w', encoding='utf-8') as f:
        f.write(files_content['src/index.css'])

    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "feat: V52 Enterprise UI, Auto-Optimize & Visual Edit"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


