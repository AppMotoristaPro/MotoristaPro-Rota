import React, { useState, useEffect, useRef } from 'react';
import { Upload, Map as MapIcon, Navigation, List, Truck, Check, AlertTriangle, ChevronRight, Package, MapPin } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-routing-machine/dist/leaflet-routing-machine.css';
import L from 'leaflet';
import 'leaflet-routing-machine';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// --- CONFIGURAÇÃO DE ÍCONES CUSTOMIZADOS ---
const createIcon = (color) => new L.Icon({
  iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/markers/marker-icon-2x-${color}.png`,
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const icons = {
  blue: createIcon('blue'),       // Pendente
  green: createIcon('green'),     // Entregue
  red: createIcon('red'),         // Ocorrência
  gold: createIcon('gold'),       // Atual
  grey: createIcon('grey')        // Inativo
};

// --- COMPONENTE DE ROTEAMENTO (LINHA NO MAPA) ---
function RoutingMachine({ userLocation, destination }) {
  const map = useMap();
  const routingControlRef = useRef(null);

  useEffect(() => {
    if (!map || !userLocation || !destination) return;

    if (routingControlRef.current) map.removeControl(routingControlRef.current);

    const plan = L.Routing.plan(
      [L.latLng(userLocation.lat, userLocation.lng), L.latLng(destination.lat, destination.lng)],
      { createMarker: () => null, addWaypoints: false, draggableWaypoints: false }
    );

    routingControlRef.current = L.Routing.control({
      waypoints: [L.latLng(userLocation.lat, userLocation.lng), L.latLng(destination.lat, destination.lng)],
      plan: plan,
      lineOptions: { styles: [{ color: '#2563eb', weight: 6, opacity: 0.9 }] }, // Azul Spoke
      routeWhileDragging: false,
      show: false, // Esconder painel de texto padrão, usar nossa UI
      addWaypoints: false
    }).addTo(map);

    return () => {
      if (routingControlRef.current) map.removeControl(routingControlRef.current);
    };
  }, [map, userLocation, destination]);

  return null;
}

// --- AJUSTE DE FOCO DO MAPA ---
function MapRecenter({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.flyTo(center, zoom || 16, { duration: 1.5 });
    }
  }, [center, map, zoom]);
  return null;
}

export default function App() {
  const [view, setView] = useState('import'); // import, list, navigation
  const [stops, setStops] = useState([]);
  const [currentStopIndex, setCurrentStopIndex] = useState(0);
  const [userLocation, setUserLocation] = useState(null);
  const [isOptimizing, setIsOptimizing] = useState(false);

  // Pegar GPS real ao iniciar
  useEffect(() => {
    navigator.geolocation.getCurrentPosition(
      (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => {
        console.error("Erro GPS", err);
        // Fallback para SP se falhar
        setUserLocation({ lat: -23.5505, lng: -46.6333 });
      },
      { enableHighAccuracy: true }
    );
  }, []);

  // --- LÓGICA DE ARQUIVOS ---
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const processFile = (dataStr, isBinary = false) => {
      let data = [];
      if (!isBinary) {
        const result = Papa.parse(dataStr, { header: true, skipEmptyLines: true });
        data = normalizeData(result.data);
      } else {
        const wb = XLSX.read(dataStr, { type: 'binary' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        data = normalizeData(XLSX.utils.sheet_to_json(ws));
      }
      if (data.length > 0) {
        setStops(data.map(d => ({ ...d, status: 'pending' }))); // Status: pending, success, failed
        setView('list');
      } else {
        alert("Erro: Planilha sem colunas Latitude/Longitude.");
      }
    };

    const reader = new FileReader();
    if (file.name.endsWith('.csv')) {
      reader.onload = (evt) => processFile(evt.target.result);
      reader.readAsText(file);
    } else {
      reader.onload = (evt) => processFile(evt.target.result, true);
      reader.readAsBinaryString(file);
    }
  };

  const normalizeData = (rawData) => {
    return rawData.map((row, index) => {
      const k = Object.keys(row).reduce((acc, key) => { acc[key.toLowerCase().trim()] = row[key]; return acc; }, {});
      const lat = parseFloat(k['latitude'] || k['lat'] || 0);
      const lng = parseFloat(k['longitude'] || k['long'] || k['lng'] || 0);
      const name = k['stop'] || k['nome'] || k['cliente'] || `Parada ${index + 1}`;
      const address = k['destination address'] || k['endereço'] || k['endereco'] || '---';
      return { id: index, name, address, lat, lng };
    }).filter(i => i.lat !== 0 && i.lng !== 0);
  };

  // --- LÓGICA DE OTIMIZAÇÃO (NEAREST NEIGHBOR COM GPS REAL) ---
  const optimizeRoute = () => {
    if (stops.length === 0) return;
    setIsOptimizing(true);

    // 1. Pega posição atual (GPS) ou a primeira parada
    let currentPos = userLocation || { lat: stops[0].lat, lng: stops[0].lng };
    let pendingStops = stops.filter(s => s.status === 'pending');
    let finishedStops = stops.filter(s => s.status !== 'pending'); // Mantém os já feitos no topo ou ignora
    
    let optimizedPending = [];

    // Algoritmo Vizinho Mais Próximo
    while (pendingStops.length > 0) {
      let nearestIndex = -1;
      let minDist = Infinity;

      for (let i = 0; i < pendingStops.length; i++) {
        const d = Math.sqrt(
          Math.pow(pendingStops[i].lat - currentPos.lat, 2) + 
          Math.pow(pendingStops[i].lng - currentPos.lng, 2)
        );
        if (d < minDist) {
          minDist = d;
          nearestIndex = i;
        }
      }

      const nextStop = pendingStops[nearestIndex];
      optimizedPending.push(nextStop);
      currentPos = { lat: nextStop.lat, lng: nextStop.lng }; // Avança o "ponteiro"
      pendingStops.splice(nearestIndex, 1);
    }

    setStops([...finishedStops, ...optimizedPending]);
    setCurrentStopIndex(finishedStops.length); // Aponta para o primeiro pendente
    setIsOptimizing(false);
    setView('navigation');
  };

  // --- AÇÕES DE ENTREGA ---
  const handleDeliveryAction = (status) => {
    const updatedStops = [...stops];
    updatedStops[currentStopIndex].status = status;
    setStops(updatedStops);

    // Avançar para próximo se existir
    if (currentStopIndex < stops.length - 1) {
      setCurrentStopIndex(prev => prev + 1);
    } else {
      alert("Rota Finalizada! Bom trabalho.");
      setView('list');
    }
  };

  // Helper para abrir no Waze/Maps externo se precisar
  const openExternalMap = (lat, lng) => {
    window.open(`geo:${lat},${lng}?q=${lat},${lng}`, '_system');
  };

  // --- RENDERIZAÇÃO ---
  const currentStop = stops[currentStopIndex];

  return (
    <div className="flex flex-col h-screen bg-gray-50 text-slate-800 font-sans">
      
      {/* --- HEADER --- */}
      <div className="bg-white px-4 py-3 shadow-sm z-30 flex justify-between items-center border-b border-gray-100">
        <h1 className="font-bold text-lg text-slate-800 flex items-center gap-2">
          <Truck className="text-blue-600" size={20} />
          MotoristaPro<span className="text-blue-600">Rota</span>
        </h1>
        <div className="text-xs font-semibold bg-gray-100 px-3 py-1 rounded-full text-gray-600">
           {stops.filter(s => s.status === 'success').length} / {stops.length}
        </div>
      </div>

      <main className="flex-1 relative overflow-hidden">
        
        {/* TELA 1: IMPORTAÇÃO */}
        {view === 'import' && (
          <div className="h-full flex flex-col items-center justify-center p-6 bg-gray-50">
            <div className="w-full max-w-sm bg-white p-8 rounded-2xl shadow-xl text-center">
              <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <Upload className="text-blue-600" size={28} />
              </div>
              <h2 className="text-xl font-bold mb-2 text-slate-800">Iniciar Rota</h2>
              <p className="text-sm text-slate-400 mb-6">Carregue sua planilha de entregas (.csv ou .xlsx)</p>
              
              <label className="block w-full cursor-pointer mb-4">
                <div className="w-full py-4 border-2 border-dashed border-blue-200 rounded-xl hover:bg-blue-50 transition text-blue-600 font-medium text-sm">
                  Toque para buscar arquivo
                </div>
                <input type="file" onChange={handleFileUpload} accept=".csv, .xlsx, .xls" className="hidden" />
              </label>
            </div>
          </div>
        )}

        {/* TELA 2: LISTA DE PARADAS */}
        {view === 'list' && (
          <div className="h-full flex flex-col">
            <div className="p-4 bg-white shadow-sm z-10">
              <button 
                onClick={optimizeRoute} 
                disabled={isOptimizing}
                className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg hover:bg-blue-700 transition flex items-center justify-center gap-2 active:scale-95"
              >
                <Navigation size={20} />
                {isOptimizing ? 'Calculando...' : 'Otimizar & Iniciar Rota'}
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {stops.map((stop, idx) => (
                <div key={idx} className={`p-4 mb-2 rounded-xl border flex items-center gap-4 ${stop.status === 'pending' ? 'bg-white border-gray-100' : 'bg-gray-50 opacity-60'}`}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm shrink-0 
                    ${stop.status === 'success' ? 'bg-green-100 text-green-700' : 
                      stop.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>
                    {stop.status === 'success' ? <Check size={16}/> : idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-slate-800 truncate">{stop.name}</h3>
                    <p className="text-xs text-slate-500 truncate">{stop.address}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TELA 3: NAVEGAÇÃO (MAPA + BOTÕES) */}
        {view === 'navigation' && (
          <div className="h-full w-full relative">
            {/* Mapa Google Style */}
            <MapContainer 
              center={[-23.5505, -46.6333]} 
              zoom={15} 
              style={{ height: '100%', width: '100%' }} 
              zoomControl={false}
            >
              {/* Google Maps Tiles */}
              <TileLayer
                url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"
                attribution="Google Maps"
              />

              {/* Centralizar no alvo atual */}
              <MapRecenter 
                center={currentStop ? [currentStop.lat, currentStop.lng] : userLocation} 
                zoom={17} 
              />

              {/* Rota visual (Linha Azul) */}
              {currentStop && userLocation && (
                <RoutingMachine userLocation={userLocation} destination={currentStop} />
              )}

              {/* Marcadores */}
              {stops.map((stop, idx) => (
                <Marker 
                  key={idx} 
                  position={[stop.lat, stop.lng]}
                  icon={
                    stop.status === 'success' ? icons.green :
                    stop.status === 'failed' ? icons.red :
                    idx === currentStopIndex ? icons.gold : icons.blue
                  }
                  opacity={stop.status !== 'pending' ? 0.6 : 1}
                >
                  <Popup className="custom-popup">
                    <div className="text-center p-1">
                      <strong className="block text-sm mb-1">{stop.name}</strong>
                      <span className="text-xs text-gray-500">{stop.address}</span>
                    </div>
                  </Popup>
                </Marker>
              ))}

              {/* Marcador User */}
              {userLocation && (
                <Marker position={[userLocation.lat, userLocation.lng]} icon={icons.grey} />
              )}
            </MapContainer>

            {/* CARD FLUTUANTE INFERIOR (CONTROLES) */}
            {currentStop ? (
              <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-3xl shadow-[0_-5px_20px_rgba(0,0,0,0.1)] p-6 z-[1000]">
                
                {/* Linha de Status Superior */}
                <div className="flex justify-center -mt-9 mb-4">
                    <div className="bg-slate-800 text-white px-4 py-1 rounded-full text-xs font-bold shadow-md flex items-center gap-2">
                        <MapPin size={12} /> PARADA {currentStopIndex + 1}
                    </div>
                </div>

                {/* Info Cliente */}
                <div className="mb-6 text-center">
                  <h2 className="text-xl font-bold text-slate-800 leading-tight">{currentStop.name}</h2>
                  <p className="text-sm text-slate-500 mt-1">{currentStop.address}</p>
                  
                  <button 
                    onClick={() => openExternalMap(currentStop.lat, currentStop.lng)}
                    className="text-xs text-blue-600 font-semibold mt-2 flex items-center justify-center gap-1"
                  >
                    Abrir no Waze <ChevronRight size={12} />
                  </button>
                </div>

                {/* Botões de Ação */}
                <div className="flex gap-3">
                  <button 
                    onClick={() => handleDeliveryAction('failed')}
                    className="flex-1 bg-orange-100 text-orange-700 py-4 rounded-xl font-bold flex flex-col items-center justify-center gap-1 active:scale-95 transition"
                  >
                    <AlertTriangle size={20} />
                    <span className="text-xs">Ocorrência</span>
                  </button>
                  
                  <button 
                    onClick={() => handleDeliveryAction('success')}
                    className="flex-[2] bg-green-600 text-white py-4 rounded-xl font-bold shadow-lg shadow-green-200 flex flex-col items-center justify-center gap-1 active:scale-95 transition"
                  >
                    <Check size={24} />
                    <span className="text-xs">CONCLUIR ENTREGA</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="absolute bottom-10 left-10 right-10 bg-white p-6 rounded-xl shadow-xl text-center z-[1000]">
                 <Check className="mx-auto text-green-500 mb-2" size={40} />
                 <h3 className="font-bold">Rota Finalizada!</h3>
                 <button onClick={() => setView('import')} className="mt-4 text-blue-600 font-bold text-sm">Nova Rota</button>
              </div>
            )}
          </div>
        )}
      </main>

      {/* NAV BAR INFERIOR (Só aparece se não estiver navegando) */}
      {view !== 'navigation' && (
        <nav className="bg-white border-t border-gray-100 flex justify-around py-3 pb-safe">
          <button onClick={() => setView('import')} className={`flex flex-col items-center ${view === 'import' ? 'text-blue-600' : 'text-gray-400'}`}>
            <Upload size={22} />
          </button>
          <button onClick={() => setView('list')} className={`flex flex-col items-center ${view === 'list' ? 'text-blue-600' : 'text-gray-400'}`}>
            <List size={22} />
          </button>
        </nav>
      )}
    </div>
  );
}