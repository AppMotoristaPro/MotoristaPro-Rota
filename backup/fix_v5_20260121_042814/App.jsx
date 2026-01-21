import React, { useState, useEffect, useMemo } from 'react';
import { 
  Upload, Navigation, Trash2, Plus, ArrowLeft, Sliders, MapPin, 
  Package, Clock, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { useJsApiLoader } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

import MapView from './components/MapView';
import RouteList from './components/RouteList';

const DB_KEY = 'mp_db_v32_metrics';
const GOOGLE_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

// --- HELPERS ---
const safeStr = (val) => val ? String(val).trim() : '';

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
    
    // Preserva ordem original
    const ordered = [];
    const seen = new Set();
    stops.forEach(stop => {
        const key = (safeStr(stop.name) || 'Sem Nome').toLowerCase();
        if (!seen.has(key)) {
            const g = groups[key];
            if(g) {
                // Lógica de Status do Grupo
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

// Otimizador
const optimizeRollingChain = async (allStops, startPos) => {
    let unvisited = [...allStops];
    let finalRoute = [];
    let currentPos = startPos;
    const service = new window.google.maps.DirectionsService();

    while (unvisited.length > 0) {
        unvisited.sort((a, b) => {
            const dA = Math.pow(a.lat - currentPos.lat, 2) + Math.pow(a.lng - currentPos.lng, 2);
            const dB = Math.pow(b.lat - currentPos.lat, 2) + Math.pow(b.lng - currentPos.lng, 2);
            return dA - dB;
        });

        const batch = unvisited.slice(0, 23);
        unvisited = unvisited.slice(23);
        const waypoints = batch.map(p => ({ location: { lat: p.lat, lng: p.lng }, stopover: true }));
        
        try {
            const res = await service.route({
                origin: currentPos,
                destination: batch[batch.length - 1], 
                waypoints: waypoints,
                optimizeWaypoints: true,
                travelMode: 'DRIVING'
            });
            const order = res.routes[0].waypoint_order;
            const orderedBatch = order.map(idx => batch[idx]);
            finalRoute.push(...orderedBatch);
            currentPos = orderedBatch[orderedBatch.length - 1];
            await new Promise(r => setTimeout(r, 400));
        } catch (e) {
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
  const [expandedGroups, setExpandedGroups] = useState({});
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  
  // Directions API Response
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

  // --- ARQUIVOS ---
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
                name: safeStr(k['stop'] || k['cliente'] || `Parada ${i+1}`),
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

  // --- LOGICA DE EDIÇÃO MANUAL (Item 4) ---
  const handleReorder = (oldGroupIndex, newGroupIndex) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      
      const currentStops = [...routes[rIdx].stops];
      const groups = groupStopsByStopName(currentStops); // Pega os grupos atuais
      
      // Validação de índices
      if(newGroupIndex < 0 || newGroupIndex >= groups.length || oldGroupIndex < 0 || oldGroupIndex >= groups.length) return;

      const movingGroup = groups[oldGroupIndex];
      
      // Remove todos os itens do grupo da lista plana original
      const remainingStops = currentStops.filter(s => !movingGroup.items.some(i => i.id === s.id));
      
      // Precisamos encontrar onde inserir na lista plana.
      // A estratégia é: pegar o "grupo alvo" (onde queremos inserir) e achar o índice do primeiro item dele na lista plana.
      const targetGroup = groups[newGroupIndex];
      const targetItemIndex = remainingStops.findIndex(s => targetGroup.items.some(i => i.id === s.id));
      
      // Insere os itens do grupo movido na nova posição
      let newStopsList = [];
      if (newGroupIndex > oldGroupIndex) {
           // Movendo para baixo: insere DEPOIS do grupo alvo
           // Achar o fim do grupo alvo
           const targetLastIndex = remainingStops.reduce((last, curr, idx) => targetGroup.items.some(i => i.id === curr.id) ? idx : last, -1);
           newStopsList = [
               ...remainingStops.slice(0, targetLastIndex + 1),
               ...movingGroup.items,
               ...remainingStops.slice(targetLastIndex + 1)
           ];
      } else {
           // Movendo para cima: insere ANTES do grupo alvo
           const targetFirstIndex = remainingStops.findIndex(s => targetGroup.items.some(i => i.id === s.id));
           newStopsList = [
               ...remainingStops.slice(0, targetFirstIndex),
               ...movingGroup.items,
               ...remainingStops.slice(targetFirstIndex)
           ];
      }

      const updatedRoutes = [...routes];
      updatedRoutes[rIdx].stops = newStopsList;
      setRoutes(updatedRoutes);
      showToast("Sequência Alterada!");
  };

  const optimizeRoute = async () => {
      setIsOptimizing(true);
      let pos = userPos || await getCurrentLocation(true);
      if (!pos) { setIsOptimizing(false); return alert("Sem GPS!"); }

      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const currentRoute = routes[rIdx];
      const pending = currentRoute.stops.filter(s => s.status === 'pending');
      const done = currentRoute.stops.filter(s => s.status !== 'pending');
      
      // Agrupa para otimizar locais, não pacotes
      const groups = groupStopsByStopName(pending);
      const locations = groups.map(g => ({ lat: g.lat, lng: g.lng, items: g.items }));
      
      try {
          const optimizedLocs = await optimizeRollingChain(locations, pos);
          const flatOptimized = optimizedLocs.flatMap(l => l.items); // Desagrupa de volta para lista plana
          
          const updated = [...routes];
          updated[rIdx] = { ...updated[rIdx], stops: [...done, ...flatOptimized], optimized: true };
          setRoutes(updated);
          showToast("Otimizado com Google Maps!");
      } catch(e) { alert("Erro ao otimizar: " + e); }
      setIsOptimizing(false);
  };

  const setStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const updated = [...routes];
      const sIdx = updated[rIdx].stops.findIndex(s => s.id === stopId);
      if (sIdx !== -1) {
          updated[rIdx].stops[sIdx].status = status;
          setRoutes(updated);
          if (status === 'success') showToast("Entregue!");
      }
  };

  const openNav = (lat, lng) => {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');

  // --- ITEM 5: MÉTRICAS REAIS ---
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
                  // Extrai dados reais
                  const leg = res.routes[0].legs[0];
                  if(leg) {
                      setRealMetrics({
                          dist: leg.distance.text,
                          time: leg.duration.text
                      });
                  }
              }
          });
      }
  }, [nextGroup?.id, userPos, isLoaded]);

  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <div className="flex justify-between items-center mb-8">
              <h1 className="text-3xl font-bold text-slate-900">Rotas</h1>
              <div className="bg-white p-2 rounded-full shadow-sm"><Package className="text-slate-400"/></div>
          </div>
          {routes.map(r => (
              <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="modern-card p-5 cursor-pointer mb-4">
                  <h3 className="font-bold text-lg">{safeStr(r.name)}</h3>
                  <div className="flex gap-4 text-sm text-slate-500 mt-2">
                      <span>{r.stops.length} vols</span>
                      {r.optimized && <span className="text-green-600 font-bold">Otimizada</span>}
                  </div>
              </div>
          ))}
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center"><Plus size={32}/></button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-white flex flex-col p-6">
          <button onClick={() => setView('home')} className="self-start mb-6"><ArrowLeft/></button>
          <h2 className="text-2xl font-bold mb-8">Nova Rota</h2>
          <div className="space-y-6 flex-1">
              <input type="text" className="w-full p-4 bg-slate-50 rounded-xl" placeholder="Nome" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
              <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl bg-slate-50">
                  <Upload className="mb-2 text-slate-400"/> <span className="text-sm font-bold text-slate-500">Importar</span>
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
          
          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-4 flex-1 text-center">{safeStr(activeRoute.name)}</h2>
                  <div className="flex gap-2">
                      <button onClick={() => setShowMap(!showMap)} className={`p-2 rounded-full ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'}`}>{showMap ? <List size={20}/> : <MapIcon size={20}/>}</button>
                      <button onClick={() => {if(confirm("Excluir?")) { setRoutes(routes.filter(r => r.id !== activeRoute.id)); setView('home'); }}}><Trash2 size={20} className="text-red-400"/></button>
                  </div>
              </div>
              
              {/* MÉTRICAS REAIS DO GOOGLE */}
              {activeRoute.optimized && realMetrics && !showMap && (
                  <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4">
                      <div className="flex items-center gap-2"><MapIcon size={16} className="text-blue-500"/><span className="text-xs font-bold">{realMetrics.dist}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Clock size={16} className="text-orange-500"/><span className="text-xs font-bold">{realMetrics.time}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Box size={16} className="text-green-500"/><span className="text-xs font-bold">{activeRoute.stops.filter(s => s.status === 'pending').length} rest.</span></div>
                  </div>
              )}
              
              {!showMap && (
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
                  onReorder={handleReorder} // NOVA PROP
              />
          )}
      </div>
  );
}
