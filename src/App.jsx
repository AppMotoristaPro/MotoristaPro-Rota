import React, { useState, useEffect } from 'react';
import { Upload, Map as MapIcon, Navigation, List, Settings, Truck, Package, CheckCircle, Smartphone } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import Papa from 'papaparse';

// Fix para ícones do Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

function MapRecenter({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points && points.length > 0) {
      const bounds = L.latLngBounds(points.map(p => [p.lat, p.lng]));
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [points, map]);
  return null;
}

export default function App() {
  const [view, setView] = useState('import');
  const [stops, setStops] = useState([]);
  const [optimized, setOptimized] = useState(false);
  const [inputText, setInputText] = useState(
`Sequence,Stop,Destination Address,Bairro,City,Latitude,Longitude
1,Entrega 01,Av. Paulista 1000,Bela Vista,São Paulo,-23.565737,-46.651336
2,Entrega 02,Parque Ibirapuera,Vila Mariana,São Paulo,-23.587416,-46.657634
3,Entrega 03,Rua Augusta 500,Consolação,São Paulo,-23.550275,-46.649692
4,Entrega 04,Museu do Ipiranga,Ipiranga,São Paulo,-23.584768,-46.609714
5,Entrega 05,Allianz Parque,Perdizes,São Paulo,-23.527376,-46.678759`
  );

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
    let current = remaining.shift(); 
    let route = [current];

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
    setOptimized(true);
    setView('map');
  };

  const parseCSV = () => {
    const results = Papa.parse(inputText, { header: true, skipEmptyLines: true });
    
    // Tentativa de identificar colunas com nomes variados
    const data = results.data.map((row, index) => {
        // Normaliza chaves para lowercase para facilitar busca
        const keys = Object.keys(row).reduce((acc, k) => { acc[k.toLowerCase()] = row[k]; return acc; }, {});
        
        // Busca inteligente de colunas
        const lat = parseFloat(keys['latitude'] || keys['lat'] || 0);
        const lng = parseFloat(keys['longitude'] || keys['long'] || keys['lng'] || 0);
        const name = keys['stop'] || keys['nome'] || keys['cliente'] || `Parada ${index + 1}`;
        const address = keys['destination address'] || keys['endereço'] || keys['endereco'] || '---';

        return { id: index, name, address, lat, lng };
    }).filter(item => item.lat !== 0 && item.lng !== 0);

    if (data.length > 0) {
        setStops(data);
        setOptimized(false);
        alert(`${data.length} paradas carregadas!`);
    } else {
        alert("Não foi possível ler as coordenadas. Verifique se o CSV tem colunas 'Latitude' e 'Longitude'.");
    }
  };

  const openInMaps = (lat, lng) => {
    window.open(`geo:${lat},${lng}?q=${lat},${lng}`, '_system');
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100 font-sans text-gray-900">
      <header className="bg-blue-700 text-white p-4 shadow-md z-20 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Truck size={24} />
          <h1 className="font-bold text-lg">MotoristaPro</h1>
        </div>
        <div className="text-xs bg-blue-800 px-2 py-1 rounded">{stops.length} Paradas</div>
      </header>

      <main className="flex-1 overflow-hidden relative">
        {view === 'import' && (
          <div className="p-4 h-full overflow-y-auto">
            <div className="bg-white p-6 rounded-lg shadow-sm mb-4">
              <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
                <Upload size={20} className="text-blue-600"/> Importar
              </h2>
              <textarea 
                className="w-full h-48 p-3 border rounded font-mono text-xs bg-gray-50 mb-4 outline-none"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
              />
              <button onClick={parseCSV} className="w-full bg-gray-800 text-white py-3 rounded-lg font-bold mb-2">
                Processar CSV
              </button>
            </div>
            {stops.length > 0 && (
              <button onClick={optimizeRoute} className="w-full bg-blue-600 text-white py-3 rounded-lg font-bold shadow-lg">
                Otimizar Rota
              </button>
            )}
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
                  <button onClick={() => openInMaps(stop.lat, stop.lng)} className="mt-2 bg-green-600 text-white text-xs py-2 px-4 rounded">
                    Navegar
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
              <MapRecenter points={stops} />
              {stops.map((stop, index) => (
                <Marker key={stop.id} position={[stop.lat, stop.lng]}>
                  <Popup>{index + 1}. {stop.name}</Popup>
                </Marker>
              ))}
            </MapContainer>
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