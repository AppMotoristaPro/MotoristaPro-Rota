import os
import shutil
import datetime
import subprocess

# --- CONFIGURAÇÕES ---
BACKUP_DIR = "backup"
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
CURRENT_BACKUP_PATH = os.path.join(BACKUP_DIR, f"update_v8_{TIMESTAMP}")

# --- CONTEÚDO DOS ARQUIVOS (TEXTO PURO) ---

# 1. MAP VIEW
CODE_MAP_VIEW = """import React, { useState } from 'react';
import { GoogleMap, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import { Loader2, Navigation, Package, MapPin } from 'lucide-react';

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = {
    disableDefaultUI: true,
    zoomControl: false,
    clickableIcons: false
};

const getMarkerIcon = (status, isCurrent) => {
    let fillColor = "#3B82F6"; // Azul
    if (status === 'success') fillColor = "#10B981"; // Verde
    if (status === 'failed') fillColor = "#EF4444"; // Vermelho
    if (isCurrent) fillColor = "#0F172A"; // Preto (Atual)

    return {
        path: "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z",
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 2,
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2.2 : 1.6,
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

export default function MapView({ 
    userPos, 
    groupedStops, 
    directionsResponse, 
    nextGroup, 
    openNav,
    isLoaded
}) {
    const [selectedMarker, setSelectedMarker] = useState(null);
    const [mapInstance, setMapInstance] = useState(null);

    if (!isLoaded) return <div className="flex h-full items-center justify-center bg-slate-100"><Loader2 className="animate-spin text-slate-400"/></div>;

    return (
        <GoogleMap
            mapContainerStyle={mapContainerStyle}
            center={userPos || { lat: -23.55, lng: -46.63 }}
            zoom={15}
            options={mapOptions}
            onLoad={setMapInstance}
        >
            {directionsResponse && (
                <DirectionsRenderer 
                    directions={directionsResponse} 
                    options={{ 
                        suppressMarkers: true, 
                        polylineOptions: { strokeColor: "#2563EB", strokeWeight: 6, strokeOpacity: 0.8 } 
                    }} 
                />
            )}
            
            {groupedStops.map((g, idx) => (
                <MarkerF 
                    key={g.id} 
                    position={{ lat: g.lat, lng: g.lng }}
                    label={{ text: String(idx + 1), color: "white", fontSize: "11px", fontWeight: "bold" }}
                    icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id)}
                    onClick={() => setSelectedMarker(g)}
                    zIndex={nextGroup && g.id === nextGroup.id ? 1000 : 1}
                />
            ))}
            
            {userPos && (
                <MarkerF 
                    position={{ lat: userPos.lat, lng: userPos.lng }} 
                    icon={{
                        path: window.google.maps.SymbolPath.CIRCLE,
                        scale: 8,
                        fillColor: "#3B82F6",
                        fillOpacity: 1,
                        strokeWeight: 3,
                        strokeColor: "white",
                    }}
                    zIndex={2000}
                />
            )}

            {selectedMarker && (
                <InfoWindowF 
                    position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }} 
                    onCloseClick={() => setSelectedMarker(null)}
                >
                    <div className="p-1 min-w-[220px]">
                        <div className="flex items-start gap-2 mb-2 border-b border-gray-100 pb-2">
                            <div className="bg-slate-100 p-1.5 rounded-full mt-0.5"><MapPin size={16} className="text-slate-600"/></div>
                            <div>
                                <h3 className="font-bold text-sm text-slate-800 leading-tight">Parada: {selectedMarker.mainName}</h3>
                                <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{selectedMarker.mainAddress}</p>
                            </div>
                        </div>
                        
                        <div className="bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-2 mb-3 w-fit">
                            <Package size={14}/> {selectedMarker.items.length} pacotes aqui
                        </div>

                        <button 
                            onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} 
                            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-lg text-xs font-bold uppercase tracking-wide flex items-center justify-center gap-2 shadow-sm active:scale-95 transition-all"
                        >
                            <Navigation size={14}/> Navegar
                        </button>
                    </div>
                </InfoWindowF>
            )}
        </GoogleMap>
    );
}
"""

# 2. ROUTE LIST
CODE_ROUTE_LIST = """import React, { useState } from 'react';
import { Check, ChevronUp, ChevronDown, Layers, Edit3, Save, Package } from 'lucide-react';

export default function RouteList(props) {
    const { 
        groupedStops = [], 
        nextGroup = null, 
        activeRoute = {}, 
        searchQuery = '', 
        expandedGroups = {}, 
        toggleGroup, 
        setStatus,
        onReorder 
    } = props;

    const [isEditing, setIsEditing] = useState(false);
    const [editValues, setEditValues] = useState({});

    const safeStr = (val) => val ? String(val).trim() : '';

    const setAllStatus = (items, status) => {
        items.forEach(item => {
            if (item.status === 'pending') setStatus(item.id, status);
        });
    };

    const filteredGroups = !searchQuery ? groupedStops : groupedStops.filter(g => 
        safeStr(g.mainName).toLowerCase().includes(searchQuery.toLowerCase()) || 
        safeStr(g.mainAddress).toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleInputChange = (groupId, value) => {
        setEditValues(prev => ({...prev, [groupId]: value}));
    };

    const handleInputBlur = (group, oldIndex) => {
        const newIndex = parseInt(editValues[group.id]);
        if (!isNaN(newIndex) && newIndex > 0 && newIndex <= groupedStops.length) {
            onReorder(oldIndex, newIndex - 1); 
        }
        setEditValues(prev => ({...prev, [group.id]: ''}));
    };

    return (
        <div className="flex-1 overflow-y-auto px-4 pt-4 pb-safe space-y-3 relative bg-slate-50">
            
            {!searchQuery && (
                <div className="flex justify-end mb-2">
                    <button 
                        onClick={() => setIsEditing(!isEditing)} 
                        className={`text-[10px] font-bold px-3 py-1.5 rounded-full flex items-center gap-2 transition uppercase tracking-wider
                        ${isEditing ? 'bg-slate-900 text-white shadow-lg' : 'bg-white text-slate-500 border border-slate-200'}`}
                    >
                        {isEditing ? <Save size={12}/> : <Edit3 size={12}/>}
                        {isEditing ? 'Salvar Ordem' : 'Editar Sequência'}
                    </button>
                </div>
            )}

            {!isEditing && !searchQuery && nextGroup && activeRoute.optimized && (
                <div className="bg-white rounded-2xl p-5 border-l-4 border-blue-600 shadow-md relative overflow-hidden mb-6">
                    <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl uppercase">Próxima Parada</div>
                    
                    <h3 className="text-lg font-bold text-slate-900 leading-tight mb-1 pr-20">Parada: {safeStr(nextGroup.mainName)}</h3>
                    <p className="text-xs text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                    
                    {nextGroup.items.filter(i => i.status === 'pending').length > 1 && (
                        <button 
                            onClick={() => setAllStatus(nextGroup.items, 'success')}
                            className="w-full mb-4 py-3 bg-blue-50 text-blue-700 rounded-xl text-xs font-bold flex items-center justify-center gap-2 border border-blue-100 active:scale-95 transition"
                        >
                            <Layers size={16}/> ENTREGAR TODOS ({nextGroup.items.filter(i => i.status === 'pending').length})
                        </button>
                    )}

                    <div className="space-y-3 border-t border-slate-100 pt-3">
                        {nextGroup.items.map((item, idx) => (
                            item.status === 'pending' && (
                                <div key={item.id} className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Package size={14} className="text-blue-400"/>
                                        <span className="text-xs font-bold text-slate-700">PACOTE {idx + 1}</span>
                                    </div>
                                    <p className="text-xs font-medium text-slate-600 mb-3 ml-6">{item.address}</p>
                                    <div className="flex gap-2">
                                        <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-3 bg-white border border-red-100 text-red-500 rounded-lg text-[10px] font-bold uppercase shadow-sm">Falha</button>
                                        <button onClick={() => setStatus(item.id, 'success')} className="flex-[2] py-3 bg-green-500 text-white rounded-lg text-[10px] font-bold uppercase shadow-md active:scale-95 transition">Entregue</button>
                                    </div>
                                </div>
                            )
                        ))}
                    </div>
                </div>
            )}

            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-1 mb-2">
                {isEditing ? 'Digite a nova posição' : 'Lista de Entregas'}
            </h4>
            
            {filteredGroups.map((group, idx) => (
                (!isEditing && !searchQuery && nextGroup && group.id === nextGroup.id && activeRoute.optimized) ? null : (
                    <div key={group.id} className={`bg-white rounded-xl shadow-sm border-l-4 overflow-hidden ${group.status === 'success' ? 'border-green-400 opacity-60' : 'border-slate-300'}`}>
                        <div onClick={() => !isEditing && toggleGroup && toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer active:bg-slate-50 transition">
                            
                            {isEditing ? (
                                <input 
                                    type="number" 
                                    className="w-10 h-10 bg-slate-100 rounded-lg text-center font-bold text-base outline-none border-2 border-transparent focus:border-blue-500 focus:bg-white transition-all"
                                    placeholder={idx + 1}
                                    value={editValues[group.id] !== undefined ? editValues[group.id] : ''}
                                    onChange={(e) => handleInputChange(group.id, e.target.value)}
                                    onBlur={() => handleInputBlur(group, idx)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleInputBlur(group, idx)}
                                    onClick={(e) => e.stopPropagation()}
                                />
                            ) : (
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                    {group.status === 'success' ? <Check size={14}/> : (idx + 1)}
                                </div>
                            )}

                            <div className="flex-1 min-w-0">
                                <h4 className="font-bold text-slate-800 text-sm truncate">Parada: {safeStr(group.mainName)}</h4>
                                <p className="text-[11px] text-slate-400 truncate mt-0.5">{group.items.length} pacote(s) • {safeStr(group.mainAddress)}</p>
                            </div>
                            
                            {!isEditing && group.items.length > 1 ? (expandedGroups[group.id] ? <ChevronUp size={16} className="text-slate-300"/> : <ChevronDown size={16} className="text-slate-300"/>) : null}
                        </div>
                        
                        {(expandedGroups[group.id] || (isEditing === false && group.items.length > 1 && expandedGroups[group.id])) && (
                            <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-2">
                                {group.items.map((item) => (
                                    <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                        <div className="mb-2">
                                            <span className="text-[10px] font-bold text-blue-500 block uppercase mb-0.5">Endereço</span>
                                            <span className="text-xs font-medium text-slate-700 block leading-tight">{item.address}</span>
                                        </div>
                                        {item.status === 'pending' ? (
                                            <div className="flex gap-2 w-full">
                                                <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-2 bg-white border border-red-200 text-red-500 rounded-lg font-bold text-[10px] uppercase">Falha</button>
                                                <button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-2 bg-green-500 text-white rounded-lg font-bold text-[10px] uppercase shadow-sm">Entregue</button>
                                            </div>
                                        ) : (
                                            <span className={`text-[10px] font-bold px-2 py-1 rounded w-fit ${item.status==='success'?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>
                                                {item.status === 'success' ? 'ENTREGUE' : 'NÃO ENTREGUE'}
                                            </span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )
            ))}
            <div className="h-12"></div>
        </div>
    );
}
"""

# 3. APP PRINCIPAL
CODE_APP = """import React, { useState, useEffect, useMemo } from 'react';
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

const DB_KEY = 'mp_db_v51_platinum';
const GOOGLE_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU";

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

// Item 6: Otimização Precisa
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
            const res = await new Promise((resolve, reject) => {
                service.route({
                    origin: currentPos,
                    destination: batch[batch.length - 1], 
                    waypoints: waypoints,
                    optimizeWaypoints: true,
                    travelMode: 'DRIVING'
                }, (result, status) => {
                    if (status === 'OK') resolve(result);
                    else reject(status);
                });
            });

            const order = res.routes[0].waypoint_order;
            const orderedBatch = order.map(idx => batch[idx]);
            finalRoute.push(...orderedBatch);
            
            currentPos = orderedBatch[orderedBatch.length - 1];
            await new Promise(r => setTimeout(r, 600));

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
  
  const [importSummary, setImportSummary] = useState(null);

  const [userPos, setUserPos] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  const [directionsResponse, setDirectionsResponse] = useState(null);
  // Item 7: Estado para métricas reais da API
  const [realMetrics, setRealMetrics] = useState({ dist: "0 km", time: "0 min" });

  const { isLoaded } = useJsApiLoader({
    id: 'google-map-script',
    googleMapsApiKey: GOOGLE_KEY
  });

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
      const locations = groups.map(g => ({ ...g.items[0] })); 
      
      try {
          const optimizedLocs = await optimizeRollingChain(locations, pos);
          
          const flatOptimized = [];
          optimizedLocs.forEach(optLoc => {
             const group = groups.find(g => g.items[0].id === optLoc.id);
             if(group) flatOptimized.push(...group.items);
          });
          
          const updated = [...routes];
          updated[rIdx] = { ...updated[rIdx], stops: [...done, ...flatOptimized], optimized: true };
          setRoutes(updated);
          showToast("Otimizado com Sucesso!");
      } catch(e) { alert("Erro: " + e); }
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
  
  // Google Directions Metrics (Item 5, 7)
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
                  // Soma todas as legs da rota para métrica precisa
                  const route = res.routes[0];
                  let totalDist = 0;
                  let totalDur = 0;
                  if (route.legs) {
                      route.legs.forEach(leg => {
                          totalDist += leg.distance.value;
                          totalDur += leg.duration.value;
                      });
                  }
                  // Converte
                  const km = (totalDist / 1000).toFixed(1) + " km";
                  const hours = Math.floor(totalDur / 3600);
                  const mins = Math.floor((totalDur % 3600) / 60);
                  const time = (hours > 0 ? `${hours}h ` : "") + `${mins}min`;
                  
                  setRealMetrics({ dist: km, time: time });
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
                      <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="modern-card p-5 cursor-pointer">
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
                      <button onClick={() => setShowMap(!showMap)} className={`p-2 rounded-full ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'}`}>{showMap ? <List size={20}/> : <MapIcon size={20}/>}</button>
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

              {/* Display de Métricas Reais do Google */}
              {activeRoute.optimized && !searchQuery && !showMap && (
                  <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4">
                      <div className="flex items-center gap-2"><MapIcon size={16} className="text-blue-500"/><span className="text-xs font-bold">{realMetrics ? realMetrics.dist : "..."}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Clock size={16} className="text-orange-500"/><span className="text-xs font-bold">{realMetrics ? realMetrics.time : "..."}</span></div>
                      <div className="w-px h-4 bg-slate-200"></div>
                      <div className="flex items-center gap-2"><Box size={16} className="text-green-500"/><span className="text-xs font-bold">{activeRoute.stops.filter(s => s.status === 'pending').length} rest.</span></div>
                  </div>
              )}
              
              {!searchQuery && !showMap && (
                  <div className="flex gap-3">
                      <button onClick={optimizeRoute} disabled={isOptimizing} className={`flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition ${!activeRoute.optimized ? 'btn-highlight animate-pulse' : 'btn-secondary'}`}>
                          {isOptimizing ? <Loader2 className="animate-spin" size={18}/> : <Sliders size={18}/>} {isOptimizing ? '...' : 'Otimizar'}
                      </button>
                      {nextGroup && (
                          <button onClick={() => openNav(nextGroup.lat, nextGroup.lng)} disabled={!activeRoute.optimized} className={`flex-[1.5] py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition ${activeRoute.optimized ? 'btn-highlight shadow-lg' : 'bg-slate-100 text-slate-300 cursor-not-allowed'}`}>
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
              />
          )}
      </div>
  );
}
"""

FILES_TO_WRITE = {
    "src/components/MapView.jsx": CODE_MAP_VIEW,
    "src/components/RouteList.jsx": CODE_ROUTE_LIST,
    "src/App.jsx": CODE_APP
}

def delete_env():
    if os.path.exists(".env"):
        os.remove(".env")
        print("Arquivo .env deletado.")

def write_files():
    for path, content in FILES_TO_WRITE.items():
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name): os.makedirs(dir_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Escrevendo {path}")

def main():
    print(f"--- Iniciando Fix V8 {TIMESTAMP} ---")
    if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)
    os.makedirs(CURRENT_BACKUP_PATH)
    
    # Backup
    for f in ["src/App.jsx", "src/components/RouteList.jsx", "src/components/MapView.jsx"]:
        if os.path.exists(f): shutil.copy2(f, CURRENT_BACKUP_PATH)

    delete_env()
    write_files()

    print("--- Git Push ---")
    subprocess.run("git add .", shell=True)
    subprocess.run(f'git commit -m "Fix V8: Syntax Fix & Google Metrics - {TIMESTAMP}"', shell=True)
    subprocess.run("git push", shell=True)

    print("--- Limpeza ---")
    os.remove(__file__)
    print("Concluído.")

if __name__ == "__main__":
    main()


