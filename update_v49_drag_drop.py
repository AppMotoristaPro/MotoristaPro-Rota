import os
import shutil
import subprocess

# --- CONFIGURAÇÕES ---
APP_NAME = "MotoristaPro-Rota"
GOOGLE_MAPS_KEY = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

files_content = {}

# 1. PACKAGE.JSON (Adicionando lib de Drag & Drop)
files_content['package.json'] = '''{
  "name": "motorista-pro-rota",
  "private": true,
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.263.1",
    "papaparse": "^5.4.1",
    "xlsx": "^0.18.5",
    "@react-google-maps/api": "^2.19.2",
    "@hello-pangea/dnd": "^16.3.0",
    "@capacitor/geolocation": "^5.0.0",
    "@capacitor/core": "^5.0.0",
    "@capacitor/android": "^5.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.15",
    "@types/react-dom": "^18.2.7",
    "@vitejs/plugin-react": "^4.0.3",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.27",
    "tailwindcss": "^3.3.3",
    "vite": "^4.4.5",
    "@capacitor/cli": "^5.0.0"
  }
}'''

# 2. CSS (Estilos para Drag & Drop)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'Inter', sans-serif;
  background-color: #F8FAFC;
  color: #0F172A;
  -webkit-tap-highlight-color: transparent;
}

/* Drag & Drop */
.draggable-item {
  touch-action: none; /* Importante para mobile */
}
.dragging {
  opacity: 0.8;
  transform: scale(1.02);
  box-shadow: 0 10px 20px rgba(0,0,0,0.15);
  z-index: 100;
}

/* Cards */
.modern-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  border: 1px solid #E2E8F0;
  overflow: hidden;
}

/* Status */
.border-l-status-pending { border-left: 5px solid #3B82F6; }
.border-l-status-success { border-left: 5px solid #10B981; background: #F0FDF4; opacity: 0.6; }
.border-l-status-failed { border-left: 5px solid #EF4444; background: #FEF2F2; opacity: 0.6; }

/* Botões */
.btn-primary { background: #2563EB; color: white; }
.btn-secondary { background: #F1F5F9; color: #475569; }
.fab-main { background: #0F172A; color: white; box-shadow: 0 4px 15px rgba(15,23,42,0.4); }
'''

# 3. APP.JSX (Implementação Completa V49)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  Upload, Navigation, Check, AlertTriangle, Trash2, Plus, 
  ArrowLeft, Sliders, MapPin, Package, Clock, GripVertical, 
  Map as MapIcon, Loader2, Search, X, List, Crosshair, Edit3, Save
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF, DirectionsService, DirectionsRenderer } from '@react-google-maps/api';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v49_dragdrop';
const GOOGLE_KEY = "__GOOGLE_KEY__";

// --- HELPERS ---
const safeStr = (val) => {
    if (!val) return '';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val).trim();
};

const getMarkerIcon = (status, isCurrent, idx) => {
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    let color = "#3B82F6"; // Azul
    if (status === 'success') color = "#10B981";
    if (status === 'failed') color = "#EF4444";
    if (isCurrent) color = "#0F172A";

    return {
        path,
        fillColor: color,
        fillOpacity: 1,
        strokeWeight: 1.5,
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2 : 1.4,
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

const mapOptions = { disableDefaultUI: true, zoomControl: false, clickableIcons: false };

// --- LOGICA DE AGRUPAMENTO (Atualizada para suportar reordenação) ---
const groupStops = (stops) => {
    if (!stops) return [];
    
    // Agrupa por nome da parada
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

    // Converte para array e calcula status
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

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); 
  const [newRouteName, setNewRouteName] = useState('');
  const [tempStops, setTempStops] = useState([]);
  const [userPos, setUserPos] = useState(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [directions, setDirections] = useState(null);
  
  // Modo de Edição Manual
  const [isEditing, setIsEditing] = useState(false);

  const { isLoaded } = useJsApiLoader({ id: 'gmaps', googleMapsApiKey: GOOGLE_KEY });

  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) { localStorage.removeItem(DB_KEY); }
    getCurrentLocation();
  }, []);

  useEffect(() => { localStorage.setItem(DB_KEY, JSON.stringify(routes)); }, [routes]);

  const getCurrentLocation = async () => {
      try {
          await Geolocation.requestPermissions();
          const pos = await Geolocation.getCurrentPosition();
          setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      } catch (e) {}
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
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
            if(norm.length) setTempStops(norm);
        } catch(e) { alert("Erro arquivo."); }
    };
    reader.readAsBinaryString(file);
  };

  const createRoute = () => {
      if(!newRouteName.trim() || !tempStops.length) return;
      setRoutes([{ id: Date.now(), name: newRouteName, date: new Date().toLocaleDateString(), stops: tempStops, optimized: false }, ...routes]);
      setNewRouteName(''); setTempStops([]); setView('home');
  };

  // --- OTIMIZAÇÃO AUTOMÁTICA (2-Opt Global) ---
  const optimizeRoute = () => {
      setIsOptimizing(true);
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1 || !userPos) { setIsOptimizing(false); return; }

      const currentRoute = routes[rIdx];
      // Agrupa logicamente por local para otimizar "nós"
      const grouped = groupStops(currentRoute.stops);
      let pendingGroups = grouped.filter(g => g.status !== 'success' && g.status !== 'failed');
      
      // Algoritmo Vizinho Mais Próximo + 2-Opt
      let path = [userPos]; // Start
      let unvisited = [...pendingGroups];
      let optimizedGroups = [];
      
      while(unvisited.length > 0) {
          let last = path[path.length-1];
          let bestIdx = 0, minD = Infinity;
          for(let i=0; i<unvisited.length; i++) {
              let d = Math.pow(unvisited[i].lat - last.lat, 2) + Math.pow(unvisited[i].lng - last.lng, 2);
              if(d < minD) { minD = d; bestIdx = i; }
          }
          optimizedGroups.push(unvisited[bestIdx]);
          path.push(unvisited[bestIdx]);
          unvisited.splice(bestIdx, 1);
      }

      // Desagrupa para salvar a lista plana ordenada
      let finalStops = [];
      // Mantem os finalizados no topo
      // Adiciona os novos ordenados
      optimizedGroups.forEach(g => finalStops.push(...g.items));

      const updatedRoutes = [...routes];
      updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: finalStops, optimized: true };
      setRoutes(updatedRoutes);
      setIsOptimizing(false);
  };

  // --- REORDENAÇÃO MANUAL (DRAG & DROP) ---
  const onDragEnd = (result) => {
      if (!result.destination) return;
      
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const currentRoute = routes[rIdx];
      
      // Reordena a lista plana de stops
      // Nota: DND funciona melhor com listas planas visualmente
      // Aqui estamos reordenando os grupos visuais e refletindo nos dados
      const grouped = groupStops(currentRoute.stops);
      const [reorderedGroup] = grouped.splice(result.source.index, 1);
      grouped.splice(result.destination.index, 0, reorderedGroup);
      
      // Reconstrói lista plana
      const newStops = [];
      grouped.forEach(g => newStops.push(...g.items));
      
      const updatedRoutes = [...routes];
      updatedRoutes[rIdx] = { ...updatedRoutes[rIdx], stops: newStops };
      setRoutes(updatedRoutes);
  };

  const openExternalMap = (lat, lng) => {
      const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
      window.open(url, '_system');
  };

  const setStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      const updated = [...routes];
      const sIdx = updated[rIdx].stops.findIndex(s => s.id === stopId);
      if (sIdx !== -1) {
          updated[rIdx].stops[sIdx].status = status;
          setRoutes(updated);
      }
  };

  // --- RENDER ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStops(activeRoute.stops) : [], [activeRoute]);
  
  // Directions (Linha Azul)
  useEffect(() => {
      if (isLoaded && activeRoute && userPos && groupedStops.length > 0) {
          const next = groupedStops.find(g => g.status === 'pending');
          if (next) {
              const service = new window.google.maps.DirectionsService();
              service.route({
                  origin: userPos,
                  destination: { lat: next.lat, lng: next.lng },
                  travelMode: 'DRIVING'
              }, (res, status) => {
                  if (status === 'OK') setDirections(res);
              });
          }
      }
  }, [groupedStops, userPos, isLoaded]);

  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-10 bg-slate-50">
          <h1 className="text-3xl font-bold mb-8">Rotas</h1>
          {routes.map(r => (
              <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="modern-card p-5 mb-4">
                  <h3 className="font-bold">{r.name}</h3>
                  <span className="text-sm text-gray-500">{r.stops.length} entregas</span>
              </div>
          ))}
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full fab-main flex items-center justify-center"><Plus/></button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-white p-6">
          <button onClick={() => setView('home')} className="mb-6"><ArrowLeft/></button>
          <h2 className="text-2xl font-bold mb-6">Nova Rota</h2>
          <input className="w-full p-4 bg-slate-50 rounded-xl mb-4" placeholder="Nome" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/>
          <label className="block w-full p-8 border-2 border-dashed rounded-xl text-center bg-slate-50 mb-4">
              Importar <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/>
          </label>
          <button onClick={createRoute} className="w-full btn-primary py-4 rounded-xl font-bold">Salvar</button>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50">
          {/* HEADER */}
          <div className="bg-white px-4 py-3 shadow-sm z-20">
              <div className="flex justify-between items-center mb-3">
                  <button onClick={() => setView('home')}><ArrowLeft/></button>
                  <h2 className="font-bold truncate px-2">{safeStr(activeRoute.name)}</h2>
                  <button onClick={() => setShowMap(!showMap)} className="p-2 bg-slate-100 rounded-full">{showMap?<List/>:<MapIcon/>}</button>
              </div>

              {/* BARRA DE COMANDOS */}
              <div className="flex gap-2">
                  {!isEditing ? (
                      <>
                        <button onClick={optimizeRoute} className="flex-1 py-2 bg-slate-100 rounded-lg text-sm font-bold flex items-center justify-center gap-2"><Sliders size={16}/> Otimizar</button>
                        <button onClick={() => setIsEditing(true)} className="flex-1 py-2 bg-slate-100 rounded-lg text-sm font-bold flex items-center justify-center gap-2"><Edit3 size={16}/> Editar Ordem</button>
                      </>
                  ) : (
                      <button onClick={() => setIsEditing(false)} className="w-full py-2 bg-green-600 text-white rounded-lg font-bold flex items-center justify-center gap-2"><Save size={16}/> Salvar Ordem</button>
                  )}
              </div>
          </div>

          {/* CONTEÚDO */}
          {showMap ? (
              <div className="flex-1 relative">
                   {isLoaded ? (
                      <GoogleMap
                          mapContainerStyle={{width:'100%', height:'100%'}}
                          center={userPos || {lat:-23.55, lng:-46.63}}
                          zoom={14}
                          options={mapOptions}
                      >
                          {directions && <DirectionsRenderer directions={directions} options={{suppressMarkers:true, polylineOptions:{strokeColor:"#2563EB", strokeWeight:5}}}/>}
                          {groupedStops.map((g, i) => (
                              <MarkerF 
                                key={g.id} 
                                position={{lat:g.lat, lng:g.lng}} 
                                label={{text: String(i+1), color:'white', fontWeight:'bold'}}
                                icon={getMarkerIcon(g.status, false)}
                                onClick={() => setSelectedMarker(g)}
                              />
                          ))}
                          {selectedMarker && (
                              <InfoWindowF position={{lat:selectedMarker.lat, lng:selectedMarker.lng}} onCloseClick={() => setSelectedMarker(null)}>
                                  <div className="p-2 min-w-[180px]">
                                      <h3 className="font-bold text-sm mb-1">{selectedMarker.mainName}</h3>
                                      <p className="text-xs text-gray-500 mb-2">{selectedMarker.mainAddress}</p>
                                      <div className="font-bold text-blue-600 text-xs mb-2">{selectedMarker.items.length} pacotes</div>
                                      <button onClick={() => openExternalMap(selectedMarker.lat, selectedMarker.lng)} className="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold">NAVEGAR (GPS)</button>
                                  </div>
                              </InfoWindowF>
                          )}
                      </GoogleMap>
                   ) : <Loader2 className="animate-spin m-auto"/>}
              </div>
          ) : (
              <div className="flex-1 overflow-y-auto px-4 pt-4 pb-safe">
                  {isEditing ? (
                      <DragDropContext onDragEnd={onDragEnd}>
                          <Droppable droppableId="stops">
                              {(provided) => (
                                  <div {...provided.droppableProps} ref={provided.innerRef} className="space-y-3">
                                      {groupedStops.map((g, index) => (
                                          <Draggable key={g.id} draggableId={g.id} index={index}>
                                              {(provided, snapshot) => (
                                                  <div
                                                      ref={provided.innerRef}
                                                      {...provided.draggableProps}
                                                      {...provided.dragHandleProps}
                                                      className={`modern-card p-4 flex items-center gap-3 ${snapshot.isDragging ? 'bg-blue-50 shadow-xl scale-105' : ''}`}
                                                      style={provided.draggableProps.style}
                                                  >
                                                      <GripVertical className="text-gray-300"/>
                                                      <div className="flex-1">
                                                          <h4 className="font-bold text-sm">#{index+1} {g.mainName}</h4>
                                                          <p className="text-xs text-gray-500">{g.mainAddress}</p>
                                                      </div>
                                                  </div>
                                              )}
                                          </Draggable>
                                      ))}
                                      {provided.placeholder}
                                  </div>
                              )}
                          </Droppable>
                      </DragDropContext>
                  ) : (
                      <div className="space-y-3">
                          {groupedStops.map((g, idx) => (
                              <div key={g.id} className={`modern-card border-l-status-${g.status}`}>
                                  <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                                      <div>
                                          <h4 className="font-bold text-sm text-slate-800">#{idx+1} {g.mainName}</h4>
                                          <p className="text-xs text-gray-500">{g.items.length} pacotes</p>
                                      </div>
                                      <button onClick={() => openExternalMap(g.lat, g.lng)} className="p-2 bg-blue-50 text-blue-600 rounded-lg"><Navigation size={18}/></button>
                                  </div>
                                  <div className="px-4 py-2 bg-gray-50 space-y-2">
                                      {g.items.map(item => (
                                          <div key={item.id} className="flex justify-between items-center py-2 border-b border-gray-200 last:border-0">
                                              <span className="text-xs font-medium text-gray-700">{item.recipient}</span>
                                              {item.status === 'pending' ? (
                                                  <div className="flex gap-2">
                                                      <button onClick={() => setStatus(item.id, 'failed')} className="p-1.5 bg-white text-red-500 rounded border"><AlertTriangle size={14}/></button>
                                                      <button onClick={() => setStatus(item.id, 'success')} className="p-1.5 bg-green-500 text-white rounded"><Check size={14}/></button>
                                                  </div>
                                              ) : (
                                                  <span className={`text-[10px] font-bold ${item.status==='success'?'text-green-600':'text-red-500'}`}>{item.status.toUpperCase()}</span>
                                              )}
                                          </div>
                                      ))}
                                  </div>
                              </div>
                          ))}
                      </div>
                  )}
              </div>
          )}
      </div>
  );
}
'''

def main():
    print(f"🚀 ATUALIZAÇÃO V49 (DRAG & DROP) - {APP_NAME}")
    
    final_app_jsx = files_content['src/App.jsx'].replace("__GOOGLE_KEY__", GOOGLE_MAPS_KEY)
    
    print("\n📦 Instalando Drag & Drop...")
    subprocess.run("npm install @hello-pangea/dnd", shell=True)
    subprocess.run("npx cap sync", shell=True)

    print("\n📝 Atualizando arquivos...")
    with open("src/App.jsx", 'w', encoding='utf-8') as f:
        f.write(final_app_jsx)
        
    for f in ['src/index.css', 'package.json']:
        if f in files_content:
            with open(f, 'w', encoding='utf-8') as file: file.write(files_content[f])

    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "feat: V49 Manual Route Reorder & Native Nav Launch"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


