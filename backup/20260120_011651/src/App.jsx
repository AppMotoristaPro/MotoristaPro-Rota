import React, { useState, useEffect, useRef } from 'react';
import { Upload, Map as MapIcon, Navigation, List, X, Truck, FileSpreadsheet } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-routing-machine/dist/leaflet-routing-machine.css';
import L from 'leaflet';
import 'leaflet-routing-machine';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// Fix ícones do Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Componente de Roteamento Interno (OSRM)
function RoutingMachine({ userLocation, destination }) {
  const map = useMap();
  const routingControlRef = useRef(null);

  useEffect(() => {
    if (!map || !userLocation || !destination) return;

    if (routingControlRef.current) {
      map.removeControl(routingControlRef.current);
    }

    const plan = L.Routing.plan(
      [
        L.latLng(userLocation.lat, userLocation.lng),
        L.latLng(destination.lat, destination.lng)
      ],
      {
        createMarker: () => null,
        addWaypoints: false,
        draggableWaypoints: false
      }
    );

    routingControlRef.current = L.Routing.control({
      waypoints: [
        L.latLng(userLocation.lat, userLocation.lng),
        L.latLng(destination.lat, destination.lng)
      ],
      plan: plan,
      lineOptions: {
        styles: [{ color: '#3b82f6', weight: 6, opacity: 0.8 }]
      },
      routeWhileDragging: false,
      show: true,
      language: 'pt-br',
      containerClassName: 'routing-container-custom'
    }).addTo(map);

    return () => {
      if (routingControlRef.current) {
        map.removeControl(routingControlRef.current);
      }
    };
  }, [map, userLocation, destination]);

  return null;
}

function MapRecenter({ points, focus }) {
  const map = useMap();
  useEffect(() => {
    if (focus) {
        map.flyTo([focus.lat, focus.lng], 16);
    } else if (points && points.length > 0) {
      const bounds = L.latLngBounds(points.map(p => [p.lat, p.lng]));
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [points, map, focus]);
  return null;
}

export default function App() {
  const [view, setView] = useState('import');
  const [stops, setStops] = useState([]);
  const [activeRoute, setActiveRoute] = useState(null);
  const [userLocation, setUserLocation] = useState(null);
  
  useEffect(() => {
    setUserLocation({ lat: -23.5505, lng: -46.6333 }); 
  }, []);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      const bstr = evt.target.result;
      let data = [];

      if (file.name.endsWith('.csv')) {
        const result = Papa.parse(bstr, { header: true, skipEmptyLines: true });
        data = processData(result.data);
      } else {
        const wb = XLSX.read(bstr, { type: 'binary' });
        const wsname = wb.SheetNames[0];
        const ws = wb.Sheets[wsname];
        const jsonData = XLSX.utils.sheet_to_json(ws);
        data = processData(jsonData);
      }
      
      if (data.length > 0) {
        setStops(data);
        alert(`${data.length} paradas importadas!`);
      } else {
        alert("Erro ao ler planilha. Verifique as colunas Latitude e Longitude.");
      }
    };

    if (file.name.endsWith('.csv')) {
        reader.readAsText(file);
    } else {
        reader.readAsBinaryString(file);
    }
  };

  const processData = (rawData) => {
    return rawData.map((row, index) => {
      const keys = Object.keys(row).reduce((acc, k) => { acc[k.toLowerCase().trim()] = row[k]; return acc; }, {});
      
      const lat = parseFloat(keys['latitude'] || keys['lat'] || 0);
      const lng = parseFloat(keys['longitude'] || keys['long'] || keys['lng'] || 0);
      const name = keys['stop'] || keys['nome'] || keys['cliente'] || `Parada ${index + 1}`;
      const address = keys['destination address'] || keys['endereço'] || keys['endereco'] || '---';

      return { id: index, name, address, lat, lng };
    }).filter(item => item.lat !== 0 && item.lng !== 0);
  };

  const getDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371; 
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
    return R * c;
  };

  const optimizeRoute = () => {
    if (stops.length === 0) return;
    let remaining = [...stops];
    let current = userLocation ? { ...userLocation, id: 'start' } : remaining.shift();
    let route = [];
    
    if (!userLocation) route.push(current);

    while (remaining.length > 0) {
      let nearestIndex = -1;
      let minDist = Infinity;
      for (let i = 0; i < remaining.length; i++) {
        const dist = getDistance(current.lat, current.lng, remaining[i].lat, remaining[i].lng);
        if (dist < minDist) {
          minDist = dist;
          nearestIndex = i;
        }
      }
      current = remaining[nearestIndex];
      route.push(current);
      remaining.splice(nearestIndex, 1);
    }
    setStops(route);
    setView('map');
  };

  const startInternalNav = (stop) => {
    setActiveRoute(stop);
    setView('map');
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100 font-sans text-gray-900">
      <header className="bg-blue-700 text-white p-4 shadow-md z-20 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Truck size={24} />
          <h1 className="font-bold text-lg">MotoristaPro</h1>
        </div>
        {activeRoute && <div className="text-xs bg-green-500 px-2 py-1 rounded font-bold animate-pulse">NAVEGANDO</div>}
      </header>

      <main className="flex-1 overflow-hidden relative">
        {view === 'import' && (
          <div className="p-4 h-full flex flex-col justify-center items-center">
            <div className="bg-white p-8 rounded-xl shadow-lg w-full max-w-sm text-center">
              <FileSpreadsheet size={48} className="mx-auto text-green-600 mb-4"/>
              <h2 className="text-xl font-bold mb-2">Importar Rota</h2>
              <p className="text-sm text-gray-500 mb-6">Suporta arquivos .CSV ou Excel (.xlsx)</p>
              
              <label className="block w-full cursor-pointer">
                <span className="sr-only">Escolher arquivo</span>
                <input type="file" onChange={handleFileUpload} accept=".csv, .xlsx, .xls" 
                  className="block w-full text-sm text-slate-500
                    file:mr-4 file:py-3 file:px-4
                    file:rounded-full file:border-0
                    file:text-sm file:font-semibold
                    file:bg-blue-50 file:text-blue-700
                    hover:file:bg-blue-100
                  "/>
              </label>

              {stops.length > 0 && (
                <div className="mt-6">
                    <p className="text-green-600 font-bold mb-3">{stops.length} paradas carregadas</p>
                    <button onClick={optimizeRoute} className="w-full bg-blue-600 text-white py-3 rounded-lg font-bold shadow-lg hover:bg-blue-700 transition">
                        Otimizar & Ver Mapa
                    </button>
                </div>
              )}
            </div>
          </div>
        )}

        {view === 'list' && (
          <div className="h-full overflow-y-auto pb-20">
            {stops.map((stop, index) => (
              <div key={stop.id} className="bg-white p-4 border-b flex items-start gap-3">
                <div className="bg-blue-100 text-blue-800 font-bold w-8 h-8 rounded-full flex items-center justify-center shrink-0">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold">{stop.name}</h3>
                  <p className="text-sm text-gray-500">{stop.address}</p>
                  <button onClick={() => startInternalNav(stop)} className="mt-2 w-full bg-blue-600 text-white text-xs py-2 px-4 rounded flex justify-center items-center gap-2">
                    <Navigation size={14}/> Navegar no App
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {view === 'map' && (
          <div className="h-full w-full relative">
            <MapContainer center={[-23.5505, -46.6333]} zoom={13} style={{ height: '100%', width: '100%' }}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              
              <MapRecenter points={stops} focus={activeRoute} />
              
              {activeRoute && userLocation && (
                  <RoutingMachine userLocation={userLocation} destination={activeRoute} />
              )}

              {stops.map((stop, index) => (
                <Marker key={stop.id} position={[stop.lat, stop.lng]}>
                  <Popup>
                    <strong>{index + 1}. {stop.name}</strong><br/>
                    {stop.address}<br/>
                    <button onClick={() => startInternalNav(stop)} style={{width:'100%', marginTop:'5px', padding:'5px', background:'#2563eb', color:'white', border:'none', borderRadius:'4px'}}>
                        Ir Agora
                    </button>
                  </Popup>
                </Marker>
              ))}
              
              {userLocation && (
                  <Marker position={[userLocation.lat, userLocation.lng]} icon={L.icon({
                      iconUrl: 'https://cdn-icons-png.flaticon.com/512/535/535188.png', 
                      iconSize: [30, 30]
                  })} />
              )}

            </MapContainer>
            
            {activeRoute && (
                <button onClick={() => setActiveRoute(null)} className="absolute top-2 right-2 bg-red-600 text-white p-2 rounded-full shadow-xl z-[1000]">
                    <X size={20} />
                </button>
            )}
          </div>
        )}
      </main>

      <nav className="bg-white border-t flex justify-around py-2 shadow-lg z-30">
        <button onClick={() => setView('import')} className={`p-2 flex flex-col items-center ${view === 'import' ? 'text-blue-600' : 'text-gray-400'}`}><Upload size={20}/><span className="text-[10px]">Importar</span></button>
        <button onClick={() => setView('list')} className={`p-2 flex flex-col items-center ${view === 'list' ? 'text-blue-600' : 'text-gray-400'}`}><List size={20}/><span className="text-[10px]">Lista</span></button>
        <button onClick={() => setView('map')} className={`p-2 flex flex-col items-center ${view === 'map' ? 'text-blue-600' : 'text-gray-400'}`}><MapIcon size={20}/><span className="text-[10px]">Mapa</span></button>
      </nav>
    </div>
  );
}