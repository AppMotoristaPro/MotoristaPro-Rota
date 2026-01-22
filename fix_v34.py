import os
import shutil
import datetime
import subprocess

# --- CONFIGURAÇÕES ---
BACKUP_DIR = "backup"
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
CURRENT_BACKUP_PATH = os.path.join(BACKUP_DIR, f"update_v34_{TIMESTAMP}")

# CHAVE API
API_KEY_VALUE = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

# --- 1. MAP VIEW (FAIXA AMARELA OTIMIZADA + SEM EDITAR ENDEREÇO) ---
CODE_MAP_VIEW = """import React, { useState } from 'react';
import { GoogleMap, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import { Loader2, Navigation, Package, MapPin, XCircle, CheckCircle, Layers, Edit3 } from 'lucide-react';

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = {
    disableDefaultUI: true,
    zoomControl: false,
    clickableIcons: false
};

const getMarkerIcon = (status, isCurrent, isReordering, reorderIndex) => {
    let fillColor = "#3B82F6"; // Azul
    let scale = 1.6;
    let strokeColor = "#FFFFFF";

    if (isReordering) {
        if (reorderIndex !== -1) {
            fillColor = "#10B981"; // Verde (Selecionado)
            scale = 1.8;
            strokeColor = "#000000";
        } else {
            fillColor = "#94A3B8"; // Cinza (Pendente)
        }
    } else {
        if (status === 'success') fillColor = "#10B981";
        if (status === 'failed') fillColor = "#EF4444";
        if (isCurrent) {
            fillColor = "#0F172A"; // Preto (Atual)
            scale = 2.2;
        }
    }

    return {
        path: "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z",
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 2,
        strokeColor: strokeColor,
        scale: scale,
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
    isLoaded,
    setStatus,
    setAllStatus,
    isReordering, 
    reorderList, 
    onMarkerClick,
    onStartReorder
}) {
    const [selectedMarker, setSelectedMarker] = useState(null);
    const [mapInstance, setMapInstance] = useState(null);

    if (!isLoaded) return <div className="flex h-full items-center justify-center bg-slate-100"><Loader2 className="animate-spin text-slate-400"/></div>;

    const handleMarkerClick = (group) => {
        if (isReordering) {
            onMarkerClick(group.id);
        } else {
            setSelectedMarker(group);
        }
    };

    return (
        <div className="relative w-full h-full">
            <GoogleMap
                mapContainerStyle={mapContainerStyle}
                center={userPos || { lat: -23.55, lng: -46.63 }}
                zoom={15}
                options={mapOptions}
                onLoad={setMapInstance}
            >
                {!isReordering && directionsResponse && (
                    <DirectionsRenderer 
                        directions={directionsResponse} 
                        options={{ 
                            suppressMarkers: true, 
                            polylineOptions: { strokeColor: "#2563EB", strokeWeight: 6, strokeOpacity: 0.8 } 
                        }} 
                    />
                )}
                
                {groupedStops.map((g, idx) => {
                    let labelText = null; 

                    if (isReordering) {
                        const newIndex = reorderList.indexOf(g.id);
                        if (newIndex !== -1) {
                            labelText = String(newIndex + 1); 
                        }
                    } else {
                        if (g.displayOrder !== null && g.displayOrder !== undefined) {
                            labelText = String(g.displayOrder);
                        }
                    }

                    return (
                        <MarkerF 
                            key={g.id} 
                            position={{ lat: g.lat, lng: g.lng }}
                            label={labelText ? { text: labelText, color: "white", fontSize: "11px", fontWeight: "bold" } : null}
                            icon={getMarkerIcon(
                                g.status, 
                                !isReordering && nextGroup && g.id === nextGroup.id,
                                isReordering,
                                isReordering ? reorderList.indexOf(g.id) : -1
                            )}
                            onClick={() => handleMarkerClick(g)}
                            zIndex={10}
                        />
                    )
                })}
                
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

                {selectedMarker && !isReordering && (
                    <InfoWindowF 
                        position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }} 
                        onCloseClick={() => setSelectedMarker(null)}
                    >
                        <div className="p-1 min-w-[240px] max-w-[260px]">
                            <div className="flex items-start gap-2 mb-2 border-b border-gray-100 pb-2">
                                <div className="bg-slate-100 p-1.5 rounded-full mt-0.5"><MapPin size={16} className="text-slate-600"/></div>
                                <div>
                                    <h3 className="font-bold text-sm text-slate-800 leading-tight">
                                        {selectedMarker.displayOrder ? `Parada ${selectedMarker.displayOrder}` : 'Sem ID Planilha'}
                                    </h3>
                                    <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{selectedMarker.mainName}</p>
                                </div>
                            </div>
                            
                            {selectedMarker.items.filter(i => i.status === 'pending').length > 1 && (
                                <button 
                                    onClick={() => {
                                        setAllStatus(selectedMarker.items, 'success');
                                        setSelectedMarker(null);
                                    }}
                                    className="w-full mb-2 bg-green-100 text-green-700 py-1.5 rounded border border-green-200 text-[10px] font-bold flex items-center justify-center gap-2"
                                >
                                    <Layers size={12}/> ENTREGAR TODOS ({selectedMarker.items.filter(i => i.status === 'pending').length})
                                </button>
                            )}

                            <div className="max-h-[150px] overflow-y-auto mb-2 space-y-2">
                                {selectedMarker.items.map((item) => (
                                    <div key={item.id} className="bg-slate-50 p-2 rounded border border-slate-100">
                                        <p className="text-[10px] font-bold text-slate-700 mb-1 truncate">{item.address}</p>
                                        
                                        {item.status === 'pending' ? (
                                            <div className="flex gap-1">
                                                <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 bg-white border border-red-200 text-red-500 py-1 rounded text-[10px] font-bold flex items-center justify-center gap-1"><XCircle size={10}/> Falha</button>
                                                <button onClick={() => setStatus(item.id, 'success')} className="flex-1 bg-green-500 text-white py-1 rounded text-[10px] font-bold flex items-center justify-center gap-1 shadow-sm"><CheckCircle size={10}/> Entregue</button>
                                            </div>
                                        ) : (
                                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded w-full block text-center ${item.status==='success'?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>{item.status === 'success' ? 'ENTREGUE' : 'FALHOU'}</span>
                                        )}
                                    </div>
                                ))}
                            </div>

                            <button onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg text-xs font-bold uppercase tracking-wide flex items-center justify-center gap-2 shadow-sm">
                                <Navigation size={14}/> Navegar
                            </button>
                        </div>
                    </InfoWindowF>
                )}
            </GoogleMap>

            {!isReordering && (
                <div className="absolute top-4 right-4 z-50">
                    <button 
                        onClick={onStartReorder}
                        className="bg-white text-slate-700 p-3 rounded-full shadow-lg border border-slate-200 flex items-center justify-center active:scale-95 transition"
                    >
                        <Edit3 size={20} />
                    </button>
                </div>
            )}
        </div>
    );
}
"""

# --- 2. ROUTE LIST (SEM LAPIS DE EDICAO) ---
CODE_ROUTE_LIST = """import React, { useState } from 'react';
import { Check, ChevronUp, ChevronDown, Layers, Package, Map as MapIcon } from 'lucide-react';

export default function RouteList(props) {
    const { 
        groupedStops = [], 
        nextGroup = null, 
        activeRoute = {}, 
        searchQuery = '', 
        expandedGroups = {}, 
        toggleGroup, 
        setStatus,
        onStartReorder
    } = props;

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

    return (
        <div className="flex-1 overflow-y-auto px-4 pt-4 pb-safe space-y-3 relative bg-slate-50">
            
            {!searchQuery && (
                <div className="flex justify-end mb-2">
                    <button 
                        onClick={onStartReorder} 
                        className="text-[10px] font-bold px-3 py-2 rounded-full flex items-center gap-2 transition uppercase tracking-wider bg-slate-900 text-white shadow-lg active:scale-95"
                    >
                        <MapIcon size={12}/> Editar Sequência no Mapa
                    </button>
                </div>
            )}

            {!searchQuery && nextGroup && (
                <div className="bg-white rounded-2xl p-5 border-l-4 border-blue-600 shadow-md relative overflow-hidden mb-6">
                    <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl uppercase">Próxima</div>
                    <h3 className="text-lg font-bold text-slate-900 leading-tight mb-1 pr-20">
                       {nextGroup.displayOrder ? `Parada ${nextGroup.displayOrder}` : 'Parada S/N'}
                    </h3>
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
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            <Package size={14} className="text-blue-400"/>
                                            <span className="text-xs font-bold text-slate-700">PACOTE {idx + 1}</span>
                                        </div>
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
                Lista de Entregas
            </h4>
            
            {filteredGroups.map((group) => (
                (!searchQuery && nextGroup && group.id === nextGroup.id) ? null : (
                    <div key={group.id} className={`bg-white rounded-xl shadow-sm border-l-4 overflow-hidden ${group.status === 'success' ? 'border-green-400 opacity-60' : 'border-slate-300'}`}>
                        <div onClick={() => toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer active:bg-slate-50 transition">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                {group.status === 'success' ? <Check size={14}/> : (idx + 1)}
                            </div>

                            <div className="flex-1 min-w-0">
                                <h4 className="font-bold text-slate-800 text-sm truncate">
                                    {group.displayOrder ? `Parada: ${group.displayOrder}` : group.mainName}
                                </h4>
                                <p className="text-[11px] text-slate-400 truncate mt-0.5">{group.items.length} pacotes • {safeStr(group.mainAddress)}</p>
                            </div>
                            
                            {group.items.length > 1 ? (expandedGroups[group.id] ? <ChevronUp size={16} className="text-slate-300"/> : <ChevronDown size={16} className="text-slate-300"/>) : null}
                        </div>
                        
                        {(expandedGroups[group.id] || (group.items.length > 1 && expandedGroups[group.id])) && (
                            <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-2">
                                {group.items.map((item) => (
                                    <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                        <div className="flex items-center justify-between mb-2">
                                            <div>
                                                <span className="text-[10px] font-bold text-blue-500 block uppercase mb-0.5">Endereço</span>
                                                <span className="text-xs font-medium text-slate-700 block leading-tight">{item.address}</span>
                                            </div>
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

# --- 3. APP (LÓGICA CORRIGIDA ITEM 1, 2 e 4) ---
APP_JSX_CONTENT = """import React, { useState, useEffect, useMemo } from 'react';
import { 
  Upload, Navigation, Trash2, Plus, ArrowLeft, MapPin, 
  Package, Clock, Box, Map as MapIcon, Loader2, Search, X, List, Check, RotateCcw, Undo2, Building, Calendar, Info, DollarSign
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { useJsApiLoader } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

import MapView from './components/MapView';
import RouteList from './components/RouteList';

const DB_KEY = 'mp_db_v69_financial';
const GOOGLE_KEY = "__API_KEY__";

const safeStr = (val) => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val).trim();
};

const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    
    stops.forEach(stop => {
        let key;
        if (stop.stopId === null || stop.stopId === undefined) {
            key = `unique_${stop.id}`; 
        } else {
            key = stop.name ? String(stop.name).trim().toLowerCase() : 'sem_nome';
        }
        
        if (!groups[key]) {
            groups[key] = {
                id: key, 
                lat: Number(stop.lat)||0, 
                lng: Number(stop.lng)||0,
                mainName: stop.name || "Endereço", 
                mainAddress: safeStr(stop.address),
                items: [], 
                status: 'pending',
                displayOrder: stop.stopId 
            };
        }
        groups[key].items.push(stop);
        
        if (stop.stopId && (!groups[key].displayOrder || stop.stopId < groups[key].displayOrder)) {
            groups[key].displayOrder = stop.stopId;
        }
    });
    
    const ordered = [];
    const seen = new Set();
    
    stops.forEach(stop => {
        let key;
        if (stop.stopId === null || stop.stopId === undefined) {
            key = `unique_${stop.id}`;
        } else {
            key = stop.name ? String(stop.name).trim().toLowerCase() : 'sem_nome';
        }

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

const getProgressText = (stops) => {
    if (!stops || stops.length === 0) return "0/0";
    const done = stops.filter(s => s.status === 'success').length;
    return `${done}/${stops.length}`;
};

const calculateProgressPercent = (stops) => {
    if (!stops || stops.length === 0) return 0;
    const done = stops.filter(s => s.status === 'success').length;
    return Math.round((done / stops.length) * 100);
};

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); 
  
  const [newRouteName, setNewRouteName] = useState('');
  const [newRouteCompany, setNewRouteCompany] = useState('');
  const [newRouteDate, setNewRouteDate] = useState(new Date().toISOString().split('T')[0]);
  const [newRouteValue, setNewRouteValue] = useState('');

  const [tempStops, setTempStops] = useState([]);
  const [importSummary, setImportSummary] = useState(null);
  const [userPos, setUserPos] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  const [directionsResponse, setDirectionsResponse] = useState(null);

  const [isReordering, setIsReordering] = useState(false);
  const [reorderList, setReorderList] = useState([]); 

  const { isLoaded } = useJsApiLoader({ id: 'google-map-script', googleMapsApiKey: GOOGLE_KEY });

  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) {}
    getCurrentLocation(true); 
  }, []);

  useEffect(() => { localStorage.setItem(DB_KEY, JSON.stringify(routes)); }, [routes]);

  const showToast = (msg, type = 'success') => {
      setToast({ msg, type });
      setTimeout(() => setToast(null), 2000);
  };

  const getCurrentLocation = async (silent = false) => {
      try {
          const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true });
          const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserPos(p);
          return p;
      } catch (e) {
          if (!silent) alert("Erro ao obter GPS: " + e.message);
          return null;
      }
  };

  const ensurePermissionAndPos = async () => {
      if (userPos) return userPos;
      if (confirm("O App precisa acessar sua localização para o mapa. Permitir?")) {
          return await getCurrentLocation(false);
      }
      return null;
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
            
            let stopId = null;
            const stopVal = k['stop'] || k['seq'] || k['ordem'] || k['sequence'];
            if (stopVal) {
                const parsed = parseInt(stopVal);
                if (!isNaN(parsed)) stopId = parsed;
            }

            return {
                id: Date.now() + i + Math.random(),
                name: name,
                stopId: stopId,
                recipient: safeStr(k['recebedor'] || k['contato'] || k['destinatario'] || 'Recebedor'),
                address: address,
                lat: parseFloat(k['latitude'] || k['lat'] || 0),
                lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                status: 'pending'
            };
        }).filter(i => i.lat !== 0);
        
        if (norm.some(i => i.stopId !== null)) {
            norm.sort((a, b) => (a.stopId || 9999) - (b.stopId || 9999));
        }

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
      setRoutes([{ 
          id: Date.now(), 
          name: newRouteName, 
          company: newRouteCompany, 
          date: newRouteDate, 
          value: newRouteValue, 
          stops: tempStops, 
          optimized: true 
      }, ...routes]);
      
      setNewRouteName(''); 
      setNewRouteCompany('');
      setNewRouteDate(new Date().toISOString().split('T')[0]);
      setNewRouteValue('');
      setTempStops([]); 
      setImportSummary(null); 
      setView('home');
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
      if (confirm("Reiniciar todo o progresso?")) {
          const rIdx = routes.findIndex(r => r.id === activeRouteId);
          const updated = [...routes];
          updated[rIdx].stops = updated[rIdx].stops.map(s => ({...s, status: 'pending'}));
          setRoutes(updated);
          showToast("Rota reiniciada!", "info");
      }
  };

  // ITEM 1: Correção - StartReorder apenas seta o estado, não toggle map
  const startReorderMode = () => {
      if (!showMap) setShowMap(true); // Garante que abre
      setIsReordering(true);
      setReorderList([]); 
      showToast("Selecione os pinos na ordem correta", "info");
  };

  const handleMapMarkerClick = (groupId) => {
      if (!isReordering) return;
      if (reorderList.includes(groupId)) return;
      setReorderList(prev => [...prev, groupId]);
  };

  const undoLastSelection = () => {
      if (reorderList.length === 0) return;
      setReorderList(prev => prev.slice(0, -1));
  };

  // ITEM 2: Validation check
  const saveReorder = () => {
      if (!isReordering) return;
      
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      const currentStops = [...routes[rIdx].stops];
      const groups = groupStopsByStopName(currentStops);
      
      // Validação: Tem que selecionar todos
      if (reorderList.length < groups.length) {
          const diff = groups.length - reorderList.length;
          alert(`Você precisa selecionar todas as paradas! Faltam ${diff}.`);
          return;
      }
      
      let newStopsList = [];
      reorderList.forEach(groupId => {
          const group = groups.find(g => g.id === groupId);
          if (group) newStopsList.push(...group.items);
      });

      const updatedRoutes = [...routes];
      updatedRoutes[rIdx].stops = newStopsList;
      setRoutes(updatedRoutes);
      
      setIsReordering(false);
      setReorderList([]);
      showToast("Nova sequência salva!");
  };

  const cancelReorder = () => {
      setIsReordering(false);
      setReorderList([]);
      // Não fecha o mapa, apenas sai do modo
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

  const setAllStatus = (items, status) => {
      items.forEach(item => setStatus(item.id, status));
  };

  const startRoute = async (lat, lng) => {
      await ensurePermissionAndPos(); 
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const handleToggleMap = async () => {
      if (!showMap) {
          await ensurePermissionAndPos();
      }
      setShowMap(!showMap);
  };

  const handleBack = () => {
      if (showMap) {
          if (isReordering) {
              if(confirm("Sair da edição sem salvar?")) cancelReorder();
          } else {
              setShowMap(false);
          }
      } else {
          setView('home');
      }
  };

  const toggleGroup = (id) => setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));

  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');
  
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
  }, [nextGroup?.id, userPos, isLoaded]);

  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-12 bg-slate-100">
          <div className="flex justify-between items-center mb-8">
              <div>
                  <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Minhas Rotas</h1>
                  <p className="text-slate-500 text-sm mt-1">Gerencie suas entregas</p>
              </div>
              <div className="bg-white p-3 rounded-2xl shadow-sm"><Package className="text-blue-600"/></div>
          </div>
          {routes.length === 0 ? (
              <div className="text-center mt-32 opacity-40 flex flex-col items-center">
                  <div className="bg-white p-6 rounded-full shadow-sm mb-4"><MapIcon size={48} className="text-slate-300"/></div>
                  <p className="font-bold text-slate-400">Nenhuma rota criada</p>
              </div>
          ) : (
              <div className="space-y-5">
                  {routes.map(r => {
                      const percent = calculateProgressPercent(r.stops);
                      const done = r.stops.filter(s => s.status === 'success').length;
                      
                      return (
                          <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 active:scale-[0.98] transition-transform duration-200">
                              <div className="flex justify-between items-start mb-3">
                                  <div>
                                      <h3 className="font-bold text-lg text-slate-800">{safeStr(r.name)}</h3>
                                      <p className="text-xs text-slate-400 font-medium mt-0.5 uppercase tracking-wider">{r.company || 'Empresa não informada'}</p>
                                  </div>
                                  <div className="text-right">
                                      <div className="bg-slate-100 px-2 py-1 rounded text-[10px] font-bold text-slate-500 mb-1">{new Date(r.date || r.id).toLocaleDateString()}</div>
                                      {r.value && <div className="text-green-600 font-bold text-xs">R$ {r.value}</div>}
                                  </div>
                              </div>
                              
                              <div className="flex items-center gap-4 mb-4">
                                  <div className="flex-1">
                                      <div className="flex justify-between text-xs font-bold text-slate-600 mb-1">
                                          <span>Progresso</span>
                                          <span>{done}/{r.stops.length}</span>
                                      </div>
                                      <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                                          <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{width: `${percent}%`}}></div>
                                      </div>
                                  </div>
                              </div>
                          </div>
                      )
                  })}
              </div>
          )}
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full bg-slate-900 text-white shadow-2xl flex items-center justify-center hover:bg-slate-800 transition active:scale-90">
              <Plus size={32}/>
          </button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-slate-50 flex flex-col">
          <div className="bg-white p-6 pb-4 shadow-sm z-10">
              <button onClick={() => setView('home')} className="mb-4 text-slate-400 hover:text-slate-600"><ArrowLeft/></button>
              <h2 className="text-2xl font-bold text-slate-900">Nova Rota</h2>
              <p className="text-sm text-slate-500">Preencha os dados para iniciar</p>
          </div>

          <div className="flex-1 p-6 space-y-6 overflow-y-auto">
              <div className="space-y-4">
                  <div><label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Nome da Rota</label><div className="flex items-center bg-white p-4 rounded-xl border border-slate-200 focus-within:border-blue-500 transition"><MapIcon className="text-slate-300 mr-3" size={20}/><input type="text" className="flex-1 outline-none text-sm font-medium" placeholder="Ex: Rota Zona Sul" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/></div></div>
                  <div><label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Empresa</label><div className="flex items-center bg-white p-4 rounded-xl border border-slate-200 focus-within:border-blue-500 transition"><Building className="text-slate-300 mr-3" size={20}/><input type="text" className="flex-1 outline-none text-sm font-medium" placeholder="Ex: Mercado Livre" value={newRouteCompany} onChange={e => setNewRouteCompany(e.target.value)}/></div></div>
                  
                  {/* Item 4: Ajuste Grid */}
                  <div className="grid grid-cols-2 gap-4">
                      <div><label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Data</label><div className="flex items-center bg-white p-4 rounded-xl border border-slate-200 focus-within:border-blue-500 transition"><Calendar className="text-slate-300 mr-3" size={20}/><input type="date" className="flex-1 outline-none text-sm font-medium" value={newRouteDate} onChange={e => setNewRouteDate(e.target.value)}/></div></div>
                      <div><label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Valor (R$)</label><div className="flex items-center bg-white p-4 rounded-xl border border-slate-200 focus-within:border-blue-500 transition"><DollarSign className="text-slate-300 mr-1" size={20}/><input type="number" className="flex-1 outline-none text-sm font-medium" placeholder="0,00" value={newRouteValue} onChange={e => setNewRouteValue(e.target.value)}/></div></div>
                  </div>
              </div>

              <div>
                  <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Arquivo de Importação</label>
                  {!importSummary ? (
                      <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-blue-200 bg-blue-50/50 rounded-2xl cursor-pointer hover:bg-blue-50 transition"><Upload className="mb-2 text-blue-500"/><span className="text-sm font-bold text-blue-600">Toque para Selecionar (CSV/XLSX)</span><input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/></label>
                  ) : (
                      <div className="w-full bg-green-50 border border-green-200 rounded-2xl p-6 text-center animate-in fade-in zoom-in"><div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3"><Check className="text-green-600" size={24}/></div><h3 className="text-green-800 font-bold text-lg">Arquivo Carregado!</h3><p className="text-green-600 mt-1 text-sm">{importSummary.count} pacotes encontrados</p><p className="text-green-500/70 text-xs mt-1 truncate px-4">{importSummary.first}...</p><button onClick={() => {setImportSummary(null); setTempStops([]);}} className="text-xs text-red-400 mt-4 font-bold hover:underline">REMOVER ARQUIVO</button></div>
                  )}
              </div>
          </div>
          <div className="p-6 bg-white border-t border-slate-100"><button onClick={createRoute} disabled={!importSummary || !newRouteName} className={`w-full py-4 rounded-xl font-bold text-lg shadow-lg transition-all ${importSummary && newRouteName ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-slate-100 text-slate-400'}`}>Criar Rota</button></div>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {toast && <div className={`fixed top-4 left-4 right-4 p-4 rounded-xl shadow-2xl z-50 text-white text-center font-bold text-sm toast-anim ${toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>{toast.msg}</div>}
          
          {/* ITEM 3: BARRA OTIMIZADA */}
          {isReordering && (
              <div className="absolute bottom-0 left-0 right-0 bg-yellow-400 px-4 py-3 z-50 flex items-center justify-between shadow-[0_-4px_10px_rgba(0,0,0,0.1)] rounded-t-2xl animate-in slide-in-from-bottom-4">
                  <div className="flex flex-col">
                      <span className="text-[10px] font-bold text-black/60 uppercase tracking-wider">Sequência</span>
                      <span className="text-lg font-extrabold text-black leading-none">{reorderList.length} Pinos</span>
                  </div>
                  <div className="flex gap-2">
                      <button onClick={undoLastSelection} className="bg-white/80 h-9 px-3 rounded-lg text-black font-bold flex items-center gap-1 active:scale-95 text-xs"><Undo2 size={14}/> Desfazer</button>
                      <button onClick={cancelReorder} className="bg-white/50 h-9 px-3 rounded-lg text-xs font-bold active:scale-95 text-black">Sair</button>
                      <button onClick={saveReorder} className="bg-black text-white h-9 px-4 rounded-lg text-xs font-bold shadow-lg active:scale-95">SALVAR</button>
                  </div>
              </div>
          )}

          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0">
              <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-4 flex-1 text-center">{safeStr(activeRoute.name)}</h2>
                  <div className="flex gap-2">
                      <button onClick={resetRoute} className="p-2 rounded-full bg-slate-100 text-slate-600 shadow-sm"><RotateCcw size={20}/></button>
                      <button onClick={deleteRoute} className="p-2 rounded-full bg-red-50 text-red-500 shadow-sm"><Trash2 size={20}/></button>
                      <button onClick={handleToggleMap} className={`p-2 rounded-full ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'}`}>{showMap ? <List size={20}/> : <MapIcon size={20}/>}</button>
                  </div>
              </div>
              
              {!showMap && (
                  <div className="relative mb-4">
                      <Search size={18} className="absolute left-3 top-3 text-slate-400"/>
                      <input type="text" placeholder="Buscar..." className="w-full pl-10 pr-4 py-2.5 rounded-xl search-input text-sm font-medium outline-none" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}/>
                      {searchQuery && <button onClick={() => setSearchQuery('')} className="absolute right-3 top-3 text-slate-400"><X size={16}/></button>}
                  </div>
              )}

              {!searchQuery && !showMap && nextGroup && (
                  <div className="flex gap-3">
                      <button onClick={() => startRoute(nextGroup.lat, nextGroup.lng)} className="w-full py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 text-white shadow-lg shadow-green-200 transition-all bg-green-600 hover:bg-green-700">
                          <Navigation size={18}/> Iniciar Rota (Próx: #{nextGroup.displayOrder || '?'})
                      </button>
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
                      openNav={startRoute} 
                      isLoaded={isLoaded}
                      setStatus={setStatus}
                      setAllStatus={setAllStatus}
                      isReordering={isReordering}
                      reorderList={reorderList}
                      onMarkerClick={handleMapMarkerClick}
                      onStartReorder={startReorderMode} 
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
                  onStartReorder={startReorderMode}
              />
          )}
      </div>
  );
}
"""

FILES_TO_WRITE = {
    "src/components/MapView.jsx": CODE_MAP_VIEW,
    "src/components/RouteList.jsx": CODE_ROUTE_LIST,
    "src/App.jsx": APP_JSX_CONTENT.replace("__API_KEY__", API_KEY_VALUE)
}

def write_files():
    for path, content in FILES_TO_WRITE.items():
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name): os.makedirs(dir_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Escrevendo {path}")

def main():
    print(f"--- Iniciando V34 (Map Edit Fix + Layout) {TIMESTAMP} ---")
    if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)
    os.makedirs(CURRENT_BACKUP_PATH)
    
    if os.path.exists("src/App.jsx"): shutil.copy2("src/App.jsx", CURRENT_BACKUP_PATH)

    write_files()

    print("--- Git Push ---")
    subprocess.run("git add .", shell=True)
    subprocess.run(f'git commit -m "Update V34: UX Improvements - {TIMESTAMP}"', shell=True)
    subprocess.run("git push", shell=True)
    
    os.remove(__file__)
    print("Concluído.")

if __name__ == "__main__":
    main()


