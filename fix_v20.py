import os
import shutil
import datetime
import subprocess

# --- CONFIGURAÇÕES ---
BACKUP_DIR = "backup"
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
CURRENT_BACKUP_PATH = os.path.join(BACKUP_DIR, f"update_v20_{TIMESTAMP}")

# CHAVE API
API_KEY_VALUE = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

# --- CONTEÚDO DO APP.JSX ---
APP_JSX_CONTENT = """import React, { useState, useEffect, useMemo } from 'react';
import { 
  Upload, Navigation, Trash2, Plus, ArrowLeft, Sliders, MapPin, 
  Package, Clock, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Check, RotateCcw
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { useJsApiLoader } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

import MapView from './components/MapView';
import RouteList from './components/RouteList';

const DB_KEY = 'mp_db_v58_pure_google';
const GOOGLE_KEY = "__API_KEY__";

// --- HELPERS ---
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
        const key = (safeStr(stop.name) || 'Sem Nome').toLowerCase();
        if (!seen.has(key)) {
            const g = groups[key];
            if (g) {
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

const calculateTotalMetrics = (stops) => {
    if (!Array.isArray(stops) || stops.length === 0) return { km: "0", time: "0h", remaining: 0 };
    
    let totalKm = 0;
    for (let i = 0; i < stops.length - 1; i++) {
        const p1 = stops[i];
        const p2 = stops[i+1];
        const R = 6371; 
        const dLat = (p2.lat - p1.lat) * Math.PI / 180;
        const dLon = (p2.lng - p1.lng) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(p1.lat * Math.PI / 180) * Math.cos(p2.lat * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
        totalKm += R * c;
    }

    const realKm = totalKm * 1.5; 
    const avgSpeed = 20; 
    const serviceTime = stops.length * 4; 
    const totalMin = (realKm / avgSpeed * 60) + serviceTime;
    
    const h = Math.floor(totalMin / 60);
    const m = Math.floor(totalMin % 60);
    
    return { 
        km: realKm.toFixed(1), 
        time: `${h}h ${m}m`,
        remaining: stops.filter(s => s.status === 'pending').length 
    };
};

// --- ALGORITMO 100% GOOGLE STEP-BY-STEP (V20) ---
const optimizePureGoogle = async (allLocations, startPos, updateProgress) => {
    let unvisited = [...allLocations];
    let finalChain = [];
    let currentOrigin = startPos;
    const service = new window.google.maps.DirectionsService();

    // Loop até acabar todas as paradas
    while (unvisited.length > 0) {
        
        // Se só sobrou 1, adiciona e acaba
        if (unvisited.length === 1) {
            finalChain.push(unvisited[0]);
            break;
        }

        // PASSO 1: PRÉ-SELEÇÃO GEOGRÁFICA
        // Pegamos os 10 vizinhos mais próximos em linha reta para serem os "Candidatos".
        unvisited.sort((a, b) => {
            const dA = Math.pow(a.lat - currentOrigin.lat, 2) + Math.pow(a.lng - currentOrigin.lng, 2);
            const dB = Math.pow(b.lat - currentOrigin.lat, 2) + Math.pow(b.lng - currentOrigin.lng, 2);
            return dA - dB;
        });

        const candidates = unvisited.slice(0, 10);
        
        // PASSO 2: PERGUNTA PRO GOOGLE
        // Definimos o último candidato (o mais longe dos 10) como 'Destination' técnico
        // e os outros 9 como 'Waypoints' intermediários.
        const dest = candidates[candidates.length - 1]; 
        const waypointsList = candidates.slice(0, -1);
        const waypoints = waypointsList.map(p => ({ location: { lat: p.lat, lng: p.lng }, stopover: true }));

        try {
            const res = await new Promise((resolve, reject) => {
                service.route({
                    origin: currentOrigin,
                    destination: dest, 
                    waypoints: waypoints, 
                    optimizeWaypoints: true, 
                    travelMode: 'DRIVING'
                }, (result, status) => {
                    if (status === 'OK') resolve(result);
                    else reject(status);
                });
            });

            // PASSO 3: A ESCOLHA DO VENCEDOR
            // O Google retornou a ordem otimizada dos waypoints.
            // Pegamos o PRIMEIRO ponto dessa ordem como o próximo passo ideal.
            const order = res.routes[0].waypoint_order;
            
            let winner = null;
            
            if (order && order.length > 0) {
                // order[0] é o índice no array 'waypointsList'
                const winnerIndex = order[0];
                winner = waypointsList[winnerIndex];
            } else {
                // Se a rota for direta ou algo der errado, pegamos o primeiro da lista
                winner = waypointsList[0];
            }

            // Se por acaso a lista de waypoints estava vazia (só tinha origem e dest), o winner é o dest
            if (!winner) winner = dest;

            // Adiciona na rota final
            finalChain.push(winner);

            // PASSO 4: ATUALIZAÇÃO
            // O vencedor vira a nova origem
            currentOrigin = winner;
            
            // Remove o vencedor da lista de não visitados
            unvisited = unvisited.filter(p => p.id !== winner.id);

            // Feedback visual no botão
            if (updateProgress) updateProgress(finalChain.length, allLocations.length);
            
            // Delay anti-ban do Google
            await new Promise(r => setTimeout(r, 450)); 

        } catch (e) {
            console.warn("Google API Fail, fallback nearest", e);
            // Fallback: pega o mais próximo matemático
            const fallback = candidates[0];
            finalChain.push(fallback);
            currentOrigin = fallback;
            unvisited = unvisited.filter(p => p.id !== fallback.id);
        }
    }

    return finalChain;
};

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); 
  const [newRouteName, setNewRouteName] = useState('');
  const [tempStops, setTempStops] = useState([]);
  const [importSummary, setImportSummary] = useState(null);
  const [userPos, setUserPos] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [isOptimizing, setIsOptimizing] = useState(false);
  
  // Estado de progresso da otimização
  const [optimizeProgress, setOptimizeProgress] = useState(null);

  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
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
            
            const name = safeStr(k['stop'] || k['parada'] || k['cliente'] || k['nome'] || k['razao social'] || `Parada ${i+1}`);
            const address = safeStr(k['destination address'] || k['endereço'] || k['endereco'] || k['rua'] || '---');
            
            return {
                id: Date.now() + i + Math.random(),
                name: name,
                recipient: safeStr(k['recebedor'] || k['contato'] || k['destinatario'] || 'Recebedor'),
                address: address,
                lat: parseFloat(k['latitude'] || k['lat'] || 0),
                lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                status: 'pending'
            };
        }).filter(i => i.lat !== 0);
        
        if (norm.length > 0) {
            setTempStops(norm);
            setImportSummary({ count: norm.length, first: norm[0].address });
        }
    };
    if(file.name.endsWith('.csv')) { reader.onload = e => processData(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = e => processData(e.target.result, true); reader.readAsBinaryString(file); }
  };

  const createRoute = () => {
      if(!newRouteName.trim() || !tempStops.length) return;
      setRoutes([{ id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops, optimized: false }, ...routes]);
      setNewRouteName(''); setTempStops([]); setImportSummary(null); setView('home');
  };

  const deleteRoute = () => {
      if (!activeRouteId) return;
      if (confirm("ATENÇÃO: Deseja apagar esta rota permanentemente?")) {
          const updated = routes.filter(r => r.id !== activeRouteId);
          setRoutes(updated);
          setView('home');
          setActiveRouteId(null);
      }
  };

  const resetRoute = () => {
      if (!activeRouteId) return;
      if (confirm("Reiniciar todo o progresso desta rota? Todas as entregas voltarão para pendente.")) {
          const rIdx = routes.findIndex(r => r.id === activeRouteId);
          const updated = [...routes];
          updated[rIdx].stops = updated[rIdx].stops.map(s => ({...s, status: 'pending'}));
          setRoutes(updated);
          showToast("Rota reiniciada!", "info");
      }
  };

  const updateAddress = async (stopId, newAddress) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      
      const updatedRoutes = [...routes];
      const stopIndex = updatedRoutes[rIdx].stops.findIndex(s => s.id === stopId);
      
      if (stopIndex !== -1) {
          updatedRoutes[rIdx].stops[stopIndex].address = newAddress;
          setRoutes(updatedRoutes);
          
          try {
              const response = await fetch(`https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(newAddress)}&key=${GOOGLE_KEY}`);
              const data = await response.json();
              if (data.status === 'OK' && data.results.length > 0) {
                  const loc = data.results[0].geometry.location;
                  updatedRoutes[rIdx].stops[stopIndex].lat = loc.lat;
                  updatedRoutes[rIdx].stops[stopIndex].lng = loc.lng;
                  setRoutes(updatedRoutes); 
                  showToast("Endereço e Mapa Atualizados!");
              } else {
                  showToast("Texto atualizado (Mapa não achou)", "info");
              }
          } catch(e) {
              console.error(e);
          }
      }
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
      // Extrai apenas 1 representativo de cada grupo para mandar pro Google
      const locations = groups.map(g => ({ ...g.items[0] })); 
      
      try {
          setOptimizeProgress("0%");
          // NOVA OTIMIZAÇÃO: PURE GOOGLE STEP-BY-STEP
          const optimizedLocs = await optimizePureGoogle(locations, pos, (current, total) => {
              setOptimizeProgress(`${Math.round(((current + 1) / total) * 100)}%`);
          });
          
          const flatOptimized = [];
          optimizedLocs.forEach(optLoc => {
             const group = groups.find(g => g.items[0].id === optLoc.id);
             if(group) flatOptimized.push(...group.items);
          });
          
          const updated = [...routes];
          updated[rIdx] = { ...updated[rIdx], stops: [...done, ...flatOptimized], optimized: true };
          setRoutes(updated);
          showToast("Otimização Google 100% Concluída!");
      } catch(e) { alert("Erro: " + e); }
      setIsOptimizing(false);
      setOptimizeProgress(null);
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
          if (status === 'success') showToast("Pacote Entregue!");
      }
  };

  const openNav = (lat, lng) => {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const toggleGroup = (id) => setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));

  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');
  
  const metrics = useMemo(() => {
      if (!activeRoute) return { km: "0", time: "0h", remaining: 0 };
      return calculateTotalMetrics(activeRoute.stops);
  }, [activeRoute]);

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
      } else {
          setDirectionsResponse(null);
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
              <input type="text" className="w-full p-4 bg-slate-50 rounded-xl border border-slate-200" placeholder="Nome da Rota" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
              
              {!importSummary ? (
                  <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-blue-200 bg-blue-50 rounded-xl cursor-pointer">
                      <Upload className="mb-2 text-blue-500"/> 
                      <span className="text-sm font-bold text-blue-600">Toque para Importar Planilha</span>
                      <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/>
                  </label>
              ) : (
                  <div className="w-full bg-green-50 border border-green-200 rounded-xl p-6 text-center animate-in fade-in zoom-in">
                      <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                          <Check className="text-green-600" size={24}/>
                      </div>
                      <h3 className="text-green-800 font-bold text-lg">Importação Sucesso!</h3>
                      <p className="text-green-600 mt-1">{importSummary.count} pacotes carregados</p>
                      <button onClick={() => {setImportSummary(null); setTempStops([]);}} className="text-xs text-red-400 mt-4 underline">Cancelar / Trocar Arquivo</button>
                  </div>
              )}
          </div>
          <button onClick={createRoute} disabled={!importSummary} className={`w-full py-5 rounded-2xl font-bold text-lg shadow-xl transition-all ${importSummary ? 'bg-slate-900 text-white' : 'bg-slate-200 text-slate-400'}`}>Salvar Rota</button>
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
                      <button onClick={resetRoute} className="p-2 rounded-full bg-slate-100 text-slate-600 shadow-sm">
                          <RotateCcw size={20}/>
                      </button>
                      <button onClick={deleteRoute} className="p-2 rounded-full bg-red-50 text-red-500 shadow-sm">
                          <Trash2 size={20}/>
                      </button>
                      <button onClick={() => setShowMap(!showMap)} className={`p-2 rounded-full ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'}`}>
                          {showMap ? <List size={20}/> : <MapIcon size={20}/>}
                      </button>
                  </div>
              </div>
              
              {!showMap && (
                  <div className="relative mb-4">
                      <Search size={18} className="absolute left-3 top-3 text-slate-400"/>
                      <input type="text" placeholder="Buscar..." className="w-full pl-10 pr-4 py-2.5 rounded-xl search-input text-sm font-medium outline-none" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}/>
                      {searchQuery && <button onClick={() => setSearchQuery('')} className="absolute right-3 top-3 text-slate-400"><X size={16}/></button>}
                  </div>
              )}

              {activeRoute.optimized && realMetrics && !showMap && (
                  <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4">
                      <div className="flex items-center gap-2"><MapIcon size={16} className="text-blue-500"/><span className="text-xs font-bold">{realMetrics.dist}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Clock size={16} className="text-orange-500"/><span className="text-xs font-bold">{realMetrics.time}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Box size={16} className="text-green-500"/><span className="text-xs font-bold">{activeRoute.stops.filter(s => s.status === 'pending').length} rest.</span></div>
                  </div>
              )}
              
              {!searchQuery && !showMap && (
                  <div className="flex gap-3">
                      <button 
                          onClick={optimizeRoute} 
                          disabled={isOptimizing} 
                          className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 text-white shadow-lg shadow-blue-200 transition-all ${!activeRoute.optimized ? 'bg-blue-600 animate-pulse' : 'bg-slate-700'}`}
                      >
                          {isOptimizing ? (
                              <div className="flex items-center gap-2">
                                <Loader2 className="animate-spin" size={18}/>
                                <span>{optimizeProgress ? `Google IA ${optimizeProgress}` : 'Calculando...'}</span>
                              </div>
                          ) : (
                              <div className="flex items-center gap-2">
                                <Sliders size={18}/> <span>Otimizar</span>
                              </div>
                          )}
                      </button>
                      
                      {nextGroup && (
                          <button 
                              onClick={() => openNav(nextGroup.lat, nextGroup.lng)} 
                              disabled={!activeRoute.optimized} 
                              className={`flex-[1.5] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 text-white shadow-lg shadow-green-200 transition-all ${activeRoute.optimized ? 'bg-green-600' : 'bg-gray-300 cursor-not-allowed'}`}
                          >
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
                  toggleGroup={toggleGroup}
                  setStatus={setStatus}
                  onReorder={handleReorder}
                  onEditAddress={updateAddress}
              />
          )}
      </div>
  );
}
"""

FILES_TO_WRITE = {
    "src/App.jsx": APP_JSX_CONTENT.replace("__API_KEY__", API_KEY_VALUE)
}

def write_files():
    if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)
    os.makedirs(CURRENT_BACKUP_PATH)
    
    if os.path.exists("src/App.jsx"): shutil.copy2("src/App.jsx", CURRENT_BACKUP_PATH)

    for path, content in FILES_TO_WRITE.items():
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name): os.makedirs(dir_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Escrevendo {path}")

def main():
    print(f"--- Iniciando V20 (100% Google Step-by-Step) {TIMESTAMP} ---")
    write_files()
    
    print("--- Git Push ---")
    subprocess.run("git add .", shell=True)
    subprocess.run(f'git commit -m "Update V20: Otimização Pure Google Step-by-Step - {TIMESTAMP}"', shell=True)
    subprocess.run("git push", shell=True)
    
    os.remove(__file__)
    print("Concluído.")

if __name__ == "__main__":
    main()


